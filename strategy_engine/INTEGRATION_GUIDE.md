# Strategy Engine 통합 가이드

## 🔍 현재 상태

### data_collection (프로젝트 #1)
- **타입**: 스케줄링 (Python Cron)
- **역할**: 주기적으로 데이터 수집 → DB 저장
- **독립성**: ✅ 완전히 독립적으로 동작
- **데이터베이스**: MySQL/SQLite

### strategy_engine (프로젝트 #2)
- **타입**: REST API 서버
- **역할**: 데이터 입력 → 분석 → 결과 반환
- **독립성**: ⚠️ API만 제공, 스케줄링 없음
- **데이터베이스**: 연결 안됨 (현재)

---

## 🚨 문제: 연계 필요!

**현재 문제점**:
```
data_collection        strategy_engine
      │                      │
      │ (데이터 저장)         │
      ↓                      │
   [Database]                │ (연결 없음!)
                             │
                          (API만 대기)
```

**strategy_engine이 자동으로 동작하지 않습니다!**

---

## ✅ 해결 방법 (3가지)

### 방법 1: 별도 스케줄러 추가 (권장) ⭐

새로운 프로젝트 #3을 만들어 연계:

```
[프로젝트 #1: data_collection]
      ↓ (데이터 저장)
   [Database]
      ↑ (데이터 읽기)
[프로젝트 #3: trading_scheduler] ← 새로 만듦!
      ↓ (API 호출)
[프로젝트 #2: strategy_engine]
      ↓ (시그널 생성)
[주문 실행]
```

**구현**:
```python
# trading_scheduler/main.py
import schedule
import time
import requests
from database import get_latest_stock_data

def analyze_and_trade():
    # 1. DB에서 최신 데이터 가져오기
    symbols = ['AAPL', 'TSLA', 'NVDA']

    for symbol in symbols:
        # 2. data_collection DB에서 데이터 조회
        stock_data = get_latest_stock_data(symbol, days=100)

        # 3. strategy_engine API 호출
        response = requests.post(
            'https://strategy-engine-xxx.railway.app/signal/buy',
            json={
                'symbol': symbol,
                'data': stock_data.to_dict(),
                'news_sentiment': 0.5,
                'news_count': 5
            }
        )

        signal = response.json()

        # 4. 시그널이 있으면 주문 실행팀으로 전달
        if signal:
            print(f"매수 시그널: {symbol}")
            # execute_order(signal)

# 매일 오전 9시 30분 실행 (미국 장 시작)
schedule.every().day.at("09:30").do(analyze_and_trade)

while True:
    schedule.run_pending()
    time.sleep(60)
```

**장점**:
- 완전히 독립적인 3개 프로젝트
- 각자 역할 명확
- 유지보수 쉬움

---

### 방법 2: strategy_engine에 스케줄링 추가

strategy_engine 내부에 스케줄링 추가:

```python
# strategy_engine/scheduler.py
import schedule
from database import connect_to_data_collection_db
from .scoring import ScoreCalculator
from .signals import SignalGenerator

def run_strategy():
    # data_collection DB 연결
    db = connect_to_data_collection_db()

    # 최신 데이터 가져오기
    stocks = db.get_latest_stocks()

    # 분석 및 시그널 생성
    calculator = ScoreCalculator()
    signal_gen = SignalGenerator()

    for stock_data in stocks:
        signal = signal_gen.generate_buy_signal(
            stock_data['symbol'],
            stock_data['ohlcv']
        )

        if signal:
            # 주문 실행
            execute_order(signal)

schedule.every(5).minutes.do(run_strategy)
```

**Procfile 수정**:
```
web: uvicorn strategy_engine.api.strategy_api:app --host 0.0.0.0 --port $PORT
worker: python strategy_engine/scheduler.py
```

**장점**:
- 하나의 프로젝트에서 모두 처리
- 관리가 간단

**단점**:
- API와 스케줄러가 섞임
- 스케일링 어려움

---

### 방법 3: data_collection에 전략 로직 추가

data_collection에서 데이터 수집 후 바로 분석:

```python
# data_collection/main.py
def collect_and_analyze():
    # 1. 데이터 수집
    collect_stock_data()

    # 2. 바로 전략 엔진 호출
    response = requests.post(
        'https://strategy-engine-xxx.railway.app/signal/buy',
        json={...}
    )

    # 3. 시그널 처리
    if response.json():
        execute_order(...)
```

**장점**:
- 추가 프로젝트 불필요

**단점**:
- data_collection이 너무 많은 역할 담당
- 관심사 분리 위반

---

## 🎯 권장 아키텍처

```
┌─────────────────────┐
│ data_collection     │ (Railway 프로젝트 #1)
│ - 데이터 수집        │
│ - DB 저장           │
└─────────┬───────────┘
          │
          ↓ (데이터 저장)
┌─────────────────────┐
│   MySQL Database    │ (Railway MySQL 플러그인)
└─────────┬───────────┘
          ↑ (데이터 읽기)
┌─────────┴───────────┐
│ trading_scheduler   │ (Railway 프로젝트 #3) ← 새로 만들기!
│ - DB에서 데이터 조회 │
│ - strategy_engine   │
│   API 호출          │
│ - 시그널 처리        │
└─────────┬───────────┘
          │
          ↓ (API 호출)
┌─────────────────────┐
│ strategy_engine     │ (Railway 프로젝트 #2)
│ - API 서버          │
│ - 점수 계산         │
│ - 시그널 생성        │
└─────────────────────┘
```

---

## 📝 구현 단계

### 1단계: Database 연결 설정

data_collection과 strategy_engine이 같은 DB 사용:

**Railway MySQL 플러그인 추가**:
```
1. data_collection 프로젝트에서
2. Add Plugin → MySQL
3. 환경변수 자동 생성:
   - DATABASE_URL
   - MYSQL_HOST
   - MYSQL_USER
   - MYSQL_PASSWORD
   - MYSQL_DATABASE
```

### 2단계: trading_scheduler 생성

```powershell
# 새 디렉토리 생성
cd C:\navis
mkdir trading_scheduler
cd trading_scheduler

# 파일 생성
# - main.py (스케줄러)
# - database.py (DB 연결)
# - requirements.txt
# - railway.toml
```

### 3단계: Railway 배포

```powershell
cd C:\navis\trading_scheduler
railway init
railway link [data_collection의 MySQL 플러그인 공유]
railway up
```

---

## 🔧 빠른 테스트 (수동 연계)

현재 상태에서 수동으로 연계 테스트:

```python
import requests
import pandas as pd

# 1. data_collection DB에서 데이터 가져오기 (직접 쿼리)
# (생략 - DB 연결 필요)

# 2. strategy_engine API 호출
response = requests.post(
    'https://YOUR-APP.railway.app/score/calculate',
    json={
        'symbol': 'AAPL',
        'data': {
            'timestamp': [...],
            'open': [...],
            'high': [...],
            'low': [...],
            'close': [...],
            'volume': [...]
        }
    }
)

print(response.json())
```

---

## 🎯 결론

**현재 상태**:
- ❌ strategy_engine은 독립적인 API 서버 (자동 동작 없음)
- ❌ data_collection과 연계 없음
- ❌ 자동매매 시스템으로 동작 안함

**필요한 작업**:
1. **trading_scheduler** 프로젝트 생성 (권장)
2. data_collection DB 연결
3. strategy_engine API 호출
4. 주문 실행 연결

**또는**:
- strategy_engine에 스케줄러 추가
- data_collection에 전략 로직 추가

---

**다음 단계**: trading_scheduler 프로젝트를 만들까요?
