from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class TechnicalAgent(BaseAgent):
    name = "Technical Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        t     = data.get("technicals", {})
        price = data.get("current_price", 0)
        rs    = data.get("relative_strength", {})

        # ATR stops
        atr_stop_long  = t.get("atr_stop_long")
        atr_stop_short = t.get("atr_stop_short")
        atr_risk_pct   = t.get("atr_risk_pct")

        # 52-week range
        range_52w_pct  = t.get("range_52w_pct")
        near_52w_high  = t.get("near_52w_high", False)
        near_52w_low   = t.get("near_52w_low", False)
        w52_note = "near 52-week HIGH (resistance)" if near_52w_high else \
                   "near 52-week LOW (support/breakdown zone)" if near_52w_low else "mid-range"

        # Consecutive days momentum / mean reversion
        streak         = t.get("streak", 0)
        streak_dir     = t.get("streak_direction", "neutral")
        mr_risk        = t.get("mean_reversion_risk", False)
        streak_note    = f"{abs(streak)} consecutive {streak_dir} days" if streak else "no clear streak"

        # Price gaps
        last_gap       = t.get("last_gap", {})
        gap_note       = f"{last_gap.get('type','none')} on {last_gap.get('date','?')} ({fmt(last_gap.get('gap_pct'))}%)" \
                         if last_gap else "no recent gap"

        # Volume signal
        vol_signal     = t.get("volume_signal", "N/A")

        # Relative strength
        rs_1m_vs_spy   = rs.get("rs_1m_vs_spy", "N/A")
        rs_3m_vs_spy   = rs.get("rs_3m_vs_spy", "N/A")
        rs_1m_vs_sector = rs.get("rs_1m_vs_sector", "N/A")

        prompt = f"""Perform technical analysis on {data.get('ticker', 'this stock')}.

Think through each indicator group step by step before forming your final view.

═══ PRICE & TREND ═══
- Current Price:        ${fmt(price)}
- SMA 50:               ${fmt(t.get('sma_50'))}  |  Price vs SMA50:  {fmt(t.get('pct_vs_sma50'))}%
- SMA 200:              ${fmt(t.get('sma_200'))}  |  Price vs SMA200: {fmt(t.get('pct_vs_sma200'))}%
- Golden/Death Cross:   {t.get('cross_signal', 'N/A')}

═══ MOMENTUM ═══
- RSI (14):             {fmt(t.get('rsi'))}
- MACD Line:            {fmt(t.get('macd'), '.4f')}  |  Signal: {fmt(t.get('macd_signal'), '.4f')}  |  Hist: {fmt(t.get('macd_hist'), '.4f')}
- 1-day return:         {fmt(t.get('ret_1d'))}%
- 5-day return:         {fmt(t.get('ret_5d'))}%
- 20-day return:        {fmt(t.get('ret_20d'))}%
- Streak:               {streak_note}{" — MEAN REVERSION RISK" if mr_risk else ""}

═══ VOLATILITY & BANDS ═══
- Bollinger Upper:      ${fmt(t.get('bb_upper'))}  |  Mid: ${fmt(t.get('bb_mid'))}  |  Lower: ${fmt(t.get('bb_lower'))}
- BB %B:                {fmt(t.get('bb_pct'), '.3f')}
- ATR (14):             ${fmt(t.get('atr'))}
- ATR Stop (Long):      ${fmt(atr_stop_long)}  |  ATR Stop (Short): ${fmt(atr_stop_short)}
- ATR Risk %:           {fmt(atr_risk_pct)}%

═══ VOLUME ═══
- Volume Signal:        {vol_signal}
- Volume vs 20d avg:    {fmt(t.get('volume_ratio'))}x
- VWAP (prev day):      ${fmt(t.get('vwap'))}

═══ STRUCTURE ═══
- 52-week Range %:      {fmt(range_52w_pct)}% ({w52_note})
- 20-day Support:       ${fmt(t.get('support'))}
- 20-day Resistance:    ${fmt(t.get('resistance'))}
- Recent Gap:           {gap_note}

═══ RELATIVE STRENGTH ═══
- 1m vs SPY:            {fmt(rs_1m_vs_spy)}%  |  3m vs SPY: {fmt(rs_3m_vs_spy)}%
- 1m vs Sector:         {fmt(rs_1m_vs_sector)}%

Data source: {t.get('data_source', 'yfinance')}

Use ONLY the real values provided. Do not estimate or fabricate values.
Prefer ATR-based stops over fixed-percentage stops in your key_levels output.

CONFIDENCE CALIBRATION: Be honest — if signals are mixed, say 0.5–0.6. Reserve 0.8+ for very clear setups.

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "trend": "uptrend" | "downtrend" | "sideways",
  "momentum": "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell",
  "rsi_signal": "overbought" | "neutral" | "oversold",
  "macd_signal": "bullish_crossover" | "bearish_crossover" | "bullish" | "bearish" | "neutral",
  "bb_signal": "near_upper" | "near_lower" | "mid" | "squeeze",
  "volume_confirmation": true | false,
  "mean_reversion_risk": true | false,
  "key_levels": {{
    "support": <number_or_null>,
    "resistance": <number_or_null>,
    "atr_stop_long": <number_or_null>,
    "atr_stop_short": <number_or_null>
  }},
  "entry_zone": {{"low": <number_or_null>, "high": <number_or_null>}},
  "reasoning": "step-by-step: trend first, then momentum, then structure, then volume — cite specific values"
}}"""
        raw = self._call(prompt, max_tokens=600)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
