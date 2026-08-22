# AI Trader — Vercel 전용 모니터 + 대시보드

브로커 조회(잔고/포지션/시세)부터 앙상블 판단, 가상 매매 기록, **화면 표시까지
전부 Vercel 안에서** 처리합니다. GitHub Actions 불필요, 외부 아티팩트 불필요 —
배포하면 `https://당신의도메인.vercel.app/dashboard`에서 바로 보입니다.

**안전장치**: `lib/brokers/*.js` 어디에도 주문을 넣는 함수가 없습니다. 조회 함수
(getAccountEquity, getPositions, getBars)만 존재하므로 실계좌 키를 넣어도
실주문이 나갈 수 없습니다.

## 파일 구조

```
middleware.js                    /dashboard, /api/dashboard-feed 비밀번호 보호
pages/dashboard.js                화면 (여기로 바로 접속)
pages/api/dashboard-feed.js       대시보드 전용 내부 API (미들웨어가 보호, 별도 키 불필요)
pages/api/state.js                외부 도구용 공개 API (x-api-key로 보호, 선택사항)
pages/api/cron/monitor-alpaca.js  Alpaca 스캔 (조회+판단+가상매매 기록)
pages/api/cron/monitor-bybit.js   Bybit 스캔
pages/api/cron/monitor-kis.js     KIS 스캔
lib/brokers/                      브로커별 조회 전용 어댑터
lib/indicators.js                 기술적 지표
lib/ensemble.js                   앙상블 스코어링
lib/regime.js                     변동성/추세 레짐 감지
lib/state.js                      Vercel KV 상태 읽기/쓰기
lib/monitorCore.js                스캔 → 판단 → 가상 매매 기록 핵심 로직
vercel.json                       Vercel Cron 설정 (Hobby는 하루 1번만 가능)
```

## 배포 방법 (직접 하셔야 하는 부분)

1. 이 폴더 내용을 기존 Next.js/Vercel 리포 루트에 합치기 (파일 그대로 덮어쓰기)
   - 이미 `package.json`이 있다면 `dependencies`에 `@vercel/kv`, `recharts`, `lucide-react`만
     추가 (next/react는 이미 있을 것)
2. Vercel 프로젝트에 **KV 스토리지 연결**: Storage 탭 → Create Database → KV
   → 연결하면 `KV_REST_API_URL` 등이 자동으로 환경변수에 세팅됨
3. Vercel 프로젝트 환경변수(Settings → Environment Variables)에 추가:

   | 변수 | 값 |
   |---|---|
   | `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | 실계좌 키 |
   | `ALPACA_BASE_URL` | `https://api.alpaca.markets` (실계좌) |
   | `BYBIT_API_KEY` / `BYBIT_API_SECRET` | 실계좌 키 |
   | `BYBIT_TESTNET` | `false` |
   | `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NO` | 실계좌 정보 |
   | `KIS_IS_VIRTUAL` | `false` |
   | `DASHBOARD_PASSWORD` | **화면 접속 비밀번호 — 반드시 설정** (직접 정하기) |
   | `DASHBOARD_USER` | 화면 접속 아이디 (생략시 기본값 `admin`) |
   | `MONITOR_SECRET` | 외부 핑서 인증용 임의 문자열 (직접 생성) |
   | `STATE_API_SECRET` | (선택) 외부 도구에서 `/api/state`를 쓸 경우에만 필요 |
   | `AITRADER_WATCHLIST_US` 등 | 필요시 워치리스트 커스텀 |

   `CRON_SECRET`은 Vercel Cron 기능 사용 시 자동으로 만들어집니다 (직접 안 넣어도 됨).

4. 배포 (`vercel --prod` 또는 git push)
5. `https://당신의도메인.vercel.app/dashboard` 접속 → 브라우저가 아이디/비밀번호
   물어봄 → `DASHBOARD_USER`/`DASHBOARD_PASSWORD` 입력하면 화면 뜸

## 15분마다 자동 스캔 돌리기 (Hobby 플랜)

Vercel Hobby는 자체 Cron이 하루 1번만 가능합니다. 그래서 실제 작업은 API
라우트가 다 하고, **호출만** 외부 무료 스케줄러가 대신합니다:

1. [cron-job.org](https://cron-job.org) 무료 가입
2. 아래 3개 URL을 각각 다른 cron job으로 등록, 15분 간격:
   - `https://당신의도메인.vercel.app/api/cron/monitor-alpaca?key=MONITOR_SECRET값`
   - `https://당신의도메인.vercel.app/api/cron/monitor-bybit?key=MONITOR_SECRET값`
   - `https://당신의도메인.vercel.app/api/cron/monitor-kis?key=MONITOR_SECRET값`
   (사용 안 하는 자산군은 등록 안 해도 됨)

Vercel Pro로 업그레이드하면 `vercel.json`의 `crons` 항목에 `*/15 * * * *` 스케줄을
그대로 추가해서 Vercel 자체 크론으로 완전히 대체할 수 있습니다 (외부 핑서 불필요).

## 제약사항

- Hobby 함수 실행 제한시간 10초 — 워치리스트가 너무 크면 한 번의 스캔 안에
  타임아웃날 수 있음. 브로커별로 엔드포인트를 나눈 이유가 이것 (종목 수를
  줄이거나 Pro로 올리면 여유 생김)
- KIS 토큰은 Vercel KV에 캐싱되어 함수 간에 공유됨 (매 호출마다 재발급 안 함)
- `data/state.json` 로컬 파일 방식은 완전히 제거됨 — 모든 상태는 Vercel KV에만 존재
- `/dashboard`는 `DASHBOARD_PASSWORD`를 안 넣으면 보호 없이 열립니다. 반드시 설정하세요.
