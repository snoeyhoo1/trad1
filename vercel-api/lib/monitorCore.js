import { runEnsemble } from "./ensemble.js";
import { detectRegime } from "./regime.js";
import { getState, saveState } from "./state.js";
import * as alpaca from "./brokers/alpaca.js";
import * as bybit from "./brokers/bybit.js";
import * as kis from "./brokers/kis.js";

const BUY_TH_BASE = parseFloat(process.env.AITRADER_BUY_THRESHOLD || "0.65");
const SELL_TH_BASE = parseFloat(process.env.AITRADER_SELL_THRESHOLD || "0.35");

const BROKERS = {
  alpaca: { mod: alpaca, watchlist: (process.env.AITRADER_WATCHLIST_US || "AAPL,MSFT,NVDA,SPY").split(",") },
  bybit: { mod: bybit, watchlist: (process.env.AITRADER_WATCHLIST_CRYPTO || "BTCUSDT,ETHUSDT").split(",") },
  kis: { mod: kis, watchlist: (process.env.AITRADER_WATCHLIST_KR || "005930,000660").split(",") },
};

function redactPositions(positions) {
  return positions.map((p) => ({
    symbol: p.symbol, qty: Math.round(p.qty * 1e6) / 1e6,
    marketValue: Math.round(p.marketValue * 100) / 100,
    unrealizedPnl: Math.round(p.unrealizedPnl * 100) / 100,
  }));
}

async function scanBroker(brokerName, mod, watchlist, state, now) {
  try {
    const equity = await mod.getAccountEquity();
    const positions = await mod.getPositions();
    state.real_accounts[brokerName] = { equity: Math.round(equity * 100) / 100, positions: redactPositions(positions) };
  } catch (e) {
    console.error(`[${brokerName}] 계좌 조회 실패:`, e.message);
  }

  for (const symbol of watchlist) {
    const key = `${brokerName}:${symbol}`;
    try {
      const bars = await mod.getBars(symbol, 120);
      if (bars.length < 60) continue;
      const closes = bars.map((b) => b.close);
      const highs = bars.map((b) => b.high);
      const lows = bars.map((b) => b.low);

      const regime = detectRegime(highs, lows, closes);
      const buyTh = BUY_TH_BASE + regime.adj;
      const sellTh = SELL_TH_BASE - regime.adj;
      const ens = runEnsemble(highs, lows, closes, buyTh, sellTh);
      const price = closes[closes.length - 1];

      state.last_signals[key] = {
        score: Math.round(ens.finalScore * 10000) / 10000, action: ens.action,
        vol_regime: regime.vol, trend_regime: regime.trend, price, t: now,
      };

      const pos = state.paper_positions[key];
      if (!pos && ens.action === "buy") {
        state.paper_positions[key] = { entry_price: price, entry_time: now };
        state.trade_log.push({
          broker: brokerName, symbol, side: "buy", entry_price: price, entry_time: now,
          exit_price: null, exit_time: null, pnl_pct: null,
          score: Math.round(ens.finalScore * 1000) / 1000, status: "open",
        });
      } else if (pos && ens.action === "sell") {
        const pnlPct = (price - pos.entry_price) / pos.entry_price;
        state.paper_equity *= (1 + pnlPct);
        for (let i = state.trade_log.length - 1; i >= 0; i--) {
          const t = state.trade_log[i];
          if (t.broker === brokerName && t.symbol === symbol && t.status === "open") {
            t.exit_price = price; t.exit_time = now;
            t.pnl_pct = Math.round(pnlPct * 100000) / 100000; t.status = "closed";
            break;
          }
        }
        delete state.paper_positions[key];
      }
      console.log(`[${brokerName}] ${symbol}: price=${price.toFixed(2)} score=${ens.finalScore.toFixed(3)} action=${ens.action}`);
    } catch (e) {
      console.error(`[${brokerName}] ${symbol} 에러:`, e.message);
    }
  }
}

/**
 * brokerNames: 예) ['alpaca'] 또는 ['alpaca','bybit','kis']
 * 조회만 하고 실제 주문 함수는 이 파일 어디에도 존재하지 않음.
 */
export async function runScan(brokerNames) {
  const now = new Date().toISOString();
  const state = await getState();

  for (const name of brokerNames) {
    const cfg = BROKERS[name];
    if (!cfg) continue;
    await scanBroker(name, cfg.mod, cfg.watchlist, state, now);
  }

  state.equity_curve.push({ t: now, equity: Math.round(state.paper_equity * 100000) / 100000 });
  state.equity_curve = state.equity_curve.slice(-2000);
  state.trade_log = state.trade_log.slice(-500);
  state.updated_at = now;

  await saveState(state);
  return {
    paper_equity: state.paper_equity,
    open_positions: Object.keys(state.paper_positions).length,
    total_trades: state.trade_log.length,
  };
}
