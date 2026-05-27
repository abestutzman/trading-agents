"""
Rule-based backtesting engine.
Zero Claude API calls — purely mathematical signal replay on historical OHLCV data.

Signal rules
────────────
LONG  : Close > SMA50 AND Close > SMA200
        AND 45 ≤ RSI(14) ≤ 70
        AND Volume > Vol_MA20
        AND MACD > 0

SHORT : Close < SMA50 AND Close < SMA200
        AND 30 ≤ RSI(14) ≤ 55
        AND Volume > Vol_MA20
        AND MACD < 0

Execution
─────────
  Entry  : next-day open + 0.1% slippage
  Stop   : entry ± 2 × ATR(14)
  Target : entry ± 3 × ATR(14)
  Size   : 3% of portfolio per trade (floor to whole shares)
  Max    : 10 simultaneous open positions
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, timedelta

from config import POLYGON_API_KEY, SECTOR_TICKER_MAP

POLYGON_BASE = "https://api.polygon.io"


# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCH
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_polygon(ticker: str, start: str, end: str) -> pd.DataFrame:
    if not POLYGON_API_KEY:
        return pd.DataFrame()
    try:
        url = (
            f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}"
            f"/range/1/day/{start}/{end}"
        )
        r = requests.get(
            url,
            params={"adjusted": "true", "sort": "asc",
                    "limit": 5000, "apiKey": POLYGON_API_KEY},
            timeout=15,
        )
        if not r.ok:
            return pd.DataFrame()
        results = r.json().get("results") or []
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame(results)
        df["t"] = (
            pd.to_datetime(df["t"], unit="ms", utc=True)
            .dt.tz_convert("America/New_York")
            .dt.normalize()
            .dt.tz_localize(None)
        )
        df = (
            df.rename(columns={"o": "Open", "h": "High", "l": "Low",
                                "c": "Close", "v": "Volume", "t": "Date"})
            .set_index("Date")[["Open", "High", "Low", "Close", "Volume"]]
        )
        df.index = pd.to_datetime(df.index)
        return df.dropna()
    except Exception:
        return pd.DataFrame()


def _fetch_yfinance(ticker: str, start: str, end: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(start=start, end=end)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.index.name = "Date"
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception:
        return pd.DataFrame()


def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Polygon primary, yfinance fallback."""
    df = _fetch_polygon(ticker, start, end)
    if df.empty:
        df = _fetch_yfinance(ticker, start, end)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# INDICATOR COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add columns: SMA50, SMA200, RSI, MACD, MACD_signal, ATR, Vol_MA20.
    All computed purely from OHLCV — no external data needed.
    """
    df = df.copy()
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]

    # ── Simple moving averages ───────────────────────────────────────────────
    df["SMA50"]  = close.rolling(50,  min_periods=50).mean()
    df["SMA200"] = close.rolling(200, min_periods=200).mean()

    # ── RSI(14) via Wilder smoothing ─────────────────────────────────────────
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(com=13, adjust=False, min_periods=14).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # ── MACD(12, 26, 9) ──────────────────────────────────────────────────────
    ema12          = close.ewm(span=12, adjust=False).mean()
    ema26          = close.ewm(span=26, adjust=False).mean()
    df["MACD"]     = ema12 - ema26
    df["MACD_sig"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # ── ATR(14) ──────────────────────────────────────────────────────────────
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(com=13, adjust=False, min_periods=14).mean()

    # ── Volume 20-day moving average ─────────────────────────────────────────
    df["Vol_MA20"] = vol.rolling(20, min_periods=20).mean()

    return df


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'signal' column.
      +1 = LONG entry signal
      -1 = SHORT entry signal
       0 = no signal / flat
    """
    df   = df.copy()
    c    = df["Close"]
    vol  = df["Volume"]

    long_cond = (
        (c > df["SMA50"])
        & (c > df["SMA200"])
        & (df["RSI"] >= 45) & (df["RSI"] <= 70)
        & (vol > df["Vol_MA20"])
        & (df["MACD"] > 0)
    )
    short_cond = (
        (c < df["SMA50"])
        & (c < df["SMA200"])
        & (df["RSI"] >= 30) & (df["RSI"] <= 55)
        & (vol > df["Vol_MA20"])
        & (df["MACD"] < 0)
    )

    df["signal"] = 0
    df.loc[long_cond,  "signal"] =  1
    df.loc[short_cond, "signal"] = -1
    return df


