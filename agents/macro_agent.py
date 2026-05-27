from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class MacroAgent(BaseAgent):
    name = "Macro Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        macro   = data.get("macro", {})
        econ_cal = data.get("economic_calendar", {})

        # Economic calendar context
        nearest_event = econ_cal.get("nearest_event", {})
        cal_name      = nearest_event.get("name", "none scheduled")
        cal_days      = nearest_event.get("days_until", "N/A")
        within_5d     = econ_cal.get("within_5_days", False)
        macro_risk    = "HIGH — major event within 5 days" if within_5d else "normal"

        # FRED real data fields
        fed_funds  = macro.get("fed_funds_rate", "N/A")
        cpi_yoy    = macro.get("cpi_yoy", "N/A")
        unemp      = macro.get("unemployment", "N/A")
        pce_yoy    = macro.get("pce_yoy", "N/A")
        gdp_growth = macro.get("gdp_growth", "N/A")

        prompt = f"""Analyze the current macroeconomic environment for trading {data.get('ticker', 'this asset')}.

Think through each section step by step before forming your final view.

═══ REAL-TIME FRED DATA ═══
- Fed Funds Rate (FRED):       {fed_funds}%
- CPI YoY Inflation (FRED):    {cpi_yoy}%
- Unemployment Rate (FRED):    {unemp}%
- PCE YoY (FRED):              {pce_yoy}%
- GDP Growth (FRED):           {gdp_growth}%

═══ MARKET PROXIES ═══
- SPY 1-month return:          {macro.get('spy_1m', 'N/A')}%
- QQQ 1-month return:          {macro.get('qqq_1m', 'N/A')}%
- VIX current level:           {macro.get('vix', 'N/A')}
- US 10Y yield (market):       {macro.get('ten_year_yield', 'N/A')}%
- DXY (USD index) trend:       {macro.get('dxy_trend', 'N/A')}
- Gold 1-month return:         {macro.get('gold_1m', 'N/A')}%
- Market breadth (% > 200MA):  {macro.get('breadth', 'N/A')}%

═══ ECONOMIC CALENDAR ═══
- Nearest event: {cal_name} (in {cal_days} days)
- Event-driven macro risk: {macro_risk}

CONFIDENCE CALIBRATION: Your confidence score must be honest. 0.70 means you expect to be correct 70% of the time.
Do not inflate scores — if the macro picture is mixed or uncertain, reflect that with a lower confidence.

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "market_phase": "risk-on" | "risk-off" | "transitioning",
  "rate_environment": "restrictive" | "neutral" | "accommodative",
  "inflation_posture": "elevated" | "normalizing" | "low",
  "key_risks": ["risk1", "risk2"],
  "tailwinds": ["tailwind1"],
  "event_risk": "high" | "medium" | "low",
  "reasoning": "step-by-step explanation: first assess rates/inflation, then growth signals, then market sentiment, then conclude"
}}"""
        raw = self._call(prompt, max_tokens=600)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
