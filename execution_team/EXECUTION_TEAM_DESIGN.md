# 주문 실행 팀 (Execution Team) 설계 문서

## 1. 팀 개요

### 역할
실제 매매 실행 및 안정성 확보

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

## 2. 아키텍처 구조

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
│   ├── order_validator.py       # 주문 검증
│   └── logger.py                # 전용 로거
│
├── tests/
│   ├── test_execution_engine.py
│   ├── test_order_manager.py
│   └── test_alpaca_broker.py
│
└── config.py                    # 설정
```

---

## 3. 핵심 컴포넌트 설계

### 3.1 ExecutionEngine (핵심)

**책임**:
- 외부로부터 주문 신호 수신
- 주문 검증 및 생성
- 브로커로 주문 전송
- 체결 확인 및 상태 업데이트

**인터페이스**:
```python
execute_order(signal: OrderSignal) -> OrderResult
get_order_status(order_id: str) -> OrderStatus
cancel_order(order_id: str) -> bool
get_positions() -> List[Position]
```

**주요 흐름**:
1. 신호 수신 → 검증
2. 주문 생성 → DB 저장 (pending)
3. 브로커 전송 → 재시도 로직
4. 체결 확인 → 상태 업데이트
5. 실패 시 → 롤백 및 알림

---

### 3.2 BrokerInterface (추상화)

**목적**: 브로커 교체 가능하도록 추상 인터페이스 제공

**메서드**:
```python
submit_order(order: Order) -> str              # 주문 제출
get_order(order_id: str) -> OrderInfo          # 주문 조회
cancel_order(order_id: str) -> bool            # 주문 취소
get_account() -> AccountInfo                   # 계좌 정보
get_positions() -> List[Position]              # 포지션 조회
```

---

### 3.3 OrderManager (상태 관리)

**책임**:
- 주문 상태 추적
- DB 저장/조회
- 주문 히스토리 관리

**상태 전이**:
```
PENDING → SUBMITTED → FILLED → COMPLETED
                    ↓
                 CANCELLED
                    ↓
                 REJECTED
```

---

### 3.4 RetryHandler (재시도)

**전략**:
- Exponential Backoff
- 최대 3회 재시도
- 재시도 가능 에러 vs 즉시 실패 에러 구분

**재시도 가능 에러**:
- 네트워크 타임아웃
- 일시적 서버 오류 (503)
- Rate limit (429)

**즉시 실패 에러**:
- 잘못된 주문 파라미터
- 계좌 잔고 부족
- 주문 거부

---

## 4. 주문 실행 흐름 (상세)

### 4.1 정상 흐름

```
1. [Signal 수신]
   ↓
2. [주문 검증]
   - 심볼 유효성
   - 수량 검증
   - 가격 검증 (지정가의 경우)
   ↓
3. [주문 생성]
   - Order 객체 생성
   - UUID 할당
   - DB 저장 (status=PENDING)
   ↓
4. [브로커 전송]
   - API 호출
   - 재시도 로직 적용
   - 응답 수신
   ↓
5. [체결 확인]
   - 주문 ID 매핑
   - 상태 업데이트 (SUBMITTED → FILLED)
   - DB 업데이트
   ↓
6. [완료 처리]
   - 체결가 기록
   - 수수료 기록
   - 알림 전송
```

### 4.2 예외 흐름

**네트워크 오류**:
```
전송 실패 → 재시도 (3회) → 여전히 실패 → FAILED 상태 → 알림
```

**주문 거부**:
```
전송 → 거부 응답 → REJECTED 상태 → 원인 로깅 → 알림
```

**부분 체결**:
```
체결 확인 → 부분 체결 감지 → PARTIALLY_FILLED 상태 → 지속 모니터링
```

---

## 5. 안전장치 (Safety Measures)

### 5.1 Pre-Flight 체크
- 계좌 잔고 확인
- 시장 개장 시간 확인
- 일일 거래 한도 확인
- 중복 주문 방지

### 5.2 Post-Flight 검증
- 체결 가격 검증 (슬리피지 체크)
- 수량 일치 확인
- 수수료 기록

### 5.3 Circuit Breaker
- 연속 실패 5회 → 자동 중단
- 비정상 슬리피지 감지 → 경고
- 계좌 손실 한계 도달 → 매매 중단

---

## 6. 데이터 모델

### OrderSignal (입력)
```python
{
    "symbol": "TSLA",
    "action": "BUY",           # BUY, SELL
    "order_type": "MARKET",    # MARKET, LIMIT
    "quantity": 10,
    "limit_price": 210.0,      # 지정가인 경우
    "time_in_force": "DAY",    # DAY, GTC, IOC
    "strategy_id": "strategy_001",
    "metadata": {...}
}
```

### OrderResult (출력)
```python
{
    "order_id": "uuid-1234",
    "status": "FILLED",
    "filled_price": 210.5,
    "filled_quantity": 10,
    "filled_at": "2024-04-06T10:30:00",
    "commission": 1.5,
    "error": None
}
```

---

## 7. 로깅 전략

### 로그 레벨
- **INFO**: 주문 생성, 체결 완료
- **WARNING**: 재시도 발생, 부분 체결
- **ERROR**: 주문 실패, 체결 확인 실패
- **CRITICAL**: 계좌 손실 한계, 시스템 중단

### 로그 저장
- 파일: `logs/execution/YYYY-MM-DD.log`
- DB: `orders` 테이블에 모든 주문 기록
- 메트릭: 성공률, 평균 체결 시간, 슬리피지

---

## 8. 성능 요구사항

- **주문 응답 시간**: < 500ms (95 percentile)
- **체결 확인 시간**: < 5초
- **가용성**: 99.5% (시장 개장 시간 기준)
- **동시 주문 처리**: 최대 10개

---

## 9. 보안

- API 키 암호화 저장
- 환경 변수로 관리
- 로그에 민감 정보 마스킹
- HTTPS 통신 강제

---

## 10. 테스트 전략

### 단위 테스트
- 각 모듈별 독립 테스트
- Mock 브로커 사용

### 통합 테스트
- Alpaca Paper Trading 환경 사용
- 실제 API 연동 테스트

### 시나리오 테스트
- 네트워크 장애 시뮬레이션
- 부분 체결 시나리오
- 동시 주문 처리

---

## 11. 모니터링 지표

### 핵심 메트릭
- 주문 성공률
- 평균 슬리피지
- 평균 체결 시간
- 재시도 발생률
- 에러율 (에러 타입별)

### 알림 조건
- 주문 실패
- 체결 확인 실패
- 비정상 슬리피지 (> 0.5%)
- 연속 실패 3회 이상

---

## 12. 향후 확장

### Phase 2
- IBKR 브로커 추가
- 옵션 거래 지원
- 복잡 주문 (bracket, OCO)

### Phase 3
- 멀티 브로커 동시 실행
- 스마트 라우팅
- 실시간 포지션 관리 대시보드

---

## 13. 팀 원칙

1. **코드는 항상 실패를 가정하고 작성한다**
2. **모든 외부 호출은 타임아웃과 재시도를 설정한다**
3. **상태 변화는 반드시 로깅한다**
4. **테스트 없는 배포는 없다**
5. **문서화는 코드와 동시에 업데이트한다**

---

**작성자**: Execution Team Lead
**작성일**: 2026-04-06
**버전**: 1.0
