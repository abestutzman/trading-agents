import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
import finnhub
import requests
from datetime import datetime, timedelta
from config import FINNHUB_API_KEY, NEWS_API_KEY

try:
    import pandas_ta as ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


class DataFetcher:
    def __init__(self):
        self._finnhub = finnhub.Client(api_key=FINNHUB_API_KEY) if FINNHUB_API_KEY else None

    # ── Price History ─────────────────────────────────────────────────────────

    def get_price_history(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        try:
            tk = yf.Ticker(ticker)
            df = tk.history(period=period)
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

    # ── Technical Indicators ──────────────────────────────────────────────────

    def get_technicals(self, ticker: str) -> dict:
        df = self.get_price_history(ticker, period="1y")
        if df.empty or len(df) < 20:
            return {}

        close = df["Close"]
        volume = df["Volume"]

        result = {}

        if TA_AVAILABLE:
            try:
                df.ta.sma(length=50,  append=True)
                df.ta.sma(length=200, append=True)
                df.ta.rsi(length=14,  append=True)
                df.ta.macd(append=True)
                df.ta.bbands(length=20, std=2, append=True)
                df.ta.atr(length=14, append=True)

                sma50_col  = [c for c in df.columns if "SMA_50"  in c]
                sma200_col = [c for c in df.columns if "SMA_200" in c]
                rsi_col    = [c for c in df.columns if "RSI_14"  in c]
                macd_col   = [c for c in df.columns if "MACD_12_26_9" == c]
                macdh_col  = [c for c in df.columns if "MACDh_12_26_9" == c]
                macds_col  = [c for c in df.columns if "MACDs_12_26_9" == c]
                bbu_col    = [c for c in df.columns if "BBU_20_2.0" in c]
                bbm_col    = [c for c in df.columns if "BBM_20_2.0" in c]
                bbl_col    = [c for c in df.columns if "BBL_20_2.0" in c]
                bbp_col    = [c for c in df.columns if "BBP_20_2.0" in c]
                atr_col    = [c for c in df.columns if "ATRr_14" in c or "ATR_14" in c]

                def last(cols):
                    if cols:
                        v = df[cols[0]].dropna()
                        return round(float(v.iloc[-1]), 4) if not v.empty else None
                    return None

                price = float(close.iloc[-1])
                sma50  = last(sma50_col)
                sma200 = last(sma200_col)

                result["sma_50"]       = sma50
                result["sma_200"]      = sma200
                result["rsi"]          = last(rsi_col)
                result["macd"]         = last(macd_col)
                result["macd_hist"]    = last(macdh_col)
                result["macd_signal"]  = last(macds_col)
                result["bb_upper"]     = last(bbu_col)
                result["bb_mid"]       = last(bbm_col)
                result["bb_lower"]     = last(bbl_col)
                result["bb_pct"]       = last(bbp_col)
                result["atr"]          = last(atr_col)

                if sma50:
                    result["pct_vs_sma50"] = round((price / sma50 - 1) * 100, 2)
                if sma200:
                    result["pct_vs_sma200"] = round((price / sma200 - 1) * 100, 2)

                # Golden / Death cross
                if sma50 and sma200:
                    result["cross_signal"] = "golden_cross" if sma50 > sma200 else "death_cross"

            except Exception as e:
                result["ta_error"] = str(e)
        else:
            # Fallback: manual indicator calculation
            price = float(close.iloc[-1])
            if len(df) >= 50:
                result["sma_50"] = round(float(close.iloc[-50:].mean()), 2)
                result["pct_vs_sma50"] = round((price / result["sma_50"] - 1) * 100, 2)
            if len(df) >= 200:
                result["sma_200"] = round(float(close.iloc[-200:].mean()), 2)
                result["pct_vs_sma200"] = round((price / result["sma_200"] - 1) * 100, 2)
            if result.get("sma_50") and result.get("sma_200"):
                result["cross_signal"] = (
                    "golden_cross" if result["sma_50"] > result["sma_200"] else "death_cross"
                )
            # RSI
            if len(close) >= 15:
                delta = close.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs   = gain / loss.replace(0, float("nan"))
                rsi_series = 100 - (100 / (1 + rs))
                result["rsi"] = round(float(rsi_series.iloc[-1]), 2)
            # Bollinger Bands (20, 2)
            if len(close) >= 20:
                mid = close.rolling(20).mean()
                std = close.rolling(20).std()
                result["bb_upper"] = round(float((mid + 2 * std).iloc[-1]), 2)
                result["bb_mid"]   = round(float(mid.iloc[-1]), 2)
                result["bb_lower"] = round(float((mid - 2 * std).iloc[-1]), 2)
                rng = result["bb_upper"] - result["bb_lower"]
                result["bb_pct"]   = round((price - result["bb_lower"]) / rng, 3) if rng else None
            # MACD (12,26,9)
            if len(close) >= 35:
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd  = ema12 - ema26
                signal_line = macd.ewm(span=9, adjust=False).mean()
                result["macd"]        = round(float(macd.iloc[-1]), 4)
                result["macd_signal"] = round(float(signal_line.iloc[-1]), 4)
                result["macd_hist"]   = round(float((macd - signal_line).iloc[-1]), 4)
            # ATR
            if len(df) >= 15:
                tr = pd.concat([
                    df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"]  - df["Close"].shift()).abs(),
                ], axis=1).max(axis=1)
                result["atr"] = round(float(tr.rolling(14).mean().iloc[-1]), 2)

        # Returns
        if len(close) > 1:
            result["ret_1d"]  = round((close.iloc[-1] / close.iloc[-2]  - 1) * 100, 2)
        if len(close) > 5:
            result["ret_5d"]  = round((close.iloc[-1] / close.iloc[-6]  - 1) * 100, 2)
        if len(close) > 20:
            result["ret_20d"] = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2)

        # Volume ratio
        if len(volume) > 20:
            avg_vol = float(volume.iloc[-21:-1].mean())
            cur_vol = float(volume.iloc[-1])
            result["volume_ratio"] = round(cur_vol / avg_vol, 2) if avg_vol else 1.0

        # Basic support / resistance (20-day high/low)
        if len(close) > 20:
            result["support"]    = round(float(close.iloc[-20:].min()), 2)
            result["resistance"] = round(float(close.iloc[-20:].max()), 2)

        return result

    # ── Fundamentals ──────────────────────────────────────────────────────────

    def get_fundamentals(self, ticker: str) -> dict:
        result = {}
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}

            result["market_cap"]        = info.get("marketCap")
            result["pe_ratio"]          = info.get("trailingPE")
            result["forward_pe"]        = info.get("forwardPE")
            result["peg_ratio"]         = info.get("pegRatio")
            result["pb_ratio"]          = info.get("priceToBook")
            result["ps_ratio"]          = info.get("priceToSalesTrailing12Months")
            result["ev_ebitda"]         = info.get("enterpriseToEbitda")
            result["revenue_growth"]    = round(info.get("revenueGrowth", 0) * 100, 2) if info.get("revenueGrowth") else None
            result["eps_growth"]        = round(info.get("earningsGrowth", 0) * 100, 2) if info.get("earningsGrowth") else None
            result["gross_margin"]      = round(info.get("grossMargins", 0) * 100, 2) if info.get("grossMargins") else None
            result["operating_margin"]  = round(info.get("operatingMargins", 0) * 100, 2) if info.get("operatingMargins") else None
            result["net_margin"]        = round(info.get("profitMargins", 0) * 100, 2) if info.get("profitMargins") else None
            result["debt_equity"]       = info.get("debtToEquity")
            result["current_ratio"]     = info.get("currentRatio")
            result["roe"]               = round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None
            result["dividend_yield"]    = round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None
            result["52w_high"]          = info.get("fiftyTwoWeekHigh")
            result["52w_low"]           = info.get("fiftyTwoWeekLow")
            result["target_price"]      = info.get("targetMeanPrice")
            result["analyst_consensus"] = info.get("recommendationKey", "").upper()
            result["short_interest"]    = round(info.get("shortPercentOfFloat", 0) * 100, 2) if info.get("shortPercentOfFloat") else None

            # Free cash flow yield
            fcf = info.get("freeCashflow")
            mc  = info.get("marketCap")
            if fcf and mc and mc > 0:
                result["fcf_yield"] = round(fcf / mc * 100, 2)

        except Exception as e:
            result["error"] = str(e)

        # Augment with Finnhub
        if self._finnhub:
            try:
                fh_basic = self._finnhub.company_basic_financials(ticker, "all")
                metrics = fh_basic.get("metric", {})
                if metrics:
                    result["insider_trend"] = "N/A"
                    result["inst_change"]   = metrics.get("epsGrowth3Y", "N/A")
            except Exception:
                pass

        return result

    # ── News ──────────────────────────────────────────────────────────────────

    def get_news(self, ticker: str, limit: int = 15) -> list:
        headlines = []

        # Finnhub company news
        if self._finnhub:
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                articles = self._finnhub.company_news(ticker, _from=week_ago, to=today)
                for a in articles[:limit]:
                    headlines.append({
                        "headline": a.get("headline", ""),
                        "source":   a.get("source", "Finnhub"),
                        "datetime": a.get("datetime", ""),
                        "summary":  a.get("summary", ""),
                    })
            except Exception:
                pass

        # NewsAPI fallback
        if len(headlines) < 5 and NEWS_API_KEY:
            try:
                tk = yf.Ticker(ticker)
                company = tk.info.get("shortName", ticker)
                url = (
                    f"https://newsapi.org/v2/everything?q={company}&"
                    f"sortBy=publishedAt&pageSize={limit}&apiKey={NEWS_API_KEY}"
                )
                resp = requests.get(url, timeout=10)
                if resp.ok:
                    for a in resp.json().get("articles", [])[:limit]:
                        headlines.append({
                            "headline": a.get("title", ""),
                            "source":   a.get("source", {}).get("name", "NewsAPI"),
                            "datetime": a.get("publishedAt", ""),
                        })
            except Exception:
                pass

        return headlines[:limit]

    # ── Macro Data ────────────────────────────────────────────────────────────

    def get_macro_data(self) -> dict:
        result = {}
        try:
            def pct_change_1m(ticker):
                df = yf.Ticker(ticker).history(period="35d")
                if len(df) < 2:
                    return None
                return round((df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100, 2)

            result["spy_1m"]  = pct_change_1m("SPY")
            result["qqq_1m"]  = pct_change_1m("QQQ")
            result["gold_1m"] = pct_change_1m("GLD")

            vix = yf.Ticker("^VIX").history(period="5d")
            if not vix.empty:
                result["vix"] = round(float(vix["Close"].iloc[-1]), 2)

            tlt = yf.Ticker("TLT").history(period="5d")
            if not tlt.empty:
                result["ten_year_yield"] = round(float(tlt["Close"].iloc[-1]), 2)

            dxy = yf.Ticker("DX-Y.NYB").history(period="30d")
            if len(dxy) > 5:
                recent = float(dxy["Close"].iloc[-1])
                old    = float(dxy["Close"].iloc[-6])
                result["dxy_trend"] = "rising" if recent > old else "falling"

            # Market breadth approximation via % stocks above SMA in SPY components
            result["breadth"] = "N/A"

        except Exception as e:
            result["error"] = str(e)

        return result

    # ── Sector Performance ────────────────────────────────────────────────────

    def get_sector_performance(self) -> dict:
        from config import SECTOR_ETFS
        perf = {}
        for sector, etf in SECTOR_ETFS.items():
            try:
                df = yf.Ticker(etf).history(period="35d")
                if len(df) > 1:
                    ret_1m  = round((df["Close"].iloc[-1] / df["Close"].iloc[0]  - 1) * 100, 2)
                    ret_5d  = round((df["Close"].iloc[-1] / df["Close"].iloc[-6] - 1) * 100, 2) if len(df) > 5 else None
                    ret_1d  = round((df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100, 2) if len(df) > 1 else None
                    perf[sector] = {
                        "etf": etf,
                        "price": round(float(df["Close"].iloc[-1]), 2),
                        "ret_1d": ret_1d,
                        "ret_5d": ret_5d,
                        "ret_1m": ret_1m,
                    }
            except Exception:
                perf[sector] = {"etf": etf, "ret_1m": None}
        return perf

    # ── Full Bundle ───────────────────────────────────────────────────────────

    def get_full_data(self, ticker: str) -> dict:
        return {
            "ticker":        ticker,
            "current_price": self.get_current_price(ticker),
            "fundamentals":  self.get_fundamentals(ticker),
            "technicals":    self.get_technicals(ticker),
            "news":          self.get_news(ticker),
            "macro":         self.get_macro_data(),
        }
