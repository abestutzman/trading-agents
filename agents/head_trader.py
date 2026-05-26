from .base_agent import BaseAgent
from config import OPUS_MODEL


class HeadTrader(BaseAgent):
    name = "Head Trader"

    def __init__(self):
        super().__init__(OPUS_MODEL)

    def analyze(self, data: dict) -> dict:
        bull    = data.get("bull_analysis", {})
        bear    = data.get("bear_analysis", {})
        risk    = data.get("risk_analysis", {})
        tech    = data.get("technical_analysis", {})
        macro   = data.get("macro_analysis", {})
        fund    = data.get("fundamental_analysis", {})
        price   = data.get("current_price", 0)
        ticker  = data.get("ticker", "?")
        account = data.get("portfolio", {}).get("account_value", 100000)

        if not risk.get("approved", False):
            return {
                "agent": self.name,
                "action": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Risk Manager vetoed: {risk.get('veto_reason', 'risk controls')}",
                "entry_price": price,
                "stop_loss": None,
                "take_profit": None,
                "quantity": 0,
            }

        prompt = f"""You are the Head Trader. Make the final trading decision for {ticker} at ${price:.2f}.

═══ AGENT CONSENSUS ═══
• Macro:       {macro.get('signal','?')} (confidence: {macro.get('confidence','?')}) — {macro.get('market_phase','?')}
• Fundamental: {fund.get('signal','?')} (confidence: {fund.get('confidence','?')}) — {fund.get('valuation','?')}
• Technical:   {tech.get('signal','?')} (confidence: {tech.get('confidence','?')}) — {tech.get('trend','?')} trend
• Bull thesis: {bull.get('bull_thesis','')} → target ${bull.get('upside_target','?')}
• Bear thesis: {bear.get('bear_thesis','')} → target ${bear.get('downside_target','?')}

═══ RISK PARAMETERS ═══
• Risk approved: {risk.get('approved')} | Risk score: {risk.get('risk_score','?')}
• Suggested position size: {risk.get('position_size_pct',0)*100:.1f}% of ${account:,.0f} account
• Suggested stop loss: ${risk.get('recommended_stop_loss','?')}
• Suggested take profit: ${risk.get('recommended_take_profit','?')}
• R:R ratio: {risk.get('risk_reward_ratio','?')}

═══ TECHNICALS ═══
• Support: {tech.get('key_levels',{}).get('support','?')} | Resistance: {tech.get('key_levels',{}).get('resistance','?')}
• Entry zone: {tech.get('entry_zone',{})}

Make the definitive trade decision. You can adjust stop/target within reason. Respond with JSON only:
{{
  "action": "LONG" | "SHORT" | "HOLD",
  "confidence": 0.0-1.0,
  "entry_price": <exact price>,
  "stop_loss": <price>,
  "take_profit": <price>,
  "quantity": <shares based on {account} account and position size>,
  "time_horizon": "intraday" | "swing" | "position",
  "entry_rationale": "why enter here",
  "exit_plan": "when/why to exit",
  "invalidation": "what would invalidate this trade",
  "reasoning": "comprehensive decision rationale"
}}"""
        raw = self._call(prompt, max_tokens=3000)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
