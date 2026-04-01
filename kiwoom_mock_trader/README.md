# Kiwoom Mock Trader

키움증권 REST API를 사용해서 **모의투자 계좌 전용** 국내주식 자동매매를 연습하기 위한 샘플 프로젝트입니다.

중요:

- 이 프로젝트는 **REST API 기준**으로만 작성했습니다.
- **OpenAPI+ OCX/COM** 방식은 사용하지 않습니다.
- **모의투자(mock) 환경 전용**입니다.
- 기본값은 `dry_run: true` 이므로 처음에는 실제 mock 주문도 나가지 않습니다.
- 코드 안에는 앱키, 시크릿키, 계좌번호, 비밀번호, 토큰을 하드코딩하지 않습니다.

## 1. 프로젝트 개요

이 프로젝트는 아래 흐름으로 동작합니다.

1. `.env`에서 키움 앱키/시크릿키/모의계좌 정보를 읽습니다.
2. `config.yaml`에서 mock URL, 종목, 거래시간, 리스크 한도를 읽습니다.
3. OAuth 토큰을 발급받아 `.runtime/token_mock.json`에 저장합니다.
4. 계좌번호 조회로 현재 토큰이 내가 지정한 모의계좌와 맞는지 검증합니다.
5. 예수금, 보유종목, 현재가, 일봉 데이터를 읽습니다.
6. 샘플 전략이 매수/매도/대기 중 하나를 결정합니다.
7. 리스크 관리가 주문 가능 여부를 다시 검사합니다.
8. `dry_run: true` 이면 모의 주문처럼 저장만 하고 실제 주문은 보내지 않습니다.
9. `dry_run: false` 이면서 mock 환경일 때만 실제 모의투자 주문을 전송합니다.

## 2. 공식 문서 기준으로 사용한 API

아래 링크는 모두 키움 공식 문서입니다.

