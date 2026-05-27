from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class FundamentalAgent(BaseAgent):
    name = "Fundamental Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        f       = data.get("fundamentals", {})
        price   = data.get("current_price", 0)
        earn    = data.get("earnings", {})

        # Alpha Vantage balance sheet fields
        av_revenue   = f.get("av_revenue", "N/A")
        av_net_income = f.get("av_net_income", "N/A")
        av_total_debt = f.get("av_total_debt", "N/A")
        av_cash      = f.get("av_cash", "N/A")
        av_ocf       = f.get("av_operating_cf", "N/A")
        av_fcf       = f.get("av_free_cashflow", "N/A")
        av_period    = f.get("av_period", "N/A")

        # Format large numbers in billions
        def bil(v):
            try:
                return f"${float(v)/1e9:.2f}B"
            except (TypeError, ValueError):
                return str(v)

        # Earnings calendar
        next_earn    = earn.get("next_earnings_date", "N/A")
        days_earn    = earn.get("days_until", "N/A")
        earn_flag    = earn.get("within_14_days", False)
        earn_warning = " ⚠️ EARNINGS WITHIN 14 DAYS — increased uncertainty" if earn_flag else ""

        prompt = f"""Analyze the fundamental value of {data.get('ticker', 'this stock')}.

Think through valuation, financial health, and growth quality step by step before concluding.

═══ VALUATION ═══
- Current Price:          ${fmt(price)}{earn_warning}
- Market Cap:             ${fmt(f.get('market_cap'), '.0f')}
- P/E Ratio (TTM):        {fmt(f.get('pe_ratio'))}
- Forward P/E:            {fmt(f.get('forward_pe'))}
- PEG Ratio:              {fmt(f.get('peg_ratio'))}
- P/B Ratio:              {fmt(f.get('pb_ratio'))}
- P/S Ratio:              {fmt(f.get('ps_ratio'))}
- EV/EBITDA:              {fmt(f.get('ev_ebitda'))}
- Analyst Target Price:   ${fmt(f.get('target_price'))}
- Analyst Consensus:      {f.get('analyst_consensus', 'N/A')}

═══ EARNINGS & GROWTH ═══
- EPS (TTM):              ${fmt(f.get('eps_ttm'))}
- Revenue Growth (YoY):   {fmt(f.get('revenue_growth'))}%
- EPS Growth (YoY):       {fmt(f.get('eps_growth'))}%
- Next Earnings Date:     {next_earn} (in {days_earn} days)

═══ PROFITABILITY ═══
- Gross Margin:           {fmt(f.get('gross_margin'))}%
- Operating Margin:       {fmt(f.get('operating_margin'))}%
- Net Margin:             {fmt(f.get('net_margin'))}%
- Return on Equity:       {fmt(f.get('roe'))}%
- Free Cash Flow Yield:   {fmt(f.get('fcf_yield'))}%

═══ BALANCE SHEET (Alpha Vantage — {av_period}) ═══
- Revenue (quarterly):    {bil(av_revenue)}
- Net Income (quarterly): {bil(av_net_income)}
- Total Debt:             {bil(av_total_debt)}
- Cash & Equivalents:     {bil(av_cash)}
- Operating Cash Flow:    {bil(av_ocf)}
- Free Cash Flow:         {bil(av_fcf)}

═══ RISK METRICS ═══
- Beta:                   {fmt(f.get('beta'))}
- Debt/Equity:            {fmt(f.get('debt_equity'))}
- Current Ratio:          {fmt(f.get('current_ratio'))}
- Short Interest:         {fmt(f.get('short_interest'))}%
- Dividend Yield:         {fmt(f.get('dividend_yield'))}%

Use ONLY the real values above. If a value is N/A, treat it as unavailable — do not estimate.
If Alpha Vantage balance sheet data is unavailable (N/A), rely on yfinance-sourced metrics.

CONFIDENCE CALIBRATION: Be honest — if fundamentals are mixed or data is sparse, score 0.5–0.65.
Reserve 0.80+ for clear undervaluation or overvaluation supported by multiple data points.

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "valuation": "overvalued" | "fairly_valued" | "undervalued",
  "financial_health": "strong" | "moderate" | "weak",
  "growth_quality": "high" | "medium" | "low",
  "earnings_risk": "high" | "medium" | "low",
  "fair_value_estimate": <number_or_null>,
  "upside_to_target": <percentage_or_null>,
  "key_strengths": ["str1", "str2"],
  "key_weaknesses": ["wk1", "wk2"],
  "reasoning": "step-by-step: valuation ratios first, then balance sheet health, then growth quality, then conclude"
}}"""
        raw = self._call(prompt, max_tokens=600)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
