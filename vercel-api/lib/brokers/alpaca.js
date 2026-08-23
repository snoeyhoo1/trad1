const BASE_URL = process.env.ALPACA_BASE_URL || "https://api.alpaca.markets";
const DATA_URL = "https://data.alpaca.markets";

function headers() {
  return {
    "APCA-API-KEY-ID": process.env.ALPACA_API_KEY || "",
    "APCA-API-SECRET-KEY": process.env.ALPACA_SECRET_KEY || "",
  };
}

export async function getAccountEquity() {
  const r = await fetch(`${BASE_URL}/v2/account`, { headers: headers() });
  if (!r.ok) throw new Error(`alpaca account ${r.status}`);
  const data = await r.json();
  return parseFloat(data.equity);
}

export async function getPositions() {
  const r = await fetch(`${BASE_URL}/v2/positions`, { headers: headers() });
  if (!r.ok) throw new Error(`alpaca positions ${r.status}`);
  const data = await r.json();
  return data.map((p) => ({
    symbol: p.symbol, qty: parseFloat(p.qty),
    marketValue: parseFloat(p.market_value), unrealizedPnl: parseFloat(p.unrealized_pl),
  }));
}

export async function getBars(symbol, limit = 120) {
  const params = new URLSearchParams({ timeframe: "1Day", limit: String(limit), adjustment: "raw" });
  const r = await fetch(`${DATA_URL}/v2/stocks/${symbol}/bars?${params}`, { headers: headers() });
  if (!r.ok) throw new Error(`alpaca bars ${symbol} ${r.status}`);
  const data = await r.json();
  const bars = data.bars || [];
  return bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c, volume: b.v }));
}

/** 뉴스 제목/출처/링크만 가져옴 (본문 텍스트는 저장하지 않음) */
export async function getNews(symbols, limit = 10) {
  const params = new URLSearchParams({ symbols: symbols.join(","), limit: String(limit) });
  const r = await fetch(`${DATA_URL}/v1beta1/news?${params}`, { headers: headers() });
  if (!r.ok) throw new Error(`alpaca news ${r.status}`);
  const data = await r.json();
  return (data.news || []).map((n) => ({
    id: n.id, headline: n.headline, source: n.source,
    url: n.url, created_at: n.created_at, symbols: n.symbols || [],
  }));
}
