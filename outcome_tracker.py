"""
시그널 발생 시점과 결과를 sqlite에 기록해 나중에 적중률(hit rate)을 계산한다.
SIGNAL DESK의 'AI 적중률' 패널과 동일한 목적. N일 후 실제 가격 변화로 채점.
"""
import sqlite3
import os
from datetime import datetime, timezone

_DB_PATH = os.path.join(os.path.dirname(__file__), "signal_outcomes.db")


def _conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            broker TEXT NOT NULL,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            score REAL NOT NULL,
            price_at_signal REAL NOT NULL,
            vol_regime TEXT,
            trend_regime TEXT,
            evaluated INTEGER DEFAULT 0,
            price_after REAL,
            correct INTEGER,
            eval_timestamp TEXT
        )
    """)
    return conn


def record_signal(broker: str, symbol: str, action: str, score: float,
                   price_at_signal: float, vol_regime: str = "", trend_regime: str = ""):
    conn = _conn()
    conn.execute(
        "INSERT INTO signals (timestamp, broker, symbol, action, score, price_at_signal, vol_regime, trend_regime) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), broker, symbol, action, score,
         price_at_signal, vol_regime, trend_regime),
    )
    conn.commit()
    conn.close()


def evaluate_pending(get_price_fn, horizon_hours: int = 24):
    """
    아직 평가 안 된 시그널 중 horizon_hours가 지난 것들을 채점.
    get_price_fn(broker, symbol) -> 현재가를 반환하는 콜백 (브로커별 어댑터 연결 필요)
    buy 시그널: 가격 상승 시 correct=1
    sell 시그널: 가격 하락 시 correct=1
    """
    conn = _conn()
    cur = conn.execute("SELECT id, timestamp, broker, symbol, action, price_at_signal FROM signals WHERE evaluated = 0")
    rows = cur.fetchall()
    now = datetime.now(timezone.utc)
    updated = 0
    for row_id, ts, broker, symbol, action, price_at_signal in rows:
        signal_time = datetime.fromisoformat(ts)
        elapsed_hours = (now - signal_time).total_seconds() / 3600
        if elapsed_hours < horizon_hours:
            continue
        try:
            price_after = get_price_fn(broker, symbol)
        except Exception:
            continue
        if action == "buy":
            correct = 1 if price_after > price_at_signal else 0
        elif action == "sell":
            correct = 1 if price_after < price_at_signal else 0
        else:
            correct = None
        conn.execute(
            "UPDATE signals SET evaluated=1, price_after=?, correct=?, eval_timestamp=? WHERE id=?",
            (price_after, correct, now.isoformat(), row_id),
        )
        updated += 1
    conn.commit()
    conn.close()
    return updated


def get_hit_rate(broker: str = None, days: int = 30) -> dict:
    conn = _conn()
    query = "SELECT correct FROM signals WHERE evaluated=1 AND correct IS NOT NULL AND timestamp >= datetime('now', ?)"
    params = [f"-{days} days"]
    if broker:
        query += " AND broker = ?"
        params.append(broker)
    cur = conn.execute(query, params)
    results = [r[0] for r in cur.fetchall()]
    conn.close()
    if not results:
        return {"total": 0, "correct": 0, "hit_rate": None}
    correct = sum(results)
    return {"total": len(results), "correct": correct, "hit_rate": correct / len(results)}
