import { kv } from "@vercel/kv";

const IS_VIRTUAL = String(process.env.KIS_IS_VIRTUAL || "false").toLowerCase() === "true";
const BASE_URL = IS_VIRTUAL
  ? "https://openapivts.koreainvestment.com:29443"
  : "https://openapi.koreainvestment.com:9443";
const APP_KEY = process.env.KIS_APP_KEY || "";
const APP_SECRET = process.env.KIS_APP_SECRET || "";
const ACCOUNT_NO = process.env.KIS_ACCOUNT_NO || "";
const TOKEN_KV_KEY = "aitrader:kis_token";

async function getToken() {
  const cached = await kv.get(TOKEN_KV_KEY);
  if (cached && cached.expiresAt > Date.now() + 60_000) {
    return cached.accessToken;
  }
  const r = await fetch(`${BASE_URL}/oauth2/tokenP`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ grant_type: "client_credentials", appkey: APP_KEY, appsecret: APP_SECRET }),
  });
  if (!r.ok) throw new Error(`kis token ${r.status}`);
  const data = await r.json();
  const expiresIn = parseInt(data.expires_in || "86400", 10);
  await kv.set(TOKEN_KV_KEY, { accessToken: data.access_token, expiresAt: Date.now() + expiresIn * 1000 });
  return data.access_token;
}

async function headers(trId) {
  const token = await getToken();
  return {
    authorization: `Bearer ${token}`, appkey: APP_KEY, appsecret: APP_SECRET,
    tr_id: trId, "content-type": "application/json; charset=utf-8",
  };
}

function accountParts() {
  const [cano, acntPrdtCd] = ACCOUNT_NO.split("-");
  return { cano, acntPrdtCd };
}

export async function getAccountEquity() {
  const trId = IS_VIRTUAL ? "VTTC8434R" : "TTTC8434R";
  const { cano, acntPrdtCd } = accountParts();
  const params = new URLSearchParams({
    CANO: cano, ACNT_PRDT_CD: acntPrdtCd, AFHR_FLPR_YN: "N", OFL_YN: "",
    INQR_DVSN: "02", UNPR_DVSN: "01", FUND_STTL_ICLD_YN: "N",
    FNCG_AMT_AUTO_RDPT_YN: "N", PRCS_DVSN: "01", CTX_AREA_FK100: "", CTX_AREA_NK100: "",
  });
  const r = await fetch(`${BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance?${params}`, {
    headers: await headers(trId),
  });
  if (!r.ok) throw new Error(`kis balance ${r.status}`);
  const data = await r.json();
  return parseFloat(data.output2?.[0]?.tot_evlu_amt || "0");
}

export async function getPositions() {
  const trId = IS_VIRTUAL ? "VTTC8434R" : "TTTC8434R";
  const { cano, acntPrdtCd } = accountParts();
  const params = new URLSearchParams({
    CANO: cano, ACNT_PRDT_CD: acntPrdtCd, AFHR_FLPR_YN: "N", OFL_YN: "",
    INQR_DVSN: "02", UNPR_DVSN: "01", FUND_STTL_ICLD_YN: "N",
    FNCG_AMT_AUTO_RDPT_YN: "N", PRCS_DVSN: "01", CTX_AREA_FK100: "", CTX_AREA_NK100: "",
  });
  const r = await fetch(`${BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance?${params}`, {
    headers: await headers(trId),
  });
  if (!r.ok) throw new Error(`kis positions ${r.status}`);
  const data = await r.json();
  return (data.output1 || [])
    .filter((p) => parseFloat(p.hldg_qty || "0") !== 0)
    .map((p) => ({
      symbol: p.pdno, qty: parseFloat(p.hldg_qty),
      marketValue: parseFloat(p.evlu_amt), unrealizedPnl: parseFloat(p.evlu_pfls_amt),
    }));
}

export async function getBars(symbol, limit = 120) {
  const trId = "FHKST03010100";
  const params = new URLSearchParams({
    FID_COND_MRKT_DIV_CODE: "J", FID_INPUT_ISCD: symbol,
    FID_PERIOD_DIV_CODE: "D", FID_ORG_ADJ_PRC: "1",
  });
  const r = await fetch(`${BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price?${params}`, {
    headers: await headers(trId),
  });
  if (!r.ok) throw new Error(`kis bars ${symbol} ${r.status}`);
  const data = await r.json();
  const rows = (data.output || []).slice(0, limit);
  const bars = rows.map((row) => ({
    time: row.stck_bsop_date,
    open: parseFloat(row.stck_oprc), high: parseFloat(row.stck_hgpr),
    low: parseFloat(row.stck_lwpr), close: parseFloat(row.stck_clpr),
    volume: parseFloat(row.acml_vol),
  }));
  return bars.reverse();
}
