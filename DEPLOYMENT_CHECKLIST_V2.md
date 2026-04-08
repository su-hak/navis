# V2 배포 체크리스트

## ✅ 빠른 답변

### Q1: Railway 재배포 필요한가요?
**❌ 아니요!** 모든 것이 로컬에서 작동합니다.

### Q2: 환경변수 추가해야 하나요?
**✅ 예!** `.env` 파일에 V2 환경변수 추가 필요

### Q3: utils 도메인 배포해야 하나요?
**❌ 아니요!** 로컬 라이브러리입니다.

---

## 📋 배포 전 체크리스트

### ✅ 필수 작업

- [ ] `.env` 파일 업데이트
  ```env
  # V2 신규 환경변수 추가
  AUTO_TRADING_ENABLED=false
  MARKET_SCAN_INTERVAL_MINUTES=5
  GAP_THRESHOLD=3.0
  VOLUME_RATIO_THRESHOLD=3.0
  MAX_WATCHLIST_SIZE=20
  MONITOR_INTERVAL_SECONDS=10
  PRICE_CHANGE_THRESHOLD=1.5
  MAX_INVESTMENT_PERCENT=10.0
  STOP_LOSS_PERCENT=2.0
  MAX_DAILY_LOSS_PERCENT=5.0
  MAX_POSITIONS=5
  LOG_LEVEL=DEBUG
  ```

- [ ] 기존 환경변수 확인
  ```env
  ALPACA_API_KEY=<있음>
  ALPACA_SECRET_KEY=<있음>
  ALPACA_BASE_URL=https://paper-api.alpaca.markets
  ```

- [ ] 임포트 테스트
  ```powershell
  python test_imports.py
  ```

- [ ] V2 봇 실행
  ```powershell
  python auto_trading_bot_v2.py
  ```

### ❌ 불필요한 작업

- [ ] ~~Railway data_collection 재배포~~ (불필요)
- [ ] ~~Railway strategy_engine 재배포~~ (불필요)
- [ ] ~~utils 도메인 배포~~ (로컬 라이브러리)
- [ ] ~~execution_team 배포~~ (로컬에서만 사용)

---

## 🚀 배포 명령어 (3줄)

```powershell
# 1. .env 업데이트
notepad .env

# 2. 임포트 테스트 (선택)
python test_imports.py

# 3. V2 봇 실행
python auto_trading_bot_v2.py
```

**끝!**

---

## 📊 도메인별 배포 상태

| 도메인 | 수정됨 | Railway 재배포 | 이유 |
|--------|--------|----------------|------|
| data_collection | ✅ | ❌ 불필요 | 로컬에서만 사용 |
| execution_team | ✅ | ❌ 불필요 | 로컬 라이브러리 |
| utils | ✅ 신규 | ❌ 불필요 | 로컬 라이브러리 |
| strategy_engine | ✅ | ❌ 불필요 | 기존 유지만 |
| auto_trading_bot_v2 | ✅ 신규 | ✅ 로컬 실행 | 메인 봇 |

---

## ⚠️ 안전 체크

### 자동매매 활성화 경고

```env
# ⚠️ 반드시 false로 시작!
AUTO_TRADING_ENABLED=false
```

**이유**:
- `true` = 실제 주문 실행
- Paper Trading이지만 신중하게
- 테스트 완료 후 `true`로 변경

### 브로커 URL 확인

```env
# ✅ Paper Trading (안전)
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# ⚠️ Live Trading (위험!)
# ALPACA_BASE_URL=https://api.alpaca.markets  # 절대 사용 금지!
```

---

## 🧪 테스트 시나리오

### 시나리오 1: 장외 시간 (현재)

```
워치리스트: 0개 (정상)
Stage 2: 작동 안 함 (정상)
```

### 시나리오 2: 장중 시간 (23:30~06:00)

```
워치리스트: 1~5개 (정상)
Stage 2: 10초마다 감시 (정상)
변동 1.5% 도달 시 → 매수 신호 발생
```

### 시나리오 3: 급등 종목 포착

```
[NVDA] $850.00 → $862.75 (+1.50%) ⚡
→ 매수 신호!
→ AUTO_TRADING_ENABLED=true면 주문 실행
→ AUTO_TRADING_ENABLED=false면 로그만 출력
```

---

## 📞 문제 해결

### 문제 1: "No module named 'dotenv'"

```powershell
pip install python-dotenv
```

### 문제 2: "No module named 'data_collection.monitoring'"

```powershell
# 현재 디렉토리 확인
pwd
# C:\navis가 아니면 이동
cd C:\navis

# 다시 실행
python auto_trading_bot_v2.py
```

### 문제 3: "워치리스트 0개"

**정상입니다!**
- 장외 시간이라 데이터 없음
- 오늘 밤 23:30에 다시 실행

### 문제 4: Stage 2 로그 안 보임

```env
# .env 파일에서
LOG_LEVEL=DEBUG
```

---

## 🎯 최종 확인

### 실행 전 마지막 체크

```powershell
# 1. 현재 디렉토리 확인
cd C:\navis

# 2. .env 파일 존재 확인
dir .env

# 3. AUTO_TRADING_ENABLED 확인
type .env | findstr "AUTO_TRADING_ENABLED"
# 출력: AUTO_TRADING_ENABLED=false

# 4. ALPACA_BASE_URL 확인
type .env | findstr "ALPACA_BASE_URL"
# 출력: ALPACA_BASE_URL=https://paper-api.alpaca.markets

# 5. 실행!
python auto_trading_bot_v2.py
```

---

**준비 완료!** 🚀
