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
  const state = await kv.get(STATE_KEY);
  return state || JSON.parse(JSON.stringify(EMPTY_STATE));
}

export async function saveState(state) {
  await kv.set(STATE_KEY, state);
}

