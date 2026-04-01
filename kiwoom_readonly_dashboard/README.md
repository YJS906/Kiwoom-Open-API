# Kiwoom Readonly Dashboard + 52-Week Pullback Strategy

키움 REST API + WebSocket 기반 조회 대시보드에
`52주 신고가 기반 눌림목 매수 시스템`을 추가한 프로젝트입니다.

이 버전의 핵심은 다음 3가지입니다.

1. 계좌 / 보유종목 / 차트 / 뉴스 대시보드
2. 52주 신고가 후보군 스캔 + 눌림목 전략 신호 생성
3. 모의주문(paper trading) 중심의 안전한 실행 흐름

중요:

- 기본값은 반드시 `AUTO_BUY_ENABLED=false`
- 기본값은 반드시 `PAPER_TRADING=true`
- 기본값은 반드시 `USE_MOCK_ONLY=true`
- 실주문은 `REAL_ORDER_ENABLED=false` 상태에서는 절대 실행되지 않습니다
- 프론트엔드에서 키움 API를 직접 호출하지 않습니다
- 민감정보는 모두 루트 `.env`에서만 읽습니다

## 1. 전체 구조

브라우저는 Next.js 프론트로 접속합니다.
프론트는 FastAPI 백엔드만 호출합니다.
백엔드는 키움 REST API / WebSocket, 뉴스 공급원, 전략 엔진, 모의주문 엔진을 관리합니다.

전략 흐름은 다음과 같습니다.

1. 52주 신고가 후보군 수집
2. 일봉 추세 필터 확인
3. 60분봉 눌림목 깊이/거래량 감소 확인
4. 15분봉 또는 5분봉 트리거 확인
5. 리스크 규칙 적용
6. 신호 큐 등록
7. 수동 모의주문 또는 자동 모의주문
8. 체결 후 paper position 갱신

## 2. 공식 키움 API 기준 사용 항목

이 프로젝트는 키움 REST/Open API 공식 문서 기준으로 아래를 사용합니다.

- OAuth 토큰: `au10001`
- 계좌번호조회: `ka00001`
- 예수금: `kt00001`
- 잔고/평가: `kt00018`
- 종목 기본정보: `ka10001`
- 종목 리스트: `ka10099`
- 일봉: `ka10081`
- 분봉: `ka10080`
- 주봉: `ka10082`
- 매수주문: `kt10000`
- 매도주문: `kt10001`
- 조건검색 목록조회: `ka10171`
- 조건검색 일반조회: `ka10172`
- 조건검색 실시간조회: `ka10173`
- 조건검색 해제: `ka10174`
- 실시간 시세 / 호가 / 장시작 상태: `0B`, `0D`, `0s`

참고:

- 조건검색은 공식 문서상 WebSocket 기반입니다
- 키움 WebSocket은 동일 App Key의 세션 충돌 가능성이 있습니다
- 그래서 이 프로젝트는 기존 시세 WebSocket이 이미 활성화된 경우,
  조건검색용 별도 WebSocket을 강제로 열지 않고 cached result 또는 fallback symbol로 안전하게 동작합니다
- 이 동작은 의도적인 안전장치입니다

## 3. 폴더 구조

```text
kiwoom_readonly_dashboard/
  .env
  .env.example
  config.yaml
  config.yaml.example
  README.md
  backend/
    .venv/
    pyproject.toml
    requirements.txt
    app/
      main.py
      core/
        config.py
        logging.py
      models/
        schemas.py
        trading.py
      routers/
        account.py
        chart.py
        health.py
        news.py
        orders.py
        scanner.py
        signals.py
        stocks.py
        strategy.py
      services/
        bar_builder.py
        cache.py
        condition_search.py
        high52_scanner.py
        kiwoom_auth.py
        kiwoom_client.py
        kiwoom_ws.py
        news_provider.py
        naver_news.py
        order_executor.py
        paper_broker.py
        position_manager.py
        pullback_strategy.py
        risk_manager.py
        rss_news.py
        session_guard.py
        signal_engine.py
    tests/
      conftest.py
      test_api.py
      test_bar_builder_strategy.py
      test_cache.py
      test_news.py
      test_pullback_strategy_engine.py
      test_risk_manager_engine.py
      test_signal_engine.py
  frontend/
    app/
    components/
    lib/
    types/
    package.json
```

