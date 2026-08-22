"""
포지션 사이징(ATR 기반) + 상관관계 필터 + 전체 노출 한도.
이 모듈은 '얼마를 살지'만 결정하고 실제 주문은 execution 계층이 담당한다.
"""
import numpy as np
from dataclasses import dataclass
from config.settings import settings


@dataclass
class SizingResult:
    qty: float
    stop_loss_price: float
    reason: str
    approved: bool


def position_size_atr(
    account_equity: float,
    entry_price: float,
    atr_value: float,
    risk_per_trade_pct: float = None,
    atr_stop_multiplier: float = None,
) -> SizingResult:
    """
    ATR 기반 포지션 사이징.
    - 계좌의 risk_per_trade_pct% 만큼만 이 트레이드에서 손실 허용
    - 손절폭 = ATR * atr_stop_multiplier
    - qty = (계좌 * risk%) / 손절폭
    """
    risk_pct = risk_per_trade_pct or settings.RISK_PER_TRADE_PCT
    stop_mult = atr_stop_multiplier or settings.ATR_STOP_MULTIPLIER

    if atr_value <= 0 or entry_price <= 0:
        return SizingResult(0, 0, "ATR/가격 데이터 이상", approved=False)

    stop_distance = atr_value * stop_mult
    stop_loss_price = entry_price - stop_distance
    dollar_risk = account_equity * risk_pct
    qty = dollar_risk / stop_distance

    # 종목당 최대 비중 캡
    max_notional = account_equity * settings.MAX_POSITION_PCT
    max_qty_by_cap = max_notional / entry_price
    qty = min(qty, max_qty_by_cap)

    if qty <= 0:
        return SizingResult(0, stop_loss_price, "계산된 수량이 0 이하", approved=False)

    return SizingResult(qty, stop_loss_price, "OK", approved=True)


def correlation_filter(
    candidate_symbol: str,
    candidate_returns: np.ndarray,
    existing_positions_returns: dict[str, np.ndarray],
    max_correlation: float = None,
) -> tuple[bool, str]:
    """
    이미 보유 중인 포지션들과 상관계수가 너무 높으면 신규 진입을 거부.
    (같은 방향 베팅 중복 방지 → 실질적 분산 확보)
    """
    threshold = max_correlation or settings.MAX_CORRELATION
    for sym, other_returns in existing_positions_returns.items():
        n = min(len(candidate_returns), len(other_returns))
        if n < 10:
            continue
        corr = np.corrcoef(candidate_returns[-n:], other_returns[-n:])[0, 1]
        if not np.isnan(corr) and abs(corr) >= threshold:
            return False, f"{sym}와 상관계수 {corr:.2f} >= 임계값 {threshold}"
    return True, "OK"


def exposure_check(
    current_total_exposure: float,
    account_equity: float,
    new_position_notional: float,
    max_total_exposure_pct: float = None,
) -> tuple[bool, str]:
    """전체 포트폴리오 노출이 한도를 넘지 않는지 확인"""
    cap_pct = max_total_exposure_pct or settings.MAX_TOTAL_EXPOSURE_PCT
    cap = account_equity * cap_pct
    projected = current_total_exposure + new_position_notional
    if projected > cap:
        return False, f"총 노출 {projected:.0f} > 한도 {cap:.0f}"
    return True, "OK"
