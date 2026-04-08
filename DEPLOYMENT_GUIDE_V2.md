# 자동매매 봇 V2 배포 가이드

**날짜**: 2026-04-08
**버전**: V2 (2단계 감시 시스템)

---

## 📋 수정된 도메인 요약

| 도메인 | 수정 사항 | 배포 필요 | 비고 |
|--------|----------|----------|------|
| **data_collection** | ✅ monitoring 모듈 추가 | ✅ 필요 | Railway 재배포 |
| **execution_team** | ✅ 임포트 경로 수정 | ❌ 불필요 | 로컬에서만 사용 |
| **utils** | ✅ 신규 생성 | ❌ 불필요 | 로컬 라이브러리 |
| **strategy_engine** | ✅ multi_strategy 추가 | ⚠️ 선택 | Railway 사용 시만 |
| **auto_trading_bot_v2.py** | ✅ 신규 메인 봇 | ✅ 필요 | 로컬 실행 |

---

## 🎯 배포 전략

### 현재 아키텍처

```
┌─────────────────────────────────────────────┐
│         로컬 머신 (자동매매 봇 실행)           │
│                                              │
│  ┌────────────────────────────────────┐     │
│  │  auto_trading_bot_v2.py            │     │
│  │  (Stage 1 + Stage 2 감시)          │     │
│  └──────────┬─────────────────────────┘     │
│             │                                │
│    ┌────────┴────────┐                      │
│    │                 │                      │
│    ▼                 ▼                      │
│  ┌─────┐       ┌──────────┐                │
│  │utils│       │execution │                │
│  │     │       │  _team   │                │
│  └─────┘       └────┬─────┘                │
│                     │                       │
└─────────────────────┼───────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │ Alpaca Broker│
              └──────────────┘
                      ▲
                      │ API 호출
                      │
┌─────────────────────┼───────────────────────┐
│     Railway (클라우드 서비스)                 │
│                     │                       │
│  ┌─────────────────┴─────────────┐         │
│  │   data_collection              │         │
│  │   - monitoring (신규)          │         │
│  │   - collectors                 │         │
│  │   - schedulers                 │         │
│  └────────────────────────────────┘         │
└──────────────────────────────────────────────┘
```

### 배포 필요 여부

#### ✅ 1. data_collection (Railway 재배포 필요)

**이유**:
- `monitoring/` 모듈 추가됨
- `watchlist_generator.py`, `high_frequency_monitor.py` 신규 파일

**하지만**:
- ⚠️ **auto_trading_bot_v2.py가 로컬에서 실행되므로**
- ⚠️ **monitoring 모듈도 로컬에서만 사용됨**
- ⚠️ **Railway 배포는 불필요할 수도 있음**

#### ❌ 2. execution_team (배포 불필요)

**이유**:
- 임포트 경로만 수정 (상대 경로로 변경)
- 기능 변경 없음
- 로컬에서만 사용

#### ❌ 3. utils (배포 불필요)

**이유**:
- 신규 생성된 로컬 라이브러리
- `auto_trading_bot_v2.py`에서만 사용
- 독립 서비스 아님

#### ❌ 4. strategy_engine (배포 선택)

**이유**:
- `multi_strategy/` 모듈 추가
- 하지만 Railway에 배포되어 있어도 V2 봇에서 직접 사용 안 함
- 기존 배포 유지만 하면 됨

---

## 🚀 배포 절차

### 방법 1: 로컬 실행 (권장)

**auto_trading_bot_v2.py는 로컬에서만 실행**하므로, Railway 재배포가 불필요합니다.

#### 1단계: 환경변수 확인

`.env` 파일:

