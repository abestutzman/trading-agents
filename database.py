import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "trading_journal.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker        TEXT    NOT NULL,
            action        TEXT    NOT NULL,
            quantity      REAL    NOT NULL,
            entry_price   REAL,
            stop_loss     REAL,
            take_profit   REAL,
            status        TEXT    DEFAULT 'pending',
            alpaca_order_id TEXT,
            created_at    TEXT    DEFAULT (datetime('now')),
            filled_at     TEXT,
            exit_price    REAL,
            pnl           REAL,
            notes         TEXT
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker      TEXT    NOT NULL,
            agent_name  TEXT    NOT NULL,
            signal      TEXT,
            confidence  REAL,
            reasoning   TEXT,
            raw_output  TEXT,
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker    TEXT    UNIQUE NOT NULL,
            added_at  TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT    UNIQUE NOT NULL,
            total_pnl    REAL    DEFAULT 0,
            trades_count INTEGER DEFAULT 0,
            wins         INTEGER DEFAULT 0,
            losses       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS cooldowns (
            ticker      TEXT    PRIMARY KEY,
            last_trade  TEXT    NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ── Trades ───────────────────────────────────────────────────────────────────

def log_trade(ticker, action, quantity, entry_price, stop_loss, take_profit,
              status="pending", alpaca_order_id=None, notes=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO trades
           (ticker, action, quantity, entry_price, stop_loss, take_profit,
            status, alpaca_order_id, notes)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (ticker, action, quantity, entry_price, stop_loss, take_profit,
         status, alpaca_order_id, notes),
    )
    conn.commit()
    conn.close()


def update_trade_status(trade_id, status, exit_price=None, pnl=None, filled_at=None):
    conn = get_conn()
    conn.execute(
        """UPDATE trades SET status=?, exit_price=?, pnl=?, filled_at=?
           WHERE id=?""",
        (status, exit_price, pnl, filled_at or datetime.utcnow().isoformat(), trade_id),
    )
    conn.commit()
    conn.close()


def get_trades(limit=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_open_trades():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM trades WHERE status IN ('pending','filled') ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Decisions ────────────────────────────────────────────────────────────────

def log_decision(ticker, agent_name, signal, confidence, reasoning, raw_output=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO decisions
           (ticker, agent_name, signal, confidence, reasoning, raw_output)
           VALUES (?,?,?,?,?,?)""",
        (ticker, agent_name, signal, confidence, reasoning,
         json.dumps(raw_output) if raw_output else None),
    )
    conn.commit()
    conn.close()


def get_decisions(ticker=None, limit=200):
    conn = get_conn()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE ticker=? ORDER BY created_at DESC LIMIT ?",
            (ticker, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Watchlist ────────────────────────────────────────────────────────────────

def add_to_watchlist(ticker):
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO watchlist (ticker) VALUES (?)", (ticker,))
        conn.commit()
    finally:
        conn.close()


def remove_from_watchlist(ticker):
    conn = get_conn()
    conn.execute("DELETE FROM watchlist WHERE ticker=?", (ticker,))
    conn.commit()
    conn.close()


def get_watchlist():
    conn = get_conn()
    rows = conn.execute("SELECT ticker FROM watchlist ORDER BY added_at").fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


# ── Cooldowns ────────────────────────────────────────────────────────────────

def set_cooldown(ticker):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO cooldowns (ticker, last_trade) VALUES (?,?)",
        (ticker, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_cooldown_minutes(ticker):
    conn = get_conn()
    row = conn.execute(
        "SELECT last_trade FROM cooldowns WHERE ticker=?", (ticker,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    last = datetime.fromisoformat(row["last_trade"])
    delta = (datetime.utcnow() - last).total_seconds() / 60
    return delta


# ── Daily Stats ──────────────────────────────────────────────────────────────

def upsert_daily_stats(pnl_delta, won: bool):
    today = datetime.utcnow().date().isoformat()
    conn = get_conn()
    conn.execute(
        """INSERT INTO daily_stats (date, total_pnl, trades_count, wins, losses)
           VALUES (?,?,1,?,?)
           ON CONFLICT(date) DO UPDATE SET
               total_pnl    = total_pnl + excluded.total_pnl,
               trades_count = trades_count + 1,
               wins         = wins   + excluded.wins,
               losses       = losses + excluded.losses""",
        (today, pnl_delta, 1 if won else 0, 0 if won else 1),
    )
    conn.commit()
    conn.close()


def get_daily_pnl():
    today = datetime.utcnow().date().isoformat()
    conn = get_conn()
    row = conn.execute(
        "SELECT total_pnl FROM daily_stats WHERE date=?", (today,)
    ).fetchone()
    conn.close()
    return row["total_pnl"] if row else 0.0
