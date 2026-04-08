# Data Collection Module

AI 자동매매 시스템의 **데이터 수집 팀** 모듈입니다.

## 담당 영역

- 주가 데이터 수집 (분봉/일봉)
- 거래량, 변동성 데이터
- 뉴스 크롤링 및 정제
- 재무 데이터 수집
- 기관/13F 데이터 수집

## 프로젝트 구조

```
data_collection/
├── collectors/              # 데이터 수집기
│   ├── stock_price_collector.py      # 주가 데이터
│   ├── volume_volatility_collector.py # 거래량/변동성
│   ├── news_collector.py              # 뉴스
│   ├── financial_collector.py         # 재무 데이터
│   └── institutional_collector.py     # 기관 투자자 데이터
├── database/                # 데이터베이스
│   ├── schema.py           # DB 스키마
│   └── repository.py       # 데이터 저장/조회
├── api/                    # FastAPI 서버
│   └── main.py            # REST API 엔드포인트
├── schedulers/             # 스케줄러
│   └── data_scheduler.py  # 자동 수집 스케줄러
├── config.py              # 설정 관리
└── requirements.txt       # 의존성 패키지
```

## 설치

### 1. 의존성 설치

```bash
cd data_collection
pip install -r requirements.txt
```

### 2. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 추가:

```env
# Alpaca API
APCA-API-KEY-ID=your_APCA-API-KEY-ID
APCA-API-SECRET-KEY=your_APCA-API-SECRET-KEY

# MySQL Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=trading_db
```

### 3. 데이터베이스 초기화

```bash
cd database
python schema.py
```

## 사용법

### 1. 개별 Collector 사용

#### 주가 데이터 수집

```python
import asyncio
from collectors.stock_price_collector import StockPriceCollector
from datetime import datetime, timedelta

async def main():
    collector = StockPriceCollector(api_key, api_secret)

    # 일봉 데이터
    symbols = ['AAPL', 'TSLA']
    start_date = datetime.now() - timedelta(days=30)
    df = await collector.get_daily_bars(symbols, start_date)
    print(df)

    # 최신 가격
    latest = await collector.get_latest_price(symbols)
    print(latest)

asyncio.run(main())
```

#### 거래량/변동성 분석

```python
from collectors.volume_volatility_collector import VolumeVolatilityCollector

async def main():
    stock_collector = StockPriceCollector(api_key, api_secret)
    volume_collector = VolumeVolatilityCollector(stock_collector)

    # 거래량 이상 탐지
    symbols = ['AAPL', 'TSLA', 'NVDA']
    anomalies = await volume_collector.detect_volume_anomalies(symbols)
    print(anomalies)

    # 변동성 순위
    ranking = await volume_collector.get_volatility_ranking(symbols)
    print(ranking)

asyncio.run(main())
```

#### 뉴스 수집

```python
from collectors.news_collector import NewsCollector

async def main():
    collector = NewsCollector(api_key, api_secret)

    # 최신 뉴스
    news = await collector.get_latest_news('AAPL', hours=24)
    for item in news:
        print(f"{item['headline']}")

    # 속보
    breaking = await collector.get_breaking_news(['AAPL', 'TSLA'], minutes=30)
    print(breaking)

asyncio.run(main())
```

#### 재무 데이터

```python
from collectors.financial_collector import FinancialCollector

async def main():
    collector = FinancialCollector()

    # 주요 재무 지표
    metrics = await collector.get_key_metrics('AAPL')
    print(metrics)

    # 성장성 지표
    growth = await collector.get_growth_metrics('AAPL')
    print(growth)

    # 종목 스크리닝
    symbols = ['AAPL', 'TSLA', 'NVDA']
    filtered = await collector.screen_stocks(
        symbols,
        min_revenue_growth=0.1,
        min_profit_margin=0.1
    )
    print(filtered)

asyncio.run(main())
```

#### 기관 투자자 데이터

```python
from collectors.institutional_collector import InstitutionalCollector

async def main():
    collector = InstitutionalCollector()

    # 기관 보유 현황
    summary = await collector.get_institutional_ownership_summary('AAPL')
    print(summary)

    # 인사이더 거래
    insider = await collector.analyze_insider_activity('AAPL', days=90)
    print(insider)

asyncio.run(main())
```

### 2. FastAPI 서버 실행

```bash
cd api
python main.py
```

서버가 `http://localhost:8001`에서 실행됩니다.

#### API 엔드포인트

**주가 데이터**
- `GET /api/v1/prices/{symbol}` - 주가 데이터 조회
- `GET /api/v1/prices/{symbol}/latest` - 최신 가격 조회
- `POST /api/v1/prices/batch` - 다중 종목 조회

