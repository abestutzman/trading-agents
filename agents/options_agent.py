from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class OptionsAgent(BaseAgent):
    name = "🎯 Options Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _nearest_strike(contracts: list, target: float) -> dict:
        if not contracts:
            return {}
        return min(contracts, key=lambda c: abs(c.get("strike", 0) - target))

    @staticmethod
    def _fmt_contract(c: dict, label: str) -> str:
        if not c:
            return f"  {label}: N/A"
        iv_pct = c.get("iv", 0) * 100
        return (
            f"  {label} (${c.get('strike', 0):.0f} strike): "
            f"mid=${c.get('mid', 0):.2f} | "
            f"Δ={c.get('delta', 0):+.2f}  "
            f"Γ={c.get('gamma', 0):.4f}  "
            f"Θ={c.get('theta', 0):.3f}  "
            f"V={c.get('vega', 0):.3f} | "
            f"IV={iv_pct:.1f}%"
        )

    # ── Main ─────────────────────────────────────────────────────────────────

    def analyze(self, data: dict) -> dict:
        trader_r   = data.get("trader_analysis", {})
        risk_r     = data.get("risk_analysis", {})
        chain_data = data.get("options_chain", {})
        ticker     = data.get("ticker", "?")
        price      = data.get("current_price", 0)

        action     = trader_r.get("action", "HOLD")
        confidence = float(trader_r.get("confidence", 0.5) or 0.5)
        stop       = trader_r.get("stop_loss")
        target     = trader_r.get("take_profit")

        # ── Graceful failure if chain unavailable ─────────────────────────────
        chain_error = chain_data.get("error") if chain_data else "No options chain provided"
        if chain_error:
            return {
                "agent":             self.name,
                "options_available": False,
                "error":             chain_error,
                "recommendation":    "none",
                "preferred":         "stock",
                "reasoning":         f"Options data unavailable: {chain_error}",
            }

        expiration  = chain_data.get("expiration", "N/A")
        dte         = chain_data.get("dte", 0)
        atm_iv      = float(chain_data.get("atm_iv", 0) or 0)
        calls       = chain_data.get("calls", [])
        puts        = chain_data.get("puts", [])

        # ── Select key contracts ──────────────────────────────────────────────
        atm_call = self._nearest_strike(calls, price)
        atm_put  = self._nearest_strike(puts,  price)
        otm_call = self._nearest_strike(calls, price * 1.05)   # ~5% OTM
        otm_put  = self._nearest_strike(puts,  price * 0.95)   # ~5% OTM

        chain_summary = "\n".join([
            self._fmt_contract(atm_call, "ATM Call"),
            self._fmt_contract(atm_put,  "ATM Put"),
            self._fmt_contract(otm_call, "OTM Call (+5%)"),
            self._fmt_contract(otm_put,  "OTM Put (-5%)"),
        ])

        # Position sizing
        pos_size_pct = float(risk_r.get("position_size_pct", 0.02) or 0.02)
        account      = float(data.get("portfolio", {}).get("account_value", 100000))
        dollar_risk  = account * pos_size_pct

        iv_label = (
            "LOW (<20%) — options are cheap, directional buys attractive"
            if atm_iv < 0.20 else
            "ELEVATED (20-35%) — spreads preferred to limit vega cost"
            if atm_iv < 0.35 else
            "HIGH (>35%) — options are expensive; selling premium or stock preferred"
        )

        prompt = f"""You are the Options Agent for an AI trading system.
Recommend the optimal options structure for {ticker} at ${price:.2f}.

═══ HEAD TRADER THESIS ═══
- Action:      {action}
- Confidence:  {confidence:.0%}
- Stop Loss:   ${stop or 'N/A'}
- Take Profit: ${target or 'N/A'}
- Time Horizon: {trader_r.get('time_horizon','?')}
- Reasoning:   {(trader_r.get('reasoning','') or '')[:250]}

═══ OPTIONS CHAIN (Tradier Sandbox) ═══
- Expiration:  {expiration} ({dte} DTE)
- ATM IV:      {atm_iv*100:.1f}% — {iv_label}

Key Contracts:
{chain_summary}

═══ POSITION SIZING ═══
- Max options budget: ${dollar_risk:,.0f}  ({pos_size_pct*100:.1f}% of ${account:,.0f})

STRUCTURE SELECTION RULES (apply in order):
1. High conviction LONG  (conf >= 0.70, action=LONG):
   - IV < 25%:  buy ATM call (outright)
   - IV 25-35%: bull call spread (buy ATM call, sell OTM call)
2. High conviction SHORT (conf >= 0.70, action=SHORT):
   - IV < 25%:  buy ATM put  (outright)
   - IV 25-35%: bear put spread (buy OTM put, sell ATM put)
3. Mixed / HOLD (conf < 0.70 or action=HOLD):
   - IV < 25%:  straddle (buy ATM call + ATM put) if expecting big move
   - IV >= 25%: recommend "none" (options too expensive for uncertain direction)
4. Already long stock:
   - covered call: sell OTM call to collect premium

PAYOFF CALCULATIONS (1 contract = 100 shares):
- Long call/put: max_loss = mid × 100; max_profit = "unlimited" (call) or (strike - 0) × 100 (put)
- Bull call spread: net_debit = (ATM_call_mid - OTM_call_mid); max_profit = (OTM_strike - ATM_strike - net_debit) × 100; max_loss = net_debit × 100
- Bear put spread: net_debit = (OTM_put_mid - ATM_put_mid); max_profit = (OTM_strike - ATM_strike - net_debit) × 100; max_loss = net_debit × 100
- Straddle: max_loss = (ATM_call_mid + ATM_put_mid) × 100

PREFERENCE: Options preferred when IV < 25% AND confidence >= 0.65.
Stock preferred when IV > 35%, confidence < 0.60, or DTE < 20.

Use actual strike/premium values from the chain above.
If a leg symbol is shown as blank, use the format: {ticker}YYMMDD[C/P]STRIKE.

Respond with JSON only:
{{
  "recommendation": "long_call" | "long_put" | "bull_call_spread" | "bear_put_spread" | "straddle" | "covered_call" | "none",
  "preferred": "options" | "stock",
  "expiration": "{expiration}",
  "dte": {dte},
  "atm_iv_pct": {atm_iv*100:.1f},
  "structure_detail": {{
    "leg1_symbol": "<option symbol>",
    "leg1_action": "buy" | "sell",
    "leg1_strike": <number>,
    "leg1_type": "call" | "put",
    "leg1_premium": <mid price>,
    "leg2_symbol": "<option symbol or null>",
    "leg2_action": "buy" | "sell" | null,
    "leg2_strike": <number or null>,
    "leg2_type": "call" | "put" | null,
    "leg2_premium": <number or null>
  }},
  "greeks": {{
    "delta": <net delta>,
    "gamma": <net gamma>,
    "theta": <net daily theta>,
    "vega":  <net vega>
  }},
  "cost_per_contract": <dollars>,
  "contracts_suggested": <int based on ${dollar_risk:,.0f} budget>,
  "max_profit": <dollars or "unlimited">,
  "max_loss": <dollars>,
  "breakeven": <price or [up_price, down_price] for straddle>,
  "options_vs_stock": "one sentence comparing risk/reward of options vs outright stock",
  "reasoning": "cite IV level, confidence, structure selection logic"
}}"""

        raw    = self._call(prompt, max_tokens=450)
        result = self._parse_json(raw)
        result["agent"]             = self.name
        result["options_available"] = True

        # Attach raw contract data for UI display
        result["atm_call"] = atm_call
        result["atm_put"]  = atm_put
        result["atm_iv"]   = atm_iv
        return result
