import { sma, rsi, macdHist, bollinger, atr } from "./indicators.js";

export function runEnsemble(highs, lows, closes, buyTh, sellTh) {
  const n = closes.length;
  const votes = [];

  const s20 = sma(closes, 20), s50 = sma(closes, 50);
  if (!isNaN(s50[n - 1])) {
    const price = closes[n - 1];
    const above20 = price > s20[n - 1];
    const golden = s20[n - 1] > s50[n - 1];
    let score = 0.5 + 0.25 * (above20 ? 1 : -1) + 0.25 * (golden ? 1 : -1);
    score = Math.min(Math.max(score, 0), 1);
    const conf = Math.min(Math.abs(s20[n - 1] - s50[n - 1]) / price * 10, 1);
    votes.push({ name: "trend", score, confidence: conf });
  } else votes.push({ name: "trend", score: 0.5, confidence: 0 });

  const rsiArr = rsi(closes, 14);
  const hist = macdHist(closes);
  if (!isNaN(rsiArr[n - 1])) {
    const r = rsiArr[n - 1];
    const rsiScore = Math.min(Math.max(1 - r / 100, 0), 1);
    const macdBull = !isNaN(hist[n - 1]) && hist[n - 1] > 0;
    const macdScore = macdBull ? 0.65 : 0.35;
    const score = 0.5 * rsiScore + 0.5 * macdScore;
    const conf = (r < 30 || r > 70) ? 0.8 : 0.4;
    votes.push({ name: "momentum", score, confidence: conf, rsi: r });
  } else votes.push({ name: "momentum", score: 0.5, confidence: 0 });

  const { mid, upper, lower } = bollinger(closes, 20, 2.0);
  if (!isNaN(mid[n - 1]) && upper[n - 1] - lower[n - 1] !== 0) {
    const price = closes[n - 1];
    const posInBand = (price - lower[n - 1]) / (upper[n - 1] - lower[n - 1]);
    const score = Math.min(Math.max(1 - posInBand, 0), 1);
    const conf = Math.abs(posInBand - 0.5) * 2;
    votes.push({ name: "mean_reversion", score, confidence: conf });
  } else votes.push({ name: "mean_reversion", score: 0.5, confidence: 0 });

  const atrArr = atr(highs, lows, closes, 14);
  let riskConf = 0;
  if (!isNaN(atrArr[n - 1]) && closes[n - 1] !== 0) {
    riskConf = Math.min((atrArr[n - 1] / closes[n - 1]) * 20, 1);
  }

  const totalW = votes.reduce((a, v) => a + v.confidence, 0) || 1e-9;
  const weighted = votes.reduce((a, v) => a + v.score * v.confidence, 0) / totalW;
  const dampen = riskConf * 0.3;
  const final = weighted * (1 - dampen) + 0.5 * dampen;

  let action = "hold";
  if (final >= buyTh) action = "buy";
  else if (final <= sellTh) action = "sell";

  return { finalScore: final, votes, action };
}
