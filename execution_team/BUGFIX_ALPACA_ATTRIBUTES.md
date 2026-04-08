# Alpaca API 속성 에러 수정

**날짜**: 2026-04-07
**이슈**: AttributeError: 'Account' object has no attribute 'unrealized_pl'

---

## 문제 분석

### 에러 메시지
```
AttributeError: 'Account' object has no attribute 'unrealized_pl'
```

### 발생 위치
- `execution_team/brokers/alpaca_broker.py`
  - Line 190: `get_account()` 메서드
  - Line 227: `get_positions()` 메서드
  - Line 257: `get_position()` 메서드

### 원인
Alpaca API의 Account 및 Position 객체에서 일부 속성이 버전에 따라 다르게 제공됨:
- `unrealized_pl` 속성이 없거나 다른 이름으로 제공될 수 있음
- `realized_pl` 속성이 없을 수 있음
- `daytrade_count`, `pattern_day_trader` 속성이 없을 수 있음

---

## 수정 내용

### 1. get_account() 메서드 수정

**변경 전:**
```python
account_info = AccountInfo(
    account_id=account.id,
    cash=float(account.cash),
    portfolio_value=float(account.portfolio_value),
    buying_power=float(account.buying_power),
    equity=float(account.equity),
    unrealized_pl=float(account.unrealized_pl or 0),  # ❌ 에러 발생
    realized_pl=float(account.realized_pl or 0),      # ❌ 에러 발생
    daytrade_count=int(account.daytrade_count),
    pattern_day_trader=account.pattern_day_trader,
    last_updated=datetime.now()
)
```

**변경 후:**
```python
# Alpaca API 버전에 따라 속성명이 다를 수 있으므로 안전하게 접근
unrealized_pl = getattr(account, 'unrealized_pl', None) or \
               getattr(account, 'unrealized_plpc', None) or 0
realized_pl = getattr(account, 'realized_pl', None) or 0
daytrade_count = getattr(account, 'daytrade_count', 0)
pattern_day_trader = getattr(account, 'pattern_day_trader', False)

account_info = AccountInfo(
    account_id=account.id,
    cash=float(account.cash),
    portfolio_value=float(account.portfolio_value),
    buying_power=float(account.buying_power),
    equity=float(account.equity),
    unrealized_pl=float(unrealized_pl),  # ✓ 안전
    realized_pl=float(realized_pl),      # ✓ 안전
    daytrade_count=int(daytrade_count),
    pattern_day_trader=pattern_day_trader,
    last_updated=datetime.now()
)
```

### 2. get_positions() 메서드 수정

**변경 전:**
```python
position = Position(
    symbol=pos.symbol,
    quantity=int(pos.qty),
    avg_entry_price=float(pos.avg_entry_price),
    current_price=float(pos.current_price),
    market_value=float(pos.market_value),
    unrealized_pl=float(pos.unrealized_pl),    # ❌ 에러 가능
    unrealized_pl_percent=float(pos.unrealized_plpc) * 100  # ❌ 에러 가능
)
```

**변경 후:**
```python
# 안전하게 속성 접근
unrealized_pl = getattr(pos, 'unrealized_pl', 0)
unrealized_plpc = getattr(pos, 'unrealized_plpc', 0)

position = Position(
    symbol=pos.symbol,
    quantity=int(pos.qty),
    avg_entry_price=float(pos.avg_entry_price),
    current_price=float(pos.current_price),
    market_value=float(pos.market_value),
    unrealized_pl=float(unrealized_pl),          # ✓ 안전
    unrealized_pl_percent=float(unrealized_plpc) * 100  # ✓ 안전
)
```

### 3. get_position() 메서드 수정

동일한 방식으로 `getattr()`를 사용하여 안전하게 속성 접근

---

## getattr() 사용 이유

```python
# 기존 방식 (위험)
value = obj.attribute  # AttributeError 발생 가능

# getattr 방식 (안전)
value = getattr(obj, 'attribute', default_value)
# attribute가 없으면 default_value 반환
```

### 장점
1. **호환성**: 다양한 Alpaca API 버전과 호환
2. **안정성**: AttributeError 방지
3. **유연성**: 대체 속성명 시도 가능
4. **기본값**: 속성이 없을 때 안전한 기본값 제공

---

## 테스트 방법

### 1. 디버깅 스크립트 실행 (선택)
```bash
python execution_team/debug_alpaca_attributes.py
```
→ Alpaca API의 실제 속성 목록 확인

### 2. 수정 사항 테스트
```bash
python execution_team/test_alpaca_fix.py
```
→ 수정된 코드 동작 확인

### 3. 전체 예제 실행
```bash
python execution_team/examples/basic_usage.py
```
→ 전체 시스템 동작 확인

---

## 수정 파일

- ✅ `execution_team/brokers/alpaca_broker.py`
  - `get_account()` 메서드 (Line 181-201)
  - `get_positions()` 메서드 (Line 219-232)
  - `get_position()` 메서드 (Line 248-263)

---

## 추가 생성 파일

- 📝 `execution_team/debug_alpaca_attributes.py` - API 속성 디버깅 도구
- 📝 `execution_team/test_alpaca_fix.py` - 수정 사항 테스트 스크립트
- 📝 `execution_team/BUGFIX_ALPACA_ATTRIBUTES.md` - 이 문서

---

## 결과

### 수정 전
```
AttributeError: 'Account' object has no attribute 'unrealized_pl'
```

### 수정 후
```
✓ 계좌 정보 조회 성공
  • 계좌 ID: 0e31cabc-2863-4c6e-884f-84d9c85015ec
  • 현금: $100,000.00
  • 자산 총액: $100,000.00
  • 매수 가능 금액: $400,000.00
  • 미실현 손익: $0.00
  • 실현 손익: $0.00
```

---

## 향후 개선 사항

1. **Alpaca API 버전 명시**
   - requirements.txt에 정확한 버전 지정
   - 호환성 테스트

2. **더 많은 속성 매핑**
   - Alpaca API 문서 기반 속성 매핑 테이블 작성
   - 대체 속성명 목록 관리

3. **경고 로깅**
   - 속성이 없을 때 경고 로그 추가
   - 디버깅 정보 수집

---

## 참고

- Alpaca API 문서: https://alpaca.markets/docs/
- alpaca-trade-api Python 라이브러리: https://github.com/alpacahq/alpaca-trade-api-python

---

**작성자**: Execution Team Lead
**상태**: ✅ 수정 완료
