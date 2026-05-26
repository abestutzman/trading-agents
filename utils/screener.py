"""
Screener — one-shot scan, Haiku-only agents, 0-100 score scale.

Strong LONG  : normalized score > 65
Strong SHORT : normalized score < 35
Hold zone    : 35-65  → excluded from recommendations
"""

import time
from config import SP50_TICKERS
from utils.data_fetcher import DataFetcher
from agents import (
    MacroAgent, FundamentalAgent, TechnicalAgent, SentimentAgent,
    BullResearcher, BearResearcher,
)


def _normalize(composite: float) -> float:
    """Map composite (-1 to +1) → score (0 to 100)."""
    return round((composite + 1) / 2 * 100, 1)


class Screener:
    """
    Run all Haiku agents on each ticker once.
    Opus agents (Risk Manager, Head Trader) are NOT invoked here —
    they're reserved for full analysis on user-selected tickers.
    """

    LONG_THRESHOLD  = 65.0   # normalized score → strong LONG
    SHORT_THRESHOLD = 35.0   # normalized score → strong SHORT

    def __init__(self, progress_callback=None):
        self.fetcher     = DataFetcher()
        self.macro_agent = MacroAgent()
        self.fund_agent  = FundamentalAgent()
        self.tech_agent  = TechnicalAgent()
        self.sent_agent  = SentimentAgent()
        self.bull_agent  = BullResearcher()
        self.bear_agent  = BearResearcher()
        self.progress_cb = progress_callback

    # ── Single ticker ─────────────────────────────────────────────────────────

    def _score_ticker(self, ticker: str, macro_cache: dict) -> dict:
        try:
            data = self.fetcher.get_full_data(ticker)
            data["macro"] = macro_cache

            macro_r = self.macro_agent.analyze(data)
            fund_r  = self.fund_agent.analyze(data)
            tech_r  = self.tech_agent.analyze(data)
            sent_r  = self.sent_agent.analyze(data)

            data.update({
                "macro_analysis":       macro_r,
                "fundamental_analysis": fund_r,
                "technical_analysis":   tech_r,
                "sentiment_analysis":   sent_r,
            })

            bull_r = self.bull_agent.analyze(data)
            bear_r = self.bear_agent.analyze(data)

            # Weighted composite: macro 15%, fund 30%, tech 35%, sentiment 20%
            sig = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
            weights = [
                (sig.get(macro_r.get("signal", "NEUTRAL"), 0) * macro_r.get("confidence", 0.5), 0.15),
                (sig.get(fund_r.get("signal",  "NEUTRAL"), 0) * fund_r.get("confidence",  0.5), 0.30),
                (sig.get(tech_r.get("signal",  "NEUTRAL"), 0) * tech_r.get("confidence",  0.5), 0.35),
                (sig.get(sent_r.get("signal",  "NEUTRAL"), 0) * sent_r.get("confidence",  0.5), 0.20),
            ]
            composite = sum(v * w for v, w in weights)
            score     = _normalize(composite)

            action = (
                "LONG"  if score > self.LONG_THRESHOLD  else
                "SHORT" if score < self.SHORT_THRESHOLD else
                "HOLD"
            )

            return {
                "ticker":          ticker,
                "price":           data.get("current_price", 0),
                "action":          action,
                "score":           score,          # 0-100 normalized
                "composite":       round(composite, 3),
                "macro_signal":    macro_r.get("signal"),
                "macro_conf":      macro_r.get("confidence", 0),
                "fund_signal":     fund_r.get("signal"),
                "fund_conf":       fund_r.get("confidence", 0),
                "tech_signal":     tech_r.get("signal"),
                "tech_conf":       tech_r.get("confidence", 0),
                "sent_signal":     sent_r.get("signal"),
                "sent_conf":       sent_r.get("confidence", 0),
                "bull_target":     bull_r.get("upside_target"),
                "bear_target":     bear_r.get("downside_target"),
                "tech_trend":      tech_r.get("trend"),
                "rsi":             data.get("technicals", {}).get("rsi"),
                "full_data":       data,
            }
        except Exception as e:
            return {
                "ticker": ticker, "action": "ERROR", "score": 50,
                "composite": 0, "error": str(e),
            }

    # ── Full scan (one-shot) ──────────────────────────────────────────────────

    def run(
        self,
        tickers: list = None,
        excluded_tickers: list = None,
    ) -> dict:
        """
        Run screener exactly once on `tickers`, skipping `excluded_tickers`.
        Returns a dict with results + metadata.
        """
        tickers          = tickers or SP50_TICKERS
        excluded         = {t.upper() for t in (excluded_tickers or [])}
        scan_tickers     = [t for t in tickers if t.upper() not in excluded]
        macro_cache      = self.fetcher.get_macro_data()
        results          = []
        total            = len(scan_tickers)

        for i, ticker in enumerate(scan_tickers):
            if self.progress_cb:
                self.progress_cb(i, total, ticker)
            result = self._score_ticker(ticker, macro_cache)
            results.append(result)
            time.sleep(0.4)  # rate-limit courtesy pause

        if self.progress_cb:
            self.progress_cb(total, total, "Done")

        # Sort: LONG by score desc, then SHORT by score asc, HOLD at bottom
        longs  = sorted([r for r in results if r["action"] == "LONG"],
                        key=lambda x: x["score"], reverse=True)
        shorts = sorted([r for r in results if r["action"] == "SHORT"],
                        key=lambda x: x["score"])
        holds  = [r for r in results if r["action"] == "HOLD"]
        errors = [r for r in results if r["action"] == "ERROR"]
        ranked = longs + shorts + holds + errors

        strong_opportunities = longs + shorts
        has_opportunities    = len(strong_opportunities) > 0

        return {
            "results":             ranked,
            "longs":               longs,
            "shorts":              shorts,
            "holds":               holds,
            "strong":              strong_opportunities,
            "has_opportunities":   has_opportunities,
            "tickers_scanned":     total,
            "tickers_excluded":    list(excluded),
            "long_count":          len(longs),
            "short_count":         len(shorts),
        }
