# Railway 빠른 배포 가이드 - V2

## 🎯 핵심 요약

**Railway에 auto_trading_bot_v2를 새로운 서비스로 배포합니다.**

### 배포 대상

- ✅ **auto_trading_bot_v2** (신규 Railway 서비스)
- ❌ data_collection (재배포 불필요 - 기존 유지)
- ❌ execution_team (별도 서비스 아님)
- ❌ utils (별도 서비스 아님)
- ❌ strategy_engine (재배포 불필요 - 기존 유지)

---

## 🚀 배포 절차 (3단계)

### 1단계: Git 푸시

```powershell
cd C:\navis

# 변경사항 커밋
git add .
git commit -m "Add auto_trading_bot_v2 with monitoring system"
git push origin main
```

### 2단계: Railway 서비스 생성

#### 옵션 A: Railway 웹 대시보드

1. https://railway.app 로그인
2. 프로젝트 선택 (또는 새로 생성)
3. **"New Service"** 클릭
4. **"GitHub Repo"** 선택
5. `navis` 저장소 선택
6. **Service Name**: `auto-trading-bot-v2`
7. **Root Directory**: `/` (루트 그대로)
8. **Build**: `Dockerfile.trading_bot_v2` 자동 감지

#### 옵션 B: Railway CLI (더 빠름)

```powershell
# Railway CLI 설치 (처음만)
# npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 링크 (처음만)
railway link

# 배포
railway up
```

### 3단계: 환경변수 설정

Railway 대시보드 → Service → **Variables** 탭:

```env
# === 필수 환경변수 (기존) ===
ALPACA_API_KEY=<여기에_입력>
ALPACA_SECRET_KEY=<여기에_입력>
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# === V2 신규 환경변수 ===
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

**또는 CLI로 일괄 설정**:

```powershell
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
railway variables set ORDER_STORAGE_PATH=/app/logs/execution/orders
```

---

## ✅ 배포 확인

### Railway 로그 확인

```
Service: auto-trading-bot-v2
Status: Running
Logs:
  Building... ✓
  자동매매 봇 V2 초기화 중...
  ✓ 브로커 연결 성공 (https://paper-api.alpaca.markets)
  ✓ 계좌 자산: $100,000.00
  ✓ 워치리스트 생성기 초기화 완료
  ✓ 고주기 모니터 초기화 완료
  [Stage 1] 전체 시장 스캔 시작
  워치리스트 생성 완료: 0개 종목 (장외)
```

---

## 📋 환경변수 전체 리스트 (복사용)

Railway Variables 탭에 **복사 & 붙여넣기**:

```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets
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

**값을 채운 후** Railway에 붙여넣기.

---

## ⚠️ 중요 체크

### 배포 전

- [ ] `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` 준비됨
- [ ] `AUTO_TRADING_ENABLED=false` 확인 (⚠️ 중요!)
- [ ] `ALPACA_BASE_URL=https://paper-api.alpaca.markets` 확인
- [ ] Git 커밋 완료

### 배포 후

- [ ] Railway 로그에서 "초기화 완료" 확인
- [ ] "브로커 연결 성공" 확인
- [ ] 에러 없이 실행 중 확인

---

## 🔄 기존 서비스 상태

| 서비스 | 상태 | 조치 |
|--------|------|------|
| data_collection | ✅ 유지 | 재배포 불필요 |
| ai_team | ✅ 유지 | 재배포 불필요 |
| strategy_engine | ✅ 유지 | 재배포 불필요 |
| **auto_trading_bot_v2** | ✅ 신규 | **배포 필요** |

**결론**: auto_trading_bot_v2만 새로 배포하면 됩니다!

---

## 💰 비용

Railway 무료 플랜:
- $5/월 무료 크레딧
- auto_trading_bot_v2: 24/7 실행 (~$5/월)
- **Hobby Plan ($5/월) 권장**

---

## 📞 문제 해결

### "Build failed"

로컬에서 Docker 테스트:
```powershell
docker build -f Dockerfile.trading_bot_v2 -t test .
```

### "ModuleNotFoundError"

Dockerfile의 PYTHONPATH 확인:
```dockerfile
ENV PYTHONPATH=/app
```

### 로그가 안 보임

```powershell
# Railway CLI로 실시간 로그
railway logs --follow
```

---

**준비 완료! Railway에 배포하세요!** 🚀
