import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SP50_TICKERS
from utils.data_fetcher import DataFetcher
from agents import (
    MacroAgent, FundamentalAgent, TechnicalAgent, SentimentAgent,
    BullResearcher, BearResearcher, RiskManager, HeadTrader,
)


class Screener:
    def __init__(self, progress_callback=None):
        self.fetcher  = DataFetcher()
        self.macro_agent = MacroAgent()
        self.fund_agent  = FundamentalAgent()
        self.tech_agent  = TechnicalAgent()
        self.sent_agent  = SentimentAgent()
        self.bull_agent  = BullResearcher()
        self.bear_agent  = BearResearcher()
        self.risk_agent  = RiskManager()
        self.head_trader = HeadTrader()
        self.progress_cb = progress_callback

    def _score_ticker(self, ticker: str, macro_cache: dict) -> dict:
        """Run all pre-HeadTrader agents on a single ticker and return a score."""
        try:
            data = self.fetcher.get_full_data(ticker)
            data["macro"] = macro_cache  # reuse cached macro data

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

            # Composite score
            signal_map = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}
            scores = [
                signal_map.get(macro_r.get("signal", "NEUTRAL"), 0) * macro_r.get("confidence", 0.5),
                signal_map.get(fund_r.get("signal",  "NEUTRAL"), 0) * fund_r.get("confidence", 0.5),
                signal_map.get(tech_r.get("signal",  "NEUTRAL"), 0) * tech_r.get("confidence", 0.5),
                signal_map.get(sent_r.get("signal",  "NEUTRAL"), 0) * sent_r.get("confidence", 0.5),
            ]
            composite = sum(scores) / len(scores)

            action = "LONG" if composite > 0.15 else "SHORT" if composite < -0.15 else "HOLD"

            return {
                "ticker":         ticker,
                "price":          data.get("current_price", 0),
                "action":         action,
                "composite_score": round(composite, 3),
                "macro_signal":   macro_r.get("signal"),
                "fund_signal":    fund_r.get("signal"),
                "tech_signal":    tech_r.get("signal"),
                "sent_signal":    sent_r.get("signal"),
                "bull_target":    bull_r.get("upside_target"),
                "bear_target":    bear_r.get("downside_target"),
                "tech_trend":     tech_r.get("trend"),
                "rsi":            data.get("technicals", {}).get("rsi"),
                "full_data":      data,
            }
        except Exception as e:
            return {"ticker": ticker, "action": "ERROR", "composite_score": 0,
                    "error": str(e)}

    def run(self, tickers: list = None, max_workers: int = 3) -> list:
        tickers = tickers or SP50_TICKERS
        macro_cache = self.fetcher.get_macro_data()
        results = []
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            if self.progress_cb:
                self.progress_cb(i, total, ticker)
            result = self._score_ticker(ticker, macro_cache)
            results.append(result)
            time.sleep(0.5)  # gentle rate limiting

        # Sort: LONG first by score desc, then HOLD, then SHORT by score asc
        longs  = sorted([r for r in results if r.get("action") == "LONG"],
                        key=lambda x: x.get("composite_score", 0), reverse=True)
        holds  = [r for r in results if r.get("action") == "HOLD"]
        shorts = sorted([r for r in results if r.get("action") == "SHORT"],
                        key=lambda x: x.get("composite_score", 0))
        errors = [r for r in results if r.get("action") == "ERROR"]

        return longs + holds + shorts + errors
