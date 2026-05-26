import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
import finnhub
import requests
from datetime import datetime, timedelta
from config import FINNHUB_API_KEY, NEWS_API_KEY, POLYGON_API_KEY

try:
    import pandas_ta as ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False

POLYGON_BASE = "https://api.polygon.io"


class DataFetcher:
    def __init__(self):
        self._finnhub = finnhub.Client(api_key=FINNHUB_API_KEY) if FINNHUB_API_KEY else None
        self._poly_key = POLYGON_API_KEY

    # ── Polygon helpers ───────────────────────────────────────────────────────

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
        """Return latest value dict from a Polygon v1/indicators endpoint."""
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
        """Fetch all technical indicators from Polygon (primary source)."""
        result = {}
        if not self._poly_key:
            return result

        # RSI (14)
        v = self._poly_indicator(ticker, "rsi", window=14)
        if v:
            result["rsi"] = round(float(v["value"]), 2)

        # MACD (12, 26, 9)
        v = self._poly_indicator(ticker, "macd",
                                  short_window=12, long_window=26, signal_window=9)
        if v:
            result["macd"]        = round(float(v.get("value", 0)), 4)
            result["macd_signal"] = round(float(v.get("signal", 0)), 4)
            result["macd_hist"]   = round(float(v.get("histogram", 0)), 4)

        # SMA 50
        v = self._poly_indicator(ticker, "sma", window=50)
        if v:
            sma50 = float(v["value"])
            result["sma_50"] = round(sma50, 2)
            if current_price:
                result["pct_vs_sma50"] = round((current_price / sma50 - 1) * 100, 2)

        # SMA 200
        v = self._poly_indicator(ticker, "sma", window=200)
        if v:
            sma200 = float(v["value"])
            result["sma_200"] = round(sma200, 2)
            if current_price:
                result["pct_vs_sma200"] = round((current_price / sma200 - 1) * 100, 2)

        # Golden / Death cross
        if result.get("sma_50") and result.get("sma_200"):
            result["cross_signal"] = (
                "golden_cross" if result["sma_50"] > result["sma_200"] else "death_cross"
            )

        # Bollinger Bands (20, 2)
        v = self._poly_indicator(ticker, "bbands", window=20)
        if v:
            result["bb_upper"] = round(float(v.get("upper_band", 0)), 2)
            result["bb_mid"]   = round(float(v.get("middle_band", 0)), 2)
            result["bb_lower"] = round(float(v.get("lower_band", 0)), 2)
            rng = result["bb_upper"] - result["bb_lower"]
            if rng and current_price:
                result["bb_pct"] = round((current_price - result["bb_lower"]) / rng, 3)

        # Previous-day VWAP + volume via aggs
        prev = self._poly(f"/v2/aggs/ticker/{ticker}/prev", {"adjusted": "true"})
        if prev and prev.get("results"):
            day = prev["results"][0]
            result["vwap"]        = round(float(day.get("vw", 0)), 2)
            result["prev_volume"] = int(day.get("v", 0))

        if result:
            result["data_source"] = "Polygon.io"
        return result

    # ── Price history ─────────────────────────────────────────────────────────

    def get_price_history(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        try:
            df = yf.Ticker(ticker).history(period=period)
            df.index = pd.to_datetime(df.index)
            return df
        except Exception:
            return pd.DataFrame()

    def get_current_price(self, ticker: str) -> float:
        try:
            df = self.get_price_history(ticker, period="5d")
            if not df.empty:
                return round(float(df["Close"].iloc[-1]), 2)
        except Exception:
            pass
        return 0.0

    # ── Technical indicators ──────────────────────────────────────────────────

    def get_technicals(self, ticker: str) -> dict:
        price = self.get_current_price(ticker)

        # 1. Try Polygon (primary)
        result = self._get_polygon_technicals(ticker, price)

        # 2. Always pull yfinance for returns, ATR, volume ratio, support/resistance
        df = self.get_price_history(ticker, period="1y")
        if not df.empty and len(df) >= 5:
            close  = df["Close"]
            volume = df["Volume"]

            if len(close) > 1:
                result["ret_1d"]  = round((close.iloc[-1] / close.iloc[-2]  - 1) * 100, 2)
            if len(close) > 5:
                result["ret_5d"]  = round((close.iloc[-1] / close.iloc[-6]  - 1) * 100, 2)
            if len(close) > 20:
                result["ret_20d"] = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2)

            if len(volume) > 20:
                avg_vol = float(volume.iloc[-21:-1].mean())
                result["avg_volume"]   = int(avg_vol)
                result["volume_ratio"] = round(float(volume.iloc[-1]) / avg_vol, 2) if avg_vol else 1.0

            if len(close) > 20:
                result["support"]    = round(float(close.iloc[-20:].min()), 2)
                result["resistance"] = round(float(close.iloc[-20:].max()), 2)

            if len(df) >= 15:
                tr = pd.concat([
                    df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"]  - df["Close"].shift()).abs(),
                ], axis=1).max(axis=1)
                result["atr"] = round(float(tr.rolling(14).mean().iloc[-1]), 2)

            # 3. Fallback: compute missing indicators from yfinance if Polygon gave nothing
            if not result.get("rsi") and len(close) >= 15:
                delta = close.diff()
                gain  = delta.clip(lower=0).rolling(14).mean()
                loss  = (-delta.clip(upper=0)).rolling(14).mean()
                rs    = gain / loss.replace(0, float("nan"))
                rsi_s = 100 - (100 / (1 + rs))
                result["rsi"] = round(float(rsi_s.iloc[-1]), 2)

            if not result.get("bb_upper") and len(close) >= 20:
                mid = close.rolling(20).mean()
                std = close.rolling(20).std()
                result["bb_upper"] = round(float((mid + 2 * std).iloc[-1]), 2)
                result["bb_mid"]   = round(float(mid.iloc[-1]), 2)
                result["bb_lower"] = round(float((mid - 2 * std).iloc[-1]), 2)
                rng = result["bb_upper"] - result["bb_lower"]
                result["bb_pct"] = round((price - result["bb_lower"]) / rng, 3) if rng else None

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
                result["sma_200"]       = round(sma200, 2)
                result["pct_vs_sma200"] = round((price / sma200 - 1) * 100, 2) if price else None

            if not result.get("cross_signal") and result.get("sma_50") and result.get("sma_200"):
                result["cross_signal"] = (
                    "golden_cross" if result["sma_50"] > result["sma_200"] else "death_cross"
                )

            if "data_source" not in result:
                result["data_source"] = "yfinance (Polygon unavailable)"

        return result

    # ── Fundamentals ──────────────────────────────────────────────────────────

    def get_fundamentals(self, ticker: str) -> dict:
        result = {}
        try:
            info = yf.Ticker(ticker).info or {}

            result["market_cap"]       = info.get("marketCap")
            result["beta"]             = info.get("beta")
            result["pe_ratio"]         = info.get("trailingPE")
            result["forward_pe"]       = info.get("forwardPE")
            result["peg_ratio"]        = info.get("pegRatio")
            result["pb_ratio"]         = info.get("priceToBook")
            result["ps_ratio"]         = info.get("priceToSalesTrailing12Months")
            result["ev_ebitda"]        = info.get("enterpriseToEbitda")
            result["eps_ttm"]          = info.get("trailingEps")
            result["revenue_growth"]   = _pct(info.get("revenueGrowth"))
            result["eps_growth"]       = _pct(info.get("earningsGrowth"))
            result["gross_margin"]     = _pct(info.get("grossMargins"))
            result["operating_margin"] = _pct(info.get("operatingMargins"))
            result["net_margin"]       = _pct(info.get("profitMargins"))
            result["debt_equity"]      = info.get("debtToEquity")
            result["current_ratio"]    = info.get("currentRatio")
            result["roe"]              = _pct(info.get("returnOnEquity"))
            result["dividend_yield"]   = _pct(info.get("dividendYield"))
            result["52w_high"]         = info.get("fiftyTwoWeekHigh")
            result["52w_low"]          = info.get("fiftyTwoWeekLow")
            result["target_price"]     = info.get("targetMeanPrice")
            result["analyst_consensus"]= info.get("recommendationKey", "").upper() or None
            result["short_interest"]   = _pct(info.get("shortPercentOfFloat"))

            # % from 52-week high
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            high  = info.get("fiftyTwoWeekHigh")
            if price and high and high > 0:
                result["pct_from_52w_high"] = round((price / high - 1) * 100, 2)

            # FCF yield
            fcf = info.get("freeCashflow")
            mc  = info.get("marketCap")
            if fcf and mc and mc > 0:
                result["fcf_yield"] = round(fcf / mc * 100, 2)

        except Exception as e:
            result["yf_error"] = str(e)

        # Finnhub supplement
        if self._finnhub:
            try:
                fh = self._finnhub.company_basic_financials(ticker, "all")
                metrics = fh.get("metric", {})
                result["insider_trend"] = "N/A"
                result["inst_change"]   = metrics.get("epsGrowth3Y")
            except Exception:
                pass

        return result

    # ── News ──────────────────────────────────────────────────────────────────

    def get_news(self, ticker: str, limit: int = 5) -> list:
        """Fetch up to `limit` recent headlines, Finnhub first then NewsAPI."""
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
                            "source":   a.get("source", {}).get("name", "NewsAPI"),
                            "datetime": a.get("publishedAt", ""),
                        })
            except Exception:
                pass

        return headlines[:limit]

    # ── Macro data ────────────────────────────────────────────────────────────

    def get_macro_data(self) -> dict:
        result = {}
        try:
            def pct_1m(sym):
                df = yf.Ticker(sym).history(period="35d")
                if len(df) < 2:
                    return None
                return round((df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100, 2)

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
        return result

    # ── Sector performance ────────────────────────────────────────────────────

    def get_sector_performance(self) -> dict:
        from config import SECTOR_ETFS
        perf = {}
        for sector, etf in SECTOR_ETFS.items():
            try:
                df = yf.Ticker(etf).history(period="35d")
                if len(df) > 1:
                    perf[sector] = {
                        "etf":   etf,
                        "price": round(float(df["Close"].iloc[-1]), 2),
                        "ret_1d": round((df["Close"].iloc[-1] / df["Close"].iloc[-2]  - 1) * 100, 2) if len(df) > 1 else None,
                        "ret_5d": round((df["Close"].iloc[-1] / df["Close"].iloc[-6]  - 1) * 100, 2) if len(df) > 5 else None,
                        "ret_1m": round((df["Close"].iloc[-1] / df["Close"].iloc[0]   - 1) * 100, 2),
                    }
            except Exception:
                perf[sector] = {"etf": etf, "ret_1m": None}
        return perf

    # ── Full bundle ───────────────────────────────────────────────────────────

    def get_full_data(self, ticker: str) -> dict:
        return {
            "ticker":        ticker,
            "current_price": self.get_current_price(ticker),
            "fundamentals":  self.get_fundamentals(ticker),
            "technicals":    self.get_technicals(ticker),
            "news":          self.get_news(ticker, limit=5),
            "macro":         self.get_macro_data(),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(v) -> float | None:
    """Convert a 0-1 ratio to a percentage, return None if missing."""
    if v is None:
        return None
    try:
        return round(float(v) * 100, 2)
    except (TypeError, ValueError):
        return None
