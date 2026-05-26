from .base_agent import BaseAgent
from config import HAIKU_MODEL


class BearResearcher(BaseAgent):
    name = "Bear Researcher"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        macro   = data.get("macro_analysis", {})
        fund    = data.get("fundamental_analysis", {})
        tech    = data.get("technical_analysis", {})
        sent    = data.get("sentiment_analysis", {})
        price   = data.get("current_price", "N/A")
        ticker  = data.get("ticker", "this stock")

        prompt = f"""You are a skeptical bear analyst. Build the strongest possible SHORT/AVOID case for {ticker} at ${price}.

Prior Agent Analysis:
- Macro: {macro.get('signal','?')} ({macro.get('reasoning','')})
- Fundamental: {fund.get('signal','?')} | Valuation: {fund.get('valuation','?')} | Fair Value: {fund.get('fair_value_estimate','?')}
- Technical: {tech.get('signal','?')} | Trend: {tech.get('trend','?')} | Momentum: {tech.get('momentum','?')}
- Sentiment: {sent.get('signal','?')} | Catalyst Risk: {sent.get('catalyst_risk','?')}

Key Risks snapshot:
- Macro risks: {macro.get('key_risks',[])}
- Technical weaknesses: {tech.get('bb_signal','?')} | RSI: {tech.get('rsi_signal','?')}

Construct the bear case. Respond with JSON only:
{{
  "signal": "BEARISH",
  "confidence": 0.0-1.0,
  "bear_thesis": "2-3 sentence thesis",
  "key_risks": ["risk1", "risk2", "risk3"],
  "downside_target": <price>,
  "downside_pct": <percentage>,
  "time_horizon": "days" | "weeks" | "months",
  "strongest_argument": "single best reason to be short/avoid",
  "bull_counterpoints_addressed": ["how to refute bull1", "how to refute bull2"]
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
