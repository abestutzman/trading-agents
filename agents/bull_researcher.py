from .base_agent import BaseAgent
from config import HAIKU_MODEL


class BullResearcher(BaseAgent):
    name = "Bull Researcher"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        macro   = data.get("macro_analysis", {})
        fund    = data.get("fundamental_analysis", {})
        tech    = data.get("technical_analysis", {})
        sent    = data.get("sentiment_analysis", {})
        price   = data.get("current_price", "N/A")
        ticker  = data.get("ticker", "this stock")

        prompt = f"""You are an aggressive bull analyst. Build the strongest possible LONG case for {ticker} at ${price}.

Prior Agent Analysis:
- Macro: {macro.get('signal','?')} ({macro.get('reasoning','')})
- Fundamental: {fund.get('signal','?')} | Valuation: {fund.get('valuation','?')} | Fair Value: {fund.get('fair_value_estimate','?')}
- Technical: {tech.get('signal','?')} | Trend: {tech.get('trend','?')} | Momentum: {tech.get('momentum','?')}
- Sentiment: {sent.get('signal','?')} | Themes: {sent.get('key_themes',[])}

Fundamentals snapshot:
- Revenue Growth: {data.get('fundamentals',{}).get('revenue_growth','N/A')}%
- EPS Growth: {data.get('fundamentals',{}).get('eps_growth','N/A')}%
- Gross Margin: {data.get('fundamentals',{}).get('gross_margin','N/A')}%

Construct the bull case. Respond with JSON only:
{{
  "signal": "BULLISH",
  "confidence": 0.0-1.0,
  "bull_thesis": "2-3 sentence thesis",
  "key_catalysts": ["catalyst1", "catalyst2", "catalyst3"],
  "upside_target": <price>,
  "upside_pct": <percentage>,
  "time_horizon": "days" | "weeks" | "months",
  "strongest_argument": "single best reason to be long",
  "bear_counterpoints_addressed": ["how to refute bear1", "how to refute bear2"]
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
