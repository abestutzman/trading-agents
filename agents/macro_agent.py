from .base_agent import BaseAgent
from config import HAIKU_MODEL


class MacroAgent(BaseAgent):
    name = "Macro Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        macro = data.get("macro", {})
        prompt = f"""Analyze the current macroeconomic environment for trading {data.get('ticker', 'this asset')}.

Macro Data:
- SPY 1-month return: {macro.get('spy_1m', 'N/A')}%
- QQQ 1-month return: {macro.get('qqq_1m', 'N/A')}%
- VIX current level: {macro.get('vix', 'N/A')}
- US 10Y yield: {macro.get('ten_year_yield', 'N/A')}%
- DXY (USD index) trend: {macro.get('dxy_trend', 'N/A')}
- Gold 1-month return: {macro.get('gold_1m', 'N/A')}%
- Market breadth (% stocks above 200MA): {macro.get('breadth', 'N/A')}%

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "market_phase": "risk-on" | "risk-off" | "transitioning",
  "key_risks": ["risk1", "risk2"],
  "tailwinds": ["tailwind1"],
  "reasoning": "brief explanation",
  "rate_environment": "restrictive" | "neutral" | "accommodative"
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
