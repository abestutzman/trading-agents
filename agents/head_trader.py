from .base_agent import BaseAgent, fmt
from config import OPUS_MODEL


class HeadTrader(BaseAgent):
    name = "Head Trader"

    def __init__(self):
        super().__init__(OPUS_MODEL)

    def _detect_contradictions(self, signals: list[dict]) -> list[str]:
        """Identify agents whose signals disagree with the majority."""
        from collections import Counter
        sig_map   = {s["name"]: s["signal"] for s in signals}
        counts    = Counter(sig_map.values())
        majority  = counts.most_common(1)[0][0]
        dissenters = [
            f"{s['name']} says {s['signal']} (conf {s.get('confidence','?')})"
            for s in signals if s["signal"] != majority
        ]
        return dissenters

    def analyze(self, data: dict) -> dict:
        bull   = data.get("bull_analysis", {})
        bear   = data.get("bear_analysis", {})
        risk   = data.get("risk_analysis", {})
        tech   = data.get("technical_analysis", {})
        macro  = data.get("macro_analysis", {})
        fund   = data.get("fundamental_analysis", {})
        sent   = data.get("sentiment_analysis", {})
        t      = data.get("technicals", {})
        earn   = data.get("earnings", {})
        econ   = data.get("economic_calendar", {})
        price  = data.get("current_price", 0)
        ticker = data.get("ticker", "?")
        account = data.get("portfolio", {}).get("account_value", 100000)

        if not risk.get("approved", False):
            return {
                "agent":       self.name,
                "action":      "HOLD",
                "confidence":  0.0,
                "reasoning":   f"Risk Manager vetoed: {risk.get('veto_reason', 'risk controls')}",
                "entry_price": price,
                "stop_loss":   None,
                "take_profit": None,
                "quantity":    0,
            }

        # Contradiction detection
        agent_signals = [
            {"name": "Macro",       "signal": macro.get("signal","?"), "confidence": macro.get("confidence","?")},
            {"name": "Fundamental", "signal": fund.get("signal","?"),  "confidence": fund.get("confidence","?")},
            {"name": "Technical",   "signal": tech.get("signal","?"),  "confidence": tech.get("confidence","?")},
            {"name": "Sentiment",   "signal": sent.get("signal","?"),  "confidence": sent.get("confidence","?")},
        ]
        contradictions = self._detect_contradictions(agent_signals)
        contradiction_note = (
            "⚠️ AGENT DISAGREEMENT: " + "; ".join(contradictions)
            if contradictions else "All agents aligned"
        )

        # ATR stops
        atr_stop_long  = t.get("atr_stop_long")
        atr_stop_short = t.get("atr_stop_short")
        atr_risk_pct   = t.get("atr_risk_pct")

        # Earnings warning
        earn_flag  = earn.get("within_14_days", False)
        earn_days  = earn.get("days_until", "N/A")
        earn_warn  = f"⚠️ EARNINGS IN {earn_days} DAYS — binary event, size small" if earn_flag else ""

        # Economic calendar warning
        econ_flag  = econ.get("within_5_days", False)
        econ_event = econ.get("nearest_event", {}).get("name", "none")
        econ_days  = econ.get("nearest_event", {}).get("days_until", "N/A")
        econ_warn  = f"⚠️ MACRO EVENT: {econ_event} in {econ_days} days — reduce size or wait" if econ_flag else ""

        prompt = f"""You are the Head Trader. Make the final trading decision for {ticker} at ${price:.2f}.

Think step by step: assess consensus, handle contradictions, apply risk parameters, then decide.

═══ AGENT CONSENSUS ═══
• Macro:       {macro.get('signal','?')} (conf: {macro.get('confidence','?')}) — {macro.get('market_phase','?')}
• Fundamental: {fund.get('signal','?')} (conf: {fund.get('confidence','?')}) — {fund.get('valuation','?')}
• Technical:   {tech.get('signal','?')} (conf: {tech.get('confidence','?')}) — {tech.get('trend','?')} trend
• Sentiment:   {sent.get('signal','?')} (conf: {sent.get('confidence','?')})
• Bull thesis: {bull.get('bull_thesis','')} → target ${bull.get('upside_target','?')}
• Bear thesis: {bear.get('bear_thesis','')} → target ${bear.get('downside_target','?')}

{contradiction_note}

═══ RISK PARAMETERS ═══
• Risk approved: {risk.get('approved')} | Risk score: {risk.get('risk_score','?')}
• Position size: {risk.get('position_size_pct',0)*100:.1f}% of ${account:,.0f}
• R:R ratio: {risk.get('risk_reward_ratio','?')}
• Risk flags: {risk.get('risk_flags',[])}
• Earnings constraint applied: {risk.get('earnings_constraint_applied', False)}
• Macro event constraint applied: {risk.get('macro_event_constraint_applied', False)}

═══ STOP/TARGET LEVELS ═══
• ATR Stop (Long):  ${fmt(atr_stop_long)}  |  ATR Stop (Short): ${fmt(atr_stop_short)}
• ATR Risk %:       {fmt(atr_risk_pct)}%
• Risk Suggested Stop: ${risk.get('recommended_stop_loss','?')}
• Risk Suggested Target: ${risk.get('recommended_take_profit','?')}
• Technical Support: {tech.get('key_levels',{}).get('support','?')}
• Technical Resistance: {tech.get('key_levels',{}).get('resistance','?')}
• Entry zone: {tech.get('entry_zone',{})}

═══ ACTIVE WARNINGS ═══
{earn_warn or "No earnings warning"}
{econ_warn or "No macro event warning"}

INSTRUCTION: Use ATR-based stops (not fixed %) whenever available.
When agents disagree, you must explicitly address the dissenting view before deciding.
If >= 3 agents are NEUTRAL or split 2-2, lean toward HOLD unless there is a clear technical setup.

CONFIDENCE CALIBRATION: Be honest. Split signals = 0.5–0.6 confidence. Clear consensus = 0.75+.

Respond with JSON only:
{{
  "action": "LONG" | "SHORT" | "HOLD",
  "confidence": 0.0-1.0,
  "entry_price": <exact price>,
  "stop_loss": <ATR-based stop preferred>,
  "take_profit": <price>,
  "quantity": <shares based on {account} account and position size>,
  "time_horizon": "intraday" | "swing" | "position",
  "contradictions_resolved": "{contradiction_note}",
  "entry_rationale": "why enter here — address any agent disagreements",
  "exit_plan": "when/why to exit — cite ATR stop level",
  "invalidation": "what would invalidate this trade",
  "earnings_warning": "{earn_warn or 'none'}",
  "macro_warning": "{econ_warn or 'none'}",
  "reasoning": "step-by-step: resolve contradictions first, assess consensus, apply constraints, then conclude"
}}"""
        raw = self._call(prompt, max_tokens=1200)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
