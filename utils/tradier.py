"""
Tradier Sandbox API client.

Provides:
  get_options_chain(ticker)       — nearest 30-45 DTE expiration, all strikes + greeks
  submit_option_order(...)        — limit order at mid price of bid/ask
  get_tradier_account_id()        — first account from sandbox profile
  get_option_positions()          — open options positions
  get_option_quote(symbol)        — current quote for open-position P&L
"""

import os
import requests
from datetime import datetime, date
from typing import Optional

from config import TRADIER_SANDBOX_TOKEN, TRADIER_SANDBOX_URL


# ── Internal helpers ─────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TRADIER_SANDBOX_TOKEN}",
        "Accept":        "application/json",
    }


def _get(path: str, params: dict | None = None) -> dict:
    if not TRADIER_SANDBOX_TOKEN:
        return {"error": "TRADIER_SANDBOX_TOKEN not configured"}
    url = f"{TRADIER_SANDBOX_URL.rstrip('/')}{path}"
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _post(path: str, data: dict) -> dict:
    if not TRADIER_SANDBOX_TOKEN:
        return {"error": "TRADIER_SANDBOX_TOKEN not configured"}
    url = f"{TRADIER_SANDBOX_URL.rstrip('/')}{path}"
    try:
        r = requests.post(url, headers=_headers(), data=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Expirations ──────────────────────────────────────────────────────────────

def get_options_expirations(ticker: str) -> list:
    resp = _get("/v1/markets/options/expirations", {"symbol": ticker, "includeAllRoots": "true"})
    exps = resp.get("expirations", {})
    if isinstance(exps, dict):
        dates = exps.get("date", []) or []
        return dates if isinstance(dates, list) else [dates]
    return []


def _pick_nearest_dte(expirations: list, min_dte: int = 25, max_dte: int = 50) -> Optional[str]:
    """Pick the expiration closest to 30-45 DTE within the min/max window."""
    today = date.today()
    candidates = []
    for exp in expirations:
        try:
            d   = datetime.strptime(exp, "%Y-%m-%d").date()
            dte = (d - today).days
            candidates.append((dte, exp))
        except ValueError:
            continue
    # Preferred window
    window = [(dte, exp) for dte, exp in candidates if min_dte <= dte <= max_dte]
    if window:
        # Pick the one closest to 37 DTE (midpoint of 25–50)
        return min(window, key=lambda x: abs(x[0] - 37))[1]
    # Broadened fallback: any DTE >= 20
    fallback = sorted([(dte, exp) for dte, exp in candidates if dte >= 20], key=lambda x: x[0])
    return fallback[0][1] if fallback else (candidates[0][1] if candidates else None)


# ── Options Chain ────────────────────────────────────────────────────────────

def get_options_chain(ticker: str) -> dict:
    """
    Fetch the full options chain for the nearest 30-45 DTE expiration.

    Returns:
      {
        "expiration": "yyyy-mm-dd",
        "dte": int,
        "calls": [contract_dict, ...],
        "puts":  [contract_dict, ...],
        "atm_iv": float,      # approximate ATM implied vol as a decimal (0.25 = 25%)
        "error": None | str,
      }

    Each contract_dict has:
      symbol, strike, option_type, bid, ask, mid, last, volume,
      open_interest, delta, gamma, theta, vega, iv
    """
    if not TRADIER_SANDBOX_TOKEN:
        return {"error": "TRADIER_SANDBOX_TOKEN not configured"}

    expirations = get_options_expirations(ticker)
    if not expirations:
        return {"error": f"No options expirations found for {ticker}"}

    exp = _pick_nearest_dte(expirations)
    if not exp:
        return {"error": f"No 25-50 DTE expiration available for {ticker}"}

    today = date.today()
    dte   = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days

    resp = _get("/v1/markets/options/chains", {
        "symbol":     ticker,
        "expiration": exp,
        "greeks":     "true",
    })
    if "error" in resp:
        return {"error": resp["error"], "expiration": exp, "dte": dte}

    raw = resp.get("options", {})
    if isinstance(raw, dict):
        raw = raw.get("option", []) or []
    if isinstance(raw, dict):   # single option returned as dict, not list
        raw = [raw]
    if not raw:
        return {"error": f"Empty chain returned for {ticker} exp {exp}", "expiration": exp, "dte": dte}

    def _clean(o: dict) -> dict:
        greeks = o.get("greeks") or {}
        bid    = float(o.get("bid",  0) or 0)
        ask    = float(o.get("ask",  0) or 0)
        return {
            "symbol":        o.get("symbol", ""),
            "strike":        float(o.get("strike", 0) or 0),
            "option_type":   o.get("option_type", "").lower(),   # "call" | "put"
            "bid":           bid,
            "ask":           ask,
            "mid":           round((bid + ask) / 2, 2),
            "last":          float(o.get("last",  0) or 0),
            "volume":        int(o.get("volume",       0) or 0),
            "open_interest": int(o.get("open_interest", 0) or 0),
            "delta":         float(greeks.get("delta",  0) or 0),
            "gamma":         float(greeks.get("gamma",  0) or 0),
            "theta":         float(greeks.get("theta",  0) or 0),
            "vega":          float(greeks.get("vega",   0) or 0),
            "iv":            float(greeks.get("smv_vol", 0) or greeks.get("mid_iv", 0) or 0),
        }

    contracts = [_clean(o) for o in raw]
    calls = sorted([c for c in contracts if c["option_type"] == "call"], key=lambda x: x["strike"])
    puts  = sorted([c for c in contracts if c["option_type"] == "put"],  key=lambda x: x["strike"])

    # ATM IV: average of near-ATM calls with |delta| between 0.40 and 0.60
    atm_ivs = [c["iv"] for c in calls if 0.35 <= abs(c["delta"]) <= 0.65 and c["iv"] > 0]
    atm_iv  = sum(atm_ivs) / len(atm_ivs) if atm_ivs else 0.0

    return {
        "expiration": exp,
        "dte":        dte,
        "calls":      calls,
        "puts":       puts,
        "atm_iv":     round(atm_iv, 4),
        "error":      None,
    }


# ── Order Submission ─────────────────────────────────────────────────────────

def get_tradier_account_id() -> Optional[str]:
    """Return the first sandbox account number from the profile."""
    resp    = _get("/v1/user/profile")
    profile = resp.get("profile", {})
    accts   = profile.get("account", [])
    if isinstance(accts, dict):
        accts = [accts]
    if not accts:
        return None
    return str(accts[0].get("account_number", ""))


def submit_option_order(
    ticker: str,
    option_symbol: str,
    side: str,          # "buy_to_open" | "sell_to_open" | "buy_to_close" | "sell_to_close"
    quantity: int,
    price: float,       # limit price — use mid of bid/ask
) -> dict:
    """
    Submit a day-limit options order to Tradier sandbox.
    Returns {"status": "ok"|"error", "order_id": str, ...}
    """
    if not TRADIER_SANDBOX_TOKEN:
        return {"status": "error", "error": "TRADIER_SANDBOX_TOKEN not configured"}

    acct_id = get_tradier_account_id()
    if not acct_id:
        return {"status": "error", "error": "Could not retrieve Tradier account ID"}

    data = {
        "class":          "option",
        "symbol":         ticker,
        "option_symbol":  option_symbol,
        "side":           side,
        "quantity":       str(quantity),
        "type":           "limit",
        "duration":       "day",
        "price":          f"{price:.2f}",
    }
    resp  = _post(f"/v1/accounts/{acct_id}/orders", data)
    if "error" in resp:
        return {"status": "error", "error": resp["error"]}

    order = resp.get("order", {})
    return {
        "status":        order.get("status", "ok"),
        "order_id":      str(order.get("id", "")),
        "option_symbol": option_symbol,
        "side":          side,
        "quantity":      quantity,
        "limit_price":   price,
    }


# ── Open Positions ───────────────────────────────────────────────────────────

def get_option_positions() -> list:
    """
    Return open options positions from Tradier sandbox.
    Filters out equity positions by symbol length heuristic.
    """
    if not TRADIER_SANDBOX_TOKEN:
        return []

    acct_id = get_tradier_account_id()
    if not acct_id:
        return []

    resp = _get(f"/v1/accounts/{acct_id}/positions")
    raw  = resp.get("positions", {})
    if not raw or raw == "null":
        return []

    positions = raw.get("position", []) or []
    if isinstance(positions, dict):
        positions = [positions]

    result = []
    for p in positions:
        sym = str(p.get("symbol", ""))
        # Option symbols are ≥ 15 chars and contain embedded date digits.
        # Equity symbols are typically 1–5 chars.
        if len(sym) >= 10 and any(ch.isdigit() for ch in sym):
            result.append({
                "symbol":        sym,
                "quantity":      int(p.get("quantity",    0)),
                "cost_basis":    float(p.get("cost_basis", 0) or 0),
                "date_acquired": p.get("date_acquired", ""),
            })
    return result


def get_option_quote(option_symbol: str) -> dict:
    """Return current bid/ask/mid/last/greeks for a single option symbol."""
    resp   = _get("/v1/markets/quotes", {"symbols": option_symbol, "greeks": "true"})
    quotes = resp.get("quotes", {})
    if not quotes:
        return {}
    quote = quotes.get("quote", {})
    if isinstance(quote, list):
        quote = quote[0] if quote else {}
    if not quote:
        return {}
    greeks = quote.get("greeks") or {}
    bid    = float(quote.get("bid",  0) or 0)
    ask    = float(quote.get("ask",  0) or 0)
    return {
        "symbol": option_symbol,
        "bid":    bid,
        "ask":    ask,
        "mid":    round((bid + ask) / 2, 2),
        "last":   float(quote.get("last", 0) or 0),
        "delta":  float(greeks.get("delta",   0) or 0),
        "iv":     float(greeks.get("smv_vol", 0) or greeks.get("mid_iv", 0) or 0),
    }
