import { kv } from "@vercel/kv";

const STATE_KEY = "aitrader:state";

export const EMPTY_STATE = {
  updated_at: null,
  paper_equity: 1.0,
  paper_positions: {},
  trade_log: [],
  equity_curve: [],
  real_accounts: {},
  last_signals: {},
};

export async function getState() {
  try {
    const state = await kv.get(STATE_KEY);
    return state || JSON.parse(JSON.stringify(EMPTY_STATE));
  } catch (e) {
    // KV가 아직 프로젝트에 연결 안 된 경우 등. 500 대신 빈 상태 + 에러 메시지를 반환해
    // 대시보드가 안내 문구를 보여줄 수 있게 한다.
    console.error("KV read error:", e.message);
    return { ...JSON.parse(JSON.stringify(EMPTY_STATE)), _error: `KV 연결 오류: ${e.message}` };
  }
}

export async function saveState(state) {
  await kv.set(STATE_KEY, state);
}
