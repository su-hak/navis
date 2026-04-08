# Railway 배포 가이드 - V2 자동매매 봇

**날짜**: 2026-04-08
**버전**: V2 (2단계 감시 시스템)

---

## 🏗️ Railway 배포 구조

### 현재 배포된 서비스

```
Railway Project: navis-trading
├── Service 1: data_collection (기존)
├── Service 2: ai_team (기존)
├── Service 3: strategy_engine (기존)
└── Service 4: auto_trading_bot_v2 (✅ 신규)
```

---

## 📦 배포할 서비스

### 1️⃣ auto_trading_bot_v2 (신규 서비스)

**파일**: `Dockerfile.trading_bot_v2`, `railway.toml`

**포함 모듈**:
```
auto_trading_bot_v2.py
├── data_collection/monitoring/     (신규)
├── execution_team/                 (수정됨)
├── utils/                          (신규)
└── strategy_engine/multi_strategy/ (신규)
```

**환경변수**:
```env
# 기존
ALPACA_API_KEY=<your_key>
ALPACA_SECRET_KEY=<your_secret>
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ANTHROPIC_API_KEY=<your_key>

# V2 신규
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
LOG_LEVEL=INFO
ORDER_STORAGE_PATH=/app/logs/execution/orders
```

---

### 2️⃣ data_collection (재배포 - 선택)

**이유**: `monitoring/` 모듈 추가됨

**하지만**:
- auto_trading_bot_v2 서비스 내부에 포함되어 있음
- data_collection 서비스는 기존 스케줄러만 실행
- **재배포 불필요** (기존 유지)

---

## 🚀 배포 절차

### 방법 1: Railway CLI (권장)

#### 1단계: Railway 프로젝트 연결

```bash
# 루트 디렉토리에서
cd C:\navis

# Railway 로그인
railway login

# 기존 프로젝트 연결 (처음만)
railway link
# 또는 새 프로젝트 생성
# railway init
```

#### 2단계: 환경변수 설정

```bash
# Railway 대시보드에서 설정 또는
railway variables set AUTO_TRADING_ENABLED=false
railway variables set ALPACA_API_KEY=<your_key>
railway variables set ALPACA_SECRET_KEY=<your_secret>
railway variables set ALPACA_BASE_URL=https://paper-api.alpaca.markets
railway variables set MARKET_SCAN_INTERVAL_MINUTES=5
railway variables set GAP_THRESHOLD=3.0
railway variables set VOLUME_RATIO_THRESHOLD=3.0
railway variables set MAX_WATCHLIST_SIZE=20
railway variables set MONITOR_INTERVAL_SECONDS=10
railway variables set PRICE_CHANGE_THRESHOLD=1.5
railway variables set MAX_INVESTMENT_PERCENT=10.0
railway variables set STOP_LOSS_PERCENT=2.0
railway variables set MAX_DAILY_LOSS_PERCENT=5.0
railway variables set MAX_POSITIONS=5
railway variables set LOG_LEVEL=INFO
```

#### 3단계: 배포

```bash
# Railway에 배포
railway up
```

---

### 방법 2: GitHub 연동 (더 쉬움)

#### 1단계: Git 커밋

```bash
cd C:\navis

git add .
git commit -m "Deploy auto trading bot V2"
git push origin main
```

#### 2단계: Railway 대시보드

1. https://railway.app 로그인
2. 프로젝트 선택
3. "New Service" → "GitHub Repo" 선택
4. `navis` 저장소 선택
5. **Root Directory**: `/` (루트)
6. **Dockerfile**: `Dockerfile.trading_bot_v2`

#### 3단계: 환경변수 설정

Railway 대시보드 → Service → Variables 탭:

```
AUTO_TRADING_ENABLED=false
ALPACA_API_KEY=<paste_here>
ALPACA_SECRET_KEY=<paste_here>
ALPACA_BASE_URL=https://paper-api.alpaca.markets
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
LOG_LEVEL=INFO
ORDER_STORAGE_PATH=/app/logs/execution/orders
```

#### 4단계: 배포 확인

Railway가 자동으로 빌드 & 배포:
```
Building... ✓
Deploying... ✓
Running... ✓
```

---

## 📊 기존 서비스 업데이트 여부

### data_collection

**수정 사항**: `monitoring/` 모듈 추가

**재배포 필요?**: ❌ 불필요

**이유**:
- monitoring 모듈은 auto_trading_bot_v2 서비스에 포함됨
- data_collection 서비스는 기존 스케줄러만 실행
- 기존 배포 그대로 유지

### execution_team

**수정 사항**: 임포트 경로 수정

**재배포 필요?**: ❌ 불필요

**이유**:
- execution_team은 별도 서비스가 아님
- auto_trading_bot_v2 서비스에 라이브러리로 포함됨

### strategy_engine

**수정 사항**: `multi_strategy/` 모듈 추가

**재배포 필요?**: ❌ 불필요

