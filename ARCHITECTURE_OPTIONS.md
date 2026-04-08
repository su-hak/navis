# 아키텍처 선택: 새 Backend vs data_collection 확장

## 🤔 핵심 질문

**"data_collection을 확장하면 되는거 아니니?"**

좋은 질문입니다! 두 가지 선택지가 있습니다.

---

## 📊 옵션 비교

### 옵션 A: 새 backend 프로젝트 생성 (기획서 원칙)

```
Railway 프로젝트 #1: data_collection
└── 역할: 데이터 수집 + DB 저장만
    (관심사 분리 ✅)

Railway 프로젝트 #2: strategy_engine
└── 역할: 전략 API만

Railway 프로젝트 #3: backend (새로 생성)
└── 역할: 전체 시스템 조율
    - 스케줄러
    - strategy_engine API 호출
    - 리스크 관리
    - 주문 실행
    - 텔레그램 알림
```

**장점**:
- ✅ 기획서 구조 엄격히 준수
- ✅ 관심사 분리 (데이터 수집 vs 매매 실행)
- ✅ 각 모듈 독립적으로 스케일링 가능
- ✅ data_collection이 다른 용도로도 사용 가능

**단점**:
- ❌ Railway 프로젝트 3개 필요 (비용/관리)
- ❌ 구조가 복잡함
- ❌ 네트워크 지연 (프로젝트 간 통신)

---

### 옵션 B: data_collection 확장 (실용적) ⭐ 추천

```
Railway 프로젝트 #1: data_collection (확장)
├── 기존: 데이터 수집 + DB 저장
└── 추가: 매매 로직 실행
    - strategy_engine API 호출
    - 리스크 관리
    - 주문 실행
    - 텔레그램 알림

Railway 프로젝트 #2: strategy_engine
└── 역할: 전략 API만
```

**장점**:
- ✅ 간단함 (Railway 프로젝트 2개만)
- ✅ 빠름 (같은 프로젝트 내 DB 연결)
- ✅ 비용 절약
- ✅ 관리 용이
- ✅ 이미 스케줄링 인프라 있음

**단점**:
- ❌ data_collection이 너무 많은 역할 담당
- ❌ 관심사 분리 약함
- ❌ 기획서 구조와 약간 다름

---

## 🎯 실용적 권장: 옵션 B (data_collection 확장)

### 이유:

1. **이미 스케줄링 있음**
   - data_collection에 cron/schedule 이미 구현됨
   - 중복 스케줄러 만들 필요 없음

2. **DB 연결 공유**
   - 같은 프로젝트에서 DB 읽기/쓰기
   - 네트워크 지연 없음

3. **Railway 비용 절감**
   - 프로젝트 2개 vs 3개
   - 무료 플랜에서 더 여유

4. **단순함**
   - 코드 한 곳에서 관리
   - 디버깅 쉬움

---

## 📝 옵션 B 구현 방법

### data_collection 구조 확장

```
data_collection/
├── collectors/              (기존)
│   ├── stock_price_collector.py
│   ├── news_collector.py
│   └── ...
│
├── schedulers/              (기존)
│   └── data_scheduler.py
│
├── trading/                 (새로 추가!)
│   ├── __init__.py
│   ├── trading_engine.py   ← 매매 엔진
│   ├── risk_manager.py     ← 리스크 관리
│   ├── execution.py        ← 주문 실행
│   └── notification.py     ← 텔레그램 알림
│
└── schedulers/
    ├── data_scheduler.py   (기존)
    └── trading_scheduler.py (새로 추가!)
```

### trading_scheduler.py

```python
import schedule
import time
from trading.trading_engine import run_trading_cycle

def start_trading_scheduler():
    """매매 스케줄러 시작"""

    # 매 5분마다 매매 사이클 실행
    schedule.every(5).minutes.do(run_trading_cycle)

    # 장 시작 전 초기화
    schedule.every().day.at("09:00").do(initialize_trading_day)

    # 장 마감 후 리포트
    schedule.every().day.at("16:30").do(generate_daily_report)

    while True:
        schedule.run_pending()
        time.sleep(60)
```

### trading_engine.py

