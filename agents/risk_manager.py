from .base_agent import BaseAgent
from config import OPUS_MODEL


class RiskManager(BaseAgent):
    name = "Risk Manager"

    def __init__(self):
        super().__init__(OPUS_MODEL)

    def analyze(self, data: dict) -> dict:
        bull   = data.get("bull_analysis", {})
        bear   = data.get("bear_analysis", {})
        tech   = data.get("technical_analysis", {})
        price  = data.get("current_price", 0)
        ticker = data.get("ticker", "?")

        portfolio = data.get("portfolio", {})
        account_value = portfolio.get("account_value", 100000)
        open_positions = portfolio.get("open_positions", 0)
        daily_pnl_pct = portfolio.get("daily_pnl_pct", 0)
        existing_exposure = portfolio.get("existing_exposure_pct", 0)

        risk_cfg = data.get("risk_config", {})
        max_pos_pct    = risk_cfg.get("max_position_pct", 0.05)
        daily_loss_lim = risk_cfg.get("daily_loss_limit", 0.02)
        max_positions  = risk_cfg.get("max_positions", 10)
        cooldown_mins  = data.get("cooldown_remaining", None)

        prompt = f"""You are the Risk Manager for an algorithmic trading system. Evaluate the risk of trading {ticker} at ${price}.

Bull Case Summary: {bull.get('bull_thesis','')} | Upside target: {bull.get('upside_target','?')} | Confidence: {bull.get('confidence','?')}
Bear Case Summary: {bear.get('bear_thesis','')} | Downside target: {bear.get('downside_target','?')} | Confidence: {bear.get('confidence','?')}
Technical Key Levels: Support {tech.get('key_levels',{}).get('support','?')} | Resistance {tech.get('key_levels',{}).get('resistance','?')}
ATR: {data.get('technicals',{}).get('atr','N/A')}

Portfolio State:
- Account Value: ${account_value:,.0f}
- Open Positions: {open_positions}/{max_positions}
- Today's P&L: {daily_pnl_pct:.2f}% (limit: -{daily_loss_lim*100:.1f}%)
- Existing {ticker} Exposure: {existing_exposure:.1f}%
- Cooldown Remaining: {f'{cooldown_mins:.0f} min' if cooldown_mins else 'None'}

Risk Rules:
- Max position size: {max_pos_pct*100:.0f}% of portfolio
- Daily loss limit: {daily_loss_lim*100:.1f}%
- Max concurrent positions: {max_positions}

Assess risk thoroughly and respond with JSON only:
{{
  "approved": true | false,
  "veto_reason": null | "reason if vetoed",
  "risk_score": 0.0-1.0,
  "position_size_pct": 0.0-{max_pos_pct},
  "recommended_stop_loss": <price>,
  "recommended_take_profit": <price>,
  "risk_reward_ratio": <float>,
  "max_loss_dollars": <float>,
  "sizing_rationale": "why this size",
  "risk_flags": ["flag1", "flag2"],
  "reasoning": "comprehensive risk assessment"
}}"""
        raw = self._call(prompt, max_tokens=1000)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
