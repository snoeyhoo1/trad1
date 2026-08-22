# AI Trader

미국주식(Alpaca) / 코인(Bybit) / 국내주식(KIS) 멀티에셋 자동매매 봇.
데이터 수집 → 앙상블 시그널 → ATR 기반 리스크 사이징 → (확인) → 주문, 전체 파이프라인.

## 안전장치 (기본값 모두 안전 쪽)

| 설정 | 기본값 | 의미 |
|---|---|---|
| `AITRADER_MODE` | `paper` | `live`가 아니면 실제 주문 절대 안 나감, 로그만 남김 |
| `AITRADER_ORDERS_ENABLED` | `false` | 브로커 어댑터 최종 관문. false면 live여도 주문 차단 |
| `AITRADER_REQUIRE_CONFIRMATION` | `true` | live+enabled여도 사람 확인 필요 |

**실거래를 켜려면 세 가지를 모두 의도적으로 바꿔야 함.** 이는 실수로 인한 자동 실거래를 막기 위한 3중 게이트입니다.

## 설치

```bash
pip install -r requirements.txt
```

## 환경변수 (.env 또는 시스템 환경변수)

```bash
# 브로커 키
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ACCOUNT_NO=12345678-01

# 자산군 on/off
AITRADER_ENABLE_US_EQUITY=true
AITRADER_ENABLE_CRYPTO=true
AITRADER_ENABLE_KR_EQUITY=true

# 워치리스트
AITRADER_WATCHLIST_US=AAPL,MSFT,NVDA,SPY
AITRADER_WATCHLIST_CRYPTO=BTCUSDT,ETHUSDT
AITRADER_WATCHLIST_KR=005930,000660
```

## 실계좌 연동 (조회 전용) + 자동 실행 대시보드

**핵심 안전장치**: `monitor.py`는 브로커의 `place_order()`를 호출하는 코드가 물리적으로
없습니다. 실계좌 키를 넣어도 조회(잔고/포지션/시세)만 하고, 매수/매도 판단은
`data/state.json`에 가상으로만 기록됩니다.

### 설정 방법
1. `.env.example`을 `.env`로 복사 후 실계좌 키 입력 (`KIS_IS_VIRTUAL=false`,
   `BYBIT_TESTNET=false`, `ALPACA_BASE_URL=https://api.alpaca.markets`로 실계좌 지정)
2. GitHub 리포에 push, Settings → Secrets에 브로커 키 등록
3. `.github/workflows/live-monitor.yml`이 한국장/미국장 시간대에 15분마다 자동 실행되고,
   실행 결과(`data/state.json`)를 리포에 자동 커밋 — **당신이 컴퓨터를 켜둘 필요 없음**,
   GitHub 서버가 스케줄대로 실행합니다.
4. 대시보드(React 아티팩트)에서 `https://raw.githubusercontent.com/사용자명/리포명/main/data/state.json`
   주소를 넣으면 누적 기록이 자동 갱신되며 표시됩니다.

⚠ 리포가 public이면 이 raw URL이 누구나 접근 가능합니다. `state.json`에는 브로커
시크릿/계좌번호는 절대 안 들어가지만(잔고 액수·심볼·손익%만 기록), 민감하다고 느끼면
리포를 private으로 두고 raw URL 대신 Vercel API 라우트를 하나 만들어 그걸 경유하는
방식으로 바꾸는 걸 추천합니다 (기존 Vercel KV 대시보드 패턴 재활용 가능).

```bash
python main.py
```

paper 모드(기본값)에서는 실제 주문 없이 콘솔에 시그널과 예상 사이징만 출력되고,
`execution/order_log.jsonl`에 기록이 남습니다.

## 구조

```
config/settings.py       전역 설정 (환경변수 기반)
brokers/                 브로커 어댑터 (alpaca, bybit, kis) - 공통 인터페이스(base.py)
signals/indicators.py    SMA/EMA/RSI/MACD/ATR/볼린저밴드 (순수 numpy)
signals/ensemble.py      멀티 에이전트 앙상블 (trend/momentum/mean_reversion/risk)
risk/manager.py          ATR 포지션 사이징, 상관관계 필터, 노출 한도
execution/order_manager.py  주문 게이트웨이 (3중 안전장치)
main.py                  전체 파이프라인 오케스트레이터
.github/workflows/run.yml   GitHub Actions 스케줄 실행 (Vercel Hobby cron 제한 우회)
```

## 추가된 모듈 (2차 확장)

### 레짐 감지 (`signals/regime.py`)
ATR 백분위(20/80/95) + EMA 기울기로 변동성/추세 국면을 분류하고, 국면에 따라
매수/매도 임계값을 동적 조정합니다. LOW·EXTREME 구간에서는 보수적으로,
HIGH(추세 구간)에서는 소폭 완화합니다. VIX 임계값이나 HMM 대비 코드 복잡도
낮고 자산군 무관하게(주식/코인 공용) 적용 가능해 채택했습니다.

### 워크포워드 백테스트 (`backtest.py`)
- Rolling-window 방식, fold 사이 embargo(기본 5봉)로 데이터 누수 방지
- 출력: fold별 수익률/샤프/MDD/승률 + 종합 지표
- 거래 표본 20건 미만이면 경고 표시 (통계적으로 판단하기엔 부족)
- 실행: `python backtest.py AAPL` (Alpaca 기준, 다른 브로커로 바꾸려면 스크립트 하단 수정)
- **주의**: 규칙 기반 전략이라 in-sample 파라미터 최적화 단계는 없음. WFA의 목적은
  "다른 시장 구간에서도 edge가 유지되는가"를 확인하는 것.

### 시그널 적중률 추적 (`signals/outcome_tracker.py`)
- `record_signal()`로 매 시그널을 sqlite에 기록
- `evaluate_pending()`을 주기적으로 돌려 N시간 후 가격과 비교해 채점
- `get_hit_rate()`로 최근 N일 적중률 조회 (SIGNAL DESK의 'AI 적중률' 패널과 동일 컨셉)

### 텔레그램 승인 (`execution/telegram_confirm.py`)
GitHub Actions처럼 표준입력이 없는 환경에서 사람 확인을 받기 위한 콜백.
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` 환경변수 설정 시 자동으로 활성화되며
(`main.py`의 `get_confirm_callback()`이 자동 선택), 타임아웃(기본 300초) 시
안전하게 자동 거부됩니다.

## 다음 단계 (아직 안 한 것)

- [ ] 대시보드 (Next.js/Vercel) - 기존 SIGNAL DESK 대시보드 재활용 고려
- [ ] 뉴스/펀더멘털 컨텍스트 에이전트 (현재는 규칙 기반 기술적 지표만 사용)
- [ ] 상관관계 필터를 main.py 루프에 실제 연결 (현재 `risk/manager.py`에 함수만 존재,
      스캔 중 보유 종목들과의 상관계수를 계산해 넘겨주는 배선 작업 필요)

## 알려진 한계

- 백테스트 없이 실거래 임계값을 낮추지 말 것. 과거 테스트에서 단기 스캘핑류 전략은
  실전 재현성이 낮았음 (MA크로스오버/RSI/볼린저 단독 전략도 마찬가지).
- `run_ensemble`은 규칙 기반 지표 조합이며, LLM 기반 컨텍스트 에이전트는 포함되어 있지
  않음 (SIGNAL DESK의 contextAgents와 다름).
- 백테스트 결과가 하나의 심볼/기간에 좋게 나와도 다른 자산·기간에서 재검증 없이
  실거래로 넘어가지 말 것 (walk-forward는 curve-fitting을 줄여줄 뿐 완전히 없애지 않음).