```env
# ============================================
# 기존 환경변수 (그대로 유지)
# ============================================
ANTHROPIC_API_KEY=<기존값>
ALPACA_API_KEY=<기존값>
ALPACA_SECRET_KEY=<기존값>
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# ============================================
# V2 신규 환경변수
# ============================================

# 자동매매 활성화 (주의!)
AUTO_TRADING_ENABLED=false  # 테스트 시 false

# [Stage 1] 전체 시장 스캔
MARKET_SCAN_INTERVAL_MINUTES=5      # 3~5분
GAP_THRESHOLD=3.0                    # 갭 임계값 (%)
VOLUME_RATIO_THRESHOLD=3.0           # 거래량 비율
MAX_WATCHLIST_SIZE=20                # 워치리스트 크기

# [Stage 2] 고주기 모니터링
MONITOR_INTERVAL_SECONDS=10          # 5~10초
PRICE_CHANGE_THRESHOLD=1.5           # 변동 임계값 (%)

# 리스크 관리
MAX_INVESTMENT_PERCENT=10.0          # 1회 투자: 10%
STOP_LOSS_PERCENT=2.0                # 손절: -2%
MAX_DAILY_LOSS_PERCENT=5.0           # 일일 손실: -5%
MAX_POSITIONS=5                      # 최대 포지션

# 로깅
LOG_LEVEL=INFO                       # DEBUG, INFO, WARNING
```

#### 2단계: 로컬 실행

```powershell
# 1. 의존성 설치 (처음만)
pip install -r requirements.txt

# 2. V2 봇 실행
python auto_trading_bot_v2.py
```

#### 3단계: 확인

```
✅ Stage 1 (5분마다 워치리스트 생성)
✅ Stage 2 (10초마다 고주기 감시)
✅ Execution Team (주문 실행)
```

---

### 방법 2: Railway 배포 (선택 - 고급)

**만약 data_collection을 Railway에서 사용 중이라면**:

#### 1단계: data_collection 재배포

```powershell
cd data_collection

# Railway CLI로 재배포
railway up
```

**또는 GitHub 연동 시**:
```powershell
git add .
git commit -m "Add monitoring module for V2"
git push origin main
# Railway가 자동으로 재배포
```

#### 2단계: 환경변수 추가 (Railway)

Railway 대시보드에서:

```env
# V2 신규 환경변수 (필요시)
MARKET_SCAN_INTERVAL_MINUTES=5
GAP_THRESHOLD=3.0
VOLUME_RATIO_THRESHOLD=3.0
MAX_WATCHLIST_SIZE=20
MONITOR_INTERVAL_SECONDS=10
PRICE_CHANGE_THRESHOLD=1.5
```

**하지만**:
- ⚠️ monitoring 모듈은 로컬 봇에서만 사용됨
- ⚠️ Railway 재배포는 불필요할 가능성 높음

---

## 📝 필수 환경변수 체크리스트

### 기존 환경변수 (유지)

- [x] `ANTHROPIC_API_KEY`
- [x] `ALPACA_API_KEY`
- [x] `ALPACA_SECRET_KEY`
- [x] `ALPACA_BASE_URL`

### V2 신규 환경변수

- [ ] `AUTO_TRADING_ENABLED=false` (⚠️ 중요!)
- [ ] `MARKET_SCAN_INTERVAL_MINUTES=5`
- [ ] `GAP_THRESHOLD=3.0`
- [ ] `VOLUME_RATIO_THRESHOLD=3.0`
- [ ] `MAX_WATCHLIST_SIZE=20`
- [ ] `MONITOR_INTERVAL_SECONDS=10`
- [ ] `PRICE_CHANGE_THRESHOLD=1.5`
- [ ] `MAX_INVESTMENT_PERCENT=10.0`
- [ ] `STOP_LOSS_PERCENT=2.0`
- [ ] `MAX_DAILY_LOSS_PERCENT=5.0`
- [ ] `MAX_POSITIONS=5`
- [ ] `LOG_LEVEL=INFO`

---

## 🔍 도메인별 상세 분석

### 1. data_collection

#### 수정 파일
```
data_collection/
├── monitoring/               # ✅ 신규
│   ├── __init__.py
│   ├── watchlist_generator.py
│   └── high_frequency_monitor.py
└── (기존 파일 그대로)
```

#### 배포 필요 여부: **❌ 불필요**

**이유**:
- `monitoring/` 모듈은 **auto_trading_bot_v2.py에서 로컬로 임포트**
- Railway 배포된 data_collection 서비스는 사용 안 함
- 기존 Railway 배포는 그대로 유지만 하면 됨

**확인 명령어**:
```python
# auto_trading_bot_v2.py에서
from data_collection.monitoring import WatchlistGenerator, HighFrequencyMonitor
# 로컬 파일을 임포트함
```

### 2. execution_team

