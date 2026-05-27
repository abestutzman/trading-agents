from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class HedgeAgent(BaseAgent):
    name = "Hedge Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        portfolio      = data.get("portfolio", {})
        positions      = portfolio.get("positions", [])
        account_value  = portfolio.get("account_value", 100000)
        long_exposure  = portfolio.get("long_exposure_pct", 0)
        short_exposure = portfolio.get("short_exposure_pct", 0)
        net_exposure   = long_exposure - short_exposure
        macro_signal   = data.get("macro_analysis", {}).get("signal", "NEUTRAL")
        macro_phase    = data.get("macro_analysis", {}).get("market_phase", "N/A")
        vix            = data.get("macro", {}).get("vix", "N/A")
        event_risk     = data.get("macro_analysis", {}).get("event_risk", "low")

        positions_summary = "\n".join(
            f"  - {p.get('symbol','?')}: {p.get('side','?')} {p.get('qty','?')} shares "
            f"@ ${p.get('avg_entry','?')} (P&L: {p.get('unrealized_pnl_pct','?')}%)"
            for p in positions[:15]
        ) or "  (No open positions)"

        prompt = f"""You are the Hedge Agent. Analyze portfolio balance and recommend hedges.

Think step by step: assess directional exposure, evaluate macro risk, then recommend hedges.

═══ PORTFOLIO EXPOSURE ═══
- Account Value:           ${account_value:,.0f}
- Long Exposure:           {long_exposure:.1f}%
- Short Exposure:          {short_exposure:.1f}%
- Net Directional Exposure: {net_exposure:+.1f}% ({'LONG heavy' if net_exposure > 10 else 'SHORT heavy' if net_exposure < -10 else 'balanced'})
- Open Positions:
{positions_summary}

═══ MARKET CONTEXT ═══
- Macro Signal:  {macro_signal}
- Market Phase:  {macro_phase}
- VIX:           {vix}
- Event Risk:    {event_risk}

═══ HEDGE GUIDELINES ═══
- Portfolio is "too directional" if net exposure > ±20%
- Consider SPY/QQQ puts for long-heavy portfolios in risk-off environments
- Consider sector ETF shorts for concentrated sector exposure
- Consider VIX calls as tail-risk hedge if VIX < 20 and macro is uncertain
- In risk-off macro + high event risk: recommend reducing net exposure to ±10%

CONFIDENCE CALIBRATION: Be honest about hedge necessity. If portfolio is balanced, hedge_needed = false.

Respond with JSON only:
{{
  "hedge_needed": true | false,
  "urgency": "HIGH" | "MEDIUM" | "LOW" | "NONE",
  "direction_bias": "LONG_HEAVY" | "SHORT_HEAVY" | "BALANCED",
  "net_exposure_pct": <float>,
  "recommendations": [
    {{
      "instrument": "ticker",
      "action": "LONG" | "SHORT",
      "allocation_pct": <float>,
      "rationale": "why"
    }}
  ],
  "portfolio_risk_assessment": "brief assessment",
  "reasoning": "step-by-step: exposure analysis, macro context, hedge selection, sizing"
}}"""
        raw = self._call(prompt, max_tokens=500)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
