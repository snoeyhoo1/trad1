import crypto from "crypto";

const TESTNET = String(process.env.BYBIT_TESTNET || "false").toLowerCase() === "true";
const BASE_URL = TESTNET ? "https://api-testnet.bybit.com" : "https://api.bybit.com";
const API_KEY = process.env.BYBIT_API_KEY || "";
const API_SECRET = process.env.BYBIT_API_SECRET || "";
const RECV_WINDOW = "5000";

function sign(paramsStr, timestamp) {
  const payload = `${timestamp}${API_KEY}${RECV_WINDOW}${paramsStr}`;
  return crypto.createHmac("sha256", API_SECRET).update(payload).digest("hex");
}

async function signedGet(path, params) {
  const timestamp = String(Date.now());
  const query = Object.keys(params).sort().map((k) => `${k}=${params[k]}`).join("&");
  const sig = sign(query, timestamp);
  const r = await fetch(`${BASE_URL}${path}?${query}`, {
    headers: {
      "X-BAPI-API-KEY": API_KEY, "X-BAPI-TIMESTAMP": timestamp,
      "X-BAPI-RECV-WINDOW": RECV_WINDOW, "X-BAPI-SIGN": sig,
    },
  });
  if (!r.ok) throw new Error(`bybit ${path} ${r.status}`);
  return r.json();
}

export async function getAccountEquity() {
  const data = await signedGet("/v5/account/wallet-balance", { accountType: "UNIFIED" });
  const coins = data.result?.list?.[0]?.coin || [];
  const usdt = coins.find((c) => c.coin === "USDT");
  return usdt ? parseFloat(usdt.walletBalance) : 0;
}

export async function getPositions() {
  const data = await signedGet("/v5/position/list", { category: "linear", settleCoin: "USDT" });
  return (data.result?.list || [])
    .filter((p) => parseFloat(p.size) !== 0)
    .map((p) => ({
      symbol: p.symbol, qty: parseFloat(p.size),
      marketValue: parseFloat(p.positionValue), unrealizedPnl: parseFloat(p.unrealisedPnl),
    }));
}

export async function getBars(symbol, limit = 120) {
  const params = new URLSearchParams({ category: "linear", symbol, interval: "D", limit: String(limit) });
  const r = await fetch(`${BASE_URL}/v5/market/kline?${params}`);
  if (!r.ok) throw new Error(`bybit kline ${symbol} ${r.status}`);
  const data = await r.json();
  const rows = data.result?.list || [];
  const bars = rows.map((row) => ({
    time: new Date(parseInt(row[0])).toISOString(),
    open: parseFloat(row[1]), high: parseFloat(row[2]), low: parseFloat(row[3]),
    close: parseFloat(row[4]), volume: parseFloat(row[5]),
  }));
  return bars.reverse(); // bybit는 최신순 -> 시간순으로 뒤집기
}
