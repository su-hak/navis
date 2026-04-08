# Trading 파트 팀별 담당 영역

## 🔍 기획서 분석 결과

trading 로직은 **단일 팀이 아니라 여러 팀에 분산**되어 있습니다!

---

## 📋 팀별 담당 영역 매핑

### 🎯 현재 상태

| 팀 번호 | 팀 이름 | 담당 영역 | 상태 |
|--------|---------|----------|------|
| 1️⃣ | 데이터 수집 팀 | 데이터 수집 + DB 저장 | ✅ 완료 (data_collection) |
| 2️⃣ | 전략 엔진 팀 | 점수 계산 + 시그널 생성 | ✅ 완료 (strategy_engine) |
| 3️⃣ | AI / RAG 팀 | 뉴스 분석 + LangChain | ❌ 미구현 |
| 4️⃣ | 주문 실행 팀 | 브로커 API + 주문 실행 | ❌ 미구현 |
| 5️⃣ | 리스크 관리 팀 | 손절/익절 + 포지션 관리 | ❌ 미구현 |
| 6️⃣ | 백엔드 / 인프라 팀 | 스케줄러 + 시스템 통합 | ❌ 미구현 |
| 7️⃣ | 알림 / 리포트 팀 | 텔레그램 + 리포트 | ❌ 미구현 |
| 8️⃣ | QA / 테스트 팀 | 백테스트 + 검증 | ❌ 미구현 |

---

## 🎯 Trading 로직 구성 요소

### "trading" 모듈이 필요한 기능:

```python
# trading/
├── scheduler.py         → 6️⃣ 백엔드 팀
├── risk_manager.py      → 5️⃣ 리스크 관리 팀
├── execution.py         → 4️⃣ 주문 실행 팀
├── notification.py      → 7️⃣ 알림 팀
└── orchestrator.py      → 6️⃣ 백엔드 팀 (전체 조율)
```

---

## 📊 상세 팀별 담당

### 3️⃣ AI / RAG 팀 (AI Team)

**담당 영역** (기획서 라인 337-356):
- ✅ 뉴스 분석 (감성/이벤트)
- ✅ RAG 구축
- ✅ LangChain Agent 구성
- ✅ 프롬프트 설계

**산출물**:
- AI 분석 결과 (점수 보정값)
- 뉴스 기반 리스크 판단

**Trading에서 필요한 부분**:
```python
# ai_agent.py
def analyze_news_sentiment(symbol: str) -> float:
    """뉴스 감성 분석 (-1.0 ~ 1.0)"""
    pass

def get_news_count(symbol: str) -> int:
    """최근 뉴스 개수"""
    pass

def assess_market_risk() -> dict:
    """시장 전체 리스크 평가"""
    pass
```

**API 제공**:
- `POST /ai/analyze-news`
- `POST /ai/market-risk`

---

### 4️⃣ 주문 실행 팀 (Execution Team) ⭐

**담당 영역** (기획서 라인 359-377):
- ✅ 브로커 API 연동 (Alpaca / IBKR)
- ✅ 주문 생성 및 전송
- ✅ 체결 확인
- ✅ 예외 처리 및 재시도

**산출물**:
- `execute_order()` 모듈
- 주문 상태 관리 시스템

**Trading에서 필요한 부분**:
```python
# execution.py
def execute_order(signal: dict) -> dict:
    """
    주문 실행

    Args:
        signal: {
            'symbol': 'AAPL',
            'action': 'BUY',
            'entry_price': 150.0,
            'quantity': 10
        }

    Returns:
        {
            'order_id': '12345',
            'status': 'FILLED',
            'filled_price': 150.05
        }
    """
    # Alpaca API 호출
    # 체결 확인
    # 재시도 로직
    pass

def cancel_order(order_id: str) -> bool:
    """주문 취소"""
    pass

def get_order_status(order_id: str) -> dict:
    """주문 상태 조회"""
    pass
```

**실행 흐름** (기획서 라인 174-182):
```
signal 생성
 → 주문 요청
 → 브로커 전송
 → 체결 확인
 → DB 저장
```

---

### 5️⃣ 리스크 관리 팀 (Risk Team) ⭐

**담당 영역** (기획서 라인 380-397):
- ✅ 손절/익절 로직
- ✅ 포지션 사이징
- ✅ 하루 손실 제한
- ✅ 포트폴리오 리스크 관리

