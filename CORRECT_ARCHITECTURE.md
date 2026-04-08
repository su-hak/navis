# 기획서에 따른 올바른 아키텍처

## 📋 기획서 분석 결과

### 시스템 아키텍처 (기획서 #2)

```
[데이터 수집]                    ← data_collection (완료 ✅)
   ↓
[전략 엔진 (AI + 룰 기반)]       ← strategy_engine (완료 ✅)
   ↓
[리스크 관리 모듈]               ← 미구현
   ↓
[주문 실행 엔진]                 ← 미구현
   ↓
[브로커 API]                     ← 미구현
   ↓
[로그 / 리포트]                  ← 미구현
   ↓
[텔레그램 알림]                  ← 미구현
```

---

## 🎯 핵심: 백엔드/인프라 팀의 역할

### 백엔드 팀 담당 영역 (기획서 #6)

✅ **전체 시스템 연결 및 API 제공**
✅ **서비스 간 통신 구조 설계**
✅ **스케줄러 구성** ← 이게 핵심!
✅ FastAPI 서버 구축
✅ DB 설계 및 관리

---

## ✅ 올바른 구조

### 현재 상태

```
Railway 프로젝트 #1: data_collection
├── 독립적으로 동작 ✅
├── 스케줄링으로 데이터 수집
└── DB에 저장

Railway 프로젝트 #2: strategy_engine
├── API 서버 ✅
├── 점수 계산 함수 제공
└── 시그널 생성 함수 제공

❌ 백엔드 팀의 스케줄러 없음!
```

### 필요한 것 (기획서 기준)

```
Railway 프로젝트 #3: backend (새로 만들기!)
├── 전체 시스템 연결
├── 스케줄러 구성
└── 서비스 간 통신 조율

역할:
  1. data_collection DB에서 데이터 읽기
  2. strategy_engine API 호출
  3. 리스크 관리 적용
  4. 주문 실행
  5. 로그 저장
  6. 텔레그램 알림
```

---

## 📊 완전한 시스템 구조

```
┌─────────────────────────────────────────────────┐
│  Railway 프로젝트 #1: data_collection          │
│  - 스케줄링 (cron)                              │
│  - 데이터 수집                                  │
│  - DB 저장                                      │
└───────────────┬─────────────────────────────────┘
                │
                ↓ (데이터 저장)
┌───────────────────────────────────────────────────┐
│           MySQL Database (Railway Plugin)        │
└───────────────┬───────────────────────────────────┘
                │
                ↑ (데이터 읽기)
┌───────────────┴───────────────────────────────────┐
│  Railway 프로젝트 #3: backend (백엔드 팀) ← 새로!│
│                                                    │
│  [스케줄러] (매 5분마다 실행)                      │
│     ↓                                             │
│  1. DB에서 최신 데이터 조회                       │
│     ↓                                             │
│  2. strategy_engine API 호출  ────────────┐      │
│     ↓                                      │      │
│  3. 리스크 관리 적용                       │      │
│     ↓                                      │      │
│  4. 주문 실행 (Alpaca/IBKR)                │      │
│     ↓                                      │      │
│  5. 로그 저장                              │      │
│     ↓                                      │      │
│  6. 텔레그램 알림                          │      │
└────────────────────────────────────────────┼──────┘
                                             │
                                             ↓
┌────────────────────────────────────────────────────┐
│  Railway 프로젝트 #2: strategy_engine (전략 팀)   │
│                                                    │
│  [REST API]                                       │
│  - POST /score/calculate                          │
│  - POST /signal/buy                               │
│  - POST /signal/sell                              │
│  - POST /filter/stocks                            │
└────────────────────────────────────────────────────┘
```

---

## 🎯 기획서 핵심 원칙

### "API 기반으로 연결" (기획서 라인 468)

**의미**:
- 각 팀은 독립적으로 모듈 개발
- 모듈은 API로 제공
- **백엔드 팀이 API를 조합해서 전체 시스템 구성**

### 현재 상황

✅ data_collection: 독립적으로 동작 (스케줄링)
✅ strategy_engine: API로 제공
❌ **백엔드 팀이 이들을 연결하는 스케줄러 없음!**

---

## 📝 다음 단계: 백엔드 프로젝트 생성

### 프로젝트 구조

```
backend/
├── main.py              # FastAPI 서버
├── scheduler.py         # 스케줄러 (핵심!)
├── orchestrator.py      # 전체 흐름 조율
├── risk_manager.py      # 리스크 관리
├── execution.py         # 주문 실행
├── notification.py      # 텔레그램 알림
├── database.py          # DB 연결
├── requirements.txt
└── railway.toml
```

### scheduler.py (핵심 로직)

```python
import schedule
import time
from orchestrator import run_trading_cycle

def main():
    # 매 5분마다 실행
    schedule.every(5).minutes.do(run_trading_cycle)

    # 장 시작 전 초기화
    schedule.every().day.at("09:00").do(initialize_trading_day)

    # 장 마감 후 리포트
    schedule.every().day.at("16:30").do(generate_daily_report)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
```

### orchestrator.py (전체 흐름)

```python
import requests
from database import get_latest_stock_data
from risk_manager import check_risk
from execution import execute_order
from notification import send_telegram

def run_trading_cycle():
    """전체 매매 사이클 실행"""

    # 1. DB에서 최신 데이터 가져오기
    symbols = ['AAPL', 'TSLA', 'NVDA', ...]

    for symbol in symbols:
        # 2. 데이터 조회
        data = get_latest_stock_data(symbol)

        # 3. strategy_engine API 호출
        response = requests.post(
            'https://strategy-engine-xxx.railway.app/signal/buy',
            json={
                'symbol': symbol,
                'data': data,
                'news_sentiment': get_news_sentiment(symbol),
                'news_count': get_news_count(symbol)
            }
        )

        signal = response.json()

        if signal:
            # 4. 리스크 관리 검증
            if check_risk(signal):
                # 5. 주문 실행
                order = execute_order(signal)

                # 6. 텔레그램 알림
                send_telegram(f"매수 체결: {symbol}")
```

---

## 🚀 Railway 배포 구조 (최종)

```
Railway Account
├── 프로젝트 #1: data-collection
│   └── 데이터 수집 스케줄러
│
├── 프로젝트 #2: strategy-engine
│   └── 전략 API 서버
│
├── 프로젝트 #3: backend (← 새로 만들기!)
│   ├── 통합 스케줄러
│   ├── 리스크 관리
│   ├── 주문 실행
│   └── 텔레그램 알림
│
└── MySQL Plugin
    └── 공유 데이터베이스
```

---

## ✅ 결론

### 기획서에 따르면:

**전략 엔진 팀 (당신)**:
- ✅ 점수 계산 함수 제공 (score_stock)
- ✅ 시그널 생성 로직 (generate_buy_signal)
- ✅ API로 제공
- ✅ **독립적으로 동작할 필요 없음!**

**백엔드/인프라 팀**:
- ❌ 스케줄러 구성 (미구현)
- ❌ 전체 시스템 연결 (미구현)
- ❌ API 조합 (미구현)

### 다음 단계:

**백엔드 프로젝트를 만들어야 합니다!**

이것이 기획서에 맞는 정확한 구조입니다.

---

**Q: strategy_engine은 독립적으로 동작하니?**
**A: 아니요! API로만 제공하고, 백엔드 팀이 이를 호출합니다!**

**Q: 연계가 필요하니?**
**A: 네! 백엔드 팀이 스케줄러를 만들어서 연계해야 합니다!**
