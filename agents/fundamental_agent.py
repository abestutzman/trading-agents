from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class FundamentalAgent(BaseAgent):
    name = "Fundamental Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        f = data.get("fundamentals", {})
        price = data.get("current_price", 0)

        prompt = f"""Analyze the fundamental value of {data.get('ticker', 'this stock')}.

Fundamental Data (pulled from yfinance/Finnhub — use only these real values):
- Current Price:          ${fmt(price)}
- Market Cap:             ${fmt(f.get('market_cap'), '.0f')}
- Beta:                   {fmt(f.get('beta'))}
- P/E Ratio (TTM):        {fmt(f.get('pe_ratio'))}
- Forward P/E:            {fmt(f.get('forward_pe'))}
- PEG Ratio:              {fmt(f.get('peg_ratio'))}
- P/B Ratio:              {fmt(f.get('pb_ratio'))}
- P/S Ratio:              {fmt(f.get('ps_ratio'))}
- EV/EBITDA:              {fmt(f.get('ev_ebitda'))}
- EPS (TTM):              ${fmt(f.get('eps_ttm'))}
- Revenue Growth (YoY):   {fmt(f.get('revenue_growth'))}%
- EPS Growth (YoY):       {fmt(f.get('eps_growth'))}%
- Gross Margin:           {fmt(f.get('gross_margin'))}%
- Operating Margin:       {fmt(f.get('operating_margin'))}%
- Net Margin:             {fmt(f.get('net_margin'))}%
- Debt/Equity:            {fmt(f.get('debt_equity'))}
- Current Ratio:          {fmt(f.get('current_ratio'))}
- Free Cash Flow Yield:   {fmt(f.get('fcf_yield'))}%
- Return on Equity:       {fmt(f.get('roe'))}%
- Dividend Yield:         {fmt(f.get('dividend_yield'))}%
- 52-week High:           ${fmt(f.get('52w_high'))}
- 52-week Low:            ${fmt(f.get('52w_low'))}
- % from 52w High:        {fmt(f.get('pct_from_52w_high'))}%
- Analyst Target Price:   ${fmt(f.get('target_price'))}
- Analyst Consensus:      {f.get('analyst_consensus', 'N/A')}
- Short Interest:         {fmt(f.get('short_interest'))}%

Use ONLY the real values above. If a value is N/A, treat it as unavailable — do not estimate.
Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "valuation": "overvalued" | "fairly_valued" | "undervalued",
  "financial_health": "strong" | "moderate" | "weak",
  "growth_quality": "high" | "medium" | "low",
  "fair_value_estimate": <number_or_null>,
  "upside_to_target": <percentage_or_null>,
  "key_strengths": ["str1", "str2"],
  "key_weaknesses": ["wk1", "wk2"],
  "reasoning": "brief explanation citing specific real values"
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
