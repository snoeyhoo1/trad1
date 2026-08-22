import time
import hmac
import hashlib
import requests
from datetime import datetime, timezone
from config.settings import settings
from brokers.base import BrokerAdapter, Bar, Position, OrderResult, OrderSide, OrderStatus


class BybitBroker(BrokerAdapter):
    name = "bybit"

    def __init__(self):
        self.base_url = "https://api-testnet.bybit.com" if settings.BYBIT_TESTNET else "https://api.bybit.com"
        self.api_key = settings.BYBIT_API_KEY
        self.api_secret = settings.BYBIT_API_SECRET
        self.recv_window = "5000"

    def _sign(self, params_str: str, timestamp: str) -> str:
        payload = f"{timestamp}{self.api_key}{self.recv_window}{params_str}"
        return hmac.new(self.api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    def _signed_get(self, path: str, params: dict) -> dict:
        timestamp = str(int(time.time() * 1000))
        query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        sig = self._sign(query, timestamp)
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
            "X-BAPI-SIGN": sig,
        }
        r = requests.get(f"{self.base_url}{path}", headers=headers, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    def _signed_post(self, path: str, body: dict) -> dict:
        import json
        timestamp = str(int(time.time() * 1000))
        body_str = json.dumps(body)
        sig = self._sign(body_str, timestamp)
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
            "X-BAPI-SIGN": sig,
            "Content-Type": "application/json",
        }
        r = requests.post(f"{self.base_url}{path}", headers=headers, data=body_str, timeout=10)
        r.raise_for_status()
        return r.json()

    def get_account_equity(self) -> float:
        data = self._signed_get("/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        coins = data["result"]["list"][0]["coin"]
        usdt = next((c for c in coins if c["coin"] == "USDT"), None)
        return float(usdt["walletBalance"]) if usdt else 0.0

    def get_positions(self) -> list[Position]:
        data = self._signed_get("/v5/position/list", {"category": "linear", "settleCoin": "USDT"})
        out = []
        for p in data["result"]["list"]:
            qty = float(p["size"])
            if qty == 0:
                continue
            out.append(Position(
                symbol=p["symbol"], qty=qty,
                avg_entry_price=float(p["avgPrice"]),
                current_price=float(p["markPrice"]),
                market_value=float(p["positionValue"]),
                unrealized_pnl=float(p["unrealisedPnl"]),
            ))
        return out

    def get_bars(self, symbol: str, timeframe: str = "D", limit: int = 200) -> list[Bar]:
        # timeframe: 1,3,5,15,30,60,120,240,360,720,D,W,M
        r = requests.get(
            f"{self.base_url}/v5/market/kline",
            params={"category": "linear", "symbol": symbol, "interval": timeframe, "limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()["result"]["list"]
        bars = [
            Bar(
                timestamp=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                open=float(row[1]), high=float(row[2]), low=float(row[3]),
                close=float(row[4]), volume=float(row[5]),
            )
            for row in rows
        ]
        return list(reversed(bars))  # bybit는 최신순으로 주므로 시간순 정렬

    def get_last_price(self, symbol: str) -> float:
        r = requests.get(
            f"{self.base_url}/v5/market/tickers",
            params={"category": "linear", "symbol": symbol}, timeout=10,
        )
        r.raise_for_status()
        return float(r.json()["result"]["list"][0]["lastPrice"])

    def place_order(self, symbol: str, side: OrderSide, qty: float, order_type: str = "market") -> OrderResult:
        if not settings.ORDERS_ENABLED:
            return OrderResult(
                order_id="", symbol=symbol, side=side, qty=qty,
                status=OrderStatus.REJECTED, message="ORDERS_ENABLED=False, 주문 차단됨",
            )
        body = {
            "category": "linear",
            "symbol": symbol,
            "side": "Buy" if side == OrderSide.BUY else "Sell",
            "orderType": "Market" if order_type == "market" else "Limit",
            "qty": str(qty),
        }
        data = self._signed_post("/v5/order/create", body)
        if data.get("retCode") != 0:
            return OrderResult(order_id="", symbol=symbol, side=side, qty=qty,
                                status=OrderStatus.REJECTED, message=data.get("retMsg", ""))
        return OrderResult(
            order_id=data["result"]["orderId"], symbol=symbol, side=side, qty=qty,
            status=OrderStatus.PENDING, message="주문 접수됨",
        )