## 4. 영웅문4에서 52주 신고가 조건검색식 만드는 방법

이 시스템의 우선순위 1 스캐너는 `영웅문4 조건검색`을 기준으로 설계했습니다.

권장 순서:

1. 영웅문4 실행
2. 조건검색 화면 열기
3. 새 조건식 만들기
4. 52주 신고가 관련 조건을 직접 구성
5. 이름을 정확히 `52주 신고가`로 저장
6. 이 이름을 `config.yaml`의 `scanner.condition_name`에 동일하게 입력

예시:

- 조건명: `52주 신고가`
- 전략 종목 풀을 너무 넓게 만들지 말고, 실제로 모니터링 가능한 수준으로 먼저 테스트

주의:

- 조건검색식의 정확한 정의는 사용자 전략에 따라 다를 수 있습니다
- 이 프로젝트는 조건검색식의 이름과 결과를 받아 전략 후속 필터를 태우는 구조입니다

## 5. 환경변수 작성

루트에서 `.env.example`을 `.env`로 복사합니다.

```powershell
cd "C:\Users\YEO_JINSEUNG\OneDrive\바탕 화면\kiwoom\kiwoom_readonly_dashboard"
Copy-Item .env.example .env
```

중요 값:

```env
KIWOOM_ENV=mock
KIWOOM_APP_KEY=YOUR_KIWOOM_APP_KEY
KIWOOM_SECRET_KEY=YOUR_KIWOOM_SECRET_KEY
KIWOOM_ACCOUNT_NO=YOUR_10_DIGIT_MOCK_ACCOUNT_NUMBER

AUTO_BUY_ENABLED=false
PAPER_TRADING=true
USE_MOCK_ONLY=true
REAL_ORDER_ENABLED=false
```

설명:

- `KIWOOM_ENV=mock`
  실계좌가 아니라 모의투자 환경을 사용합니다
- `AUTO_BUY_ENABLED=false`
  신호가 나와도 자동으로 매수하지 않습니다
- `PAPER_TRADING=true`
  주문은 paper broker가 즉시 모의 체결합니다
- `USE_MOCK_ONLY=true`
  mock 환경이 아니면 실주문 제출을 거부합니다
- `REAL_ORDER_ENABLED=false`
  이 값이 false면 실주문 코드는 막혀 있습니다

## 6. config.yaml 작성

루트에서 `config.yaml.example`을 `config.yaml`로 복사합니다.

```powershell
Copy-Item config.yaml.example config.yaml
```

가장 먼저 볼 값:

```yaml
scanner:
  condition_name: "52주 신고가"
  refresh_seconds: 45

strategy:
  trigger_timeframe: "15m"

risk:
  buy_cash_pct_of_remaining: 0.20
  max_positions: 3
  max_daily_new_entries: 2
  max_daily_loss_krw: 50000
  no_new_entry_after: "14:30"

execution:
  paper_trading: true
  auto_buy_enabled: false
  use_mock_only: true
  real_order_enabled: false
  order_type: "market"
```

처음에는 절대 바꾸지 말 것을 권장하는 값:

- `execution.paper_trading`
- `execution.auto_buy_enabled`
- `execution.use_mock_only`
- `execution.real_order_enabled`

## 7. 백엔드 실행 방법

### 7-1. 가상환경 생성

```powershell
cd "C:\Users\YEO_JINSEUNG\OneDrive\바탕 화면\kiwoom\kiwoom_readonly_dashboard\backend"
python -m venv .venv
```

### 7-2. 가상환경 활성화

```powershell
.\.venv\Scripts\Activate.ps1
```

### 7-3. 패키지 설치

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 7-4. 테스트 실행

```powershell
pytest -q
```

현재 기준 기대 결과:

```text
13 passed
```

