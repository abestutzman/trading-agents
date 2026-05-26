from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class SentimentAgent(BaseAgent):
    name = "Sentiment Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        news = data.get("news", [])
        f = data.get("fundamentals", {})

        # Format real headlines — these are fetched from Finnhub, not training data
        if news:
            headlines_block = "\n".join(
                f"  [{n.get('source', '?')}] {n.get('headline', '').strip()}"
                for n in news[:5]
            )
        else:
            headlines_block = "  (No recent headlines available from Finnhub)"

        prompt = f"""Analyze market sentiment for {data.get('ticker', 'this stock')}.

Recent News Headlines (fetched live from Finnhub — analyze these specific headlines):
{headlines_block}

Market Sentiment Metrics (real data):
- Analyst Consensus:              {f.get('analyst_consensus', 'N/A')}
- Short Interest (% float):       {fmt(f.get('short_interest'))}%
- Insider Buying Trend (30d):     {f.get('insider_trend', 'N/A')}
- Institutional Ownership Change: {fmt(f.get('inst_change'))}%

Base your analysis ONLY on the headlines provided above and the real metrics.
Do not use general knowledge about the company — analyze the specific news given.
If no headlines are available, base sentiment only on the metrics.

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "overall_sentiment": "very_positive" | "positive" | "neutral" | "negative" | "very_negative",
  "news_sentiment_score": <-1.0 to 1.0>,
  "key_themes": ["theme1", "theme2"],
  "catalyst_risk": "high" | "medium" | "low",
  "social_buzz": "high" | "normal" | "low",
  "contrarian_signal": true | false,
  "headline_count_analyzed": {len(news[:5])},
  "reasoning": "cite specific headlines or metrics that drove your assessment"
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
