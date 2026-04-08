# 프로덕션 환경 배포 가이드

**작성일**: 2026-04-07
**대상**: Navis AI 자동매매 시스템 전체 통합

---

## 📋 환경변수 설정

### 필수 환경변수 (.env 파일)

```bash
# ============================================
# 1. AI Team (필수)
# ============================================
ANTHROPIC_API_KEY=your_anthropic_key_here
MODEL_NAME=claude-3-5-sonnet-20241022
TEMPERATURE=0.7
MAX_TOKENS=4096
AI_AGENT_TYPE=native

# ============================================
# 2. Execution Team (필수) ⭐⭐⭐
# ============================================
# Alpaca Paper Trading (테스트용)
ALPACA_API_KEY=your_alpaca_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Alpaca Live Trading (실전용 - 주의!)
# ALPACA_BASE_URL=https://api.alpaca.markets

# 실행 엔진 설정
ENABLE_CIRCUIT_BREAKER=true
MAX_RETRY_ATTEMPTS=3
ORDER_STORAGE_PATH=logs/execution/orders

# ============================================
# 3. Data Collection (선택)
# ============================================
NEWS_API_KEY=your_news_api_key_here
# ALPHA_VANTAGE_API_KEY=your_key_here
# FINNHUB_API_KEY=your_key_here

# ============================================
# 4. Strategy Engine (선택)
# ============================================
# 전략 엔진은 별도 환경변수 불필요
# execution_team을 통해 주문 실행

# ============================================
# 5. Telegram (선택 - 알림용)
# ============================================
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_USER_IDS=your_telegram_id

# ============================================
# 6. 로깅
# ============================================
LOG_LEVEL=INFO
LOG_FILE=logs/agent.log
EXECUTION_LOG_FILE=logs/execution/execution.log

# ============================================
# 7. 자동매매 설정 ⭐⭐⭐
# ============================================
# 자동매매 활성화 (true/false)
AUTO_TRADING_ENABLED=true

# 투자 금액 설정 (퍼센트 기반)
MAX_INVESTMENT_PERCENT=10.0    # 1회 최대 투자 (현금의 %)
MAX_DAILY_LOSS_PERCENT=5.0     # 1일 최대 손실 (현금의 %)
MAX_POSITIONS=5                # 최대 동시 보유 종목 수

# 리스크 관리
STOP_LOSS_PERCENT=2.0          # 손절 비율 (%)
TAKE_PROFIT_PERCENT=5.0        # 익절 비율 (%)

# 실행 주기
TRADING_INTERVAL_MINUTES=60    # AI 분석 주기 (분)
```

---

## 🔗 팀 간 연결

### 1. Data Collection → Strategy Engine → AI Team → Execution Team

**데이터 흐름**:
```
[Data Collection] → 시장 데이터 수집
        ↓
[Strategy Engine] → 점수 계산 및 신호 생성
        ↓
[AI Team] → AI 분석 및 매매 결정
        ↓
[Execution Team] → 실제 주문 실행 ⭐
```

### 2. 필요한 환경변수

| 팀 | 환경변수 | 필수 여부 |
|----|----------|-----------|
| **AI Team** | ANTHROPIC_API_KEY | ✅ 필수 |
| **Execution Team** | ALPACA_API_KEY, ALPACA_SECRET_KEY | ✅ 필수 |
| **Data Collection** | NEWS_API_KEY | ⚠️ 선택 |
| **Strategy Engine** | (없음) | ℹ️ 환경변수 없음 |
| **Telegram** | TELEGRAM_BOT_TOKEN | ⚠️ 선택 (알림용) |

---

## 🚀 자동매매 활성화 설정

### 현재 상태
- ❌ 예제 코드에서 주문 실행이 주석 처리됨
- ❌ AI Agent가 수동으로만 작동

### 목표 상태
- ✅ AI Agent가 자동으로 주문 실행
- ✅ 정해진 주기마다 시장 분석
- ✅ 매매 신호 발생 시 자동 주문

---

## 📝 다음 단계

1. **환경변수 설정**
   ```bash
   # .env 파일 수정
   nano .env

   # 필수 항목 확인
   # - ANTHROPIC_API_KEY
   # - ALPACA_API_KEY
   # - ALPACA_SECRET_KEY
   # - AUTO_TRADING_ENABLED=true
   ```

2. **자동매매 스크립트 실행**
   ```bash
   # 자동매매 시작
   python auto_trading_bot.py
   ```

3. **모니터링**
   ```bash
   # 로그 확인
   tail -f logs/execution/execution.log

   # 주문 현황 확인
   python execution_team/examples/check_status.py
   ```

---

## ⚠️ 중요 주의사항

### Paper Trading vs Live Trading

**Paper Trading (테스트용)**:
```bash
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```
- ✅ 가상 돈으로 테스트
- ✅ 실제 손실 없음
- ✅ 시스템 검증용

**Live Trading (실전용)**:
```bash
ALPACA_BASE_URL=https://api.alpaca.markets
```
- ⚠️ 실제 돈 사용
- ⚠️ 실제 손실 발생 가능
- ⚠️ 충분한 테스트 후 사용

### 권장 순서
1. Paper Trading으로 최소 1주일 테스트
2. 모든 기능 정상 작동 확인
3. 소액($100~$1,000)으로 Live Trading 시작
4. 점진적으로 투자 금액 증가

---

## 📊 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    Auto Trading Bot                      │
│                  (자동매매 메인 루프)                      │
└──────────────┬────────────────────────────┬──────────────┘
               │                            │
       ┌───────▼────────┐          ┌───────▼────────┐
       │  Data Collection│          │  Strategy Engine│
       │  (시장 데이터)   │          │  (점수 계산)     │
       └───────┬────────┘          └───────┬────────┘
               │                            │
               └────────────┬───────────────┘
                            │
                    ┌───────▼────────┐
                    │    AI Team     │
                    │  (AI 분석)      │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │ Execution Team │  ⭐ 주문 실행
                    │ (주문 실행)     │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  Alpaca API    │
                    │ (브로커)        │
                    └────────────────┘
```

---

## 🔧 트러블슈팅

### Q1. "ALPACA_API_KEY가 설정되지 않았습니다"
```bash
# .env 파일 확인
cat .env | grep ALPACA

# 없으면 추가
echo "ALPACA_API_KEY=your_key_here" >> .env
echo "ALPACA_SECRET_KEY=your_secret_here" >> .env
```

### Q2. "주문이 실행되지 않습니다"
```bash
# AUTO_TRADING_ENABLED 확인
cat .env | grep AUTO_TRADING_ENABLED

# true로 설정
echo "AUTO_TRADING_ENABLED=true" >> .env
```

### Q3. "시장이 폐장 중입니다"
- 미국 주식 시장 시간: 월~금 9:30 AM - 4:00 PM ET
- 한국 시간: 23:30 - 06:00 (서머타임 22:30 - 05:00)

---

**다음**: `auto_trading_bot.py` 실행으로 자동매매 시작