### 7-5. 백엔드 서버 실행

```powershell
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

정상 확인:

- [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- [http://127.0.0.1:8000/api/scanner/overview](http://127.0.0.1:8000/api/scanner/overview)

## 8. 프론트엔드 실행 방법

### 8-1. 패키지 설치

```powershell
cd "C:\Users\YEO_JINSEUNG\OneDrive\바탕 화면\kiwoom\kiwoom_readonly_dashboard\frontend"
npm install
```

### 8-2. 개발 서버 실행

```powershell
npm run dev
```

또는 빌드 확인:

```powershell
npm run build
npm run start
```

브라우저 접속:

- [http://127.0.0.1:3000/dashboard](http://127.0.0.1:3000/dashboard)

## 9. 화면에서 확인할 수 있는 것

상단:

- 계좌 요약
- 총 평가금액
- 총 손익
- 수익률
- 보유 종목 수
- 예수금

좌측:

- 종목 검색
- 관심종목
- 52주 신고가 후보군
- 보유 종목
- 눌림목 감시중 종목

중앙:

- 선택 종목 헤더
- 멀티 타임프레임 차트
- 전략 설명 카드
- 호가 패널

우측:

- 진입 신호 대기열
- 차단 종목
- 주문 로그
- 전략 파라미터
- 관리자 설정
- 뉴스
- API 상태

## 10. 모의투자에서만 테스트하는 방법

반드시 아래 4가지를 확인하세요.

1. `.env`에서 `KIWOOM_ENV=mock`
2. `.env`에서 `PAPER_TRADING=true`
3. `.env`에서 `AUTO_BUY_ENABLED=false`
4. `.env`에서 `REAL_ORDER_ENABLED=false`

추가 확인:

- 대시보드 상단 safety 배너
- 전략 파라미터 패널의 `PAPER TRADING`, `AUTO BUY OFF`, `MOCK ONLY`

## 11. 실주문 비활성화 확인 방법

아래가 모두 만족되어야 실주문은 비활성화 상태입니다.

- `AUTO_BUY_ENABLED=false`
- `PAPER_TRADING=true`
- `USE_MOCK_ONLY=true`
- `REAL_ORDER_ENABLED=false`

이 프로젝트의 실주문 코드 경로는 다음 조건을 모두 만족하지 않으면 실행되지 않습니다.

1. `paper_trading == false`
2. `real_order_enabled == true`
3. `KIWOOM_ENV == mock` 또는 `use_mock_only == false`

즉, 기본값에서는 실주문이 절대 나가지 않습니다.

## 12. 전략 파라미터 조정 방법

방법은 2가지입니다.

### 방법 A. `config.yaml` 수정

가장 안전하고 권장되는 방법입니다.

- `strategy.trigger_timeframe`
- `strategy.pullback_min_ratio`
- `strategy.pullback_max_ratio`
- `risk.stop_loss_pct`
- `risk.take_profit_r_multiple`
- `risk.max_positions`
- `execution.order_type`

수정 후 백엔드를 재시작하세요.

### 방법 B. 관리자 설정 패널 사용

대시보드 우측의 관리자 설정 패널은 런타임 override를 저장합니다.

저장 위치:

- `runtime/strategy_runtime_overrides.json`

주의:

- 이 파일은 `config.yaml` 기본값 위에 덮어쓰기 됩니다
- 서버 재시작 후에도 유지됩니다

## 13. 로그와 런타임 파일 읽는 방법

로그 폴더:

- `logs/`

런타임 상태 파일:

- `runtime/strategy_runtime_state.json`
- `runtime/strategy_runtime_overrides.json`

확인 포인트:

- `strategy_runtime_state.json`
  후보군, 신호, 주문, fill, paper position, 세션 상태가 저장됩니다
- `strategy_runtime_overrides.json`
  관리자 패널에서 저장한 override가 저장됩니다

## 14. 자주 나는 오류와 해결 방법

### 1. `App Key와 Secret Key 검증에 실패했습니다`

원인:

- `.env` 값이 틀렸거나 예시값 그대로입니다

해결:

- `KIWOOM_APP_KEY`
- `KIWOOM_SECRET_KEY`
- `KIWOOM_ACCOUNT_NO`

를 다시 확인하세요.

### 2. `Configured KIWOOM_ACCOUNT_NO was not returned`

원인:

- 계좌번호를 8자리로 넣었을 가능성이 큽니다

해결:

- 10자리 전체 계좌번호를 넣으세요

### 3. WebSocket이 끊겼다 연결됐다 반복됨

원인:

- 같은 App Key로 여러 WebSocket 세션이 붙고 있을 수 있습니다

해결:

- 브라우저 탭을 여러 개 열지 마세요
- 다른 실시간 테스트 프로그램을 동시에 켜지 마세요
- 이 프로젝트는 백엔드가 키움 upstream WebSocket 1개를 공유하도록 설계되어 있습니다

### 4. 조건검색 결과가 안 나옵니다

원인:

- 영웅문4에 해당 조건식이 없거나 이름이 다릅니다
- 또는 이미 시세 WebSocket이 활성화되어 별도 조건검색 WebSocket을 열지 못하고 fallback으로 동작 중입니다

해결:

- 영웅문4에 `scanner.condition_name`과 동일한 이름의 조건검색식이 있는지 확인
- 조건검색 테스트는 브라우저를 모두 닫은 뒤 백엔드만 켠 상태에서 먼저 확인
- `config.yaml`의 `fallback_symbols`도 함께 설정해 두세요

### 5. 뉴스가 비어 있습니다

원인:

- NAVER API 키가 없고 RSS fallback 결과가 적을 수 있습니다

해결:

- `.env`에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 추가

## 15. 왜 바로 실계좌 자동매매를 켜면 안 되는가

절대 바로 실계좌 자동매매를 켜지 마세요.

이유:

1. 조건검색 결과가 사용자의 영웅문 조건식에 따라 달라집니다
2. 장중 분봉 데이터와 실시간 체결의 지연/누락 상황을 충분히 검증하지 않았습니다
3. 리스크 규칙이 실제 체결/부분체결/거래정지 상황까지 충분히 검증되어야 합니다
4. WebSocket 세션 충돌, 토큰 만료, 재시도 로직은 실거래에서 훨씬 민감합니다
5. 전략이 수익을 보장하지 않습니다

권장 순서:

1. 조회만 확인
2. 신호만 확인
3. 수동 paper order 확인
4. 자동 paper order 확인
5. 충분한 로그 검토
6. 그 다음에도 실거래는 별도 코드 리뷰와 모니터링 체계를 먼저 준비

## 16. 지금 바로 실행 순서

1. 루트에서 `.env.example`을 `.env`로 복사합니다
2. 루트에서 `config.yaml.example`을 `config.yaml`로 복사합니다
3. `.env`에서 키움 mock App Key / Secret / 계좌번호를 넣습니다
4. `.env`에서 아래 값이 맞는지 확인합니다
   - `AUTO_BUY_ENABLED=false`
   - `PAPER_TRADING=true`
   - `USE_MOCK_ONLY=true`
   - `REAL_ORDER_ENABLED=false`
5. `backend`에서 `pip install -r requirements.txt`
6. `backend`에서 `pytest -q`
7. `backend`에서 `uvicorn` 실행
8. `frontend`에서 `npm install`
9. `frontend`에서 `npm run dev`
10. 브라우저에서 `/dashboard` 열기

## 17. 현재 검증 상태

로컬에서 확인한 내용:

- 백엔드 테스트 통과
- 프론트 `next build` 통과
- 기존 계좌/시세/뉴스/상태 패널 유지
- 전략 엔진 / 신호 생성 / paper trading 패널 추가

다음 확장 포인트:

- 조건검색 실시간 편입/이탈을 기존 공유 WebSocket 업스트림에 직접 통합
- replay/backtest 전용 화면 추가
- 부분체결 / 취소 / 재시도 정책 세분화
- 종목별 섹터 / 변동성 필터 추가