#### 수정 파일
```
execution_team/
├── core/
│   └── execution_engine.py   # ✅ 임포트 경로 수정
├── brokers/
│   ├── broker_interface.py   # ✅ 임포트 경로 수정
│   └── alpaca_broker.py       # ✅ 임포트 경로 수정
├── utils/
│   └── retry_handler.py       # ✅ 임포트 경로 수정
└── api.py                     # ✅ 임포트 경로 수정
```

#### 배포 필요 여부: **❌ 불필요**

**이유**:
- 임포트 경로만 수정 (`from core.` → `from .core.`)
- 기능 변경 없음
- 로컬에서만 사용

### 3. utils (신규)

#### 파일 구조
```
utils/
├── __init__.py
├── risk_manager.py    # ✅ 신규 (리스크 관리)
├── logger.py          # (기존)
└── tool.py            # (기존)
```

#### 배포 필요 여부: **❌ 불필요**

**이유**:
- 로컬 라이브러리
- `auto_trading_bot_v2.py`에서만 사용
- 독립 서비스 아님

### 4. strategy_engine

#### 수정 파일
```
strategy_engine/
└── multi_strategy/           # ✅ 신규
    ├── __init__.py
    ├── strategy_manager.py
    └── strategies.py
```

#### 배포 필요 여부: **⚠️ 선택**

**이유**:
- Railway에 배포되어 있어도 V2에서 직접 사용 안 함
- 기존 배포 유지만 하면 됨
- 향후 확장용

---

## ⚠️ 중요 주의사항

### 1. AUTO_TRADING_ENABLED

```env
# ⚠️ 반드시 false로 시작!
AUTO_TRADING_ENABLED=false
```

**이유**:
- true = 실제 주문 실행
- Paper Trading이지만 신중하게

### 2. LOG_LEVEL

```env
# 처음엔 DEBUG 권장
LOG_LEVEL=DEBUG

# 안정화 후
LOG_LEVEL=INFO
```

### 3. 시장 시간 체크

```
한국시간 기준:
- 여름: 22:30 ~ 05:00
- 겨울: 23:30 ~ 06:00

장외 시간에는 워치리스트가 비어있을 수 있음
```

---

## 🧪 테스트 절차

### 1단계: 임포트 테스트

```powershell
python test_imports.py
```

**예상 출력**:
```
✓ execution_team.core 임포트 성공
✓ execution_team.brokers 임포트 성공
✓ data_collection.monitoring 임포트 성공
✓ utils 임포트 성공
✓ strategy_engine.multi_strategy 임포트 성공
```

### 2단계: 시뮬레이션 모드 실행

```powershell
# .env에서 AUTO_TRADING_ENABLED=false 확인

python auto_trading_bot_v2.py
```

**예상 로그**:
```
자동매매 활성화: False
[Stage 1] 전체 시장 스캔 시작
  미국 시장 시간: NO (장외)
워치리스트 생성 완료: 0개 종목
[Stage 2] 고주기 모니터링 시작
```

### 3단계: 장중 시간 테스트

**오늘 밤 23:30 ~ 익일 06:00**:

```
워치리스트 생성 완료: 3개 종목
  1. NVDA: 거래량 4.2배 + 갭 3.8%
  2. TSLA: 갭 5.1%
  3. AMD: 거래량 3.5배

[모니터링 루프 #1] 3개 종목 체크 중...
[NVDA] $850.00 → $862.75 (+1.50%) ⚡ 매수 신호!
```

---

## 🎯 결론

### 배포 요약

| 작업 | 필요 여부 | 방법 |
|------|----------|------|
| **Railway 재배포** | ❌ 불필요 | 로컬 실행만 하면 됨 |
| **.env 업데이트** | ✅ 필요 | V2 환경변수 추가 |
| **의존성 설치** | ✅ 필요 | `pip install -r requirements.txt` |
| **V2 봇 실행** | ✅ 필요 | `python auto_trading_bot_v2.py` |

### 빠른 배포

```powershell
# 1. .env 업데이트 (.env.example 참고)
notepad .env

# 2. 의존성 설치
pip install -r requirements.txt

# 3. V2 봇 실행
python auto_trading_bot_v2.py
```

**끝!** Railway 재배포는 불필요합니다. 모든 것이 로컬에서 작동합니다.

---

**작성**: 2026-04-08
**버전**: V2
**상태**: ✅ 배포 가능
