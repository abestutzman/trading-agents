import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
FINNHUB_API_KEY    = os.getenv("FINNHUB_API_KEY", "")
ALPACA_API_KEY     = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY  = os.getenv("ALPACA_SECRET_KEY", "")
NEWS_API_KEY       = os.getenv("NEWS_API_KEY", "")
POLYGON_API_KEY    = os.getenv("POLYGON_API_KEY", "")
FRED_API_KEY       = os.getenv("FRED_API_KEY", "")
ALPHA_VANTAGE_KEY  = os.getenv("ALPHA_VANTAGE_KEY", "")

ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

# ── Tradier Sandbox ──────────────────────────────────────────────────────────
TRADIER_SANDBOX_TOKEN = os.getenv("TRADIER_SANDBOX_TOKEN", "")
TRADIER_SANDBOX_URL   = os.getenv("TRADIER_SANDBOX_URL", "https://sandbox.tradier.com")

# ── Claude Models ────────────────────────────────────────────────────────────
HAIKU_MODEL = "claude-haiku-4-5-20251001"
OPUS_MODEL  = "claude-opus-4-7"          # latest Opus

# ── S&P 50 Tickers (top 50 by market cap) ───────────────────────────────────
SP50_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
    "GOOGL", "BRK-B", "LLY",  "JPM",  "AVGO",
    "TSLA", "UNH",  "V",    "XOM",  "MA",
    "JNJ",  "PG",   "COST", "HD",   "MRK",
    "ABBV", "CRM",  "CVX",  "BAC",  "NFLX",
    "AMD",  "WMT",  "KO",   "PEP",  "TMO",
    "ACN",  "CSCO", "MCD",  "ADBE", "NOW",
    "LIN",  "ABT",  "TXN",  "DHR",  "NEE",
    "PM",   "ORCL", "AMGN", "HON",  "UNP",
    "MS",   "QCOM", "IBM",  "GE",   "CAT",
]

# ── Sector ETF Proxies ───────────────────────────────────────────────────────
SECTOR_ETFS = {
    "Technology":             "XLK",
    "Financials":             "XLF",
    "Healthcare":             "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples":       "XLP",
    "Energy":                 "XLE",
    "Industrials":            "XLI",
    "Materials":              "XLB",
    "Utilities":              "XLU",
    "Real Estate":            "XLRE",
    "Communication Services": "XLC",
}

SECTOR_TICKER_MAP = {
    "AAPL": "Technology",    "MSFT": "Technology",  "NVDA": "Technology",
    "AVGO": "Technology",    "AMD":  "Technology",  "CRM":  "Technology",
    "ADBE": "Technology",    "NOW":  "Technology",  "CSCO": "Technology",
    "TXN":  "Technology",    "ORCL": "Technology",  "IBM":  "Technology",
    "QCOM": "Technology",    "ACN":  "Technology",
    "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "HD":   "Consumer Discretionary", "MCD":  "Consumer Discretionary",
    "NKE":  "Consumer Discretionary",
    "META": "Communication Services", "GOOGL": "Communication Services",
    "NFLX": "Communication Services",
    "JPM":  "Financials",    "BAC":  "Financials",  "V":    "Financials",
    "MA":   "Financials",    "MS":   "Financials",
    "LLY":  "Healthcare",    "UNH":  "Healthcare",  "JNJ":  "Healthcare",
    "MRK":  "Healthcare",    "ABBV": "Healthcare",  "TMO":  "Healthcare",
    "DHR":  "Healthcare",    "ABT":  "Healthcare",  "AMGN": "Healthcare",
    "XOM":  "Energy",        "CVX":  "Energy",
    "PG":   "Consumer Staples", "KO": "Consumer Staples",
    "PEP":  "Consumer Staples", "WMT": "Consumer Staples",
    "COST": "Consumer Staples", "PM":  "Consumer Staples",
    "BRK-B": "Financials",
    "GE":   "Industrials",   "HON":  "Industrials", "UNP":  "Industrials",
    "CAT":  "Industrials",
    "LIN":  "Materials",
    "NEE":  "Utilities",
}

# ── Risk Controls ────────────────────────────────────────────────────────────
DEFAULT_MAX_POSITION_PCT  = 0.05   # 5% of portfolio per trade
DEFAULT_DAILY_LOSS_LIMIT  = 0.02   # stop trading if down 2% on the day
DEFAULT_MAX_POSITIONS     = 10     # max concurrent open positions
DEFAULT_COOLDOWN_MINUTES  = 60     # minutes between trades on the same ticker
DEFAULT_STOP_LOSS_PCT     = 0.02   # 2% default stop loss
DEFAULT_TAKE_PROFIT_PCT   = 0.04   # 4% default take profit (2:1 R/R)