```python
import requests
from database.repository import get_latest_stock_data
from .risk_manager import RiskManager
from .execution import execute_order
from .notification import send_telegram_alert

STRATEGY_ENGINE_URL = "https://strategy-engine-xxx.railway.app"

def run_trading_cycle():
    """전체 매매 사이클 실행"""

    # 1. DB에서 최신 데이터 가져오기
    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']

    for symbol in symbols:
        try:
            # 2. 로컬 DB에서 데이터 조회 (빠름!)
            stock_data = get_latest_stock_data(symbol, days=100)

            if stock_data.empty:
                continue

            # 3. strategy_engine API 호출
            response = requests.post(
                f"{STRATEGY_ENGINE_URL}/signal/buy",
                json={
                    'symbol': symbol,
                    'data': stock_data.to_dict('list'),
                    'news_sentiment': get_news_sentiment(symbol),
                    'news_count': get_news_count(symbol)
                },
                timeout=10
            )

            if response.status_code != 200:
                continue

            signal = response.json()

            if signal:
                # 4. 리스크 관리 검증
                risk_manager = RiskManager()
                if risk_manager.validate_signal(signal):

                    # 5. 주문 실행
                    order_result = execute_order(signal)

                    # 6. 텔레그램 알림
                    send_telegram_alert(
                        f"🚀 매수 체결\n"
                        f"종목: {symbol}\n"
                        f"가격: ${signal['entry_price']}\n"
                        f"점수: {signal['score']}"
                    )

        except Exception as e:
            print(f"Error processing {symbol}: {e}")
```

### Procfile 수정

```
# data_collection/Procfile
collector: python -m schedulers.data_scheduler
trader: python -m schedulers.trading_scheduler
```

Railway에서 두 프로세스 모두 실행!

---

## 🎯 기획서 관점에서

### 기획서는 "관심사 분리"를 강조

하지만:
- **실용성**: data_collection 확장이 훨씬 간단
- **비용**: Railway 프로젝트 적을수록 좋음
- **성능**: 같은 프로젝트 내에서 DB 접근이 빠름

### 기획서의 핵심은:

> "각 팀은 모듈 단위로 독립 개발"
> "API 기반으로 연결"

✅ **여전히 만족**:
- data_collection은 데이터 수집 모듈
- strategy_engine은 전략 API 모듈
- 이 둘을 연결하는 trading 모듈 추가

---

## 🔄 마이그레이션 경로

### 지금은 옵션 B (data_collection 확장)

나중에 필요하면 옵션 A로 마이그레이션:

```python
# trading/ 디렉토리를 통째로 새 backend 프로젝트로 이동
cp -r data_collection/trading/ backend/
```

---

## ✅ 최종 권장

### ⭐ 옵션 B: data_collection 확장

**이유**:
1. 간단함 (프로젝트 2개)
2. 빠름 (로컬 DB 접근)
3. 저렴함 (Railway 비용)
4. 이미 스케줄러 있음
5. 나중에 분리 가능

**구현**:
```
data_collection/
├── collectors/     (기존)
├── schedulers/     (기존)
└── trading/        (새로 추가!)
    ├── trading_engine.py
    ├── risk_manager.py
    ├── execution.py
    └── notification.py
```

---

## 📊 비교표

| 항목 | 새 Backend | data_collection 확장 |
|------|-----------|---------------------|
| Railway 프로젝트 수 | 3개 | 2개 ⭐ |
| 관리 복잡도 | 높음 | 낮음 ⭐ |
| DB 접근 속도 | 느림 (네트워크) | 빠름 (로컬) ⭐ |
| 비용 | 높음 | 낮음 ⭐ |
| 기획서 준수 | 엄격히 준수 | 유연한 해석 |
| 스케일링 | 독립적 | 함께 스케일 |
| 관심사 분리 | 명확 | 약간 섞임 |

---

## 🎯 결론

**data_collection을 확장하세요!**

- 훨씬 간단하고 실용적
- Railway 프로젝트 2개만 필요
- 나중에 분리 가능
- 기획서 핵심 원칙은 여전히 만족

**다음 단계**: data_collection에 trading 모듈 추가!
