from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class BullResearcher(BaseAgent):
    name = "Bull Researcher"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        macro  = data.get("macro_analysis", {})
        fund   = data.get("fundamental_analysis", {})
        tech   = data.get("technical_analysis", {})
        sent   = data.get("sentiment_analysis", {})
        rs     = data.get("relative_strength", {})
        earn   = data.get("earnings", {})
        price  = data.get("current_price", "N/A")
        ticker = data.get("ticker", "this stock")

        # Relative strength summary
        rs_1m  = rs.get("rs_1m_vs_spy", "N/A")
        rs_3m  = rs.get("rs_3m_vs_spy", "N/A")
        rs_sec = rs.get("rs_1m_vs_sector", "N/A")

        # Earnings warning
        earn_flag = earn.get("within_14_days", False)
        earn_note = f"Earnings in {earn.get('days_until','?')} days — potential catalyst" if earn_flag else ""

        prompt = f"""You are a bull analyst. Your job is to build the strongest possible LONG case for {ticker} at ${price}.

IMPORTANT — DEVIL'S ADVOCATE FIRST:
Before making the bull case, briefly steelman the bear case: what are the 2 strongest arguments AGAINST going long?
Then explain why each bear argument is wrong or outweighed by bullish factors.
This makes your bull case more credible.

═══ PRIOR AGENT SIGNALS ═══
- Macro:       {macro.get('signal','?')} (conf: {macro.get('confidence','?')}) — {macro.get('market_phase','?')}
- Fundamental: {fund.get('signal','?')} (conf: {fund.get('confidence','?')}) — {fund.get('valuation','?')} | fair value: ${fund.get('fair_value_estimate','?')}
- Technical:   {tech.get('signal','?')} (conf: {tech.get('confidence','?')}) — {tech.get('trend','?')} trend, momentum: {tech.get('momentum','?')}
- Sentiment:   {sent.get('signal','?')} (conf: {sent.get('confidence','?')}) — themes: {sent.get('key_themes',[])}

═══ KEY METRICS ═══
- Revenue Growth:   {data.get('fundamentals',{}).get('revenue_growth','N/A')}%
- EPS Growth:       {data.get('fundamentals',{}).get('eps_growth','N/A')}%
- Gross Margin:     {data.get('fundamentals',{}).get('gross_margin','N/A')}%
- Insider Signal:   {sent.get('insider_signal','N/A')}

═══ RELATIVE STRENGTH ═══
- 1m vs SPY:        {fmt(rs_1m)}%
- 3m vs SPY:        {fmt(rs_3m)}%
- 1m vs Sector:     {fmt(rs_sec)}%

{earn_note}

CONFIDENCE CALIBRATION: Be honest. If the bull case depends on 1-2 weak signals, score 0.55.
Reserve 0.80+ for setups with broad multi-factor alignment and strong relative strength.

Construct the bull case. Respond with JSON only:
{{
  "signal": "BULLISH",
  "confidence": 0.0-1.0,
  "bear_steelman": ["strongest bear arg 1", "strongest bear arg 2"],
  "bear_rebuttals": ["why bear arg 1 is wrong", "why bear arg 2 is wrong"],
  "bull_thesis": "2-3 sentence thesis",
  "key_catalysts": ["catalyst1", "catalyst2", "catalyst3"],
  "relative_strength_view": "outperforming/underperforming and why it matters",
  "upside_target": <price>,
  "upside_pct": <percentage>,
  "time_horizon": "days" | "weeks" | "months",
  "strongest_argument": "single best reason to be long",
  "reasoning": "step-by-step: bear steelman first, then rebuttals, then build the bull case"
}}"""
        raw = self._call(prompt, max_tokens=1024)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
