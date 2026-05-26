from .base_agent import BaseAgent, fmt
from config import HAIKU_MODEL


class TechnicalAgent(BaseAgent):
    name = "Technical Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        t = data.get("technicals", {})
        price = data.get("current_price", 0)

        prompt = f"""Perform technical analysis on {data.get('ticker', 'this stock')}.

Technical Indicators (computed from real market data):
- Current Price:        ${fmt(price)}
- SMA 50:               ${fmt(t.get('sma_50'))}  |  Price vs SMA50:  {fmt(t.get('pct_vs_sma50'))}%
- SMA 200:              ${fmt(t.get('sma_200'))}  |  Price vs SMA200: {fmt(t.get('pct_vs_sma200'))}%
- Golden/Death Cross:   {t.get('cross_signal', 'N/A')}
- RSI (14):             {fmt(t.get('rsi'))}
- MACD Line:            {fmt(t.get('macd'), '.4f')}  |  Signal: {fmt(t.get('macd_signal'), '.4f')}  |  Hist: {fmt(t.get('macd_hist'), '.4f')}
- Bollinger Upper:      ${fmt(t.get('bb_upper'))}  |  Mid: ${fmt(t.get('bb_mid'))}  |  Lower: ${fmt(t.get('bb_lower'))}
- BB %B:                {fmt(t.get('bb_pct'), '.3f')}
- VWAP (prev day):      ${fmt(t.get('vwap'))}
- Volume vs 20d avg:    {fmt(t.get('volume_ratio'))}x
- Avg Daily Volume:     {fmt(t.get('avg_volume'), '.0f')}
- ATR (14):             ${fmt(t.get('atr'))}
- 1-day return:         {fmt(t.get('ret_1d'))}%
- 5-day return:         {fmt(t.get('ret_5d'))}%
- 20-day return:        {fmt(t.get('ret_20d'))}%
- 20-day Support:       ${fmt(t.get('support'))}
- 20-day Resistance:    ${fmt(t.get('resistance'))}

Data source: {t.get('data_source', 'yfinance')}

Use ONLY the real values provided above. Do not estimate or fabricate any indicator values.
Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "trend": "uptrend" | "downtrend" | "sideways",
  "momentum": "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell",
  "rsi_signal": "overbought" | "neutral" | "oversold",
  "macd_signal": "bullish_crossover" | "bearish_crossover" | "bullish" | "bearish" | "neutral",
  "bb_signal": "near_upper" | "near_lower" | "mid" | "squeeze",
  "key_levels": {{"support": <number_or_null>, "resistance": <number_or_null>}},
  "entry_zone": {{"low": <number_or_null>, "high": <number_or_null>}},
  "reasoning": "brief explanation citing specific indicator values"
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
