"""
워크포워드 백테스트 엔진.

방법론 (2026년 1월 기준 학계/업계 관행 반영):
- Rolling-window walk-forward: 전체 기간을 N개 fold로 나누고, 각 fold는
  in-sample(파라미터 검토용) + out-of-sample(순수 평가용)로 구성
- Embargo: train/test 경계에 gap을 둬서 데이터 누수 방지 (기본 5봉)
- 이 엔진의 시그널 로직(signals/ensemble.py)은 파라미터 최적화 대상이 아닌
  고정 규칙 기반이므로, WFA의 목적은 "다른 시장 구간에서도 edge가
  유지되는지" 검증하는 것 (curve-fitting 방지 목적과는 별개)
- 단일 in-sample 최적화로 얻은 파라미터를 그대로 미래에 쓰는 것은 금지.
  이 스크립트로 나온 OOS 성과가 일관되게 나쁘면 전략/임계값을 재검토할 것.

지표: 총수익률, 샤프비율(무위험수익률 0 가정), MDD, 승률, 거래횟수
"""
import numpy as np
from dataclasses import dataclass, field
from signals.ensemble import run_ensemble
from signals.regime import detect_regime
from signals.indicators import atr as calc_atr


@dataclass
class FoldResult:
    fold_index: int
    start_idx: int
    end_idx: int
    total_return_pct: float
    sharpe: float
    max_drawdown_pct: float
    win_rate: float
    num_trades: int


@dataclass
class BacktestReport:
    folds: list = field(default_factory=list)
    aggregate_return_pct: float = 0.0
    aggregate_sharpe: float = 0.0
    aggregate_mdd_pct: float = 0.0
    aggregate_win_rate: float = 0.0
    total_trades: int = 0


def _simulate_segment(highs, lows, closes, buy_th, sell_th, fee_bps: float = 5.0):
    """
    단순 롱온리 시뮬레이션: 시그널 buy에서 진입, sell/hold 전환에서 청산.
    fee_bps: 왕복 수수료+슬리피지 가정 (기본 5bp = 0.05%, 각 방향)
    """
    equity = 1.0
    equity_curve = [equity]
    position = 0  # 0=없음, 1=보유중
    entry_price = 0.0
    trades = []  # (pnl_pct,)

    min_window = 60
    for i in range(min_window, len(closes)):
        window_h, window_l, window_c = highs[:i+1], lows[:i+1], closes[:i+1]
        ens = run_ensemble(window_h, window_l, window_c, buy_th, sell_th)
        price = closes[i]

        if position == 0 and ens.action == "buy":
            position = 1
            entry_price = price * (1 + fee_bps / 10000)
        elif position == 1 and ens.action == "sell":
            exit_price = price * (1 - fee_bps / 10000)
            pnl_pct = (exit_price - entry_price) / entry_price
            trades.append(pnl_pct)
            equity *= (1 + pnl_pct)
            position = 0
        equity_curve.append(equity if position == 0 else equity * (price / entry_price))

    # 종료 시점까지 보유 중이면 강제 청산해서 성과에 반영
    if position == 1:
        exit_price = closes[-1] * (1 - fee_bps / 10000)
        pnl_pct = (exit_price - entry_price) / entry_price
        trades.append(pnl_pct)
        equity *= (1 + pnl_pct)

    equity_curve = np.array(equity_curve)
    returns = np.diff(equity_curve) / np.where(equity_curve[:-1] == 0, 1e-9, equity_curve[:-1])
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0.0
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - running_max) / np.where(running_max == 0, 1e-9, running_max)
    mdd = drawdown.min() * 100

    win_rate = (np.array(trades) > 0).mean() if trades else 0.0

    return {
        "total_return_pct": (equity - 1.0) * 100,
        "sharpe": sharpe,
        "max_drawdown_pct": mdd,
        "win_rate": win_rate,
        "num_trades": len(trades),
    }


def walk_forward_backtest(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    n_folds: int = 5, embargo: int = 5,
    buy_threshold: float = 0.65, sell_threshold: float = 0.35,
) -> BacktestReport:
    """
    전체 구간을 n_folds개의 순차적 out-of-sample 구간으로 나눠 각각 시뮬레이션.
    각 fold 사이에 embargo(봉 수)를 둬서 앞 구간 정보 누수를 방지.
    (규칙기반 전략이라 in-sample 최적화 단계는 생략하고, 대신
     "레짐이 다른 여러 구간에서 일관되게 동작하는가"를 확인하는 용도로 사용)
    """
    n = len(closes)
    fold_size = n // n_folds
    report = BacktestReport()

    for f in range(n_folds):
        start = f * fold_size
        end = start + fold_size if f < n_folds - 1 else n
        start_embargo = start + embargo if f > 0 else start
        if end - start_embargo < 60:
            continue

        seg_h = highs[start_embargo:end]
        seg_l = lows[start_embargo:end]
        seg_c = closes[start_embargo:end]

        result = _simulate_segment(seg_h, seg_l, seg_c, buy_threshold, sell_threshold)
        report.folds.append(FoldResult(
            fold_index=f, start_idx=start_embargo, end_idx=end,
            total_return_pct=result["total_return_pct"], sharpe=result["sharpe"],
            max_drawdown_pct=result["max_drawdown_pct"], win_rate=result["win_rate"],
            num_trades=result["num_trades"],
        ))

    if report.folds:
        report.aggregate_return_pct = float(np.mean([f.total_return_pct for f in report.folds]))
        report.aggregate_sharpe = float(np.mean([f.sharpe for f in report.folds]))
        report.aggregate_mdd_pct = float(np.min([f.max_drawdown_pct for f in report.folds]))
        weighted_wins = sum(f.win_rate * f.num_trades for f in report.folds)
        report.total_trades = sum(f.num_trades for f in report.folds)
        report.aggregate_win_rate = weighted_wins / report.total_trades if report.total_trades else 0.0

    return report


def print_report(report: BacktestReport, label: str = ""):
    print(f"\n=== 워크포워드 백테스트 결과 {label} ===")
    for f in report.folds:
        print(f"  Fold {f.fold_index}: 수익률={f.total_return_pct:+.2f}% "
              f"샤프={f.sharpe:.2f} MDD={f.max_drawdown_pct:.2f}% "
              f"승률={f.win_rate*100:.1f}% 거래수={f.num_trades}")
    print(f"  --- 종합: 평균수익률={report.aggregate_return_pct:+.2f}% "
          f"평균샤프={report.aggregate_sharpe:.2f} 최악MDD={report.aggregate_mdd_pct:.2f}% "
          f"가중승률={report.aggregate_win_rate*100:.1f}% 총거래={report.total_trades}")
    if report.total_trades < 20:
        print("  ⚠ 거래 표본이 20건 미만 - 통계적 신뢰도 낮음. 실거래 판단에 쓰지 말 것.")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from brokers.alpaca_broker import AlpacaBroker

    broker = AlpacaBroker()
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    bars = broker.get_bars(symbol, timeframe="1Day", limit=1000)
    highs = np.array([b.high for b in bars])
    lows = np.array([b.low for b in bars])
    closes = np.array([b.close for b in bars])
    report = walk_forward_backtest(highs, lows, closes, n_folds=5)
    print_report(report, label=symbol)
