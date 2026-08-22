import { atr, ema } from "./indicators.js";

export function detectRegime(highs, lows, closes) {
  const atrArr = atr(highs, lows, closes, 14);
  const atrPctSeries = atrArr.map((a, i) => (closes[i] !== 0 ? a / closes[i] : NaN));
  const valid = atrPctSeries.filter((v) => !isNaN(v));
  let pct = 50;
  if (valid.length >= 20) {
    const window = valid.slice(-100);
    const current = window[window.length - 1];
    pct = (window.filter((v) => v < current).length / window.length) * 100;
  }

  const emaArr = ema(closes, 50);
  const validEma = emaArr.filter((v) => !isNaN(v));
  let trend = "sideways";
  if (validEma.length >= 10) {
    const last = validEma[validEma.length - 1];
    const prev = validEma[validEma.length - 10];
    const slope = prev !== 0 ? (last - prev) / prev : 0;
    if (slope > 0.02) trend = "up";
    else if (slope < -0.02) trend = "down";
  }

  let vol, adj;
  if (pct < 20) { vol = "low"; adj = 0.05; }
  else if (pct < 80) { vol = "normal"; adj = 0; }
  else if (pct < 95) { vol = "high"; adj = -0.03; }
  else { vol = "extreme"; adj = 0.12; }

  return { vol, trend, atrPct: pct, adj };
}
