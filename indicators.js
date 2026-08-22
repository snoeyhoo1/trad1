export function sma(closes, period) {
  const out = new Array(closes.length).fill(NaN);
  for (let i = period - 1; i < closes.length; i++) {
    let s = 0;
    for (let j = i - period + 1; j <= i; j++) s += closes[j];
    out[i] = s / period;
  }
  return out;
}

export function ema(closes, period) {
  const out = new Array(closes.length).fill(NaN);
  if (closes.length < period) return out;
  const k = 2 / (period + 1);
  let s = 0;
  for (let j = 0; j < period; j++) s += closes[j];
  out[period - 1] = s / period;
  for (let i = period; i < closes.length; i++) out[i] = closes[i] * k + out[i - 1] * (1 - k);
  return out;
}

export function rsi(closes, period = 14) {
  const out = new Array(closes.length).fill(NaN);
  if (closes.length <= period) return out;
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    avgGain += Math.max(d, 0); avgLoss += Math.max(-d, 0);
  }
  avgGain /= period; avgLoss /= period;
  out[period] = avgLoss !== 0 ? 100 - 100 / (1 + avgGain / avgLoss) : 100;
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    const g = Math.max(d, 0), l = Math.max(-d, 0);
    avgGain = (avgGain * (period - 1) + g) / period;
    avgLoss = (avgLoss * (period - 1) + l) / period;
    out[i] = avgLoss !== 0 ? 100 - 100 / (1 + avgGain / avgLoss) : 100;
  }
  return out;
}

export function macdHist(closes, fast = 12, slow = 26, signal = 9) {
  const ef = ema(closes, fast), es = ema(closes, slow);
  const macdLine = closes.map((_, i) => (isNaN(ef[i]) || isNaN(es[i])) ? NaN : ef[i] - es[i]);
  const validIdx = macdLine.map((v, i) => (!isNaN(v) ? i : -1)).filter((i) => i >= 0);
  const signalLine = new Array(closes.length).fill(NaN);
  if (validIdx.length >= signal) {
    const compact = validIdx.map((i) => macdLine[i]);
    const sig = ema(compact, signal);
    validIdx.forEach((origI, k) => (signalLine[origI] = sig[k]));
  }
  return macdLine.map((v, i) => (isNaN(v) || isNaN(signalLine[i])) ? NaN : v - signalLine[i]);
}

export function atr(highs, lows, closes, period = 14) {
  const n = closes.length;
  const tr = new Array(n).fill(0);
  tr[0] = highs[0] - lows[0];
  for (let i = 1; i < n; i++) {
    tr[i] = Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1]));
  }
  const out = new Array(n).fill(NaN);
  if (n < period) return out;
  let s = 0;
  for (let j = 0; j < period; j++) s += tr[j];
  out[period - 1] = s / period;
  for (let i = period; i < n; i++) out[i] = (out[i - 1] * (period - 1) + tr[i]) / period;
  return out;
}

export function bollinger(closes, period = 20, numStd = 2.0) {
  const mid = sma(closes, period);
  const upper = new Array(closes.length).fill(NaN), lower = new Array(closes.length).fill(NaN);
  for (let i = period - 1; i < closes.length; i++) {
    const win = closes.slice(i - period + 1, i + 1);
    const mean = mid[i];
    const variance = win.reduce((a, v) => a + (v - mean) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    upper[i] = mid[i] + numStd * std;
    lower[i] = mid[i] - numStd * std;
  }
  return { mid, upper, lower };
}
