# Kiwoom Open API Workspace

키움증권 REST API + WebSocket 기반으로 만든 국내주식 프로젝트 모음 저장소입니다.

현재 이 저장소에는 아래 2개 프로젝트가 포함되어 있습니다.

## 1. `kiwoom_mock_trader`

키움 REST API 공식 문서 기준으로 작성한 모의투자 전용 자동매매 입문 프로젝트입니다.

주요 특징:

- Python 3.11 기반
- 키움 REST API OAuth 인증
- 모의투자 계좌 검증
- 예수금 / 잔고 / 현재가 / 일봉 조회
- 매우 단순한 샘플 전략
- `dry_run` 기본 활성화
- `use_mock_only` 기본 활성화
- 테스트 코드 포함

용도:

- 키움 REST API 흐름을 처음 익힐 때
- 모의투자 주문 흐름을 안전하게 확인할 때
- 자동매매 기초 구조를 학습할 때

프로젝트 문서:

- [`kiwoom_mock_trader/README.md`](./kiwoom_mock_trader/README.md)

## 2. `kiwoom_readonly_dashboard`

키움 REST API + WebSocket 기반 조회용 대시보드 프로젝트입니다.

기존 조회 기능 위에 `52주 신고가 기반 눌림목 매수 시스템`의 전략 엔진, 신호 생성, 리스크 관리, 모의주문 흐름까지 확장했습니다.

주요 특징:

- FastAPI 백엔드 + Next.js 프론트엔드
- 계좌 요약 / 보유 종목 / 종목 검색 / 차트 / 뉴스
- 키움 WebSocket 실시간 데이터 relay
- 52주 신고가 후보군 스캐너
- 눌림목 전략 판정 엔진
- 신호 큐 / 차단 사유 / 주문 로그 시각화
- 기본값은 조회 + 신호 생성 + 모의주문만 허용
- 실주문은 feature flag 로 완전 분리

기본 안전값:

- `AUTO_BUY_ENABLED=false`
- `PAPER_TRADING=true`
- `USE_MOCK_ONLY=true`
- `REAL_ORDER_ENABLED=false`

프로젝트 문서:

- [`kiwoom_readonly_dashboard/README.md`](./kiwoom_readonly_dashboard/README.md)

## 현재까지 완료한 작업

### 공통

- 민감정보는 `.env` 에서만 읽도록 구성
- 프론트엔드에서 키움 API 직접 호출 금지
- 백엔드 프록시를 통해서만 키움 REST / WebSocket 사용
- 로그에 민감정보 남기지 않도록 주의

### `kiwoom_mock_trader`

- 모의투자 계좌 인증 성공
- 모의계좌 검증 로직 구현
- 샘플 전략 + 리스크 관리 구현
- `pytest` 테스트 통과

### `kiwoom_readonly_dashboard`

- 조회용 대시보드 완성
- WebSocket 단일 upstream + 다중 브로드캐스트 구조 반영
- 52주 신고가 스캐너 / 눌림목 전략 / 신호 엔진 / 리스크 관리 / paper broker 추가
- 백엔드 테스트 통과
- 프론트엔드 빌드 통과

## 저장소 운영 원칙

- 실계좌 자동주문은 기본 비활성화 상태를 유지합니다.
- 모의투자 / paper trading 중심으로 검증합니다.
- `.env`, `config.yaml`, 로그, 런타임 상태 파일은 커밋하지 않습니다.
- 키움 Open API 설치 파일이나 개인 개발 산출물은 저장소에 포함하지 않습니다.

## 주의사항

- 이 저장소는 학습, 검증, 모의투자, 전략 실험을 위한 프로젝트입니다.
- 충분한 검증 없이 실계좌 자동매매를 바로 활성화하면 안 됩니다.
- 키움 WebSocket 은 같은 App Key 기준 세션 충돌이 생길 수 있으므로 연결 구조를 신중하게 다뤄야 합니다.

## 폴더 구조

```text
Kiwoom-Open-API/
  README.md
  .gitignore
  kiwoom_mock_trader/
  kiwoom_readonly_dashboard/
```

## 다음 목표

- 조건검색 실시간 편입/이탈 감시 안정화
- 전략 리플레이 / 백테스트 화면 보강
- 운영 모니터링 및 로그 시각화 개선
- 실전 전환 전 검증 절차 문서화
