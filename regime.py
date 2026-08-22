"""
레짐 감지: ATR 백분위(변동성) + EMA 기울기(추세) 조합.
참고: ATR percentile 방식이 VIX 임계값/HMM보다 코드 복잡도 대비 실전 채택률이 높고
자산 종류 무관하게(주식/코인 공용) 적용 가능해 기본 채택. 임계값은 업계 통용값
(20/80/95 percentile) 사용.

레짐에 따라 앙상블의 buy/sell 임계값과 포지션 사이징을 동적으로 조정한다:
  - LOW: 거래대금 적고 신호 신뢰도 낮음 -> 임계값 상향(보수적)
  - NORMAL: 기본값
  - HIGH: 추세 추종에 유리 -> 임계값 소폭 완화
  - EXTREME: 뉴스/급락 등 예측 불가 구간 -> 신규 진입 자체를 보수적으로 (임계값 대폭 상향)
"""
from dataclasses import dataclass
from enum import Enum
import numpy as np
from signals.indicators import atr, ema


class VolRegime(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


class TrendRegime(str, Enum):
    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


@dataclass
class RegimeState:
    vol_regime: VolRegime
    trend_regime: TrendRegime
    atr_percentile: float
    threshold_adjustment: float  # buy_threshold에 더할 값 (음수면 완화, 양수면 강화)


def _atr_percentile(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, lookback: int = 100) -> float:
    atr_vals = atr(highs, lows, closes, 14)
    atr_pct_series = atr_vals / np.where(closes == 0, np.nan, closes)
    valid = atr_pct_series[~np.isnan(atr_pct_series)]
    if len(valid) < 20:
        return 50.0  # 데이터 부족 시 중립값
    window = valid[-lookback:] if len(valid) >= lookback else valid
    current = window[-1]
    percentile = (window < current).sum() / len(window) * 100
    return percentile


def _trend_regime(closes: np.ndarray, period: int = 50) -> TrendRegime:
    ema_vals = ema(closes, period)
    valid = ema_vals[~np.isnan(ema_vals)]
    if len(valid) < 10:
        return TrendRegime.SIDEWAYS
    # 최근 10봉간 EMA 기울기(정규화)
    slope = (valid[-1] - valid[-10]) / valid[-10] if valid[-10] != 0 else 0
    if slope > 0.02:
        return TrendRegime.UP
    elif slope < -0.02:
        return TrendRegime.DOWN
    return TrendRegime.SIDEWAYS


def detect_regime(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> RegimeState:
    pct = _atr_percentile(highs, lows, closes)
    trend = _trend_regime(closes)

    if pct < 20:
        vol = VolRegime.LOW
        adj = +0.05  # 거래 신뢰도 낮음 -> 보수적
    elif pct < 80:
        vol = VolRegime.NORMAL
        adj = 0.0
    elif pct < 95:
        vol = VolRegime.HIGH
        adj = -0.03  # 추세 추종 유리 -> 소폭 완화
    else:
        vol = VolRegime.EXTREME
        adj = +0.12  # 급변동 구간 -> 신규 진입 대폭 보수적

    return RegimeState(vol_regime=vol, trend_regime=trend, atr_percentile=pct, threshold_adjustment=adj)
