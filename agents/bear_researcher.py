from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class BearResearcher(BaseAgent):
    name = "Bear Researcher"

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
        earn_note = f"Earnings in {earn.get('days_until','?')} days — binary event risk" if earn_flag else ""

        prompt = f"""You are a bear analyst. Your job is to build the strongest possible SHORT/AVOID case for {ticker} at ${price}.

IMPORTANT — DEVIL'S ADVOCATE FIRST:
Before making the bear case, briefly steelman the bull case: what are the 2 strongest arguments AGAINST being short/avoiding?
Then explain why each bull argument is wrong or outweighed by bearish factors.
This makes your bear case more credible.

═══ PRIOR AGENT SIGNALS ═══
- Macro:       {macro.get('signal','?')} (conf: {macro.get('confidence','?')}) — {macro.get('market_phase','?')}
- Fundamental: {fund.get('signal','?')} (conf: {fund.get('confidence','?')}) — {fund.get('valuation','?')}
- Technical:   {tech.get('signal','?')} (conf: {tech.get('confidence','?')}) — {tech.get('trend','?')} trend, RSI: {tech.get('rsi_signal','?')}
- Sentiment:   {sent.get('signal','?')} (conf: {sent.get('confidence','?')}) — catalyst risk: {sent.get('catalyst_risk','?')}

═══ KEY RISKS ═══
- Macro risks:         {macro.get('key_risks',[])}
- Financial health:    {fund.get('financial_health','?')}
- Earnings risk:       {fund.get('earnings_risk','?')}
- BB signal:           {tech.get('bb_signal','?')}
- Mean reversion risk: {tech.get('mean_reversion_risk', False)}

═══ RELATIVE STRENGTH ═══
- 1m vs SPY:        {fmt(rs_1m)}%
- 3m vs SPY:        {fmt(rs_3m)}%
- 1m vs Sector:     {fmt(rs_sec)}%

{earn_note}

CONFIDENCE CALIBRATION: Be honest. If the bear case rests on 1-2 weak signals, score 0.55.
Reserve 0.80+ for situations with clear overvaluation, broken technicals, and negative relative strength.

Construct the bear case. Respond with JSON only:
{{
  "signal": "BEARISH",
  "confidence": 0.0-1.0,
  "bull_steelman": ["strongest bull arg 1", "strongest bull arg 2"],
  "bull_rebuttals": ["why bull arg 1 is wrong", "why bull arg 2 is wrong"],
  "bear_thesis": "2-3 sentence thesis",
  "key_risks": ["risk1", "risk2", "risk3"],
  "relative_strength_view": "underperforming/outperforming and why it matters for the bear case",
  "downside_target": <price>,
  "downside_pct": <percentage>,
  "time_horizon": "days" | "weeks" | "months",
  "strongest_argument": "single best reason to be short/avoid",
  "reasoning": "step-by-step: bull steelman first, then rebuttals, then build the bear case"
}}"""
        raw = self._call(prompt, max_tokens=600)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
