"""
전역 설정
모든 민감정보(API 키)는 환경변수로만 관리. 코드에 하드코딩 금지.
"""
import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # ---- 안전장치 ----
    # paper: 모의투자만 실행. live: 실제 주문 실행 (반드시 명시적으로 켜야 함)
    MODE: str = os.getenv("AITRADER_MODE", "paper")
    # True면 주문 직전 사람 확인 필요 (SIGNAL DESK 방식과 동일한 안전장치)
    REQUIRE_CONFIRMATION: bool = _bool("AITRADER_REQUIRE_CONFIRMATION", True)
    # 자동 실행 완전 차단 스위치. False면 어떤 경우에도 주문 함수가 실행되지 않음
    ORDERS_ENABLED: bool = _bool("AITRADER_ORDERS_ENABLED", False)

    # ---- 자산군별 활성화 ----
    ENABLE_US_EQUITY: bool = _bool("AITRADER_ENABLE_US_EQUITY", True)
    ENABLE_CRYPTO: bool = _bool("AITRADER_ENABLE_CRYPTO", True)
    ENABLE_KR_EQUITY: bool = _bool("AITRADER_ENABLE_KR_EQUITY", True)

    # ---- 리스크 파라미터 ----
    MAX_POSITION_PCT: float = float(os.getenv("AITRADER_MAX_POSITION_PCT", "0.10"))  # 종목당 최대 비중
    MAX_TOTAL_EXPOSURE_PCT: float = float(os.getenv("AITRADER_MAX_TOTAL_EXPOSURE_PCT", "0.80"))
    MAX_CORRELATION: float = float(os.getenv("AITRADER_MAX_CORRELATION", "0.7"))
    ATR_STOP_MULTIPLIER: float = float(os.getenv("AITRADER_ATR_STOP_MULT", "2.0"))
    RISK_PER_TRADE_PCT: float = float(os.getenv("AITRADER_RISK_PER_TRADE_PCT", "0.01"))  # 계좌 대비 트레이드당 손실 허용치

    # ---- 시그널 파라미터 ----
    SCORE_BUY_THRESHOLD: float = float(os.getenv("AITRADER_BUY_THRESHOLD", "0.65"))
    SCORE_SELL_THRESHOLD: float = float(os.getenv("AITRADER_SELL_THRESHOLD", "0.35"))

    # ---- 브로커 자격증명 (환경변수에서만 로드) ----
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    BYBIT_API_KEY: str = os.getenv("BYBIT_API_KEY", "")
    BYBIT_API_SECRET: str = os.getenv("BYBIT_API_SECRET", "")
    BYBIT_TESTNET: bool = _bool("BYBIT_TESTNET", True)

    KIS_APP_KEY: str = os.getenv("KIS_APP_KEY", "")
    KIS_APP_SECRET: str = os.getenv("KIS_APP_SECRET", "")
    KIS_ACCOUNT_NO: str = os.getenv("KIS_ACCOUNT_NO", "")
    KIS_IS_VIRTUAL: bool = _bool("KIS_IS_VIRTUAL", True)

    WATCHLIST_US: list = field(default_factory=lambda: os.getenv("AITRADER_WATCHLIST_US", "AAPL,MSFT,NVDA,SPY").split(","))
    WATCHLIST_CRYPTO: list = field(default_factory=lambda: os.getenv("AITRADER_WATCHLIST_CRYPTO", "BTCUSDT,ETHUSDT").split(","))
    WATCHLIST_KR: list = field(default_factory=lambda: os.getenv("AITRADER_WATCHLIST_KR", "005930,000660").split(","))


settings = Settings()
