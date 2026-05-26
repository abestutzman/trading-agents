from .base_agent import BaseAgent
from config import HAIKU_MODEL


class TechnicalAgent(BaseAgent):
    name = "Technical Agent"

    def __init__(self):
        super().__init__(HAIKU_MODEL)

    def analyze(self, data: dict) -> dict:
        t = data.get("technicals", {})
        prompt = f"""Perform technical analysis on {data.get('ticker', 'this stock')}.

Technical Indicators:
- Current Price: ${data.get('current_price', 'N/A')}
- SMA 50: ${t.get('sma_50', 'N/A')} | Price vs SMA50: {t.get('pct_vs_sma50', 'N/A')}%
- SMA 200: ${t.get('sma_200', 'N/A')} | Price vs SMA200: {t.get('pct_vs_sma200', 'N/A')}%
- Golden/Death Cross: {t.get('cross_signal', 'N/A')}
- RSI (14): {t.get('rsi', 'N/A')}
- MACD Line: {t.get('macd', 'N/A')} | Signal: {t.get('macd_signal', 'N/A')} | Hist: {t.get('macd_hist', 'N/A')}
- Bollinger Upper: ${t.get('bb_upper', 'N/A')} | Lower: ${t.get('bb_lower', 'N/A')} | Mid: ${t.get('bb_mid', 'N/A')}
- BB %B: {t.get('bb_pct', 'N/A')}
- Volume vs 20-day avg: {t.get('volume_ratio', 'N/A')}x
- ATR (14): ${t.get('atr', 'N/A')}
- 1-day return: {t.get('ret_1d', 'N/A')}%
- 5-day return: {t.get('ret_5d', 'N/A')}%
- 20-day return: {t.get('ret_20d', 'N/A')}%
- Support levels: {t.get('support', 'N/A')}
- Resistance levels: {t.get('resistance', 'N/A')}

Respond with JSON only:
{{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": 0.0-1.0,
  "trend": "uptrend" | "downtrend" | "sideways",
  "momentum": "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell",
  "rsi_signal": "overbought" | "neutral" | "oversold",
  "macd_signal": "bullish_crossover" | "bearish_crossover" | "bullish" | "bearish" | "neutral",
  "bb_signal": "near_upper" | "near_lower" | "mid" | "squeeze",
  "key_levels": {{"support": <number>, "resistance": <number>}},
  "entry_zone": {{"low": <number>, "high": <number>}},
  "reasoning": "brief explanation"
}}"""
        raw = self._call(prompt)
        result = self._parse_json(raw)
        result["agent"] = self.name
        return result
