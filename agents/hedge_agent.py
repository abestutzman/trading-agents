from .base_agent import BaseAgent
from config import HAIKU_MODEL


class HedgeAgent(BaseAgent):
    name = "Hedge Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        portfolio = data.get("portfolio", {})
        positions = portfolio.get("positions", [])
        account_value = portfolio.get("account_value", 100000)
        long_exposure  = portfolio.get("long_exposure_pct", 0)
        short_exposure = portfolio.get("short_exposure_pct", 0)
        net_exposure   = long_exposure - short_exposure
        macro_signal   = data.get("macro_analysis", {}).get("signal", "NEUTRAL")
        vix            = data.get("macro", {}).get("vix", "N/A")

        positions_summary = "\n".join(
            f"  - {p.get('symbol','?')}: {p.get('side','?')} {p.get('qty','?')} shares "
            f"@ ${p.get('avg_entry','?')} (P&L: {p.get('unrealized_pnl_pct','?')}%)"
            for p in positions[:15]
        ) or "  (No open positions)"

        prompt = f"""You are the Hedge Agent. Analyze portfolio balance and recommend hedges.

Portfolio Summary:
- Account Value: ${account_value:,.0f}
- Long Exposure: {long_exposure:.1f}%
- Short Exposure: {short_exposure:.1f}%
- Net Directional Exposure: {net_exposure:+.1f}% ({'LONG heavy' if net_exposure > 10 else 'SHORT heavy' if net_exposure < -10 else 'balanced'})
- Open Positions:
{positions_summary}

Market Context:
- Macro Signal: {macro_signal}
- VIX: {vix}

Hedge guidelines:
- Portfolio is "too directional" if net exposure > ±20%
- Consider SPY/QQQ puts for long-heavy portfolios in risk-off environments
- Consider sector ETF shorts for concentrated sector exposure
- Consider VIX calls as tail-risk hedges if VIX < 20

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
  "reasoning": "explanation of hedge strategy"
}}"""
        raw = self._call(prompt, max_tokens=500)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
