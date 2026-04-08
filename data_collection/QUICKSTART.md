# Quick Start Guide

데이터 수집 모듈 빠른 시작 가이드

## 1. 설치 및 설정 (5분)

### Step 1: 의존성 설치

```bash
cd data_collection
pip install -r requirements.txt
```

**주의**: 버전 충돌 경고가 나타나면 무시하고 계속 진행하세요. 기능에는 문제가 없습니다.

### Step 2: 환경 변수 설정

프로젝트 루트의 `.env` 파일에 다음 내용 추가:

```env
# Alpaca API (페이퍼 트레이딩 계정)
APCA-API-KEY-ID=YOUR_KEY_HERE
APCA-API-SECRET-KEY=YOUR_SECRET_HERE
```

**Alpaca API 키 발급**: https://alpaca.markets (무료 페이퍼 트레이딩 계정)

### Step 3: 데이터베이스 초기화

**간편한 방법 (권장):**
```bash
python setup_database.py
```

대화형 마법사가 실행됩니다:
- **옵션 1: SQLite** - 설치 불필요, 즉시 사용 가능 (권장)
- **옵션 2: MySQL** - 프로덕션용

**또는 직접 설정:**

**SQLite (간편):**
```bash
cd database
python schema_sqlite.py
```

**MySQL (고급):**
```bash
cd database
python schema.py
```

MySQL 연결 에러가 발생하면 `INSTALL_MYSQL.md`를 참조하세요.

## 2. 테스트 실행 (3분)

### 주가 데이터 수집 테스트

```bash
cd collectors
python stock_price_collector.py
```

출력 예시:
```
Fetching daily bars for ['AAPL', 'TSLA', 'NVDA']...
Daily bars:
   symbol  timestamp    close    volume
0   AAPL 2024-03-01  180.50  50000000
...
```

### 뉴스 수집 테스트

```bash
python news_collector.py
```

### 재무 데이터 수집 테스트

```bash
python financial_collector.py
```

## 3. API 서버 실행 (1분)

```bash
cd ../api
python main.py
```

브라우저에서 확인: http://localhost:8001/docs

### API 테스트

```bash
# 최신 가격 조회
curl http://localhost:8001/api/v1/prices/AAPL/latest

# 뉴스 조회
curl http://localhost:8001/api/v1/news/AAPL?hours=24
```

## 4. 자동 스케줄러 실행

```bash
cd ../schedulers
python data_scheduler.py
```

스케줄러가 시작되면 자동으로 데이터를 수집합니다:
- 분봉: 시장 시간 중 매 5분
- 일봉: 매일 오후 5시
- 뉴스: 매 30분
- 재무 데이터: 매주 일요일

## 5. 주요 사용 패턴

### 패턴 1: 실시간 가격 모니터링

```python
import asyncio
from collectors.stock_price_collector import StockPriceCollector

async def monitor_prices():
    collector = StockPriceCollector(api_key, api_secret)

    while True:
        prices = await collector.get_latest_price(['AAPL', 'TSLA'])
        print(f"AAPL: ${prices['AAPL']:.2f}, TSLA: ${prices['TSLA']:.2f}")
        await asyncio.sleep(60)  # 1분마다 체크

asyncio.run(monitor_prices())
```

### 패턴 2: 이상 거래량 탐지

```python
from collectors.volume_volatility_collector import VolumeVolatilityCollector

async def detect_unusual_volume():
    stock_collector = StockPriceCollector(api_key, api_secret)
    volume_collector = VolumeVolatilityCollector(stock_collector)

    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']
    anomalies = await volume_collector.detect_volume_anomalies(symbols, threshold_multiplier=2.5)

    for item in anomalies:
        print(f"{item['symbol']}: 거래량 {item['volume_ratio']:.1f}배 증가!")

asyncio.run(detect_unusual_volume())
```

### 패턴 3: 속보 모니터링

```python
from collectors.news_collector import NewsCollector

async def monitor_breaking_news():
    collector = NewsCollector(api_key, api_secret)

    while True:
        breaking = await collector.get_breaking_news(
            ['AAPL', 'TSLA', 'NVDA'],
            minutes=5
        )

        for news in breaking:
            if news['priority'] == 'high':
                print(f"[속보] {news['symbol']}: {news['headline']}")

        await asyncio.sleep(300)  # 5분마다 체크

asyncio.run(monitor_breaking_news())
```

### 패턴 4: 재무 스크리닝

```python
from collectors.financial_collector import FinancialCollector

async def screen_growth_stocks():
    collector = FinancialCollector()

    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META']

    # 성장주 필터: 매출 성장률 20%+, 이익률 10%+, PER 50 이하
    filtered = await collector.screen_stocks(
        symbols,
        min_revenue_growth=0.2,
        min_profit_margin=0.1,
        max_pe_ratio=50
    )

    print(f"발견된 성장주: {len(filtered)}개")
    for stock in filtered:
        print(f"{stock['symbol']}: 매출 성장률 {stock['revenue_growth']:.1f}%")

asyncio.run(screen_growth_stocks())
```

## 6. 트러블슈팅

### MySQL 연결 오류
```bash
# MySQL 서비스 확인 및 재시작
sudo systemctl status mysql
sudo systemctl restart mysql
```

### Alpaca API 오류
- API 키 확인: https://app.alpaca.markets
- 페이퍼 트레이딩 사용 확인
- 레이트 리미트: 200 requests/minute

### 의존성 오류
```bash
pip install --upgrade -r requirements.txt
```

## 7. 다음 단계

1. **커스터마이징**: `config.py`에서 watchlist 수정
2. **스케줄 조정**: `schedulers/data_scheduler.py`에서 수집 주기 변경
3. **다른 팀과 연동**: REST API를 통해 데이터 공유

## 문의

데이터 수집 팀 - data-collection-team@example.com
