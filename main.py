"""
전체 파이프라인 진입점.
데이터 수집 -> 앙상블 시그널 -> 리스크 사이징 -> (확인) -> 주문

실행: python main.py
GitHub Actions에서 크론으로 이 스크립트를 호출한다.
"""
import numpy as np
from config.settings import settings
from brokers.alpaca_broker import AlpacaBroker
from brokers.bybit_broker import BybitBroker
from brokers.kis_broker import KISBroker
from signals.ensemble import run_ensemble
from signals.regime import detect_regime
from signals.outcome_tracker import record_signal
from risk.manager import position_size_atr, exposure_check
from signals.indicators import atr as calc_atr
from execution.order_manager import execute_intent, TradeIntent
from brokers.base import OrderSide
import os


def cli_confirm(intent: TradeIntent) -> bool:
    """터미널에서 사람이 y/n으로 승인."""
    print(f"\n[확인 필요] {intent.broker} {intent.symbol} {intent.side.value} "
          f"{intent.qty:.4f}주 | score={intent.score:.2f} | {intent.reason}")
    ans = input("승인하시겠습니까? (y/n): ").strip().lower()
    return ans == "y"


def get_confirm_callback():
    """
    표준입력이 있는 대화형 환경이면 cli_confirm,
    TELEGRAM_BOT_TOKEN이 설정되어 있으면 telegram_confirm,
    둘 다 아니면(예: 비대화형+텔레그램 미설정) None -> REQUIRE_CONFIRMATION 하에서는
    자동 거부되어 안전하게 동작한다.
    """
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        from execution.telegram_confirm import telegram_confirm
        return telegram_confirm
    if os.isatty(0):
        return cli_confirm
    return None


def scan_universe(broker, symbols: list[str], broker_name: str, account_equity: float, current_exposure: float):
    results = []
    for symbol in symbols:
        try:
            bars = broker.get_bars(symbol, limit=120)
            if len(bars) < 60:
                print(f"[{broker_name}] {symbol}: 데이터 부족, 스킵")
                continue
            closes = np.array([b.close for b in bars])
            highs = np.array([b.high for b in bars])
            lows = np.array([b.low for b in bars])

            # 레짐 감지로 임계값 동적 조정 (변동성 낮음/극단 구간엔 보수적으로)
            regime = detect_regime(highs, lows, closes)
            buy_th = settings.SCORE_BUY_THRESHOLD + regime.threshold_adjustment
            sell_th = settings.SCORE_SELL_THRESHOLD - regime.threshold_adjustment

            ens = run_ensemble(highs, lows, closes, buy_th, sell_th)
            print(f"[{broker_name}] {symbol}: score={ens.final_score:.3f} action={ens.action} "
                  f"| regime=vol:{regime.vol_regime.value}/trend:{regime.trend_regime.value} "
                  f"(ATR pct={regime.atr_percentile:.0f})")

            if ens.action != "hold":
                record_signal(broker_name, symbol, ens.action, ens.final_score, closes[-1],
                               regime.vol_regime.value, regime.trend_regime.value)

            if ens.action == "hold":
                continue

            atr_vals = calc_atr(highs, lows, closes, 14)
            entry_price = closes[-1]
            sizing = position_size_atr(account_equity, entry_price, atr_vals[-1])
            if not sizing.approved:
                print(f"  -> 사이징 거부: {sizing.reason}")
                continue

            notional = sizing.qty * entry_price
            ok, msg = exposure_check(current_exposure, account_equity, notional)
            if not ok:
                print(f"  -> 노출 한도 초과: {msg}")
                continue

            side = OrderSide.BUY if ens.action == "buy" else OrderSide.SELL
            reason = "; ".join(f"{v.name}={v.score:.2f}" for v in ens.votes)
            intent = TradeIntent(
                broker=broker_name, symbol=symbol, side=side, qty=round(sizing.qty, 6),
                score=ens.final_score, reason=reason, stop_loss_price=sizing.stop_loss_price,
            )
            results.append(intent)
            current_exposure += notional
        except Exception as e:
            print(f"[{broker_name}] {symbol}: 에러 - {e}")
    return results


def main():
    print(f"=== AI Trader 실행 시작 | MODE={settings.MODE} | "
          f"ORDERS_ENABLED={settings.ORDERS_ENABLED} | "
          f"REQUIRE_CONFIRMATION={settings.REQUIRE_CONFIRMATION} ===\n")

    all_intents = []

    if settings.ENABLE_US_EQUITY:
        broker = AlpacaBroker()
        equity = broker.get_account_equity()
        positions = broker.get_positions()
        exposure = sum(p.market_value for p in positions)
        all_intents += scan_universe(broker, settings.WATCHLIST_US, "alpaca", equity, exposure)

    if settings.ENABLE_CRYPTO:
        broker = BybitBroker()
        equity = broker.get_account_equity()
        positions = broker.get_positions()
        exposure = sum(p.market_value for p in positions)
        all_intents += scan_universe(broker, settings.WATCHLIST_CRYPTO, "bybit", equity, exposure)

    if settings.ENABLE_KR_EQUITY:
        broker = KISBroker()
        equity = broker.get_account_equity()
        positions = broker.get_positions()
        exposure = sum(p.market_value for p in positions)
        all_intents += scan_universe(broker, settings.WATCHLIST_KR, "kis", equity, exposure)

    print(f"\n=== 총 {len(all_intents)}건의 트레이드 후보 발견 ===")

    broker_map = {"alpaca": AlpacaBroker, "bybit": BybitBroker, "kis": KISBroker}
    confirm_callback = get_confirm_callback()
    for intent in all_intents:
        broker = broker_map[intent.broker]()
        result = execute_intent(broker, intent, confirm_callback=confirm_callback)
        print(f"  -> {intent.symbol} {result.status.value}: {result.message}")


if __name__ == "__main__":
    main()
