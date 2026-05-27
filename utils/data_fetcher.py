"""
DataFetcher — unified market data layer.

Source priority:
  Price / OHLCV / TA : Polygon.io  →  yfinance
  Fundamentals        : Alpha Vantage  →  yfinance  →  Finnhub
  News / Insiders     : Finnhub  →  NewsAPI
  Macro               : FRED  →  yfinance proxies
  Earnings / Calendar : Finnhub
"""
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
import finnhub
import requests
from datetime import datetime, timedelta
from config import (
    FINNHUB_API_KEY, NEWS_API_KEY, POLYGON_API_KEY,
    FRED_API_KEY, ALPHA_VANTAGE_KEY,
)

POLYGON_BASE = "https://api.polygon.io"
FRED_BASE    = "https://api.stlouisfed.org/fred"
AV_BASE      = "https://www.alphavantage.co/query"


class DataFetcher:
    def __init__(self):
        self._finnhub  = finnhub.Client(api_key=FINNHUB_API_KEY) if FINNHUB_API_KEY else None
        self._poly_key = POLYGON_API_KEY
        self._fred_key = FRED_API_KEY
        self._av_key   = ALPHA_VANTAGE_KEY
        # Lightweight in-session cache for repeated market-wide fetches
        self._cache: dict = {}

    # ──────────────────────────────────────────────────────────────────────────
    # POLYGON helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _poly(self, endpoint: str, params: dict = None) -> dict | None:
        if not self._poly_key:
            return None
        p = dict(params or {})
        p["apiKey"] = self._poly_key
        try:
            r = requests.get(f"{POLYGON_BASE}{endpoint}", params=p, timeout=10)
            if r.ok:
                return r.json()
        except Exception:
            pass
        return None

    def _poly_indicator(self, ticker: str, indicator: str, **kwargs) -> dict | None:
        params = {
            "order": "desc", "limit": 1, "timespan": "day",
            "adjusted": "true", "series_type": "close", **kwargs,
        }
        data = self._poly(f"/v1/indicators/{indicator}/{ticker}", params)
        if data:
            values = (data.get("results") or {}).get("values") or []
            return values[0] if values else None
        return None

    def _get_polygon_technicals(self, ticker: str, current_price: float) -> dict:
        result = {}
        if not self._poly_key:
            return result

        v = self._poly_indicator(ticker, "rsi", window=14)
        if v:
            result["rsi"] = round(float(v["value"]), 2)

        v = self._poly_indicator(ticker, "macd",
                                  short_window=12, long_window=26, signal_window=9)
        if v:
            result["macd"]        = round(float(v.get("value", 0)), 4)
            result["macd_signal"] = round(float(v.get("signal", 0)), 4)
            result["macd_hist"]   = round(float(v.get("histogram", 0)), 4)

        v = self._poly_indicator(ticker, "sma", window=50)
        if v:
            sma50 = float(v["value"])
            result["sma_50"] = round(sma50, 2)
            if current_price:
                result["pct_vs_sma50"] = round((current_price / sma50 - 1) * 100, 2)

        v = self._poly_indicator(ticker, "sma", window=200)
        if v:
            sma200 = float(v["value"])
            result["sma_200"] = round(sma200, 2)
            if current_price:
                result["pct_vs_sma200"] = round((current_price / sma200 - 1) * 100, 2)

        if result.get("sma_50") and result.get("sma_200"):
            result["cross_signal"] = (
                "golden_cross" if result["sma_50"] > result["sma_200"] else "death_cross"
            )

        v = self._poly_indicator(ticker, "bbands", window=20)
        if v:
            result["bb_upper"] = round(float(v.get("upper_band", 0)), 2)
            result["bb_mid"]   = round(float(v.get("middle_band", 0)), 2)
            result["bb_lower"] = round(float(v.get("lower_band", 0)), 2)
            rng = result["bb_upper"] - result["bb_lower"]
            if rng and current_price:
                result["bb_pct"] = round((current_price - result["bb_lower"]) / rng, 3)

        prev = self._poly(f"/v2/aggs/ticker/{ticker}/prev", {"adjusted": "true"})
        if prev and prev.get("results"):
            day = prev["results"][0]
            result["vwap"]        = round(float(day.get("vw", 0)), 2)
            result["prev_volume"] = int(day.get("v", 0))

        if result:
            result["data_source"] = "Polygon.io"
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # FRED helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _fred_obs(self, series_id: str, limit: int = 14) -> list:
        """Return list of (date, value) tuples from FRED, most recent first."""
        if not self._fred_key:
            return []
        try:
            resp = requests.get(
                f"{FRED_BASE}/series/observations",
                params={
                    "series_id":  series_id,
                    "api_key":    self._fred_key,
                    "file_type":  "json",
                    "sort_order": "desc",
                    "limit":      limit,
                },
                timeout=10,
            )
            if resp.ok:
                return [
                    (o["date"], o["value"])
                    for o in resp.json().get("observations", [])
                    if o.get("value") != "."
                ]
        except Exception:
            pass
        return []

    def get_fred_macro(self) -> dict:
        """Pull real macro data from FRED API (free, requires FRED_API_KEY)."""
        result = {}
        if not self._fred_key:
            return result

        # Fed Funds Effective Rate
        obs = self._fred_obs("FEDFUNDS", 1)
        if obs:
            result["fed_funds_rate"] = round(float(obs[0][1]), 2)

        # 10-Year Treasury Yield (daily, more current than TLT proxy)
        obs = self._fred_obs("DGS10", 1)
        if obs:
            result["ten_year_yield_fred"] = round(float(obs[0][1]), 2)

        # Unemployment Rate
        obs = self._fred_obs("UNRATE", 1)
        if obs:
            result["unemployment"] = round(float(obs[0][1]), 2)

        # CPI YoY (CPIAUCSL — need 13 months for YoY)
        obs = self._fred_obs("CPIAUCSL", 14)
        valid = [(d, v) for d, v in obs if v not in (".", "")]
        if len(valid) >= 13:
            try:
                latest   = float(valid[0][1])
                year_ago = float(valid[12][1])
                result["cpi_yoy"]   = round((latest / year_ago - 1) * 100, 2)
                result["cpi_level"] = round(latest, 1)
            except (ValueError, ZeroDivisionError):
                pass

        # PCE YoY (Fed's preferred inflation gauge)
        obs = self._fred_obs("PCEPI", 14)
        valid = [(d, v) for d, v in obs if v not in (".", "")]
        if len(valid) >= 13:
            try:
                result["pce_yoy"] = round(
                    (float(valid[0][1]) / float(valid[12][1]) - 1) * 100, 2
                )
            except (ValueError, ZeroDivisionError):
                pass

        # Real GDP growth rate (quarterly)
        obs = self._fred_obs("A191RL1Q225SBEA", 1)
        if obs:
            try:
                result["gdp_growth"] = round(float(obs[0][1]), 2)
            except ValueError:
                pass

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # ALPHA VANTAGE fundamentals
    # ──────────────────────────────────────────────────────────────────────────

    def _av_request(self, function: str, ticker: str) -> dict:
        if not self._av_key:
            return {}
        try:
            resp = requests.get(
                AV_BASE,
                params={"function": function, "symbol": ticker, "apikey": self._av_key},
                timeout=20,
            )
            if resp.ok:
                data = resp.json()
                # Guard against AV rate-limit messages
                if "Note" in data or "Information" in data:
                    return {}
                return data
        except Exception:
            pass
        return {}

    def get_av_fundamentals(self, ticker: str) -> dict:
        """Pull income statement + balance sheet + cash flow from Alpha Vantage."""
        result = {}
        if not self._av_key:
            return result

        def _num(d: dict, key: str):
            v = (d or {}).get(key)
            if v in (None, "None", "", "N/A"):
                return None
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        inc_raw  = self._av_request("INCOME_STATEMENT", ticker)
        bal_raw  = self._av_request("BALANCE_SHEET",    ticker)
        cf_raw   = self._av_request("CASH_FLOW",        ticker)

        # Prefer quarterly (most recent) then annual
        inc = (inc_raw.get("quarterlyReports")  or inc_raw.get("annualReports")  or [{}])[0]
        bal = (bal_raw.get("quarterlyReports")   or bal_raw.get("annualReports")  or [{}])[0]
        cf  = (cf_raw.get("quarterlyReports")    or cf_raw.get("annualReports")   or [{}])[0]

        if inc:
            result["av_revenue"]         = _num(inc, "totalRevenue")
            result["av_net_income"]      = _num(inc, "netIncome")
            result["av_gross_profit"]    = _num(inc, "grossProfit")
            result["av_operating_inc"]   = _num(inc, "operatingIncome")
            result["av_ebitda"]          = _num(inc, "ebitda")
            result["av_period"]          = inc.get("fiscalDateEnding", "N/A")

        if bal:
            result["av_total_assets"]    = _num(bal, "totalAssets")
            result["av_total_debt"]      = (
                _num(bal, "longTermDebtNoncurrent") or _num(bal, "longTermDebt")
            )
            result["av_cash"]            = _num(bal, "cashAndCashEquivalentsAtCarryingValue")
            result["av_total_equity"]    = _num(bal, "totalShareholderEquity")

        if cf:
            result["av_operating_cf"]    = _num(cf, "operatingCashflow")
            result["av_capex"]           = _num(cf, "capitalExpenditures")
            ocf   = result.get("av_operating_cf")
            capex = result.get("av_capex")
            if ocf is not None and capex is not None:
                result["av_free_cashflow"] = round(ocf + capex, 0)

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # EARNINGS CALENDAR  (Finnhub)
    # ──────────────────────────────────────────────────────────────────────────

    def get_earnings_calendar(self, ticker: str) -> dict:
        """Return upcoming earnings info for ticker (next 60 days)."""
        result = {"has_upcoming": False, "within_14_days": False, "within_7_days": False}
        if not self._finnhub:
            return result
        try:
            today = datetime.now()
            end   = (today + timedelta(days=60)).strftime("%Y-%m-%d")
            data  = self._finnhub.earnings_calendar(
                _from=today.strftime("%Y-%m-%d"), to=end, symbol=ticker
            )
            cal = (data or {}).get("earningsCalendar") or []
            if cal:
                nxt      = cal[0]
                date_str = nxt.get("date", "")
                if date_str:
                    ev_date = datetime.strptime(date_str, "%Y-%m-%d")
                    days    = (ev_date - today).days
                    result  = {
                        "has_upcoming":   True,
                        "date":           date_str,
                        "days_until":     days,
                        "eps_estimate":   nxt.get("epsEstimate"),
                        "revenue_estimate": nxt.get("revenueEstimate"),
                        "within_14_days": days <= 14,
                        "within_7_days":  days <= 7,
                        "hour":           nxt.get("hour", "N/A"),  # bmo / amc / dmh
                    }
        except Exception:
            pass
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # RELATIVE STRENGTH  (yfinance vs SPY + sector ETF)
    # ──────────────────────────────────────────────────────────────────────────

    def get_relative_strength(self, ticker: str) -> dict:
        """Compute 1m/3m/6m return vs SPY and sector ETF. Uses in-session cache."""
        from config import SECTOR_TICKER_MAP, SECTOR_ETFS
        result = {}
        try:
            sector     = SECTOR_TICKER_MAP.get(ticker.upper())
            sector_etf = SECTOR_ETFS.get(sector) if sector else None

            # Cached SPY history (shared across all tickers in a screener run)
            if "spy_6mo" not in self._cache:
                self._cache["spy_6mo"] = yf.Ticker("SPY").history(period="6mo")
            spy_df = self._cache["spy_6mo"]

            # Cached sector ETF history
            if sector_etf:
                cache_key = f"etf_{sector_etf}_6mo"
                if cache_key not in self._cache:
                    self._cache[cache_key] = yf.Ticker(sector_etf).history(period="6mo")
                sec_df = self._cache[cache_key]
            else:
                sec_df = pd.DataFrame()

            t_df = yf.Ticker(ticker).history(period="6mo")
            if t_df.empty or spy_df.empty:
                return result

            def _ret(df, days):
                if len(df) < days:
                    return None
                return round((df["Close"].iloc[-1] / df["Close"].iloc[-days] - 1) * 100, 2)

            for label, days in [("1m", 21), ("3m", 63), ("6m", 126)]:
                t_r  = _ret(t_df,  days)
                sp_r = _ret(spy_df, days)
                if t_r is not None:
                    result[f"ret_{label}"] = t_r
                if t_r is not None and sp_r is not None:
                    result[f"rs_{label}_vs_spy"] = round(t_r - sp_r, 2)

            if not sec_df.empty:
                for label, days in [("1m", 21), ("3m", 63), ("6m", 126)]:
                    t_r = _ret(t_df,  days)
                    e_r = _ret(sec_df, days)
                    if t_r is not None and e_r is not None:
                        result[f"rs_{label}_vs_sector"] = round(t_r - e_r, 2)

            result["sector"]     = sector or "Unknown"
            result["sector_etf"] = sector_etf or "N/A"

            rs1  = result.get("rs_1m_vs_spy")
            rs3  = result.get("rs_3m_vs_spy")
            rss1 = result.get("rs_1m_vs_sector")
            result["underperforming_spy"]    = (rs1 is not None and rs3 is not None and
                                                (rs1 < -5 or rs3 < -10))
            result["underperforming_sector"] = rss1 is not None and rss1 < -3

        except Exception:
            pass
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # INSIDER TRANSACTIONS  (Finnhub — SEC Form 4)
    # ──────────────────────────────────────────────────────────────────────────

    def get_insider_transactions(self, ticker: str) -> dict:
        """Recent SEC Form 4 insider buying/selling (last 90 days)."""
        result = {"recent_buying": False, "recent_selling": False,
                  "net_sentiment": "neutral", "recent_txns": []}
        if not self._finnhub:
            return result
        try:
            data   = self._finnhub.stock_insider_transactions(ticker)
            txns   = (data or {}).get("data") or []
            cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            recent = [t for t in txns if (t.get("transactionDate") or "") >= cutoff]

            buys    = [t for t in recent if (t.get("change") or 0) > 0]
            sells   = [t for t in recent if (t.get("change") or 0) < 0]
            buy_sh  = sum(abs(t.get("change", 0)) for t in buys)
            sell_sh = sum(abs(t.get("change", 0)) for t in sells)

            result = {
                "recent_buying":     len(buys) > 0,
                "recent_selling":    len(sells) > 0,
                "buy_transactions":  len(buys),
                "sell_transactions": len(sells),
                "buy_shares":        int(buy_sh),
                "sell_shares":       int(sell_sh),
                "net_sentiment": (
                    "strongly_bullish" if buy_sh > sell_sh * 2  else
                    "bullish"          if buy_sh > sell_sh       else
                    "strongly_bearish" if sell_sh > buy_sh * 2  else
                    "bearish"          if sell_sh > buy_sh       else
                    "neutral"
                ),
                "recent_txns": [
                    {
                        "date":   t.get("transactionDate"),
                        "name":   t.get("name"),
                        "shares": t.get("change"),
                        "type":   "BUY" if (t.get("change") or 0) > 0 else "SELL",
                    }
                    for t in recent[:5]
                ],
            }
        except Exception:
            pass
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # ECONOMIC CALENDAR  (hardcoded FOMC + heuristic CPI/NFP dates)
    # ──────────────────────────────────────────────────────────────────────────

    def get_economic_calendar(self) -> dict:
        """
        Return upcoming major macro events in the next 30 days.
        FOMC dates are exact (from Fed schedule).
        CPI/NFP dates are estimated heuristics (2nd Wednesday / 1st Friday).
        """
        today = datetime.now().date()

        fomc_dates = [
            # 2025
            "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
            "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
            # 2026
            "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
            "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
        ]

        events = []

        for d_str in fomc_dates:
            try:
                ev   = datetime.strptime(d_str, "%Y-%m-%d").date()
                days = (ev - today).days
                if -2 <= days <= 30:
                    events.append(
                        {"event": "FOMC Decision", "date": d_str, "days_until": days}
                    )
            except Exception:
                pass

        # Approximate NFP (1st Friday) and CPI (2nd Wednesday) for next 3 months
        for mo in range(3):
            ms = (today.replace(day=1) + timedelta(days=32 * mo)).replace(day=1)

            # 1st Friday
            day = ms
            while day.weekday() != 4:
                day += timedelta(days=1)
            du = (day - today).days
            if -2 <= du <= 30:
                events.append(
                    {"event": "Jobs Report (NFP est.)", "date": day.isoformat(), "days_until": du}
                )

            # 2nd Wednesday
            count, day = 0, ms
            while count < 2:
                if day.weekday() == 2:
                    count += 1
                if count < 2:
                    day += timedelta(days=1)
            du = (day - today).days
            if -2 <= du <= 30:
                events.append(
                    {"event": "CPI Release (est.)", "date": day.isoformat(), "days_until": du}
                )

        events.sort(key=lambda x: x["days_until"])
        upcoming = [e for e in events if e["days_until"] >= 0]
        within_5 = [e for e in upcoming if e["days_until"] <= 5]

        return {
            "events":        events[:6],
            "within_5_days": bool(within_5),
            "nearest_event": upcoming[0] if upcoming else None,
            "macro_risk":    "HIGH" if within_5 else "NORMAL",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PRICE HISTORY  (Polygon primary, yfinance fallback)
    # ──────────────────────────────────────────────────────────────────────────

    def get_price_history(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        if self._poly_key:
            try:
                days  = {"5d": 8, "1mo": 35, "6mo": 185, "1y": 370, "2y": 740}.get(period, 370)
                end   = datetime.now()
                start = end - timedelta(days=days)
                resp  = self._poly(
                    f"/v2/aggs/ticker/{ticker}/range/1/day/"
                    f"{start.strftime('%Y-%m-%d')}/{end.strftime('%Y-%m-%d')}",
                    {"adjusted": "true", "sort": "asc", "limit": 500},
                )
                if resp and resp.get("results"):
                    bars = resp["results"]
                    df   = pd.DataFrame(bars)
                    df["t"] = (
                        pd.to_datetime(df["t"], unit="ms", utc=True)
                        .dt.tz_convert("America/New_York")
                        .dt.tz_localize(None)
                    )
                    df = df.rename(columns={
                        "o": "Open", "h": "High", "l": "Low",
                        "c": "Close", "v": "Volume", "t": "Date",
                    }).set_index("Date")[["Open", "High", "Low", "Close", "Volume"]]
                    return df
            except Exception:
                pass

        try:
            df = yf.Ticker(ticker).history(period=period)
            df.index = pd.to_datetime(df.index)
            return df
        except Exception:
            return pd.DataFrame()

    def get_current_price(self, ticker: str) -> float:
        # Polygon snapshot
        if self._poly_key:
            try:
                resp = self._poly(
                    f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
                )
                if resp and resp.get("ticker"):
                    snap = resp["ticker"]
                    price = (snap.get("day") or {}).get("c") or \
                            (snap.get("prevDay") or {}).get("c")
                    if price:
                        return round(float(price), 2)
            except Exception:
                pass

        try:
            df = yf.Ticker(ticker).history(period="5d")
            if not df.empty:
                return round(float(df["Close"].iloc[-1]), 2)
        except Exception:
            pass
        return 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # TECHNICALS  (Polygon primary + yfinance enrichment + new indicators)
    # ──────────────────────────────────────────────────────────────────────────

    def get_technicals(self, ticker: str) -> dict:
        price  = self.get_current_price(ticker)
        result = self._get_polygon_technicals(ticker, price)

        df = self.get_price_history(ticker, period="1y")
        if not df.empty and len(df) >= 5:
            close  = df["Close"]
            volume = df["Volume"]

            # ── Returns ──────────────────────────────────────────────────────
            if len(close) > 1:
                result["ret_1d"]  = round((close.iloc[-1] / close.iloc[-2]  - 1) * 100, 2)
            if len(close) > 5:
                result["ret_5d"]  = round((close.iloc[-1] / close.iloc[-6]  - 1) * 100, 2)
            if len(close) > 20:
                result["ret_20d"] = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2)

            # ── Volume confirmation ───────────────────────────────────────────
            if len(volume) > 20:
                avg_vol = float(volume.iloc[-21:-1].mean())
                cur_vol = float(volume.iloc[-1])
                result["avg_volume"]      = int(avg_vol)
                result["current_volume"]  = int(cur_vol)
                result["volume_ratio"]    = round(cur_vol / avg_vol, 2) if avg_vol else 1.0
                result["volume_above_avg"] = result["volume_ratio"] >= 1.0
                result["volume_signal"]   = (
                    "high_volume"   if result["volume_ratio"] >= 1.5 else
                    "above_average" if result["volume_ratio"] >= 1.0 else
                    "below_average" if result["volume_ratio"] >= 0.5 else
                    "low_volume"
                )

            # ── Support / Resistance (20-day) ─────────────────────────────────
            if len(close) > 20:
                result["support"]    = round(float(close.iloc[-20:].min()), 2)
                result["resistance"] = round(float(close.iloc[-20:].max()), 2)

            # ── ATR (14) + ATR-based stop levels ─────────────────────────────
            if len(df) >= 15:
                tr = pd.concat([
                    df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"]  - df["Close"].shift()).abs(),
                ], axis=1).max(axis=1)
                atr = float(tr.rolling(14).mean().iloc[-1])
                result["atr"] = round(atr, 2)
                if price and atr:
                    result["atr_stop_long"]  = round(price - 2 * atr, 2)
                    result["atr_stop_short"] = round(price + 2 * atr, 2)
                    result["atr_risk_pct"]   = round(2 * atr / price * 100, 2) if price else None

            # ── 52-week range positioning ─────────────────────────────────────
            lookback = min(252, len(close))
            if lookback >= 50:
                hi52 = float(close.iloc[-lookback:].max())
                lo52 = float(close.iloc[-lookback:].min())
                rng52 = hi52 - lo52
                result["52w_high"]         = round(hi52, 2)
                result["52w_low"]          = round(lo52, 2)
                if rng52 > 0 and price:
                    result["range_52w_pct"]      = round((price - lo52) / rng52 * 100, 1)
                    result["dist_52w_high_pct"]  = round((price / hi52 - 1) * 100, 2)
                    result["dist_52w_low_pct"]   = round((price / lo52 - 1) * 100, 2)
                    result["near_52w_high"]      = result["range_52w_pct"] > 90
                    result["near_52w_low"]       = result["range_52w_pct"] < 10

            # ── Consecutive up/down days ──────────────────────────────────────
            if len(close) >= 10:
                changes = close.diff().dropna().iloc[-10:].tolist()
                streak, direction = 0, None
                for ch in reversed(changes):
                    d = "up" if ch > 0 else "down" if ch < 0 else None
                    if d is None:
                        break
                    if direction is None:
                        direction = d
                    if d != direction:
                        break
                    streak += 1
                result["consecutive_days"]      = streak
                result["consecutive_direction"] = direction or "flat"
                result["mean_reversion_risk"]   = streak >= 5

            # ── Price gap detection (last 30 bars) ────────────────────────────
            if len(df) >= 2:
                gaps   = []
                window = df.iloc[-31:]
                for i in range(1, len(window)):
                    ph  = float(window["High"].iloc[i - 1])
                    pl  = float(window["Low"].iloc[i - 1])
                    co  = float(window["Open"].iloc[i])
                    raw_dt = window.index[i]
                    ds  = raw_dt.strftime("%Y-%m-%d") if hasattr(raw_dt, "strftime") else str(raw_dt)[:10]
                    if co > ph:
                        gaps.append({"type": "gap_up",   "date": ds,
                                     "size_pct": round((co / ph - 1) * 100, 2),
                                     "level": round(ph, 2)})
                    elif co < pl:
                        gaps.append({"type": "gap_down", "date": ds,
                                     "size_pct": round((co / pl - 1) * 100, 2),
                                     "level": round(pl, 2)})
                result["price_gaps"] = gaps[-3:] if gaps else []
                result["has_gap"]    = bool(gaps)

            # ── yfinance fallbacks for Polygon indicators ─────────────────────
            if not result.get("rsi") and len(close) >= 15:
                delta = close.diff()
                gain  = delta.clip(lower=0).rolling(14).mean()
                loss  = (-delta.clip(upper=0)).rolling(14).mean()
                rs    = gain / loss.replace(0, float("nan"))
                result["rsi"] = round(float((100 - 100 / (1 + rs)).iloc[-1]), 2)

            if not result.get("bb_upper") and len(close) >= 20:
                mid = close.rolling(20).mean()
                std = close.rolling(20).std()
                result["bb_upper"] = round(float((mid + 2 * std).iloc[-1]), 2)
                result["bb_mid"]   = round(float(mid.iloc[-1]), 2)
                result["bb_lower"] = round(float((mid - 2 * std).iloc[-1]), 2)
                rng = result["bb_upper"] - result["bb_lower"]
                result["bb_pct"]   = round((price - result["bb_lower"]) / rng, 3) if rng else None

            if not result.get("macd") and len(close) >= 35:
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd  = ema12 - ema26
                sig   = macd.ewm(span=9, adjust=False).mean()
                result["macd"]        = round(float(macd.iloc[-1]), 4)
                result["macd_signal"] = round(float(sig.iloc[-1]), 4)
                result["macd_hist"]   = round(float((macd - sig).iloc[-1]), 4)

            if not result.get("sma_50") and len(close) >= 50:
                sma50 = float(close.iloc[-50:].mean())
                result["sma_50"]       = round(sma50, 2)
                result["pct_vs_sma50"] = round((price / sma50 - 1) * 100, 2) if price else None

            if not result.get("sma_200") and len(close) >= 200:
                sma200 = float(close.iloc[-200:].mean())
                result["sma_200"]        = round(sma200, 2)
                result["pct_vs_sma200"]  = round((price / sma200 - 1) * 100, 2) if price else None

            if not result.get("cross_signal") and result.get("sma_50") and result.get("sma_200"):
                result["cross_signal"] = (
                    "golden_cross" if result["sma_50"] > result["sma_200"] else "death_cross"
                )

        if "data_source" not in result:
            result["data_source"] = "yfinance (Polygon unavailable)"
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # FUNDAMENTALS  (yfinance + Finnhub + Alpha Vantage)
    # ──────────────────────────────────────────────────────────────────────────

    def get_fundamentals(self, ticker: str) -> dict:
        result = {}
        try:
            info = yf.Ticker(ticker).info or {}
            result.update({
                "market_cap":        info.get("marketCap"),
                "beta":              info.get("beta"),
                "pe_ratio":          info.get("trailingPE"),
                "forward_pe":        info.get("forwardPE"),
                "peg_ratio":         info.get("pegRatio"),
                "pb_ratio":          info.get("priceToBook"),
                "ps_ratio":          info.get("priceToSalesTrailing12Months"),
                "ev_ebitda":         info.get("enterpriseToEbitda"),
                "eps_ttm":           info.get("trailingEps"),
                "revenue_growth":    _pct(info.get("revenueGrowth")),
                "eps_growth":        _pct(info.get("earningsGrowth")),
                "gross_margin":      _pct(info.get("grossMargins")),
                "operating_margin":  _pct(info.get("operatingMargins")),
                "net_margin":        _pct(info.get("profitMargins")),
                "debt_equity":       info.get("debtToEquity"),
                "current_ratio":     info.get("currentRatio"),
                "roe":               _pct(info.get("returnOnEquity")),
                "dividend_yield":    _pct(info.get("dividendYield")),
                "52w_high":          info.get("fiftyTwoWeekHigh"),
                "52w_low":           info.get("fiftyTwoWeekLow"),
                "target_price":      info.get("targetMeanPrice"),
                "analyst_consensus": (info.get("recommendationKey") or "").upper() or None,
                "short_interest":    _pct(info.get("shortPercentOfFloat")),
            })
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            high  = info.get("fiftyTwoWeekHigh")
            if price and high and high > 0:
                result["pct_from_52w_high"] = round((price / high - 1) * 100, 2)
            fcf = info.get("freeCashflow")
            mc  = info.get("marketCap")
            if fcf and mc and mc > 0:
                result["fcf_yield"] = round(fcf / mc * 100, 2)
        except Exception as e:
            result["yf_error"] = str(e)

        # Finnhub supplement
        if self._finnhub:
            try:
                fh      = self._finnhub.company_basic_financials(ticker, "all")
                metrics = fh.get("metric", {})
                result["inst_change"] = metrics.get("epsGrowth3Y")
            except Exception:
                pass

        # Alpha Vantage real balance sheet (overrides yfinance where available)
        if self._av_key:
            av = self.get_av_fundamentals(ticker)
            for k, v in av.items():
                if v is not None:
                    result[k] = v

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # NEWS  (Finnhub primary, NewsAPI fallback)
    # ──────────────────────────────────────────────────────────────────────────

    def get_news(self, ticker: str, limit: int = 5) -> list:
        headlines = []
        if self._finnhub:
            try:
                today    = datetime.now().strftime("%Y-%m-%d")
                week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                articles = self._finnhub.company_news(ticker, _from=week_ago, to=today)
                for a in (articles or [])[:limit]:
                    headlines.append({
                        "headline": a.get("headline", "").strip(),
                        "source":   a.get("source", "Finnhub"),
                        "datetime": a.get("datetime", ""),
                        "summary":  a.get("summary", ""),
                    })
            except Exception:
                pass

        if len(headlines) < limit and NEWS_API_KEY:
            try:
                info    = yf.Ticker(ticker).info or {}
                company = info.get("shortName", ticker)
                resp    = requests.get(
                    "https://newsapi.org/v2/everything",
                    params={"q": company, "sortBy": "publishedAt",
                            "pageSize": limit, "apiKey": NEWS_API_KEY},
                    timeout=10,
                )
                if resp.ok:
                    for a in resp.json().get("articles", [])[:limit]:
                        headlines.append({
                            "headline": a.get("title", "").strip(),
                            "source":   (a.get("source") or {}).get("name", "NewsAPI"),
                            "datetime": a.get("publishedAt", ""),
                        })
            except Exception:
                pass

        return headlines[:limit]

    # ──────────────────────────────────────────────────────────────────────────
    # MACRO DATA  (yfinance proxies + FRED overlay)
    # ──────────────────────────────────────────────────────────────────────────

    def get_macro_data(self) -> dict:
        result = {}
        try:
            def pct_1m(sym):
                df = yf.Ticker(sym).history(period="35d")
                return round((df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100, 2) if len(df) > 1 else None

            result["spy_1m"]  = pct_1m("SPY")
            result["qqq_1m"]  = pct_1m("QQQ")
            result["gold_1m"] = pct_1m("GLD")

            vix = yf.Ticker("^VIX").history(period="5d")
            if not vix.empty:
                result["vix"] = round(float(vix["Close"].iloc[-1]), 2)

            tlt = yf.Ticker("TLT").history(period="5d")
            if not tlt.empty:
                result["ten_year_yield"] = round(float(tlt["Close"].iloc[-1]), 2)

            dxy = yf.Ticker("DX-Y.NYB").history(period="30d")
            if len(dxy) > 5:
                result["dxy_trend"] = (
                    "rising" if float(dxy["Close"].iloc[-1]) > float(dxy["Close"].iloc[-6])
                    else "falling"
                )
            result["breadth"] = "N/A"
        except Exception as e:
            result["error"] = str(e)

        # FRED overlay — real data replaces proxies where available
        fred = self.get_fred_macro()
        result.update(fred)
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # SECTOR PERFORMANCE
    # ──────────────────────────────────────────────────────────────────────────

    def get_sector_performance(self) -> dict:
        from config import SECTOR_ETFS
        perf = {}
        for sector, etf in SECTOR_ETFS.items():
            try:
                df = yf.Ticker(etf).history(period="35d")
                if len(df) > 1:
                    perf[sector] = {
                        "etf":    etf,
                        "price":  round(float(df["Close"].iloc[-1]), 2),
                        "ret_1d": round((df["Close"].iloc[-1] / df["Close"].iloc[-2]  - 1) * 100, 2) if len(df) > 1 else None,
                        "ret_5d": round((df["Close"].iloc[-1] / df["Close"].iloc[-6]  - 1) * 100, 2) if len(df) > 5 else None,
                        "ret_1m": round((df["Close"].iloc[-1] / df["Close"].iloc[0]   - 1) * 100, 2),
                    }
            except Exception:
                perf[sector] = {"etf": etf, "ret_1m": None}
        return perf

    # ──────────────────────────────────────────────────────────────────────────
    # FULL DATA BUNDLE
    # ──────────────────────────────────────────────────────────────────────────

    def get_full_data(self, ticker: str) -> dict:
        return {
            "ticker":            ticker,
            "current_price":     self.get_current_price(ticker),
            "fundamentals":      self.get_fundamentals(ticker),
            "technicals":        self.get_technicals(ticker),
            "news":              self.get_news(ticker, limit=5),
            "macro":             self.get_macro_data(),
            "earnings":          self.get_earnings_calendar(ticker),
            "relative_strength": self.get_relative_strength(ticker),
            "insider":           self.get_insider_transactions(ticker),
            "economic_calendar": self.get_economic_calendar(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pct(v) -> float | None:
    """Convert 0-1 ratio to percentage; return None if missing."""
    if v is None:
        return None
    try:
        return round(float(v) * 100, 2)
    except (TypeError, ValueError):
        return None
