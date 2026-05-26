try:
    import alpaca_trade_api as tradeapi
    _ALPACA_AVAILABLE = True
except ImportError:
    tradeapi = None
    _ALPACA_AVAILABLE = False

from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL


class PortfolioManager:
    def __init__(self):
        self._api = None
        if _ALPACA_AVAILABLE and ALPACA_API_KEY and ALPACA_SECRET_KEY:
            try:
                self._api = tradeapi.REST(
                    key_id=ALPACA_API_KEY,
                    secret_key=ALPACA_SECRET_KEY,
                    base_url=ALPACA_BASE_URL,
                )
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        return self._api is not None

    # ── Account ───────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        if not self._api:
            return {"account_value": 100000, "buying_power": 100000,
                    "cash": 100000, "connected": False}
        try:
            acc = self._api.get_account()
            return {
                "account_value": float(acc.portfolio_value),
                "buying_power":  float(acc.buying_power),
                "cash":          float(acc.cash),
                "day_trade_count": int(acc.daytrade_count),
                "connected": True,
            }
        except Exception as e:
            return {"account_value": 100000, "buying_power": 100000,
                    "cash": 100000, "connected": False, "error": str(e)}

    # ── Positions ─────────────────────────────────────────────────────────────

    def get_positions(self) -> list:
        if not self._api:
            return []
        try:
            positions = self._api.list_positions()
            result = []
            for p in positions:
                result.append({
                    "symbol":            p.symbol,
                    "qty":               float(p.qty),
                    "side":              p.side,
                    "avg_entry":         float(p.avg_entry_price),
                    "current_price":     float(p.current_price),
                    "market_value":      float(p.market_value),
                    "unrealized_pnl":    float(p.unrealized_pl),
                    "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                })
            return result
        except Exception:
            return []

    def get_portfolio_summary(self) -> dict:
        account   = self.get_account()
        positions = self.get_positions()
        acc_value = account.get("account_value", 100000)

        long_val  = sum(p["market_value"] for p in positions if p["side"] == "long")
        short_val = sum(abs(p["market_value"]) for p in positions if p["side"] == "short")

        return {
            "account_value":        acc_value,
            "buying_power":         account.get("buying_power", 0),
            "cash":                 account.get("cash", 0),
            "open_positions":       len(positions),
            "long_exposure_pct":    round(long_val / acc_value * 100, 1) if acc_value else 0,
            "short_exposure_pct":   round(short_val / acc_value * 100, 1) if acc_value else 0,
            "positions":            positions,
            "daily_pnl_pct":        0.0,
            "existing_exposure_pct": 0.0,
        }

    def get_ticker_exposure(self, ticker: str, portfolio: dict) -> float:
        """Return existing % exposure to a ticker."""
        positions = portfolio.get("positions", [])
        for p in positions:
            if p["symbol"].upper() == ticker.upper():
                acc = portfolio.get("account_value", 100000)
                return abs(p["market_value"]) / acc * 100 if acc else 0
        return 0.0

    # ── Orders ────────────────────────────────────────────────────────────────

    def submit_bracket_order(self, ticker: str, action: str, quantity: int,
                              stop_loss: float, take_profit: float) -> dict:
        if not self._api:
            return {"status": "error", "error": "Alpaca not connected",
                    "order_id": None}
        if quantity <= 0:
            return {"status": "error", "error": "Invalid quantity", "order_id": None}

        side = "buy" if action == "LONG" else "sell"
        try:
            order = self._api.submit_order(
                symbol=ticker,
                qty=quantity,
                side=side,
                type="market",
                time_in_force="gtc",
                order_class="bracket",
                stop_loss={"stop_price": round(stop_loss, 2)},
                take_profit={"limit_price": round(take_profit, 2)},
            )
            return {
                "status":   order.status,
                "order_id": order.id,
                "symbol":   order.symbol,
                "qty":      float(order.qty),
                "side":     order.side,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "order_id": None}

    def cancel_order(self, order_id: str) -> bool:
        if not self._api:
            return False
        try:
            self._api.cancel_order(order_id)
            return True
        except Exception:
            return False

    def close_position(self, ticker: str) -> dict:
        if not self._api:
            return {"status": "error", "error": "Not connected"}
        try:
            self._api.close_position(ticker)
            return {"status": "submitted"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_orders(self, status: str = "all", limit: int = 50) -> list:
        if not self._api:
            return []
        try:
            orders = self._api.list_orders(status=status, limit=limit)
            return [
                {
                    "id":         o.id,
                    "symbol":     o.symbol,
                    "side":       o.side,
                    "qty":        float(o.qty),
                    "status":     o.status,
                    "created_at": str(o.created_at),
                    "filled_avg": float(o.filled_avg_price) if o.filled_avg_price else None,
                }
                for o in orders
            ]
        except Exception:
            return []
