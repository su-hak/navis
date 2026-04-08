# 주문 실행 팀 (Execution Team)

실제 매매 실행 및 안정성 확보를 담당하는 팀

---

## 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [아키텍처](#아키텍처)
- [설치](#설치)
- [사용법](#사용법)
- [API 레퍼런스](#api-레퍼런스)
- [테스트](#테스트)
- [안전장치](#안전장치)

---

## 개요

주문 실행 팀은 AI 자동매매 시스템에서 **실제 주문을 실행하는 핵심 모듈**입니다.

### 핵심 책임

- 브로커 API 연동 (Alpaca / IBKR)
- 주문 생성 및 전송
- 체결 확인 및 추적
- 예외 처리 및 재시도
- 주문 상태 관리

### 설계 철학

1. **안정성 우선**: 모든 코드는 실패를 가정하고 작성
2. **명확한 책임 분리**: 각 모듈은 단일 책임만 수행
3. **추상화**: 브로커 교체 가능한 아키텍처
4. **로깅**: 모든 주문 단계 기록
5. **멱등성**: 동일 요청 중복 실행 방지

---

## 주요 기능

### 1. 주문 실행
- 시장가 / 지정가 주문
- 매수 / 매도
- 다양한 유효기간 설정 (DAY, GTC, IOC, FOK)

### 2. 안정성
- 자동 재시도 (Exponential Backoff)
- 서킷 브레이커 (연속 실패 시 자동 차단)
- Pre-flight 체크 (계좌 잔고, 시장 상태 등)

### 3. 상태 관리
- 실시간 주문 상태 추적
- 주문 히스토리 저장
- 체결 확인 및 기록

### 4. 모니터링
- 주문 통계
- 성공률 추적
- 실행 시간 측정

---

## 아키텍처

```
execution_team/
├── core/
│   ├── execution_engine.py      # 주문 실행 엔진 (메인)
│   ├── order_manager.py         # 주문 상태 관리
│   └── order_models.py          # 주문 데이터 모델
│
├── brokers/
│   ├── broker_interface.py      # 브로커 추상 인터페이스
│   ├── alpaca_broker.py         # Alpaca 구현체
│   └── ibkr_broker.py           # IBKR 구현체 (향후)
│
├── utils/
│   ├── retry_handler.py         # 재시도 로직
│   └── logger.py                # 전용 로거
│
├── tests/                       # 테스트
├── examples/                    # 사용 예제
├── config.py                    # 설정
└── api.py                       # FastAPI 엔드포인트
```

### 데이터 흐름

```
[전략 신호] → [ExecutionEngine] → [브로커 API] → [실제 주문]
                    ↓
            [OrderManager] → [DB/파일 저장]
                    ↓
               [상태 업데이트]
```

---

## 설치

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일 생성:

```env
# Alpaca API (Paper Trading)
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# 실행 설정
ENABLE_CIRCUIT_BREAKER=true
MAX_RETRY_ATTEMPTS=3
ORDER_STORAGE_PATH=logs/execution/orders

# 로깅
LOG_LEVEL=INFO
EXECUTION_LOG_FILE=logs/execution/execution.log
```

### 3. 로그 디렉토리 생성

```bash
mkdir -p logs/execution/orders
```

---

## 사용법

### 방법 1: Python 코드에서 직접 사용

```python
from execution_team.core import (
    ExecutionEngine, OrderManager, OrderSignal,
    OrderAction, OrderType
)
from execution_team.brokers import AlpacaBroker

# 1. 브로커 초기화
broker_config = {
    'api_key': 'your_api_key',
    'secret_key': 'your_secret_key',
    'base_url': 'https://paper-api.alpaca.markets'
}
broker = AlpacaBroker(broker_config)
broker.connect()

# 2. 주문 관리자 초기화
order_manager = OrderManager(storage_path="logs/execution/orders")

# 3. 실행 엔진 초기화
engine = ExecutionEngine(
    broker=broker,
    order_manager=order_manager,
    enable_circuit_breaker=True
)

# 4. 주문 신호 생성
signal = OrderSignal(
    symbol="AAPL",
    action=OrderAction.BUY,
    order_type=OrderType.MARKET,
    quantity=10,
    strategy_id="my_strategy"
)

# 5. 주문 실행
result = engine.execute_order(signal)

if result.success:
    print(f"주문 성공! ID: {result.order_id}")
    print(f"체결가: ${result.filled_price:.2f}")
else:
    print(f"주문 실패: {result.error_message}")

# 6. 정리
broker.disconnect()
```

### 방법 2: FastAPI 서버 사용

#### 서버 시작

```bash
python -m execution_team.api
```

또는

```bash
uvicorn execution_team.api:app --host 0.0.0.0 --port 8001
```

#### API 호출

```bash
# 주문 실행
curl -X POST "http://localhost:8001/orders/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "action": "BUY",
    "order_type": "MARKET",
    "quantity": 10,
    "strategy_id": "test_strategy"
  }'

# 계좌 정보 조회
curl "http://localhost:8001/account"

# 포지션 조회
curl "http://localhost:8001/positions"

# 주문 상태 조회
curl "http://localhost:8001/orders/{order_id}/status"

# 주문 취소
curl -X POST "http://localhost:8001/orders/{order_id}/cancel"

# 통계 조회
curl "http://localhost:8001/stats"
```

---

## API 레퍼런스

### OrderSignal (입력)

```python
{
    "symbol": str,              # 종목 심볼 (예: "TSLA")
    "action": "BUY" | "SELL",  # 매수/매도
    "order_type": "MARKET" | "LIMIT",  # 주문 타입
    "quantity": int,            # 수량
    "limit_price": float,       # 지정가 (LIMIT인 경우)
    "time_in_force": "DAY" | "GTC" | "IOC" | "FOK",
    "strategy_id": str,         # 전략 ID (옵션)
    "reason": str               # 매매 이유 (옵션)
}
```

### OrderResult (출력)

```python
{
    "success": bool,            # 성공 여부
    "order_id": str,            # 주문 ID
    "broker_order_id": str,     # 브로커 주문 ID
    "status": str,              # 주문 상태
    "filled_quantity": int,     # 체결 수량
    "filled_price": float,      # 체결가
    "commission": float,        # 수수료
    "execution_time_ms": float, # 실행 시간 (ms)
    "error_message": str        # 에러 메시지 (실패 시)
}
```

### OrderStatus (상태)

- `PENDING`: 대기 중
- `VALIDATING`: 검증 중
- `SUBMITTED`: 브로커에 제출됨
- `PARTIALLY_FILLED`: 부분 체결
- `FILLED`: 완전 체결
- `CANCELLED`: 취소됨
- `REJECTED`: 거부됨
- `FAILED`: 실패

---

## 테스트

### 단위 테스트 실행

```bash
pytest execution_team/tests/test_execution_engine.py -v
```

### 전체 테스트 실행

```bash
pytest execution_team/tests/ -v
```

### 커버리지 확인

```bash
pytest --cov=execution_team execution_team/tests/
```

---

## 안전장치

### 1. Pre-Flight 체크

주문 전송 전 다음을 검증:
- 브로커 연결 상태
- 계좌 잔고 (매수 시)
- 시장 개장 여부 (옵션)
- 주문 파라미터 유효성

### 2. 재시도 로직

- Exponential Backoff 알고리즘
- 최대 3회 재시도
- 재시도 가능 에러 vs 즉시 실패 에러 구분

**재시도 가능 에러:**
- 네트워크 타임아웃
- 일시적 서버 오류 (503)
- Rate limit (429)

**즉시 실패 에러:**
- 잘못된 주문 파라미터
- 계좌 잔고 부족
- 인증 실패

### 3. 서킷 브레이커

- 연속 5회 실패 시 자동 차단
- 60초 후 자동 복구 시도
- 수동 리셋 가능

```python
# 서킷 브레이커 리셋
engine.reset_circuit_breaker()
```

### 4. 체결 확인

- 시장가 주문: 자동으로 체결 확인 (타임아웃 10초)
- 지정가 주문: 수동으로 상태 조회 필요

### 5. 로깅

모든 주문 단계가 로그로 기록됨:

```
2026-04-06 10:30:00 - INFO - 주문 생성 - ID: abc123, BUY 10 TSLA
2026-04-06 10:30:01 - INFO - 주문 제출 성공 - 브로커 ID: ALPACA_xyz
2026-04-06 10:30:02 - INFO - 주문 완전 체결 - ID: abc123, 가격: $210.50
```

---

## 모니터링 지표

### 주문 통계

```python
stats = engine.get_execution_stats()

{
    'total': 100,                      # 전체 주문 수
    'by_status': {
        'FILLED': 95,
        'CANCELLED': 3,
        'FAILED': 2
    },
    'by_symbol': {
        'TSLA': 50,
        'AAPL': 30,
        'NVDA': 20
    },
    'success_rate': 95.0               # 성공률 (%)
}
```

---

## 브로커 추가하기

새로운 브로커를 추가하려면 `BrokerInterface`를 구현:

```python
from execution_team.brokers import BrokerInterface

class MyBroker(BrokerInterface):
    def connect(self) -> bool:
        # 연결 로직
        pass

    def submit_order(self, order) -> str:
        # 주문 제출 로직
        pass

    # 나머지 메서드 구현...
```

---

## 문제 해결

### 브로커 연결 실패

```
BrokerError: Alpaca 연결 실패
```

**해결:**
1. API 키가 올바른지 확인
2. base_url이 올바른지 확인 (paper vs live)
3. 인터넷 연결 확인

### 주문 실패

```
OrderResult: success=False, error_message="잔고 부족"
```

**해결:**
1. 계좌 잔고 확인
2. 주문 수량 줄이기
3. Paper Trading 계좌 사용 권장

### 서킷 브레이커 차단

```
Exception: 서킷 브레이커 OPEN - 5회 연속 실패 후 차단됨
```

**해결:**
1. 에러 로그 확인
2. 브로커 상태 확인
3. 서킷 브레이커 수동 리셋: `engine.reset_circuit_breaker()`

---

## 팀 연락처

**팀장**: Execution Team Lead
**담당 영역**: 주문 실행 및 안정성 확보
**문서 버전**: 1.0.0
**작성일**: 2026-04-06

---

## 라이선스

이 프로젝트는 Navis AI 자동매매 시스템의 일부입니다.