**산출물**:
- `risk_manager` 모듈
- 포지션 관리 로직

**Trading에서 필요한 부분**:
```python
# risk_manager.py
class RiskManager:
    def __init__(self):
        self.max_daily_loss = 0.05  # -5%
        self.max_position_size = 0.20  # 20%
        self.max_positions = 5

    def validate_signal(self, signal: dict) -> bool:
        """
        시그널 검증 (리스크 룰 적용)

        Returns:
            True: 주문 실행 가능
            False: 리스크 룰 위반
        """
        # 1. 하루 최대 손실 체크
        if self.get_daily_loss() <= -self.max_daily_loss:
            return False

        # 2. 포지션 수 제한
        if self.get_position_count() >= self.max_positions:
            return False

        # 3. 포지션 크기 제한
        if signal['position_size'] > self.max_position_size:
            return False

        return True

    def calculate_position_size(self, signal: dict, account_value: float) -> int:
        """포지션 크기 계산 (주식 수)"""
        max_investment = account_value * self.max_position_size
        shares = int(max_investment / signal['entry_price'])
        return shares

    def should_stop_loss(self, position: dict) -> bool:
        """손절 여부 판단"""
        loss_pct = (position['current_price'] - position['entry_price']) / position['entry_price']
        return loss_pct <= -0.02  # -2%

    def should_take_profit(self, position: dict) -> bool:
        """익절 여부 판단"""
        profit_pct = (position['current_price'] - position['entry_price']) / position['entry_price']
        return profit_pct >= 0.10  # +10%
```

**필수 룰** (기획서 라인 142-147):
- 손절 필수
- 하루 최대 손실 제한 (ex: -5%)
- 포지션 수 제한
- 슬리피지 고려

---

### 6️⃣ 백엔드 / 인프라 팀 (Backend Team) ⭐

**담당 영역** (기획서 라인 400-419):
- ✅ 전체 시스템 연결 및 API 제공
- ✅ DB 설계 및 관리
- ✅ 서비스 간 통신 구조 설계
- ✅ **스케줄러 구성** ← 핵심!

**산출물**:
- REST API 서버
- DB 스키마

**Trading에서 필요한 부분**:
```python
# scheduler.py
import schedule
import time

def run_trading_cycle():
    """전체 매매 사이클 실행"""
    # 1. data_collection DB에서 데이터 조회
    # 2. strategy_engine API 호출
    # 3. ai_team API 호출 (뉴스 분석)
    # 4. risk_manager 검증
    # 5. execution_team에 주문 전달
    # 6. notification_team에 알림 전달
    pass

def start_scheduler():
    """스케줄러 시작"""
    # 매 5분마다 실행
    schedule.every(5).minutes.do(run_trading_cycle)

    # 장 시작 전 초기화
    schedule.every().day.at("09:00").do(initialize_trading_day)

    # 장 마감 후 리포트
    schedule.every().day.at("16:30").do(generate_daily_report)

    while True:
        schedule.run_pending()
        time.sleep(60)

# orchestrator.py
def orchestrate_trade(symbol: str):
    """전체 매매 프로세스 조율"""
    # 1. 데이터 조회
    data = data_collection.get_latest_data(symbol)

    # 2. 전략 엔진 호출
    signal = strategy_engine.generate_signal(data)

    # 3. AI 분석
    ai_analysis = ai_team.analyze_news(symbol)

    # 4. 리스크 검증
    if not risk_manager.validate(signal):
        return

    # 5. 주문 실행
    order = execution_team.execute_order(signal)

    # 6. 알림
    notification_team.send_alert(order)
```

---

### 7️⃣ 알림 / 리포트 팀 (Notification Team) ⭐

**담당 영역** (기획서 라인 422-437):
- ✅ 텔레그램 봇 개발
- ✅ 거래 알림 전송
- ✅ 일일 리포트 생성

**산출물**:
- 알림 시스템
- 리포트 메시지 포맷

