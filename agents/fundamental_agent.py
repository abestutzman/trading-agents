from .base_agent import BaseAgent
from config import HAIKU_MODEL


class FundamentalAgent(BaseAgent):
    name = "Fundamental Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        f = data.get("fundamentals", {})
        prompt = f"""Analyze the fundamental value of {data.get('ticker', 'this stock')}.

Fundamental Data:
- Current Price: ${data.get('current_price', 'N/A')}
- Market Cap: ${f.get('market_cap', 'N/A')}
- P/E Ratio (TTM): {f.get('pe_ratio', 'N/A')}
- Forward P/E: {f.get('forward_pe', 'N/A')}
- PEG Ratio: {f.get('peg_ratio', 'N/A')}
- P/B Ratio: {f.get('pb_ratio', 'N/A')}
- P/S Ratio: {f.get('ps_ratio', 'N/A')}
- EV/EBITDA: {f.get('ev_ebitda', 'N/A')}
- Revenue Growth (YoY): {f.get('revenue_growth', 'N/A')}%
- EPS Growth (YoY): {f.get('eps_growth', 'N/A')}%
- Gross Margin: {f.get('gross_margin', 'N/A')}%
- Operating Margin: {f.get('operating_margin', 'N/A')}%
- Net Margin: {f.get('net_margin', 'N/A')}%
- Debt/Equity: {f.get('debt_equity', 'N/A')}
- Current Ratio: {f.get('current_ratio', 'N/A')}
- Free Cash Flow Yield: {f.get('fcf_yield', 'N/A')}%
- Return on Equity: {f.get('roe', 'N/A')}%
- Dividend Yield: {f.get('dividend_yield', 'N/A')}%
- 52-week range: {f.get('52w_low', 'N/A')} - {f.get('52w_high', 'N/A')}
- Analyst Target Price: ${f.get('target_price', 'N/A')}

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "valuation": "overvalued" | "fairly_valued" | "undervalued",
  "financial_health": "strong" | "moderate" | "weak",
  "growth_quality": "high" | "medium" | "low",
  "fair_value_estimate": <number or null>,
  "upside_to_target": <percentage or null>,
  "key_strengths": ["str1"],
  "key_weaknesses": ["wk1"],
  "reasoning": "brief explanation"
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