- OAuth 접근토큰 발급: [au10001](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=a1&apiId=au10001)
- OAuth 접근토큰 폐기: [au10002](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=a2&apiId=au10002)
- 계좌번호조회: [ka00001](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=08&apiId=ka00001)
- 예수금상세현황요청: [kt00001](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=08&apiId=kt00001)
- 계좌평가잔고내역요청: [kt00018](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=08&apiId=kt00018)
- 계좌별주문체결현황요청: [kt00009](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=08&apiId=kt00009)
- 주식기본정보요청: [ka10001](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=01&apiId=ka10001)
- 주식일봉차트조회요청: [ka10081](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=07&apiId=ka10081)
- 주식 매수주문: [kt10000](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=13&apiId=kt10000)
- 주식 매도주문: [kt10001](https://openapi.kiwoom.com/m/guide/apiguide?jobTpCode=13&apiId=kt10001)

참고:

- 공식 검색 스니펫이나 검색엔진 캐시에는 예전 TR 번호가 섞여 나올 수 있습니다.
- 이 프로젝트는 검색결과 요약이 아니라 **공식 모바일 가이드의 현재 direct URL** 기준으로 맞췄습니다.

## 3. 폴더 구조

```text
kiwoom_mock_trader/
  app/
    __init__.py
    account.py
    auth.py
    bot.py
    client.py
    config.py
    exceptions.py
    logger.py
    market.py
    models.py
    orders.py
    risk.py
    scheduler.py
    strategy.py
    utils.py
  tests/
    conftest.py
    test_auth.py
    test_risk.py
    test_strategy.py
  .env.example
  .gitignore
  config.yaml.example
  README.md
  requirements.txt
  run_bot.py
```

## 4. 각 파일 역할

- `app/config.py`: `.env`와 `config.yaml`을 읽어서 하나의 설정 객체로 합칩니다.
- `app/auth.py`: OAuth 토큰 발급, 만료 체크, 캐시 저장을 담당합니다.
- `app/client.py`: Kiwoom REST 공통 POST 호출과 인증 헤더 처리를 담당합니다.
- `app/market.py`: 현재가와 일봉 데이터를 조회합니다.
- `app/account.py`: 계좌번호 검증, 예수금, 잔고를 조회합니다.
- `app/orders.py`: 지정가/시장가 주문과 주문 체결 상태 조회를 담당합니다.
- `app/strategy.py`: 매우 단순한 샘플 전략을 담고 있습니다.
- `app/risk.py`: 주문 한도, 일일 손실 한도, 중복 주문 방지, 상태 저장을 담당합니다.
- `app/bot.py`: 전체 실행 순서를 묶는 메인 로직입니다.
- `app/scheduler.py`: 일정 간격으로 `run_once()`를 반복 호출합니다.
- `tests/`: 실서버 없이 동작하는 단위 테스트입니다.

## 5. 전략 설명

이 프로젝트의 전략은 **수익용 전략이 아니라 작동 확인용 샘플 전략**입니다.

전략 이름:

- `previous_close_demo`

동작 방식:

- 보유 종목이 없을 때:
  - 현재가가 전일 종가 대비 `buy_above_prev_close_pct` 이상 상승하면 매수 신호
- 보유 종목이 있을 때:
  - 현재가가 매입가 대비 `stop_loss_pct` 이상 하락하면 매도
  - 현재가가 매입가 대비 `take_profit_pct` 이상 상승하면 매도

주의:

- 이 전략은 실제 투자 성과를 보장하지 않습니다.
- 자동매매 흐름이 정상적으로 이어지는지 확인하기 위한 예시일 뿐입니다.

## 6. 리스크 관리 기본값

기본 설정은 다음과 같습니다.

- `dry_run: true`
- `use_mock_only: true`
- `max_daily_orders: 3`
- `max_position_count: 1`
- `max_order_amount_krw: 100000`
- `max_daily_loss_krw: 30000`
- 장중 지정 시간 외 주문 금지
- 계좌 검증 실패 시 즉시 중단
- 토큰 발급 실패 시 즉시 중단
- 주문/조회 예외 발생 시 즉시 중단
- mock URL이 아니면 주문 함수 자체가 거부됨

추가 안전장치:

- 주문 전 `mockapi.kiwoom.com` 여부를 다시 확인합니다.
- `.env`의 계좌번호가 토큰으로 조회한 계좌번호 목록에 없으면 중단합니다.
- 같은 종목/같은 방향의 미체결 주문이 있으면 중복 주문을 막습니다.
- 상태는 `.runtime/state.json`에 저장됩니다.

## 7. 키움 REST API 사용 신청 개요

이미 등록을 해두셨다면 이 단계는 대부분 끝난 상태입니다.

기본 개요는 아래와 같습니다.

1. 키움증권 Open API/REST API 사용 신청을 합니다.
2. 앱키(App Key), 시크릿키(Secret Key)를 발급받습니다.
3. 모의투자 계좌를 준비합니다.
4. REST API 사용 가능 상태인지 확인합니다.
5. 이 프로젝트의 `.env`에 앱키/시크릿키/모의계좌번호를 넣습니다.

중요:

- 이번 프로젝트는 **REST** 기준이므로 OpenAPI+ 설치 여부와 별개로 동작합니다.
- 설치 파일이 있어도 코드에서는 OCX/COM 객체를 생성하지 않습니다.

## 8. 모의투자 환경 준비 개요

실행 전에 준비할 것:

- 키움 REST API 사용 등록 완료
- 모의투자 계좌번호 확인
- 앱키, 시크릿키 확보
- Python 3.11 설치

권장:

- 처음에는 반드시 `dry_run: true`
- 주문 가능 시간이 아닐 때는 조회만 돌려보며 로그 구조 확인

## 9. .env 작성 방법

먼저 예시 파일을 복사합니다.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

그 다음 `.env`를 열어서 실제 값을 넣습니다.

```env
KIWOOM_APP_KEY=발급받은_앱키
KIWOOM_SECRET_KEY=발급받은_시크릿키
KIWOOM_ACCOUNT_NO=모의투자_계좌번호
KIWOOM_ACCOUNT_PASSWORD=모의투자_비밀번호
KIWOOM_ENV=mock
```

주의:

- `KIWOOM_ENV`는 반드시 `mock`
- 실계좌 번호를 넣지 마세요
- 이 파일은 깃에 올리지 마세요

## 10. config.yaml 작성 방법

예시 파일을 복사합니다.

Windows PowerShell:

```powershell
Copy-Item config.yaml.example config.yaml
```

Linux/macOS:

```bash
cp config.yaml.example config.yaml
```

기본 예시는 아래와 같습니다.

```yaml
environment: mock

api:
  mock_base_url: "https://mockapi.kiwoom.com"
  production_base_url: "https://api.kiwoom.com"
  mock_websocket_url: "wss://mockapi.kiwoom.com:10000/api/dostk/websocket"
  production_websocket_url: "wss://api.kiwoom.com:10000/api/dostk/websocket"
  request_timeout_seconds: 15

trading:
  symbol: "005930"
  exchange: "KRX"
  default_order_type: "limit"
  poll_interval_seconds: 30
  market_open_time: "09:05"
  market_close_time: "15:10"
  timezone: "Asia/Seoul"

safety:
  dry_run: true
  use_mock_only: true
  stop_on_error: true
  fail_if_account_mismatch: true

risk:
  max_daily_orders: 3
  max_position_count: 1
  max_order_amount_krw: 100000
  max_daily_loss_krw: 30000

strategy:
  name: "previous_close_demo"
  buy_above_prev_close_pct: 0.01
  take_profit_pct: 0.03
  stop_loss_pct: 0.02
```

처음에는 이 값 그대로 두고 `symbol`만 원하는 종목으로 바꾸는 것을 추천합니다.

## 11. 가상환경 생성

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

## 12. 패키지 설치

```bash
pip install -r requirements.txt
```

설치되는 핵심 패키지:

- `httpx`: REST 통신
- `python-dotenv`: `.env` 로딩
- `pydantic`: 설정/모델 검증
- `PyYAML`: `config.yaml` 로딩
- `rich`: 보기 좋은 콘솔 로그
- `pytest`: 테스트

## 13. 실행 방법

### 13-1. dry_run 단일 실행

가장 먼저 이 명령을 권장합니다.

```bash
python run_bot.py --once
```

이 모드에서 기대하는 결과:

- 토큰 발급 성공
- 계좌번호 검증 성공
- 예수금/잔고/시세 조회 성공
- 전략 판단 결과 출력
- 주문 조건이 맞아도 실제 주문 대신 `DRYRUN-...` 응답 저장

### 13-2. 반복 실행

```bash
python run_bot.py
```

이 모드는 `poll_interval_seconds` 간격으로 계속 조회합니다.

중단:

- `Ctrl + C`

### 13-3. mock 주문 테스트

mock 주문까지 실제로 보내보고 싶다면 다음 순서로 진행하세요.

1. `config.yaml`에서 `dry_run: false` 로 변경
2. `environment: mock` 인지 다시 확인
3. `use_mock_only: true` 인지 다시 확인
4. 주문 한도를 매우 작게 유지
5. `python run_bot.py --once` 로 한 번만 실행

추천:

- 처음 mock 주문 테스트도 무조건 `--once`
- 반복 실행은 dry_run과 단일 실행 검증 후에

## 14. 생성되는 파일

실행 후 아래 파일들이 생깁니다.

- `.runtime/token_mock.json`
  - OAuth 토큰 캐시
- `.runtime/state.json`
  - 일일 주문 횟수, 기준 자산, halt 상태
- `.runtime/orders/YYYYMMDD/*.json`
  - 주문 응답 저장
- `logs/bot.log`
  - 실행 로그

## 15. 로그 포맷

로그 포맷은 다음과 같습니다.

```text
YYYY-MM-DD HH:MM:SS | LEVEL | logger_name | message
```

예:

```text
2026-04-01 09:05:10 | INFO     | kiwoom_mock_trader.bot | Bot initialized. environment=mock dry_run=True
```

민감정보 보호:

- 앱키, 시크릿키, 계좌번호, 비밀번호는 로그에서 마스킹됩니다.
- `Bearer ...` 형태 토큰도 로그에서 제거됩니다.
- 원시 요청 전체를 로그로 남기지 않습니다.

## 16. 테스트 방법

### 16-1. 단위 테스트 실행

```bash
pytest -q
```

현재 포함된 테스트:

- `tests/test_auth.py`
  - 토큰 캐시 사용
  - 만료 토큰 자동 재발급
- `tests/test_strategy.py`
  - 매수 신호
  - 손절 매도 신호
- `tests/test_risk.py`
  - 주문 금액 제한
  - 일일 손실 제한
  - 일일 주문 횟수 증가

### 16-2. dry_run 테스트 체크 포인트

다음이 정상이어야 합니다.

- 프로그램이 mock 환경으로 시작한다
- 계좌번호 검증이 통과한다
- 로그에 민감정보가 보이지 않는다
- 주문 신호가 나와도 실제 주문번호 대신 `DRYRUN-...` 이 저장된다

## 17. 자주 나는 오류와 해결법

### 오류 1. `Missing required environment variables`

원인:

- `.env`가 없거나 값이 비어 있음

해결:

- `.env.example`을 `.env`로 복사
- 앱키/시크릿키/모의계좌번호 입력

### 오류 2. `The configured KIWOOM_ACCOUNT_NO was not returned by ka00001`

원인:

- `.env` 계좌번호가 실제 토큰 계좌와 다름
- 실계좌/모의계좌를 혼동함

해결:

- `.env`의 `KIWOOM_ACCOUNT_NO` 재확인
- 모의계좌 번호가 맞는지 확인

### 오류 3. `This sample project is intentionally restricted to the mock environment only`

원인:

- `KIWOOM_ENV` 또는 `config.yaml`의 `environment`를 `production` 등으로 바꿈

해결:

- 둘 다 `mock`으로 고정

### 오류 4. `REST base URL is not the documented mock host`

원인:

- `mock_base_url`을 잘못 적었거나 운영 URL로 바꿈

해결:

- `https://mockapi.kiwoom.com` 으로 복구

### 오류 5. `Authorization failed while calling Kiwoom REST API`

원인:

- 토큰 만료
- 앱키/시크릿키 오류
- 권한 문제

해결:

- `.runtime/token_mock.json` 삭제 후 재실행
- 앱키/시크릿키 재확인
- 키움 쪽 권한 상태 확인

### 오류 6. 주문이 안 나감

원인:

- `dry_run: true`
- 장 시간 아님
- 리스크 제한에 걸림
- 이미 같은 종목/같은 방향 주문이 열려 있음

해결:

- 로그에서 차단 사유 확인
- 처음엔 의도적으로 안 나가는 것이 정상일 수 있음

## 18. 왜 실계좌에 바로 쓰면 안 되나

절대 바로 실계좌에 쓰면 안 되는 이유:

- 샘플 전략은 수익 전략이 아니라 동작 확인용입니다.
- 주문 중복, 장중 예외, API 오류, 필드 해석 실수 같은 문제가 실제 손실로 이어질 수 있습니다.
- REST 응답 필드가 바뀌거나 계좌 상태가 예상과 다를 수 있습니다.
- 초보 단계에서는 로그, 토큰, 상태 파일, 예외 처리 흐름을 먼저 익혀야 합니다.

권장 순서:

1. 단위 테스트 통과
2. `dry_run: true` 로 단일 실행
3. `dry_run: true` 로 반복 실행
4. 아주 작은 금액으로 mock 주문 테스트
5. mock에서 충분히 검증 후 전략/로직 보완

## 19. 실제 프로젝트 확장 아이디어

이 샘플을 다음처럼 확장할 수 있습니다.

- WebSocket 실시간 시세 연동
- 장 시작/종료 이벤트 처리
- 주문 정정/취소 API 추가
- 종목 여러 개 순회
- DB 저장
- Telegram/Slack 알림
- 백테스트 모듈 추가

하지만 처음에는 절대 확장부터 하지 말고, 현재 샘플이 안정적으로 한 사이클 돌아가는지부터 확인하는 것이 좋습니다.

## 20. 처음 실행할 때 해야 할 일

1. 이 폴더로 이동합니다.
2. 가상환경을 만듭니다.
3. `pip install -r requirements.txt` 를 실행합니다.
4. `.env.example` 을 `.env` 로 복사합니다.
5. `.env` 에 앱키, 시크릿키, 모의계좌번호를 넣습니다.
6. `config.yaml.example` 을 `config.yaml` 로 복사합니다.
7. `config.yaml` 에서 종목코드만 먼저 확인합니다.
8. `environment: mock`, `dry_run: true`, `use_mock_only: true` 인지 다시 확인합니다.
9. `pytest -q` 로 단위 테스트를 실행합니다.
10. `python run_bot.py --once` 로 첫 dry_run 테스트를 합니다.
11. 로그와 `.runtime/orders/` 저장 결과를 확인합니다.
12. 그 다음에만 `dry_run: false` 로 바꿔서 mock 주문 단일 테스트를 합니다.

## 21. 마지막 확인

이 프로젝트는 초보자가 위험하게 시작하지 않도록 일부러 보수적으로 만들었습니다.

- 실계좌 차단
- mock URL 강제
- dry_run 기본
- 작은 주문 한도
- 하루 주문 횟수 제한
- 일일 손실 제한
- 예외 발생 시 중단

첫 목표는 돈을 버는 것이 아니라 **실수 없이 자동매매 파이프라인을 이해하는 것**입니다.
