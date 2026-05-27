from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class SentimentAgent(BaseAgent):
    name = "Sentiment Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        news    = data.get("news", [])
        f       = data.get("fundamentals", {})
        insider = data.get("insider", {})
        earn    = data.get("earnings", {})

        # Format live headlines from Finnhub
        if news:
            headlines_block = "\n".join(
                f"  [{n.get('source', '?')}] {n.get('headline', '').strip()}"
                for n in news[:5]
            )
        else:
            headlines_block = "  (No recent headlines available from Finnhub)"

        # Insider transaction data
        insider_net   = insider.get("net_sentiment", "N/A")
        insider_buys  = insider.get("buy_count", 0)
        insider_sells = insider.get("sell_count", 0)
        recent_txns   = insider.get("recent_txns", [])
        txn_lines = "\n".join(
            f"  {tx.get('date','?')}: {tx.get('name','?')} ({tx.get('title','?')}) "
            f"{tx.get('transaction_type','?')} {tx.get('shares','?')} shares @ ${tx.get('price','?')}"
            for tx in recent_txns[:3]
        ) or "  (No recent Form 4 filings)"

        # Earnings proximity warning
        earn_flag    = earn.get("within_14_days", False)
        earn_warning = f"⚠️ EARNINGS IN {earn.get('days_until','?')} DAYS — sentiment may be driven by pre-earnings speculation" \
                       if earn_flag else "no imminent earnings"

        prompt = f"""Analyze market sentiment for {data.get('ticker', 'this stock')}.

Think step by step: first assess news headlines, then insider activity, then quantitative metrics, then synthesize.

═══ RECENT NEWS (live from Finnhub — analyze these specific headlines) ═══
{headlines_block}

═══ INSIDER TRANSACTIONS (Form 4 filings) ═══
- Net Sentiment:   {insider_net}  (Buys: {insider_buys} | Sells: {insider_sells})
- Recent Filings:
{txn_lines}

═══ QUANTITATIVE SENTIMENT ═══
- Analyst Consensus:              {f.get('analyst_consensus', 'N/A')}
- Short Interest (% float):       {fmt(f.get('short_interest'))}%
- Insider Buying Trend (30d):     {f.get('insider_trend', 'N/A')}
- Institutional Ownership Change: {fmt(f.get('inst_change'))}%
- Earnings Proximity:             {earn_warning}

Base your analysis ONLY on the headlines and real metrics provided above.
Do not use general knowledge about the company outside of what is given.
Insider buys from officers/directors = strongly bullish signal. Sells = mildly bearish.

CONFIDENCE CALIBRATION: 0.70 = expect to be right 70% of the time. Be honest about uncertainty.
If headlines are absent or mixed, lower your confidence accordingly.

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "overall_sentiment": "very_positive" | "positive" | "neutral" | "negative" | "very_negative",
  "news_sentiment_score": <-1.0 to 1.0>,
  "insider_signal": "bullish" | "bearish" | "neutral" | "no_data",
  "key_themes": ["theme1", "theme2"],
  "catalyst_risk": "high" | "medium" | "low",
  "earnings_driven_risk": {str(earn_flag).lower()},
  "contrarian_signal": true | false,
  "headline_count_analyzed": {len(news[:5])},
  "reasoning": "step-by-step: headlines first, then insider data, then quantitative metrics, then overall conclusion"
}}"""
        raw = self._call(prompt, max_tokens=1024)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