**Trading에서 필요한 부분**:
```python
# notification.py
import requests

TELEGRAM_BOT_TOKEN = "..."
TELEGRAM_CHAT_ID = "..."

def send_telegram_alert(message: str):
    """텔레그램 알림 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    })

def notify_trade_execution(order: dict):
    """매매 체결 알림"""
    message = f"""
🚀 *매수 체결*
종목: {order['symbol']}
진입가: ${order['filled_price']}
수량: {order['quantity']}
금액: ${order['filled_price'] * order['quantity']}
"""
    send_telegram_alert(message)

def notify_stop_loss(position: dict):
    """손절 알림"""
    loss_pct = (position['exit_price'] - position['entry_price']) / position['entry_price']
    message = f"""
🛑 *손절 체결*
종목: {position['symbol']}
손실률: {loss_pct:.2%}
잔고: ${get_account_balance()}
"""
    send_telegram_alert(message)

def generate_daily_report():
    """일일 리포트 생성"""
    # 오늘 거래 내역
    # 수익/손실
    # 보유 포지션
    pass
```

**알림 예시** (기획서 라인 223-235):
```
[매수 체결]
TSLA
진입가: 210

[손절]
-2%

[잔고]
1,032,000원
```

---

### 8️⃣ QA / 테스트 팀 (QA Team)

**담당 영역** (기획서 라인 441-453):
- ✅ 백테스트
- ✅ 페이퍼 트레이딩 검증
- ✅ 오류 케이스 테스트

**산출물**:
- 테스트 리포트
- 전략 검증 결과

**Trading에서 필요한 부분**:
```python
# backtest.py
def run_backtest(start_date, end_date):
    """백테스트 실행"""
    pass

# paper_trading.py
def run_paper_trading():
    """페이퍼 트레이딩 실행 (실제 돈 사용 안함)"""
    pass
```

---

## 🎯 팀별 우선순위

### 필수 팀 (즉시 필요):

1. **6️⃣ 백엔드 팀** ⭐⭐⭐
   - 스케줄러 + 전체 조율
   - 가장 중요!

2. **5️⃣ 리스크 관리 팀** ⭐⭐⭐
   - 손실 방지
   - 매우 중요!

3. **4️⃣ 주문 실행 팀** ⭐⭐⭐
   - 실제 매매
   - 매우 중요!

4. **7️⃣ 알림 팀** ⭐⭐
   - 모니터링
   - 중요

### 선택적 팀 (나중에):

5. **3️⃣ AI 팀** ⭐
   - 뉴스 분석 (strategy_engine에서 간단히 대체 가능)

6. **8️⃣ QA 팀** ⭐
   - 백테스트 (나중에)

---

## 📦 배포 구조

### 옵션 A: 각 팀이 별도 Railway 프로젝트

```
Railway 프로젝트 #1: data_collection
Railway 프로젝트 #2: strategy_engine
Railway 프로젝트 #3: ai_team
Railway 프로젝트 #4: execution_team
Railway 프로젝트 #5: risk_team
Railway 프로젝트 #6: backend_team
Railway 프로젝트 #7: notification_team
```

**단점**: 관리 복잡, 비용 증가

---

### 옵션 B: data_collection에 통합 (권장) ⭐

```
data_collection/
├── collectors/          (팀 #1: 데이터 수집)
├── schedulers/          (팀 #6: 백엔드)
├── trading/
│   ├── orchestrator.py  (팀 #6: 백엔드)
│   ├── risk_manager.py  (팀 #5: 리스크 관리)
│   ├── execution.py     (팀 #4: 주문 실행)
│   └── notification.py  (팀 #7: 알림)
└── ai/                  (팀 #3: AI, 선택적)
```

**장점**: 간단, 빠름, 저렴

---

## ✅ 결론

**Q: trading 파트가 3,4,5,6,7,8 팀 중에 있니?**

**A: 네! 여러 팀에 분산되어 있습니다!**

- **4️⃣ 주문 실행 팀**: execution.py
- **5️⃣ 리스크 관리 팀**: risk_manager.py
- **6️⃣ 백엔드 팀**: scheduler.py, orchestrator.py
- **7️⃣ 알림 팀**: notification.py
- 3️⃣ AI 팀: (선택적) ai_agent.py
- 8️⃣ QA 팀: (선택적) backtest.py

---

## 🚀 다음 단계

**각 팀에게 맡기세요!**

1. **백엔드 팀**: 스케줄러 + 전체 조율
2. **리스크 관리 팀**: 리스크 룰 구현
3. **주문 실행 팀**: Alpaca API 연동
4. **알림 팀**: 텔레그램 봇

**또는**:

한 사람이 모든 팀 역할을 하려면 data_collection에 통합!
