import requests
from datetime import datetime
from config.settings import settings
from brokers.base import BrokerAdapter, Bar, Position, OrderResult, OrderSide, OrderStatus


class AlpacaBroker(BrokerAdapter):
    name = "alpaca"

    def __init__(self):
        self.base_url = settings.ALPACA_BASE_URL
        self.data_url = "https://data.alpaca.markets"
        self.headers = {
            "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
        }

    def get_account_equity(self) -> float:
        r = requests.get(f"{self.base_url}/v2/account", headers=self.headers, timeout=10)
        r.raise_for_status()
        return float(r.json()["equity"])

    def get_positions(self) -> list[Position]:
        r = requests.get(f"{self.base_url}/v2/positions", headers=self.headers, timeout=10)
        r.raise_for_status()
        out = []
        for p in r.json():
            out.append(Position(
                symbol=p["symbol"],
                qty=float(p["qty"]),
                avg_entry_price=float(p["avg_entry_price"]),
                current_price=float(p["current_price"]),
                market_value=float(p["market_value"]),
                unrealized_pnl=float(p["unrealized_pl"]),
            ))
        return out

    def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 200) -> list[Bar]:
        params = {"timeframe": timeframe, "limit": limit, "adjustment": "raw"}
        r = requests.get(
            f"{self.data_url}/v2/stocks/{symbol}/bars",
            headers=self.headers, params=params, timeout=10,
        )
        r.raise_for_status()
        bars = r.json().get("bars", [])
        return [
            Bar(
                timestamp=datetime.fromisoformat(b["t"].replace("Z", "+00:00")),
                open=b["o"], high=b["h"], low=b["l"], close=b["c"], volume=b["v"],
            )
            for b in bars
        ]

    def get_last_price(self, symbol: str) -> float:
        r = requests.get(
            f"{self.data_url}/v2/stocks/{symbol}/trades/latest",
            headers=self.headers, timeout=10,
        )
        r.raise_for_status()
        return float(r.json()["trade"]["p"])

    def place_order(self, symbol: str, side: OrderSide, qty: float, order_type: str = "market") -> OrderResult:
        if not settings.ORDERS_ENABLED:
            return OrderResult(
                order_id="", symbol=symbol, side=side, qty=qty,
                status=OrderStatus.REJECTED, message="ORDERS_ENABLED=False, 주문 차단됨",
            )
        payload = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side.value,
            "type": order_type,
            "time_in_force": "day",
        }
        r = requests.post(f"{self.base_url}/v2/orders", headers=self.headers, json=payload, timeout=10)
        if r.status_code >= 400:
            return OrderResult(order_id="", symbol=symbol, side=side, qty=qty,
                                status=OrderStatus.REJECTED, message=r.text)
        data = r.json()
        return OrderResult(
            order_id=data["id"], symbol=symbol, side=side, qty=qty,
            status=OrderStatus.PENDING, message="주문 접수됨",
        )
