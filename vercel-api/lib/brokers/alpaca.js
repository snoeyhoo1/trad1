const BASE_URL = process.env.ALPACA_BASE_URL || "https://api.alpaca.markets";
const DATA_URL = "https://data.alpaca.markets";

function headers() {
  return {
    "APCA-API-KEY-ID": process.env.ALPACA_API_KEY || "",
    "APCA-API-SECRET-KEY": process.env.ALPACA_SECRET_KEY || "",
  };
}

/** 전체 키를 남기지 않고 진단용으로 앞4자리+뒤4자리+길이만 로그에 남김 */
function maskedDiag() {
  const k = process.env.ALPACA_API_KEY || "";
  const s = process.env.ALPACA_SECRET_KEY || "";
  const mask = (v) => (v ? `${v.slice(0, 4)}...${v.slice(-4)} (len:${v.length})` : "MISSING/EMPTY");
  return `KEY=${mask(k)} SECRET=${mask(s)} BASE_URL=${BASE_URL}`;
}

async function checkOk(r, label) {
  if (!r.ok) {
    if (r.status === 401 || r.status === 403) {
      console.error(`[alpaca 진단] ${label} ${r.status} - ${maskedDiag()}`);
    }
    throw new Error(`alpaca ${label} ${r.status}`);
  }
}

export async function getAccountEquity() {
  const r = await fetch(`${BASE_URL}/v2/account`, { headers: headers() });
  await checkOk(r, "account");
  const data = await r.json();
  return parseFloat(data.equity);
}

export async function getPositions() {
  const r = await fetch(`${BASE_URL}/v2/positions`, { headers: headers() });
  await checkOk(r, "positions");
  const data = await r.json();
  return data.map((p) => ({
    symbol: p.symbol, qty: parseFloat(p.qty),
    marketValue: parseFloat(p.market_value), unrealizedPnl: parseFloat(p.unrealized_pl),
  }));
}

export async function getBars(symbol, limit = 120) {
  const params = new URLSearchParams({ timeframe: "1Day", limit: String(limit), adjustment: "raw" });
  const r = await fetch(`${DATA_URL}/v2/stocks/${symbol}/bars?${params}`, { headers: headers() });
  await checkOk(r, `bars ${symbol}`);
  const data = await r.json();
  const bars = data.bars || [];
  return bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c, volume: b.v }));
}

/** 뉴스 제목/출처/링크만 가져옴 (본문 텍스트는 저장하지 않음) */
export async function getNews(symbols, limit = 10) {
  const params = new URLSearchParams({ symbols: symbols.join(","), limit: String(limit) });
  const r = await fetch(`${DATA_URL}/v1beta1/news?${params}`, { headers: headers() });
  await checkOk(r, "news");
  const data = await r.json();
  return (data.news || []).map((n) => ({
    id: n.id, headline: n.headline, source: n.source,
    url: n.url, created_at: n.created_at, symbols: n.symbols || [],
  }));
}

/**
 * 전체 시장(미국 상장 종목 전부)을 대상으로 Alpaca가 계산한 상승률/하락률 상위 종목.
 * 1단계 스크리닝 역할 - 이 결과에 대해서만 2단계로 앙상블 정밀분석을 돌린다.
 */
export async function getMovers(top = 25) {
  const params = new URLSearchParams({ top: String(top) });
  const r = await fetch(`${DATA_URL}/v1beta1/screener/stocks/movers?${params}`, { headers: headers() });
  await checkOk(r, "movers");
  const data = await r.json();
  const gainers = (data.gainers || []).map((m) => ({ symbol: m.symbol, percentChange: m.percent_change, price: m.price }));
  const losers = (data.losers || []).map((m) => ({ symbol: m.symbol, percentChange: m.percent_change, price: m.price }));
  return { gainers, losers };
}

/**
 * 여러 종목의 일봉을 한 번의 요청으로 가져옴 (종목마다 따로 요청하면 느리고 레이트리밋에 걸림).
 * 응답이 여러 페이지로 나뉘면 이어붙임 (최대 5페이지까지, 시간제한 안전장치).
 */
export async function getBarsMulti(symbols, limit = 90) {
  const result = {};
  let pageToken = null;
  let pages = 0;
  do {
    const params = new URLSearchParams({
      symbols: symbols.join(","), timeframe: "1Day", limit: String(limit), adjustment: "raw",
    });
    if (pageToken) params.set("page_token", pageToken);
    const r = await fetch(`${DATA_URL}/v2/stocks/bars?${params}`, { headers: headers() });
    await checkOk(r, "bars-multi");
    const data = await r.json();
    for (const [sym, bars] of Object.entries(data.bars || {})) {
      const mapped = (bars || []).map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c, volume: b.v }));
      result[sym] = (result[sym] || []).concat(mapped);
    }
    pageToken = data.next_page_token || null;
    pages += 1;
  } while (pageToken && pages < 5);
  return result;
}
