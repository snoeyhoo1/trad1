"""순수 함수 기술적 지표. numpy만 사용 (외부 TA 라이브러리 의존 없음)."""
import numpy as np


def sma(closes: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(closes, np.nan, dtype=float)
    for i in range(period - 1, len(closes)):
        out[i] = closes[i - period + 1:i + 1].mean()
    return out


def ema(closes: np.ndarray, period: int) -> np.ndarray:
    out = np.full_like(closes, np.nan, dtype=float)
    k = 2 / (period + 1)
    if len(closes) < period:
        return out
    out[period - 1] = closes[:period].mean()
    for i in range(period, len(closes)):
        out[i] = closes[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    deltas = np.diff(closes)
    out = np.full(len(closes), np.nan)
    if len(deltas) < period:
        return out
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    out[period] = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss != 0 else 100
    for i in range(period + 1, len(closes)):
        d = deltas[i - 1]
        g = max(d, 0.0)
        l = max(-d, 0.0)
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        out[i] = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss != 0 else 100
    return out


def macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = ema_fast - ema_slow
    valid = ~np.isnan(macd_line)
    signal_line = np.full_like(macd_line, np.nan)
    if valid.sum() >= signal:
        signal_line[valid] = ema(macd_line[valid], signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
    tr = np.zeros(len(closes))
    tr[0] = highs[0] - lows[0]
    for i in range(1, len(closes)):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    out = np.full(len(closes), np.nan)
    if len(closes) < period:
        return out
    out[period - 1] = tr[:period].mean()
    for i in range(period, len(closes)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def bollinger_bands(closes: np.ndarray, period: int = 20, num_std: float = 2.0):
    mid = sma(closes, period)
    out_upper = np.full_like(closes, np.nan, dtype=float)
    out_lower = np.full_like(closes, np.nan, dtype=float)
    for i in range(period - 1, len(closes)):
        std = closes[i - period + 1:i + 1].std()
        out_upper[i] = mid[i] + num_std * std
        out_lower[i] = mid[i] - num_std * std
    return mid, out_upper, out_lower
