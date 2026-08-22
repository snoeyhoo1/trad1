"""
멀티 에이전트 앙상블 스코어러.
각 에이전트는 (score 0~1, confidence 0~1)을 반환.
score: 1에 가까울수록 강한 매수, 0에 가까울수록 강한 매도.
최종 스코어는 confidence 가중 평균.

주의: 과거 백테스트 결과 스캘핑/데이트레이딩류 단기 전략은 실전에서
성과가 재현되지 않는 경향이 확인됨. 기본값은 스윙(수일~수주) 타임프레임
지표 위주로 구성하고, walk-forward 검증 없이는 실거래 임계값을 낮추지 말 것.
"""
from dataclasses import dataclass
import numpy as np
from signals import indicators as ind


@dataclass
class AgentVote:
    name: str
    score: float       # 0~1
    confidence: float  # 0~1
    reason: str


@dataclass
class EnsembleResult:
    final_score: float
    votes: list[AgentVote]
    action: str  # "buy" / "sell" / "hold"


def _trend_agent(closes: np.ndarray) -> AgentVote:
    sma20 = ind.sma(closes, 20)
    sma50 = ind.sma(closes, 50)
    if np.isnan(sma50[-1]):
        return AgentVote("trend", 0.5, 0.0, "데이터 부족")
    price = closes[-1]
    above20 = price > sma20[-1]
    golden = sma20[-1] > sma50[-1]
    score = 0.5 + 0.25 * (1 if above20 else -1) + 0.25 * (1 if golden else -1)
    score = min(max(score, 0.0), 1.0)
    conf = min(abs(sma20[-1] - sma50[-1]) / price * 10, 1.0) if price else 0.0
    return AgentVote("trend", score, conf, f"20/50 SMA 추세 {'상승' if golden else '하락'}")


def _momentum_agent(closes: np.ndarray) -> AgentVote:
    rsi_vals = ind.rsi(closes, 14)
    macd_line, signal_line, hist = ind.macd(closes)
    if np.isnan(rsi_vals[-1]):
        return AgentVote("momentum", 0.5, 0.0, "데이터 부족")
    r = rsi_vals[-1]
    # RSI: 과매도(30 이하)->매수 신호, 과매수(70 이상)->매도 신호
    rsi_score = 1.0 - (r / 100.0)  # 낮을수록 매수 쪽
    rsi_score = min(max(rsi_score, 0.0), 1.0)
    macd_bull = not np.isnan(hist[-1]) and hist[-1] > 0
    macd_score = 0.65 if macd_bull else 0.35
    score = 0.5 * rsi_score + 0.5 * macd_score
    conf = 0.8 if (r < 30 or r > 70) else 0.4
    return AgentVote("momentum", score, conf, f"RSI={r:.1f}, MACD={'상승' if macd_bull else '하락'}")


def _mean_reversion_agent(closes: np.ndarray) -> AgentVote:
    mid, upper, lower = ind.bollinger_bands(closes, 20, 2.0)
    if np.isnan(mid[-1]):
        return AgentVote("mean_reversion", 0.5, 0.0, "데이터 부족")
    price = closes[-1]
    band_width = upper[-1] - lower[-1]
    if band_width == 0:
        return AgentVote("mean_reversion", 0.5, 0.0, "밴드폭 0")
    position_in_band = (price - lower[-1]) / band_width  # 0=하단, 1=상단
    score = 1.0 - position_in_band  # 하단 근접일수록 매수
    score = min(max(score, 0.0), 1.0)
    conf = abs(position_in_band - 0.5) * 2
    return AgentVote("mean_reversion", score, conf, f"밴드 내 위치={position_in_band:.2f}")


def _volatility_risk_agent(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> AgentVote:
    atr_vals = ind.atr(highs, lows, closes, 14)
    if np.isnan(atr_vals[-1]) or closes[-1] == 0:
        return AgentVote("volatility_risk", 0.5, 0.0, "데이터 부족")
    atr_pct = atr_vals[-1] / closes[-1]
    # 변동성이 너무 크면 confidence를 낮춰 전체 시그널을 약화시키는 역할
    conf = min(atr_pct * 20, 1.0)
    score = 0.5  # 방향성 없음, risk agent는 오직 confidence 조절 역할
    return AgentVote("volatility_risk", score, conf, f"ATR%={atr_pct*100:.2f}")


def run_ensemble(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                  buy_threshold: float = 0.65, sell_threshold: float = 0.35) -> EnsembleResult:
    votes = [
        _trend_agent(closes),
        _momentum_agent(closes),
        _mean_reversion_agent(closes),
    ]
    risk_vote = _volatility_risk_agent(highs, lows, closes)

    total_w = sum(v.confidence for v in votes) or 1e-9
    weighted = sum(v.score * v.confidence for v in votes) / total_w

    # 변동성이 지나치게 크면(리스크 conf 높음) 최종 스코어를 0.5쪽으로 당겨 보수적으로 만든다
    dampen = risk_vote.confidence * 0.3
    final = weighted * (1 - dampen) + 0.5 * dampen

    if final >= buy_threshold:
        action = "buy"
    elif final <= sell_threshold:
        action = "sell"
    else:
        action = "hold"

    return EnsembleResult(final_score=final, votes=votes + [risk_vote], action=action)
