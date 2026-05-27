from .base_agent import BaseAgent, fmt
from config import OPUS_MODEL


class RiskManager(BaseAgent):
    name = "Risk Manager"

    def __init__(self):
        super().__init__(OPUS_MODEL)

    def analyze(self, data: dict) -> dict:
        bull     = data.get("bull_analysis", {})
        bear     = data.get("bear_analysis", {})
        tech     = data.get("technical_analysis", {})
        price    = data.get("current_price", 0)
        ticker   = data.get("ticker", "?")
        t        = data.get("technicals", {})
        earn     = data.get("earnings", {})
        econ_cal = data.get("economic_calendar", {})

        portfolio      = data.get("portfolio", {})
        account_value  = portfolio.get("account_value", 100000)
        open_positions = portfolio.get("open_positions", 0)
        daily_pnl_pct  = portfolio.get("daily_pnl_pct", 0)
        existing_exp   = portfolio.get("existing_exposure_pct", 0)

        risk_cfg       = data.get("risk_config", {})
        max_pos_pct    = risk_cfg.get("max_position_pct", 0.05)
        daily_loss_lim = risk_cfg.get("daily_loss_limit", 0.02)
        max_positions  = risk_cfg.get("max_positions", 10)
        cooldown_mins  = data.get("cooldown_remaining", None)

        # ATR-based stops
        atr_stop_long  = t.get("atr_stop_long")
        atr_stop_short = t.get("atr_stop_short")
        atr_risk_pct   = t.get("atr_risk_pct")

        # Earnings proximity cap: reduce max position to 1% if within 14 days
        earn_within_14  = earn.get("within_14_days", False)
        earn_days       = earn.get("days_until", "N/A")
        if earn_within_14:
            effective_max_pct  = min(max_pos_pct, 0.01)
            earn_rule_note     = f"EARNINGS RULE: Position capped at 1% — earnings in {earn_days} days"
        else:
            effective_max_pct  = max_pos_pct
            earn_rule_note     = f"No earnings within 14 days (next: {earn_days} days)"

        # Economic calendar cap: reduce position 50% if major event within 5 days
        econ_within_5   = econ_cal.get("within_5_days", False)
        nearest_event   = econ_cal.get("nearest_event", {})
        event_name      = nearest_event.get("name", "none")
        event_days      = nearest_event.get("days_until", "N/A")
        if econ_within_5:
            effective_max_pct = effective_max_pct * 0.50
            econ_rule_note    = f"MACRO EVENT RULE: Position halved — {event_name} in {event_days} days"
        else:
            econ_rule_note    = f"No macro events within 5 days (next: {event_name} in {event_days} days)"

        prompt = f"""You are the Risk Manager for an algorithmic trading system. Evaluate risk for {ticker} at ${price:.2f}.

Think through each risk dimension step by step before issuing your final risk assessment.

═══ THESIS SUMMARY ═══
- Bull: {bull.get('bull_thesis','')} | Target: ${bull.get('upside_target','?')} | Conf: {bull.get('confidence','?')}
- Bear: {bear.get('bear_thesis','')} | Target: ${bear.get('downside_target','?')} | Conf: {bear.get('confidence','?')}

═══ TECHNICAL RISK LEVELS ═══
- Support:          ${tech.get('key_levels',{}).get('support','?')}
- Resistance:       ${tech.get('key_levels',{}).get('resistance','?')}
- ATR (14):         ${fmt(t.get('atr'))}
- ATR Stop (Long):  ${fmt(atr_stop_long)}  |  ATR Stop (Short): ${fmt(atr_stop_short)}
- ATR Risk %:       {fmt(atr_risk_pct)}%   ← prefer this over fixed % stops

═══ PORTFOLIO STATE ═══
- Account Value:       ${account_value:,.0f}
- Open Positions:      {open_positions}/{max_positions}
- Today's P&L:         {daily_pnl_pct:.2f}% (daily loss limit: -{daily_loss_lim*100:.1f}%)
- Existing {ticker} Exposure: {existing_exp:.1f}%
- Cooldown Remaining:  {f'{cooldown_mins:.0f} min' if cooldown_mins else 'None'}

═══ POSITION SIZE RULES ═══
- Base max position: {max_pos_pct*100:.0f}%
- {earn_rule_note}
- {econ_rule_note}
- EFFECTIVE MAX POSITION: {effective_max_pct*100:.1f}%

CONFIDENCE CALIBRATION: Be honest. A risk_score of 0.8 = high risk. Low risk_score = safe trade.

Respond with JSON only:
{{
  "approved": true | false,
  "veto_reason": null | "reason if vetoed",
  "risk_score": 0.0-1.0,
  "position_size_pct": 0.0-{effective_max_pct:.3f},
  "recommended_stop_loss": <use ATR stop if available, else support level>,
  "recommended_take_profit": <price>,
  "risk_reward_ratio": <float>,
  "max_loss_dollars": <float>,
  "earnings_constraint_applied": {str(earn_within_14).lower()},
  "macro_event_constraint_applied": {str(econ_within_5).lower()},
  "sizing_rationale": "why this size — cite ATR stop usage and any constraint rules applied",
  "risk_flags": ["flag1", "flag2"],
  "reasoning": "step-by-step: R:R first, then position sizing, then portfolio limits, then constraints, then conclude"
}}"""
        raw = self._call(prompt, max_tokens=1000)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
