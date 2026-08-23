import { runEnsemble } from "./ensemble.js";
import { detectRegime } from "./regime.js";
import { getState, saveState } from "./state.js";
import * as alpaca from "./brokers/alpaca.js";
import * as bybit from "./brokers/bybit.js";
import * as kis from "./brokers/kis.js";

const BUY_TH_BASE = parseFloat(process.env.AITRADER_BUY_THRESHOLD || "0.65");
const SELL_TH_BASE = parseFloat(process.env.AITRADER_SELL_THRESHOLD || "0.35");
const MARKET_SCAN_TOP = parseInt(process.env.AITRADER_MARKET_SCAN_TOP || "25", 10);

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

/**
 * 한 종목의 봉 데이터로 앙상블/레짐을 계산하고 state(시그널, 가상 포지션, 거래기록)를 갱신.
 * 워치리스트 스캔과 시장 전체 스캔이 이 함수를 공유한다.
 * source: "watchlist" | "market" - 화면에서 구분 표시하는 용도
 */
function applySignal(state, brokerName, symbol, bars, now, source) {
  if (!bars || bars.length < 60) return null;
  const closes = bars.map((b) => b.close);
  const highs = bars.map((b) => b.high);
  const lows = bars.map((b) => b.low);

  const regime = detectRegime(highs, lows, closes);
  const buyTh = BUY_TH_BASE + regime.adj;
  const sellTh = SELL_TH_BASE - regime.adj;
  const ens = runEnsemble(highs, lows, closes, buyTh, sellTh);
  const price = closes[closes.length - 1];
  const key = `${brokerName}:${symbol}`;

  state.last_signals[key] = {
    score: Math.round(ens.finalScore * 10000) / 10000, action: ens.action,
    vol_regime: regime.vol, trend_regime: regime.trend, price, t: now, source,
  };

  const pos = state.paper_positions[key];
  if (!pos && ens.action === "buy") {
    state.paper_positions[key] = { entry_price: price, entry_time: now };
    state.trade_log.push({
      broker: brokerName, symbol, side: "buy", entry_price: price, entry_time: now,
      exit_price: null, exit_time: null, pnl_pct: null,
      score: Math.round(ens.finalScore * 1000) / 1000, status: "open", source,
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
  console.log(`[${brokerName}/${source}] ${symbol}: price=${price.toFixed(2)} score=${ens.finalScore.toFixed(3)} action=${ens.action}`);
  return ens.action;
}

async function scanBroker(brokerName, mod, watchlist, state, now) {
  const tally = { buy: 0, sell: 0, hold: 0, error: 0 };
  try {
    const equity = await mod.getAccountEquity();
    const positions = await mod.getPositions();
    state.real_accounts[brokerName] = { equity: Math.round(equity * 100) / 100, positions: redactPositions(positions) };
  } catch (e) {
    console.error(`[${brokerName}] 계좌 조회 실패:`, e.message);
  }

  for (const symbol of watchlist) {
    try {
      const bars = await mod.getBars(symbol, 120);
      const action = applySignal(state, brokerName, symbol, bars, now, "watchlist");
      if (action) tally[action] = (tally[action] || 0) + 1;
    } catch (e) {
      tally.error += 1;
      console.error(`[${brokerName}] ${symbol} 에러:`, e.message);
    }
  }
  return tally;
}

/**
 * 전체 시장 스캔 (Alpaca 전용).
 * 1단계: Alpaca 스크리너로 시장 전체 상승률/하락률 상위 종목 추출 (가벼운 연산, Alpaca가 이미 전체 시장을 훑어서 계산해줌)
 * 2단계: 그 후보군에 대해서만 다중 종목 일괄 조회 + 앙상블 정밀분석 (요청 수 최소화, 시간제한 안에 끝내기 위함)
 * 매 스캔마다 그날 가장 많이 움직인 종목들이 후보로 잡히므로, 반복하다 보면 사실상 시장 전반을 훑게 된다.
 */
async function scanMarket(state, now) {
  const tally = { buy: 0, sell: 0, hold: 0, error: 0 };
  let symbols = [];
  try {
    const { gainers, losers } = await alpaca.getMovers(MARKET_SCAN_TOP);
    symbols = [...new Set([...gainers.map((g) => g.symbol), ...losers.map((l) => l.symbol)])];
    state.market_movers = { gainers, losers, t: now };
  } catch (e) {
    console.error("[market] 스크리너 조회 실패:", e.message);
    return tally;
  }
  if (symbols.length === 0) return tally;

  let barsMap = {};
  try {
    barsMap = await alpaca.getBarsMulti(symbols, 90);
  } catch (e) {
    console.error("[market] 다중 시세 조회 실패:", e.message);
    return tally;
  }

  for (const symbol of symbols) {
    try {
      const action = applySignal(state, "alpaca", symbol, barsMap[symbol], now, "market");
      if (action) tally[action] = (tally[action] || 0) + 1;
    } catch (e) {
      tally.error += 1;
      console.error(`[market] ${symbol} 에러:`, e.message);
    }
  }
  return tally;
}

/**
 * brokerNames: 예) ['alpaca'] 또는 ['alpaca','bybit','kis']
 * 조회만 하고 실제 주문 함수는 이 파일 어디에도 존재하지 않음.
 */
export async function runScan(brokerNames, options = {}) {
  const startedAt = Date.now();
  const now = new Date().toISOString();
  const state = await getState();
  state.scan_log = state.scan_log || [];
  state.news = state.news || [];
  state.market_movers = state.market_movers || null;

  for (const name of brokerNames) {
    const cfg = BROKERS[name];
    if (!cfg) continue;
    const tally = await scanBroker(name, cfg.mod, cfg.watchlist, state, now);
    state.scan_log.push({
      t: now, broker: name, source: "watchlist", symbols: cfg.watchlist.length,
      buy: tally.buy || 0, sell: tally.sell || 0, hold: tally.hold || 0, error: tally.error || 0,
      duration_ms: Date.now() - startedAt,
    });
  }

  // 전체 시장 스캔 (옵션, Alpaca 전용)
  if (options.marketScan && brokerNames.includes("alpaca")) {
    const marketStarted = Date.now();
    const tally = await scanMarket(state, now);
    state.scan_log.push({
      t: now, broker: "alpaca", source: "market", symbols: (state.market_movers?.gainers?.length || 0) + (state.market_movers?.losers?.length || 0),
      buy: tally.buy || 0, sell: tally.sell || 0, hold: tally.hold || 0, error: tally.error || 0,
      duration_ms: Date.now() - marketStarted,
    });
  }
  state.scan_log = state.scan_log.slice(-150);

  // Alpaca 조회 전용 키로 얻을 수 있는 실제 뉴스 (제목/출처/링크만, 본문 저장 안 함)
  if (brokerNames.includes("alpaca")) {
    try {
      const symbols = BROKERS.alpaca.watchlist;
      const news = await alpaca.getNews(symbols, 10);
      state.news = news;
    } catch (e) {
      console.error("뉴스 조회 실패:", e.message);
    }
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
    market_symbols_scanned: options.marketScan ? symbolsScannedCount(state) : 0,
  };
}

function symbolsScannedCount(state) {
  const m = state.market_movers;
  if (!m) return 0;
  return (m.gainers?.length || 0) + (m.losers?.length || 0);
}