**이유**:
- multi_strategy 모듈도 auto_trading_bot_v2에 포함됨
- 기존 strategy_engine 서비스는 독립 API로 유지

### utils

**배포 필요?**: ❌ 불필요

**이유**:
- 신규 생성된 로컬 라이브러리
- auto_trading_bot_v2 서비스에 포함됨

---

## 🔍 배포 확인

### 1. Railway 대시보드에서 로그 확인

```
Service: auto_trading_bot_v2
Logs:
  자동매매 봇 V2 초기화 중...
  ✓ 브로커 연결 성공
  ✓ 워치리스트 생성기 초기화 완료
  ✓ 고주기 모니터 초기화 완료
  [Stage 1] 전체 시장 스캔 시작
```

### 2. 헬스 체크 (선택)

**만약 health check 엔드포인트를 추가하려면**:

`auto_trading_bot_v2.py`에 FastAPI 추가:

```python
from fastapi import FastAPI
import uvicorn
import threading

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "running", "version": "v2"}

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# 메인에서
if __name__ == "__main__":
    # API 서버를 별도 스레드로 실행
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # 메인 봇 실행
    bot = AutoTradingBotV2()
    bot.run()
```

---

## ⚠️ 중요 주의사항

### 1. AUTO_TRADING_ENABLED

```env
# ⚠️ Railway 배포 시 반드시 false로 시작!
AUTO_TRADING_ENABLED=false
```

### 2. ALPACA_BASE_URL

```env
# ✅ Paper Trading (안전)
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# ❌ Live Trading (절대 사용 금지!)
# ALPACA_BASE_URL=https://api.alpaca.markets
```

### 3. 로그 저장

Railway는 기본적으로 로그를 콘솔에만 출력:
- `LOG_LEVEL=INFO` 권장 (DEBUG는 너무 많음)
- 파일 로그는 Railway Volume 필요 (별도 설정)

### 4. 비용 관리

Railway 무료 플랜:
- $5/월 무료 크레딧
- auto_trading_bot_v2는 24/7 실행되므로 비용 발생
- **Hobby Plan ($5/월) 권장**

---

## 🎯 배포 체크리스트

### 배포 전

- [ ] `Dockerfile.trading_bot_v2` 확인
- [ ] `railway.toml` 확인
- [ ] `.dockerignore` 확인
- [ ] Git 커밋 완료

### Railway 설정

- [ ] Railway 프로젝트 생성/연결
- [ ] GitHub 저장소 연결
- [ ] 환경변수 설정 (15개)
  - [ ] ALPACA_API_KEY
  - [ ] ALPACA_SECRET_KEY
  - [ ] ALPACA_BASE_URL
  - [ ] AUTO_TRADING_ENABLED=false
  - [ ] MARKET_SCAN_INTERVAL_MINUTES=5
  - [ ] GAP_THRESHOLD=3.0
  - [ ] VOLUME_RATIO_THRESHOLD=3.0
  - [ ] MAX_WATCHLIST_SIZE=20
  - [ ] MONITOR_INTERVAL_SECONDS=10
  - [ ] PRICE_CHANGE_THRESHOLD=1.5
  - [ ] MAX_INVESTMENT_PERCENT=10.0
  - [ ] STOP_LOSS_PERCENT=2.0
  - [ ] MAX_DAILY_LOSS_PERCENT=5.0
  - [ ] MAX_POSITIONS=5
  - [ ] LOG_LEVEL=INFO

### 배포 후

- [ ] Railway 로그 확인
- [ ] 초기화 성공 확인
- [ ] Stage 1 (5분 스캔) 작동 확인
- [ ] Stage 2 (10초 감시) 작동 확인
- [ ] 워치리스트 생성 확인

---

## 📞 문제 해결

### 문제 1: "ModuleNotFoundError: No module named 'data_collection'"

**해결**:
```dockerfile
# Dockerfile.trading_bot_v2에 추가
ENV PYTHONPATH=/app
```

### 문제 2: "Permission denied: /app/logs"

**해결**:
```dockerfile
# Dockerfile.trading_bot_v2에 추가
RUN mkdir -p /app/logs/execution/orders
RUN chmod -R 777 /app/logs
```

### 문제 3: 빌드 실패

**확인**:
```bash
# 로컬에서 Docker 빌드 테스트
docker build -f Dockerfile.trading_bot_v2 -t trading-bot-v2 .
docker run --env-file .env trading-bot-v2
```

---

## 🚀 빠른 배포 명령어

```bash
# 1. Git 커밋
git add .
git commit -m "Deploy auto trading bot V2"
git push origin main

# 2. Railway CLI 배포 (또는 GitHub 자동 배포)
railway up

# 3. 환경변수 설정 (Railway 대시보드)
# Variables 탭에서 15개 환경변수 입력

# 4. 배포 확인
railway logs
```

---

**준비 완료!** Railway에 배포하세요! 🚀