# ══════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_backtest(
    tickers: list,
    start_date: str,
    end_date: str,
    starting_capital: float = 100_000.0,
    position_size_pct: float = 0.03,
    max_positions: int = 10,
    stop_atr_mult: float = 2.0,
    take_atr_mult: float = 3.0,
    slippage_pct: float = 0.001,
    progress_cb=None,          # optional: progress_cb(ticker, i, total)
) -> dict:
    """
    Multi-ticker rule-based backtest.

    Returns
    -------
    dict with keys:
      error, metrics, trades, equity_curve, drawdown_series,
      monthly_returns, sector_stats, tickers_used, tickers_failed
    """

    # ── 1. Fetch + prepare data ───────────────────────────────────────────────
    # Extra warmup for SMA200: need 200 bars before start_date
    dt_start  = datetime.strptime(start_date, "%Y-%m-%d")
    warmup    = (dt_start - timedelta(days=310)).strftime("%Y-%m-%d")

    ticker_dfs   = {}
    fetch_errors = []

    for i, tk in enumerate(tickers):
        if progress_cb:
            progress_cb(tk, i, len(tickers))
        df = fetch_ohlcv(tk, warmup, end_date)
        if df.empty or len(df) < 60:
            fetch_errors.append(tk)
            continue
        df = compute_indicators(df)
        df = generate_signals(df)
        ticker_dfs[tk] = df

    if not ticker_dfs:
        return {
            "error": (
                f"No data retrieved for any ticker. "
                f"Failed: {', '.join(fetch_errors) or 'all'}"
            ),
            "metrics": {}, "trades": [], "equity_curve": [],
            "drawdown_series": [], "monthly_returns": {}, "sector_stats": {},
            "tickers_used": [], "tickers_failed": fetch_errors,
        }

    # ── 2. Build date index limited to [start_date, end_date] ────────────────
    all_dates = sorted(
        set.union(*[set(df.index) for df in ticker_dfs.values()])
    )
    all_dates = [
        d for d in all_dates
        if start_date <= str(d)[:10] <= end_date
    ]

    if not all_dates:
        return {
            "error": "No trading dates found in the requested date range.",
            "metrics": {}, "trades": [], "equity_curve": [],
            "drawdown_series": [], "monthly_returns": {}, "sector_stats": {},
            "tickers_used": list(ticker_dfs), "tickers_failed": fetch_errors,
        }

    # ── 3. Portfolio state ────────────────────────────────────────────────────
    cash           = float(starting_capital)
    open_positions = {}     # ticker -> position dict
    completed      = []     # list of trade result dicts
    equity_curve   = []     # list of {"date": dt, "value": float}
    daily_rets     = []     # for Sharpe

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _current_close(tk: str, dt) -> float:
        df = ticker_dfs.get(tk)
        if df is None:
            return open_positions[tk]["entry"]
        if dt in df.index:
            return float(df.loc[dt, "Close"])
        # Use last available close
        past = df[df.index <= dt]
        return float(past["Close"].iloc[-1]) if not past.empty else open_positions[tk]["entry"]

    def _portfolio_value(dt) -> float:
        mtm = 0.0
        for tk, pos in open_positions.items():
            cp = _current_close(tk, dt)
            if pos["direction"] == "LONG":
                mtm += pos["shares"] * cp
            else:                               # SHORT
                mtm += pos["shares"] * (2.0 * pos["entry"] - cp)
        return cash + mtm

    def _record_close(tk: str, pos: dict, exit_raw: float, exit_dt, exit_type: str):
        nonlocal cash
        d      = pos["direction"]
        shares = pos["shares"]
        entry  = pos["entry"]
        slp    = exit_raw * slippage_pct

        exit_price = (exit_raw - slp) if d == "LONG" else (exit_raw + slp)

        if d == "LONG":
            pnl = (exit_price - entry) * shares
        else:
            pnl = (entry - exit_price) * shares

        pnl_pct    = pnl / (entry * shares) * 100.0
        risk_amt   = abs(entry - pos["stop"]) * shares
        r_multiple = pnl / risk_amt if risk_amt > 0 else 0.0
        hold_days  = max(1, (exit_dt - pos["entry_date"]).days)

        # Return allocated capital + P&L to cash
        cash += entry * shares + pnl

        completed.append({
            "ticker":       tk,
            "sector":       SECTOR_TICKER_MAP.get(tk, "Other"),
            "direction":    d,
            "entry_date":   pos["entry_date"],
            "exit_date":    exit_dt,
            "entry_price":  round(entry, 2),
            "exit_price":   round(exit_price, 2),
            "shares":       shares,
            "pnl":          round(pnl, 2),
            "pnl_pct":      round(pnl_pct, 2),
            "exit_type":    exit_type,
            "holding_days": hold_days,
            "r_multiple":   round(r_multiple, 2),
            "stop":         round(pos["stop"], 2),
            "target":       round(pos["target"], 2),
        })

    # ── 4. Main simulation loop ───────────────────────────────────────────────
    prev_pv = starting_capital

    for bar_idx, dt in enumerate(all_dates):

        # ── A: Process exits for open positions ──────────────────────────────
        for tk in list(open_positions.keys()):
            df = ticker_dfs.get(tk)
            if df is None or dt not in df.index:
                continue
            bar = df.loc[dt]
            pos = open_positions[tk]
            d   = pos["direction"]

            exited = False
            if d == "LONG":
                if float(bar["Low"]) <= pos["stop"]:
                    # Stop-loss: assume fill at stop (gap-open scenario handled by Low)
                    fill = max(float(bar["Low"]), pos["stop"])
                    _record_close(tk, pos, fill, dt.date() if hasattr(dt, "date") else dt, "SL")
                    exited = True
                elif float(bar["High"]) >= pos["target"]:
                    fill = min(float(bar["High"]), pos["target"])
                    _record_close(tk, pos, fill, dt.date() if hasattr(dt, "date") else dt, "TP")
                    exited = True
            else:  # SHORT
                if float(bar["High"]) >= pos["stop"]:
                    fill = min(float(bar["High"]), pos["stop"])
                    _record_close(tk, pos, fill, dt.date() if hasattr(dt, "date") else dt, "SL")
                    exited = True
                elif float(bar["Low"]) <= pos["target"]:
                    fill = max(float(bar["Low"]), pos["target"])
                    _record_close(tk, pos, fill, dt.date() if hasattr(dt, "date") else dt, "TP")
                    exited = True

            if exited:
                del open_positions[tk]

        # ── B: Enter new positions (signal from previous bar, entry at today's open)
        if bar_idx > 0 and len(open_positions) < max_positions:
            prev_dt = all_dates[bar_idx - 1]
            pv_now  = _portfolio_value(dt)

            for tk, df in ticker_dfs.items():
                if len(open_positions) >= max_positions:
                    break
                if tk in open_positions:
                    continue
                if prev_dt not in df.index or dt not in df.index:
                    continue
                prev_row = df.loc[prev_dt]
                # Require all indicators to be valid (post-warmup)
                if any(pd.isna(prev_row[c]) for c in ["SMA200", "ATR", "RSI", "MACD"]):
                    continue

                sig = int(prev_row["signal"])
                if sig == 0:
                    continue

                entry_raw = float(df.loc[dt, "Open"])
                atr       = float(prev_row["ATR"])
                if atr <= 0 or entry_raw <= 0:
                    continue

                if sig == 1:   # LONG
                    entry_px = entry_raw * (1.0 + slippage_pct)
                    stop_px  = entry_px - stop_atr_mult * atr
                    tgt_px   = entry_px + take_atr_mult * atr
                    direction = "LONG"
                else:          # SHORT
                    entry_px = entry_raw * (1.0 - slippage_pct)
                    stop_px  = entry_px + stop_atr_mult * atr
                    tgt_px   = entry_px - take_atr_mult * atr
                    direction = "SHORT"

                alloc  = pv_now * position_size_pct
                shares = max(1, int(alloc / entry_px))
                cost   = shares * entry_px

                if cost > cash * 0.99:     # insufficient cash
                    continue

                cash -= cost               # reserve capital

                entry_date = dt.date() if hasattr(dt, "date") else dt
                open_positions[tk] = {
                    "direction":  direction,
                    "entry_date": entry_date,
                    "entry":      entry_px,
                    "shares":     shares,
                    "stop":       stop_px,
                    "target":     tgt_px,
                    "atr":        atr,
                }

        # ── C: Record daily portfolio value ──────────────────────────────────
        pv = _portfolio_value(dt)
        equity_curve.append({"date": dt, "value": round(pv, 2)})
        if prev_pv > 0:
            daily_rets.append((pv - prev_pv) / prev_pv)
        prev_pv = pv

    # ── D: Close residual open positions at final bar's close ─────────────────
    last_dt = all_dates[-1]
    last_date = last_dt.date() if hasattr(last_dt, "date") else last_dt
    for tk in list(open_positions.keys()):
        pos = open_positions[tk]
        df  = ticker_dfs.get(tk)
        if df is not None and last_dt in df.index:
            close_px = float(df.loc[last_dt, "Close"])
        elif df is not None and not df.empty:
            close_px = float(df["Close"].iloc[-1])
        else:
            close_px = pos["entry"]
        _record_close(tk, pos, close_px, last_date, "EOD")

    # ══════════════════════════════════════════════════════════════════════════
    # 5. Performance metrics
    # ══════════════════════════════════════════════════════════════════════════

    eq_df = pd.DataFrame(equity_curve).set_index("date")
    eq_df.index = pd.to_datetime(eq_df.index)

    final_val  = float(eq_df["value"].iloc[-1]) if not eq_df.empty else starting_capital
    n_days     = len(all_dates)
    total_ret  = (final_val - starting_capital) / starting_capital
    ann_ret    = (1.0 + total_ret) ** (252.0 / max(n_days, 1)) - 1.0

    dr = pd.Series(daily_rets, dtype=float)
    if len(dr) > 1 and dr.std() > 0:
        rfr_daily = 0.05 / 252.0
        sharpe    = (dr.mean() - rfr_daily) / dr.std() * np.sqrt(252)
    else:
        sharpe = 0.0

    # Max drawdown
    roll_max = eq_df["value"].expanding().max()
    dd_series = (eq_df["value"] - roll_max) / roll_max.replace(0, np.nan)
    max_dd    = float(dd_series.min()) if not dd_series.empty else 0.0

    # Trade-level stats
    n_trades  = len(completed)
    wins      = [t for t in completed if t["pnl"] > 0]
    losses    = [t for t in completed if t["pnl"] <= 0]
    win_rate  = len(wins) / n_trades if n_trades else 0.0
    avg_hold  = float(np.mean([t["holding_days"] for t in completed])) if completed else 0.0
    avg_rr    = float(np.mean([t["r_multiple"]   for t in completed])) if completed else 0.0

    gross_win  = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    pft_factor = (gross_win / gross_loss) if gross_loss > 0 else (
        999.0 if gross_win > 0 else 0.0
    )

    by_pnl_pct  = sorted(completed, key=lambda t: t["pnl_pct"])
    worst_trade = by_pnl_pct[0]  if completed else {}
    best_trade  = by_pnl_pct[-1] if completed else {}

    # Monthly equity-curve returns
    monthly     = eq_df["value"].resample("ME").last()
    monthly_ret = monthly.pct_change().dropna()
    monthly_map: dict = {}
    for mdt, ret in monthly_ret.items():
        monthly_map[(int(mdt.year), int(mdt.month))] = round(float(ret) * 100, 2)

    best_month  = max(monthly_map.items(), key=lambda x: x[1])  if monthly_map else None
    worst_month = min(monthly_map.items(), key=lambda x: x[1])  if monthly_map else None

    # Sector stats
    sector_stats: dict = {}
    for t in completed:
        sec = t["sector"]
        s   = sector_stats.setdefault(sec, {"count": 0, "wins": 0, "pnl": 0.0})
        s["count"] += 1
        s["pnl"]   += t["pnl"]
        if t["pnl"] > 0:
            s["wins"] += 1
    for sec, s in sector_stats.items():
        s["win_rate"] = round(s["wins"] / s["count"] * 100, 1) if s["count"] else 0.0
        s["pnl"]      = round(s["pnl"], 2)

    return {
        "error":          None,
        "tickers_used":   list(ticker_dfs.keys()),
        "tickers_failed": fetch_errors,
        "n_trading_days": n_days,
        "start_date":     start_date,
        "end_date":       end_date,
        "metrics": {
            "starting_capital":  starting_capital,
            "final_value":       round(final_val, 2),
            "total_return_pct":  round(total_ret * 100, 2),
            "ann_return_pct":    round(ann_ret * 100, 2),
            "sharpe":            round(sharpe, 2),
            "max_drawdown_pct":  round(max_dd * 100, 2),
            "profit_factor":     round(min(pft_factor, 999.0), 2),
            "total_trades":      n_trades,
            "win_rate_pct":      round(win_rate * 100, 1),
            "avg_hold_days":     round(avg_hold, 1),
            "avg_r_multiple":    round(avg_rr, 2),
            "gross_profit":      round(gross_win,  2),
            "gross_loss":        round(gross_loss, 2),
            "best_trade":        best_trade,
            "worst_trade":       worst_trade,
            "best_month":        best_month,
            "worst_month":       worst_month,
        },
        "trades":          completed,
        "equity_curve":    equity_curve,
        "drawdown_series": [
            {"date": str(d)[:10], "dd": round(float(v) * 100, 2)}
            for d, v in dd_series.items()
        ],
        "monthly_returns": {f"{y}-{m:02d}": v for (y, m), v in monthly_map.items()},
        "_monthly_map":    monthly_map,   # (year, month) keyed dict for heatmap
        "sector_stats":    sector_stats,
    }
