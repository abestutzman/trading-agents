from .base_agent import BaseAgent
from config import HAIKU_MODEL


class SentimentAgent(BaseAgent):
    name = "Sentiment Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        news = data.get("news", [])
        headlines = "\n".join(
            f"- [{n.get('source','?')}] {n.get('headline','')}" for n in news[:15]
        )
        prompt = f"""Analyze market sentiment for {data.get('ticker', 'this stock')}.

Recent News Headlines:
{headlines if headlines else '(No recent headlines available)'}

Additional Sentiment Data:
- Short Interest: {data.get('fundamentals', {}).get('short_interest', 'N/A')}%
- Analyst Consensus: {data.get('fundamentals', {}).get('analyst_consensus', 'N/A')}
- Insider Transactions (30d): {data.get('fundamentals', {}).get('insider_trend', 'N/A')}
- Institutional Ownership Change: {data.get('fundamentals', {}).get('inst_change', 'N/A')}%

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "overall_sentiment": "very_positive" | "positive" | "neutral" | "negative" | "very_negative",
  "news_sentiment_score": -1.0 to 1.0,
  "key_themes": ["theme1", "theme2"],
  "catalyst_risk": "high" | "medium" | "low",
  "social_buzz": "high" | "normal" | "low",
  "contrarian_signal": true | false,
  "reasoning": "brief explanation"
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
