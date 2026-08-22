"""
모든 브로커 어댑터가 구현해야 하는 공통 인터페이스.
전략/리스크/실행 계층은 이 인터페이스에만 의존하고 브로커별 구현을 몰라야 함.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    status: OrderStatus
    filled_price: Optional[float] = None
    message: str = ""


class BrokerAdapter(ABC):
    """자산군 무관 공통 브로커 인터페이스"""

    name: str = "base"

    @abstractmethod
    def get_account_equity(self) -> float:
        """계좌 총 평가금액 (원화/달러 등 해당 통화 기준)"""
        ...

    @abstractmethod
    def get_positions(self) -> list[Position]:
        ...

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, limit: int = 200) -> list[Bar]:
        """timeframe 예: '1D', '1H', '15Min'"""
        ...

    @abstractmethod
    def get_last_price(self, symbol: str) -> float:
        ...

    @abstractmethod
    def place_order(self, symbol: str, side: OrderSide, qty: float, order_type: str = "market") -> OrderResult:
        """
        실제 주문 실행. 이 함수는 execution/order_manager.py의 안전장치를 통과한
        경우에만 호출되어야 함. 어댑터 자체에서 재차 ORDERS_ENABLED를 확인한다.
        """
        ...
