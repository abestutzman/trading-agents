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

        CREATE TABLE IF NOT EXISTS options_trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT    NOT NULL,
            option_symbol   TEXT    NOT NULL,
            action          TEXT    NOT NULL,   -- buy_to_open / sell_to_open / buy_to_close
            quantity        INTEGER NOT NULL,
            limit_price     REAL,               -- mid of bid/ask at order time
            status          TEXT    DEFAULT 'pending',
            tradier_order_id TEXT,
            created_at      TEXT    DEFAULT (datetime('now')),
            filled_at       TEXT,
            exit_price      REAL,
            pnl             REAL,
            expiration      TEXT,
            strike          REAL,
            option_type     TEXT,               -- "call" | "put"
            structure       TEXT,               -- e.g. "bull_call_spread"
            notes           TEXT
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


# ── Agent Performance Stats ──────────────────────────────────────────────────

def get_agent_stats():
    """
    Return per-agent accuracy stats derived from logged decisions vs. trade outcomes.
    For each agent, counts how many signals match the final trade action (LONG/BULLISH,
    SHORT/BEARISH, HOLD/NEUTRAL) and computes an accuracy rate.
    """
    conn = get_conn()

    # Pull all decisions joined to trades on same ticker within 5 minutes
    rows = conn.execute("""
        SELECT
            d.agent_name,
            d.signal,
            d.confidence,
            t.action,
            t.pnl
        FROM decisions d
        INNER JOIN trades t
          ON d.ticker = t.ticker
         AND ABS(
               (julianday(d.created_at) - julianday(t.created_at)) * 1440
             ) <= 5
        WHERE t.pnl IS NOT NULL
        ORDER BY d.agent_name, d.created_at DESC
    """).fetchall()

    stats = {}
    for row in rows:
        agent      = row["agent_name"]
        signal     = (row["signal"] or "").upper()
        action     = (row["action"] or "").upper()
        confidence = row["confidence"] or 0.0
        pnl        = row["pnl"] or 0.0

        # Normalise: BULLISH → LONG, BEARISH → SHORT, NEUTRAL → HOLD
        sig_norm = "LONG" if signal in ("BULLISH", "LONG") else \
                   "SHORT" if signal in ("BEARISH", "SHORT") else "HOLD"
        act_norm = "LONG" if action == "LONG" else \
                   "SHORT" if action == "SHORT" else "HOLD"

        if agent not in stats:
            stats[agent] = {
                "agent_name":    agent,
                "total_signals": 0,
                "aligned":       0,       # signal matched trade action
                "profitable":    0,       # aligned AND trade was profitable
                "avg_confidence": 0.0,
                "total_pnl":     0.0,
                "confidence_sum": 0.0,
            }

        stats[agent]["total_signals"] += 1
        stats[agent]["confidence_sum"] += confidence
        stats[agent]["total_pnl"]     += pnl

        if sig_norm == act_norm:
            stats[agent]["aligned"] += 1
            if pnl > 0:
                stats[agent]["profitable"] += 1

    conn.close()

    result = []
    for agent, s in stats.items():
        n   = s["total_signals"]
        aln = s["aligned"]
        prft = s["profitable"]
        result.append({
            "agent_name":       agent,
            "total_signals":    n,
            "alignment_rate":   round(aln / n, 3) if n else 0.0,
            "win_rate":         round(prft / aln, 3) if aln else 0.0,
            "avg_confidence":   round(s["confidence_sum"] / n, 3) if n else 0.0,
            "total_pnl":        round(s["total_pnl"], 2),
        })

    # Sort by alignment_rate descending
    result.sort(key=lambda x: x["alignment_rate"], reverse=True)
    return result


def get_daily_stats(days: int = 30):
    """Return daily stats for the last N days."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT date, total_pnl, trades_count, wins, losses
           FROM daily_stats
           ORDER BY date DESC
           LIMIT ?""",
        (days,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Options Trades ───────────────────────────────────────────────────────────

def log_option_trade(ticker, option_symbol, action, quantity, limit_price,
                     status="pending", tradier_order_id=None,
                     expiration=None, strike=None, option_type=None,
                     structure=None, notes=None):
    conn = get_conn()
    conn.execute(
        """INSERT INTO options_trades
           (ticker, option_symbol, action, quantity, limit_price,
            status, tradier_order_id, expiration, strike, option_type, structure, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ticker, option_symbol, action, quantity, limit_price,
         status, tradier_order_id, expiration, strike, option_type, structure, notes),
    )
    conn.commit()
    conn.close()


def update_option_trade_status(trade_id, status, exit_price=None, pnl=None):
    conn = get_conn()
    conn.execute(
        """UPDATE options_trades
           SET status=?, exit_price=?, pnl=?, filled_at=?
           WHERE id=?""",
        (status, exit_price, pnl,
         datetime.utcnow().isoformat(), trade_id),
    )
    conn.commit()
    conn.close()


def get_option_trades(limit=100):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM options_trades ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_open_option_trades():
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM options_trades
           WHERE status IN ('pending','filled')
           ORDER BY created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
