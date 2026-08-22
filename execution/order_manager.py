"""
주문 실행 게이트웨이. 모든 주문은 반드시 이 모듈을 통과해야 한다.
안전장치 3중:
  1) settings.ORDERS_ENABLED = False 면 브로커 어댑터 자체에서 거부
  2) settings.REQUIRE_CONFIRMATION = True 면 콜백을 통한 사람 확인 필요
  3) MODE != "live" 면 무조건 페이퍼 로그만 남김
"""
import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Callable, Optional
from config.settings import settings
from brokers.base import BrokerAdapter, OrderSide, OrderResult, OrderStatus

_LOG_PATH = os.path.join(os.path.dirname(__file__), "order_log.jsonl")


@dataclass
class TradeIntent:
    broker: str
    symbol: str
    side: OrderSide
    qty: float
    score: float
    reason: str
    stop_loss_price: float


ConfirmCallback = Optional[Callable[[TradeIntent], bool]]


def _log(entry: dict):
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def execute_intent(
    broker: BrokerAdapter,
    intent: TradeIntent,
    confirm_callback: ConfirmCallback = None,
) -> OrderResult:
    """
    intent를 받아 안전장치를 순서대로 통과시킨 뒤 최종적으로 브로커에 주문을 낸다.
    confirm_callback: None이면 REQUIRE_CONFIRMATION 설정에 따라 자동 결정.
                       콜백을 주면 그 결과(True/False)로 확인 여부를 판단.
                       (예: Slack/텔레그램 알림 보내고 응답 대기하는 함수를 넣을 수 있음)
    """
    # 1) 페이퍼 모드면 실제 주문 없이 로그만
    if settings.MODE != "live":
        result = OrderResult(
            order_id=f"paper-{datetime.now().timestamp()}",
            symbol=intent.symbol, side=intent.side, qty=intent.qty,
            status=OrderStatus.FILLED, message="PAPER MODE - 실제 주문 없음",
        )
        _log({"mode": "paper", "intent": asdict(intent), "result": asdict(result)})
        return result

    # 2) 사람 확인 필요 시
    if settings.REQUIRE_CONFIRMATION:
        approved = confirm_callback(intent) if confirm_callback else False
        if not approved:
            result = OrderResult(
                order_id="", symbol=intent.symbol, side=intent.side, qty=intent.qty,
                status=OrderStatus.REJECTED, message="사람 확인 미승인 - 주문 실행 안 함",
            )
            _log({"mode": "live", "intent": asdict(intent), "result": asdict(result), "confirmed": False})
            return result

    # 3) 최종 주문 (브로커 어댑터가 ORDERS_ENABLED 재확인함)
    result = broker.place_order(intent.symbol, intent.side, intent.qty)
    _log({"mode": "live", "intent": asdict(intent), "result": asdict(result), "confirmed": True})
    return result
