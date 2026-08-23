import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart,
} from "recharts";
import { RefreshCw, Wifi, WifiOff, TrendingUp, TrendingDown, Minus } from "lucide-react";

const font = "ui-monospace, 'SF Mono', 'Cascadia Code', 'JetBrains Mono', monospace";
const REGIME_LABEL = { low: "저변동", normal: "보통", high: "고변동", extreme: "극단" };
const BROKER_LABEL = { alpaca: "미국주식(Alpaca)", bybit: "코인(Bybit)", kis: "국내주식(KIS)" };

export default function DashboardContent() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [intervalSec, setIntervalSec] = useState(60);
  const [lastFetched, setLastFetched] = useState(null);
  const timerRef = useRef(null);

  const fetchState = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/dashboard-feed", { credentials: "same-origin" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setState(data);
      setLastFetched(new Date());
    } catch (e) {
      setError(e.message || "불러오기 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchState();
  }, [fetchState]);

  useEffect(() => {
    if (autoRefresh) {
      timerRef.current = setInterval(fetchState, intervalSec * 1000);
      return () => clearInterval(timerRef.current);
    }
  }, [autoRefresh, intervalSec, fetchState]);

  const trades = state?.trade_log || [];
  const closedTrades = trades.filter((t) => t.status === "closed");
  const openTrades = trades.filter((t) => t.status === "open");
  const wins = closedTrades.filter((t) => t.pnl_pct > 0).length;
  const winRate = closedTrades.length ? (wins / closedTrades.length) * 100 : 0;
  const equity = state?.paper_equity ?? 1.0;
  const totalReturn = (equity - 1) * 100;
  const equityCurve = (state?.equity_curve || []).map((p, i) => ({ i, equity: p.equity }));
  let peak = -Infinity, mdd = 0;
  equityCurve.forEach((p) => { peak = Math.max(peak, p.equity); mdd = Math.min(mdd, (p.equity - peak) / peak); });

  const realAccounts = state?.real_accounts || {};
  const lastSignals = state?.last_signals || {};
  const notUpdatedYet = state && !state.updated_at;

  return (
    <div style={{ minHeight: "100vh", background: "#0A0C10", color: "#E7E9EE", fontFamily: font, padding: "20px 16px", boxSizing: "border-box" }}>
      {/* 헤더 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10, marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: "0.12em", color: "#8B93A7", marginBottom: 4 }}>LIVE MONITOR · READ-ONLY</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>실계좌 연동 대시보드</div>
          <div style={{ fontSize: 11.5, color: "#5C6479", marginTop: 4, maxWidth: 480, lineHeight: 1.5 }}>
            실계좌 잔고·시세는 조회만 하고, 매매는 전부 가상 기록입니다.
            {state?.updated_at ? ` 마지막 스캔: ${fmtTime(state.updated_at)}` : ""}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: state ? "#3DDC97" : "#5C6479" }}>
            {state ? <Wifi size={14} /> : <WifiOff size={14} />}
            {lastFetched ? `${lastFetched.toLocaleTimeString("ko-KR")} 갱신` : "불러오는 중"}
          </div>
          <button onClick={fetchState} disabled={loading} style={btnStyle(false)}>
            <RefreshCw size={13} style={{ marginRight: 5, animation: loading ? "spin 1s linear infinite" : "none" }} />
            새로고침
          </button>
          <select value={intervalSec} onChange={(e) => setIntervalSec(Number(e.target.value))}
            style={{ background: "#12151B", color: "#E7E9EE", border: "1px solid #262B36", borderRadius: 6, padding: "6px 10px", fontSize: 12, fontFamily: font }}>
            <option value={30}>30초마다</option>
            <option value={60}>1분마다</option>
            <option value={300}>5분마다</option>
          </select>
        </div>
      </div>

      {error && (
        <div style={{ background: "#1A0F10", border: "1px solid #3A1A1A", color: "#FF6B6B", borderRadius: 8, padding: "10px 12px", fontSize: 12, marginBottom: 14 }}>
          ⚠ {error}
        </div>
      )}

      {state?._error && (
        <div style={{ background: "#1A0F10", border: "1px solid #3A1A1A", color: "#FF6B6B", borderRadius: 8, padding: "10px 12px", fontSize: 12, marginBottom: 14 }}>
          ⚠ 데이터를 못 불러왔습니다: {state._error}
          <div style={{ color: "#8B93A7", marginTop: 4 }}>
            Vercel 프로젝트 Storage 탭에서 KV 데이터베이스를 연결했는지 확인해주세요.
          </div>
        </div>
      )}

      {notUpdatedYet && (
        <div style={{ background: "#151710", border: "1px solid #3A3520", color: "#F2B94A", borderRadius: 8, padding: "10px 12px", fontSize: 12, marginBottom: 14 }}>
          아직 스캔이 한 번도 안 돌았습니다. cron-job.org 등록을 확인하거나 아래 엔드포인트를 직접 한 번 호출해보세요:
          <code style={{ display: "block", marginTop: 6, color: "#8B93A7" }}>/api/cron/monitor-alpaca?key=MONITOR_SECRET값</code>
        </div>
      )}

      {!state ? (
        <div style={{ textAlign: "center", color: "#5C6479", fontSize: 12.5, padding: "40px 0" }}>불러오는 중...</div>
      ) : (
        <>
          {/* 요약 통계 */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10, marginBottom: 16 }}>
            <Stat label="누적 수익률 (모의)" value={`${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(2)}%`}
              color={totalReturn >= 0 ? "#3DDC97" : "#FF6B6B"} big />
            <Stat label="완료 거래" value={closedTrades.length} />
            <Stat label="승률" value={closedTrades.length ? `${winRate.toFixed(0)}%` : "—"} />
            <Stat label="최대 낙폭" value={`${(mdd * 100).toFixed(2)}%`} color="#FF6B6B" />
            <Stat label="보유중 포지션" value={openTrades.length} color={openTrades.length ? "#F2B94A" : "#5C6479"} />
          </div>

          {/* 실계좌 스냅샷 */}
          <Panel title="실계좌 스냅샷 (조회 전용)">
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              {Object.keys(realAccounts).length === 0 && (
                <div style={{ color: "#5C6479", fontSize: 12 }}>연결된 실계좌 데이터 없음</div>
              )}
              {Object.entries(realAccounts).map(([broker, acc]) => (
                <div key={broker} style={{ minWidth: 160, background: "#0A0C10", border: "1px solid #1B1F27", borderRadius: 8, padding: 10 }}>
                  <div style={{ fontSize: 10.5, color: "#5C6479", marginBottom: 4 }}>{BROKER_LABEL[broker] || broker}</div>
                  <div style={{ fontSize: 16, fontWeight: 700 }}>{acc.equity?.toLocaleString()}</div>
                  <div style={{ fontSize: 10.5, color: "#5C6479", marginTop: 4 }}>포지션 {acc.positions?.length ?? 0}건</div>
                </div>
              ))}
            </div>
          </Panel>

          {/* 누적 자산 곡선 */}
          <Panel title="누적 자산 곡선 (모의 매매 기준)">
            <ResponsiveContainer width="100%" height={150}>
              <AreaChart data={equityCurve} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3DDC97" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3DDC97" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1B1F27" vertical={false} />
                <XAxis dataKey="i" tick={{ fill: "#5C6479", fontSize: 10 }} axisLine={{ stroke: "#262B36" }} tickLine={false} />
                <YAxis domain={["auto", "auto"]} tick={{ fill: "#5C6479", fontSize: 10 }} axisLine={false} tickLine={false} width={44} tickFormatter={(v) => v.toFixed(2)} />
                <Tooltip contentStyle={{ background: "#12151B", border: "1px solid #262B36", fontSize: 11, fontFamily: font }}
                  formatter={(v) => [`${((v - 1) * 100).toFixed(2)}%`, "누적수익"]} />
                <Area type="monotone" dataKey="equity" stroke="#3DDC97" strokeWidth={1.6} fill="url(#eqGrad)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </Panel>

          {/* 최근 시그널 */}
          <Panel title="최근 시그널 (종목별)">
            {Object.keys(lastSignals).length === 0 ? (
              <div style={{ color: "#5C6479", fontSize: 12 }}>데이터 없음</div>
            ) : (
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                {Object.entries(lastSignals).map(([key, sig]) => (
                  <div key={key} style={{ minWidth: 130, background: "#0A0C10", border: "1px solid #1B1F27", borderRadius: 8, padding: 10 }}>
                    <div style={{ fontSize: 10.5, color: "#5C6479" }}>{key}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: sig.price ? "#E7E9EE" : "#5C6479" }}>{sig.price?.toFixed(2)}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 10.5 }}>
                      <ActionTag action={sig.action} />
                      <span style={{ color: "#5C6479" }}>{REGIME_LABEL[sig.vol_regime] || sig.vol_regime}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          {/* 거래 기록 */}
          <Panel title={`누적 거래 기록 (${trades.length}건)`}>
            {trades.length === 0 ? (
              <div style={{ color: "#5C6479", fontSize: 12, padding: "16px 0", textAlign: "center" }}>아직 기록된 거래가 없습니다.</div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
                  <thead>
                    <tr style={{ color: "#5C6479", textAlign: "left" }}>
                      <th style={th}>종목</th><th style={th}>진입시각</th><th style={th}>진입가</th>
                      <th style={th}>청산시각</th><th style={th}>청산가</th><th style={th}>손익%</th>
                      <th style={th}>스코어</th><th style={th}>상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...trades].reverse().map((t, i) => (
                      <tr key={i} style={{ borderTop: "1px solid #1B1F27" }}>
                        <td style={td}>{t.broker}:{t.symbol}</td>
                        <td style={td}>{fmtTime(t.entry_time)}</td>
                        <td style={td}>{t.entry_price?.toFixed(2)}</td>
                        <td style={td}>{t.exit_time ? fmtTime(t.exit_time) : "—"}</td>
                        <td style={td}>{t.exit_price ? t.exit_price.toFixed(2) : "—"}</td>
                        <td style={{ ...td, color: t.pnl_pct == null ? "#5C6479" : t.pnl_pct > 0 ? "#3DDC97" : "#FF6B6B", fontWeight: 600 }}>
                          {t.pnl_pct == null ? "—" : `${t.pnl_pct >= 0 ? "+" : ""}${(t.pnl_pct * 100).toFixed(2)}%`}
                        </td>
                        <td style={td}>{t.score}</td>
                        <td style={{ ...td, color: t.status === "open" ? "#F2B94A" : "#8B93A7" }}>{t.status === "open" ? "보유중" : "완료"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function fmtTime(iso) {
  try { return new Date(iso).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}

function ActionTag({ action }) {
  const map = {
    buy: { label: "매수", color: "#3DDC97", Icon: TrendingUp },
    sell: { label: "매도", color: "#FF6B6B", Icon: TrendingDown },
    hold: { label: "관망", color: "#8B93A7", Icon: Minus },
  };
  const m = map[action] || map.hold;
  const Icon = m.Icon;
  return <span style={{ display: "flex", alignItems: "center", gap: 3, color: m.color, fontWeight: 700 }}><Icon size={11} />{m.label}</span>;
}

function Panel({ title, children }) {
  return (
    <div style={{ background: "#12151B", border: "1px solid #1B1F27", borderRadius: 10, padding: "14px 14px 12px", marginBottom: 14 }}>
      <div style={{ fontSize: 11, color: "#5C6479", letterSpacing: "0.06em", marginBottom: 10 }}>{title.toUpperCase()}</div>
      {children}
    </div>
  );
}
function Stat({ label, value, color = "#E7E9EE", big = false }) {
  return (
    <div style={{ background: "#12151B", border: "1px solid #1B1F27", borderRadius: 10, padding: "10px 12px" }}>
      <div style={{ fontSize: 10, color: "#5C6479", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: big ? 20 : 15, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}
function btnStyle(primary) {
  return {
    display: "flex", alignItems: "center", background: primary ? "#3DDC97" : "#12151B",
    color: primary ? "#0A0C10" : "#E7E9EE", border: primary ? "none" : "1px solid #262B36",
    borderRadius: 7, padding: "8px 12px", fontSize: 12, fontWeight: 600, fontFamily: "inherit", cursor: "pointer",
  };
}
const th = { padding: "6px 10px", fontWeight: 500, whiteSpace: "nowrap" };
const td = { padding: "6px 10px", whiteSpace: "nowrap" };