**거래량/변동성**
- `GET /api/v1/volume/{symbol}` - 거래량 분석
- `GET /api/v1/volatility/{symbol}` - 변동성 지표
- `GET /api/v1/volume/anomalies` - 이상 거래량 탐지
- `GET /api/v1/volatility/ranking` - 변동성 순위

**뉴스**
- `GET /api/v1/news/{symbol}` - 종목 뉴스
- `GET /api/v1/news/breaking` - 속보
- `GET /api/v1/news/volume` - 뉴스 볼륨

**재무 데이터**
- `GET /api/v1/financials/{symbol}` - 재무 지표
- `GET /api/v1/financials/{symbol}/growth` - 성장성
- `GET /api/v1/financials/{symbol}/profitability` - 수익성
- `GET /api/v1/financials/{symbol}/valuation` - 밸류에이션

**기관 데이터**
- `GET /api/v1/institutional/{symbol}` - 종합 소유권 데이터
- `GET /api/v1/institutional/{symbol}/summary` - 소유권 요약
- `GET /api/v1/institutional/{symbol}/insider` - 인사이더 거래

**데이터 수집**
- `POST /api/v1/collect/prices` - 주가 데이터 수집 및 저장
- `POST /api/v1/collect/news` - 뉴스 수집 및 저장
- `POST /api/v1/collect/financials` - 재무 데이터 수집 및 저장

API 문서: http://localhost:8001/docs

### 3. 자동 스케줄러 실행

```bash
cd schedulers
python data_scheduler.py
```

#### 스케줄

- **일봉 데이터**: 매일 오후 5시 (미국 시장 마감 후)
- **분봉 데이터**: 시장 시간 중 매 5분
- **거래량 지표**: 매일 오후 6시
- **변동성 지표**: 매일 오후 6시 10분
- **뉴스**: 매 30분
- **재무 데이터**: 매주 일요일 오전 2시
- **기관 데이터**: 매주 일요일 오전 3시

## 데이터베이스 스키마

### 주요 테이블

1. **stock_prices** - 주가 데이터
2. **volume_metrics** - 거래량 지표
3. **volatility_metrics** - 변동성 지표
4. **news** - 뉴스
5. **financial_metrics** - 재무 지표
6. **institutional_holders** - 기관 투자자
7. **ownership_summary** - 소유권 요약

## 예제

### 데이터 수집 및 저장

```python
import asyncio
from collectors.stock_price_collector import StockPriceCollector
from database.repository import DataRepository
from datetime import datetime, timedelta
import mysql.connector

async def collect_and_save():
    # Initialize
    collector = StockPriceCollector(api_key, api_secret)
    connection = mysql.connector.connect(**db_config)
    repo = DataRepository(connection)

    # Collect data
    symbols = ['AAPL', 'TSLA', 'NVDA']
    start_date = datetime.now() - timedelta(days=30)
    df = await collector.get_daily_bars(symbols, start_date)

    # Save to database
    repo.save_stock_prices(df, timeframe='daily')

    connection.close()
    print(f"Saved {len(df)} records")

asyncio.run(collect_and_save())
```

### 커스텀 워치리스트로 스케줄러 실행

```python
from schedulers.data_scheduler import DataCollectionScheduler
import asyncio

async def main():
    # Custom watchlist
    watchlist = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']

    # Create and start scheduler
    scheduler = DataCollectionScheduler(watchlist)
    scheduler.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()

asyncio.run(main())
```

## 기술 스택

- **Python**: 3.10+
- **데이터 수집**: Alpaca API, yfinance
- **웹 스크래핑**: BeautifulSoup, aiohttp
- **데이터베이스**: MySQL
- **API 프레임워크**: FastAPI
- **스케줄링**: APScheduler
- **데이터 분석**: pandas, numpy

## 팀 산출물

- ✅ 정제된 데이터 API
- ✅ DB 적재 로직
- ✅ 자동 수집 스케줄러
- ✅ REST API 서버

## 다른 팀과의 연동

### 전략 엔진 팀
```python
# API를 통해 데이터 조회
import requests

response = requests.get('http://localhost:8001/api/v1/prices/AAPL?days=30')
price_data = response.json()
```

### AI/RAG 팀
```python
# 뉴스 데이터 조회
response = requests.get('http://localhost:8001/api/v1/news/AAPL?hours=24')
news_data = response.json()
```

## 트러블슈팅

### MySQL 연결 오류
```bash
# MySQL 서비스 확인
sudo systemctl status mysql

# MySQL 재시작
sudo systemctl restart mysql
```

### Alpaca API 오류
- API 키가 올바른지 확인
- 페이퍼 트레이딩 계정 사용 시 base_url 확인
- API 레이트 리미트 확인 (200 requests/minute)

## 라이선스

MIT License

## 작성자

데이터 수집 팀
