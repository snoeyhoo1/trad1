import time
import json
import os
import threading
import requests
from datetime import datetime
from config.settings import settings
from brokers.base import BrokerAdapter, Bar, Position, OrderResult, OrderSide, OrderStatus

_TOKEN_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".kis_token_cache.json")
_token_lock = threading.Lock()


class KISBroker(BrokerAdapter):
    name = "kis"

    def __init__(self):
        self.base_url = "https://openapivts.koreainvestment.com:29443" if settings.KIS_IS_VIRTUAL \
            else "https://openapi.koreainvestment.com:9443"
        self.app_key = settings.KIS_APP_KEY
        self.app_secret = settings.KIS_APP_SECRET
        self.account_no = settings.KIS_ACCOUNT_NO
        self._access_token = None

    def _load_cached_token(self) -> str | None:
        if not os.path.exists(_TOKEN_CACHE_PATH):
            return None
        try:
            with open(_TOKEN_CACHE_PATH) as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time() + 60:
                return data["access_token"]
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _save_token(self, token: str, expires_in: int):
        with open(_TOKEN_CACHE_PATH, "w") as f:
            json.dump({"access_token": token, "expires_at": time.time() + expires_in}, f)

    def _get_token(self) -> str:
        """
        콜드스타트 레이스 컨디션 방지: 프로세스 내 lock + 파일 캐시로
        동시 다발적 토큰 발급 요청을 막는다. (KIS는 1분당 발급 제한이 있음)
        """
        with _token_lock:
            cached = self._load_cached_token()
            if cached:
                self._access_token = cached
                return cached
            r = requests.post(
                f"{self.base_url}/oauth2/tokenP",
                json={"grant_type": "client_credentials", "appkey": self.app_key, "appsecret": self.app_secret},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            token = data["access_token"]
            self._save_token(token, int(data.get("expires_in", 86400)))
            self._access_token = token
            return token

    def _headers(self, tr_id: str) -> dict:
        return {
            "authorization": f"Bearer {self._get_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "content-type": "application/json; charset=utf-8",
        }

    def get_account_equity(self) -> float:
        tr_id = "VTTC8434R" if settings.KIS_IS_VIRTUAL else "TTTC8434R"
        cano, acnt_prdt_cd = self.account_no.split("-")
        params = {
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
            "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }
        r = requests.get(f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                          headers=self._headers(tr_id), params=params, timeout=10)
        r.raise_for_status()
        return float(r.json()["output2"][0]["tot_evlu_amt"])

    def get_positions(self) -> list[Position]:
        tr_id = "VTTC8434R" if settings.KIS_IS_VIRTUAL else "TTTC8434R"
        cano, acnt_prdt_cd = self.account_no.split("-")
        params = {
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
            "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }
        r = requests.get(f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                          headers=self._headers(tr_id), params=params, timeout=10)
        r.raise_for_status()
        out = []
        for p in r.json().get("output1", []):
            qty = float(p.get("hldg_qty", 0))
            if qty == 0:
                continue
            out.append(Position(
                symbol=p["pdno"], qty=qty,
                avg_entry_price=float(p["pchs_avg_pric"]),
                current_price=float(p["prpr"]),
                market_value=float(p["evlu_amt"]),
                unrealized_pnl=float(p["evlu_pfls_amt"]),
            ))
        return out

    def get_bars(self, symbol: str, timeframe: str = "D", limit: int = 200) -> list[Bar]:
        tr_id = "FHKST03010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol,
            "FID_PERIOD_DIV_CODE": timeframe, "FID_ORG_ADJ_PRC": "1",
        }
        r = requests.get(f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price",
                          headers=self._headers(tr_id), params=params, timeout=10)
        r.raise_for_status()
        rows = r.json().get("output", [])[:limit]
        bars = [
            Bar(
                timestamp=datetime.strptime(row["stck_bsop_date"], "%Y%m%d"),
                open=float(row["stck_oprc"]), high=float(row["stck_hgpr"]),
                low=float(row["stck_lwpr"]), close=float(row["stck_clpr"]),
                volume=float(row["acml_vol"]),
            )
            for row in rows
        ]
        return list(reversed(bars))

    def get_last_price(self, symbol: str) -> float:
        tr_id = "FHKST01010100"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol}
        r = requests.get(f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
                          headers=self._headers(tr_id), params=params, timeout=10)
        r.raise_for_status()
        return float(r.json()["output"]["stck_prpr"])

    def place_order(self, symbol: str, side: OrderSide, qty: float, order_type: str = "market") -> OrderResult:
        if not settings.ORDERS_ENABLED:
            return OrderResult(
                order_id="", symbol=symbol, side=side, qty=qty,
                status=OrderStatus.REJECTED, message="ORDERS_ENABLED=False, 주문 차단됨",
            )
        tr_id = ("VTTC0802U" if side == OrderSide.BUY else "VTTC0801U") if settings.KIS_IS_VIRTUAL \
            else ("TTTC0802U" if side == OrderSide.BUY else "TTTC0801U")
        cano, acnt_prdt_cd = self.account_no.split("-")
        body = {
            "CANO": cano, "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": symbol, "ORD_DVSN": "01",  # 01 = 시장가
            "ORD_QTY": str(int(qty)), "ORD_UNPR": "0",
        }
        r = requests.post(f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash",
                           headers=self._headers(tr_id), json=body, timeout=10)
        data = r.json()
        if data.get("rt_cd") != "0":
            return OrderResult(order_id="", symbol=symbol, side=side, qty=qty,
                                status=OrderStatus.REJECTED, message=data.get("msg1", ""))
        return OrderResult(
            order_id=data["output"]["ODNO"], symbol=symbol, side=side, qty=qty,
            status=OrderStatus.PENDING, message="주문 접수됨",
        )
