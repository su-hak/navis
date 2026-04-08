# Strategy Engine (전략 엔진)

AI 자동매매 시스템의 핵심 전략 로직을 담당하는 모듈입니다.

## 팀 정보

- **팀명**: Strategy Engine Team (전략 엔진 팀)
- **역할**: 매매 전략 및 점수 시스템 개발
- **버전**: 1.0.0

## 주요 기능

### 1. 기술적 지표 계산 (Technical Indicators)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- 이동평균 (SMA, EMA)
- 거래량 분석
- 추세 강도 분석

### 2. 종목 필터링 (Stock Filter)
- 거래량 급증 감지
- 변동성 기반 필터링
- 가격 범위 필터링
- 추세 강도 필터링
- 뉴스 이벤트 필터링

### 3. 점수 계산 (Score Calculator)
- 기술적 지표 점수 (40%)
- 거래량 점수 (20%)
- 추세 점수 (20%)
- 뉴스 감성 점수 (10%)
- 재무 성장성 점수 (10%)
- **총점**: 0~100점 스케일

### 4. 매매 시그널 생성 (Signal Generator)
- 매수 시그널 (BUY)
- 매도 시그널 (SELL)
- 손절 시그널 (STOP_LOSS)
- 익절 시그널 (TAKE_PROFIT)
- 보유 시그널 (HOLD)

## 디렉토리 구조

```
strategy_engine/
├── __init__.py
├── README.md
│
├── indicators/              # 기술적 지표
│   ├── __init__.py
│   └── technical_indicators.py
│
├── filters/                 # 종목 필터링
│   ├── __init__.py
│   └── stock_filter.py
│
├── scoring/                 # 점수 계산
│   ├── __init__.py
│   └── score_calculator.py
│
├── signals/                 # 시그널 생성
│   ├── __init__.py
│   └── signal_generator.py
│
├── api/                     # API 엔드포인트
│   ├── __init__.py
│   └── strategy_api.py
│
└── tests/                   # 테스트
    ├── __init__.py
    └── test_strategy_engine.py
```

## 설치

```bash
# 의존성 설치
pip install pandas numpy ta scikit-learn fastapi uvicorn
```

## 사용 예시

### 1. 기술적 지표 계산

```python
import pandas as pd
from strategy_engine.indicators import TechnicalIndicators

# OHLCV 데이터 준비
df = pd.DataFrame({
    'close': [100, 102, 101, 103, 105],
    'volume': [1000000, 1200000, 1100000, 1300000, 1500000]
})

# 지표 계산
indicators = TechnicalIndicators.calculate_all_indicators(df)

print(f"RSI: {indicators.rsi}")
print(f"MACD: {indicators.macd}")
print(f"추세 강도: {indicators.trend_strength}")
```

### 2. 종목 필터링

```python
from strategy_engine.filters import StockFilter, FilterCriteria

# 필터링 기준 설정
criteria = FilterCriteria(
    min_volume_ratio=1.5,      # 평균 대비 1.5배 이상 거래량
    min_volatility=0.02,        # 최소 2% 변동성
    min_trend_strength=60.0,    # 최소 60점 추세 강도
    uptrend_only=True           # 상승 추세만
)

# 필터링 실행
stock_filter = StockFilter(criteria)
results = stock_filter.filter_stocks(stock_data, news_data)

# 통과한 종목
passed_stocks = stock_filter.get_passed_stocks(results)
print(f"필터링 통과 종목: {passed_stocks}")
```

### 3. 점수 계산

```python
from strategy_engine.scoring import ScoreCalculator

# 점수 계산기 생성
calculator = ScoreCalculator()

# 종목 점수 계산
score_result = calculator.score_stock(
    symbol='AAPL',
    df=df,
    news_sentiment=0.5,         # 긍정적 뉴스
    news_count=5,
    revenue_growth=15.0,        # 15% 매출 성장
    eps_growth=20.0,            # 20% EPS 성장
)

print(f"총점: {score_result.total_score}/100")
print(f"추천: {score_result.recommendation}")  # BUY/HOLD/SELL
```

### 4. 매수 시그널 생성

```python
from strategy_engine.signals import SignalGenerator

# 시그널 생성기 생성
signal_gen = SignalGenerator()

# 매수 시그널 생성
buy_signal = signal_gen.generate_buy_signal(
    symbol='NVDA',
    df=df,
    news_sentiment=0.6,
    news_count=8
)

if buy_signal:
    print(f"매수 시그널 생성!")
    print(f"진입가: ${buy_signal.entry_price}")
    print(f"목표가: ${buy_signal.target_price}")
    print(f"손절가: ${buy_signal.stop_loss_price}")
    print(f"신뢰도: {buy_signal.confidence:.2%}")
```

### 5. 매도 시그널 생성

```python
# 매도 시그널 생성
sell_signal = signal_gen.generate_sell_signal(
    symbol='NVDA',
    df=df,
    entry_price=100.0,          # 진입가
    previous_score=85.0         # 이전 점수
)

if sell_signal:
    print(f"매도 시그널: {sell_signal.signal_type.value}")
    print(f"수익률: {sell_signal.metadata['profit_pct']:.2%}")
```

## API 서버 실행

```bash
# API 서버 시작
python -m strategy_engine.api.strategy_api

# 또는
uvicorn strategy_engine.api.strategy_api:app --host 0.0.0.0 --port 8001
```

API 문서: http://localhost:8001/docs

### API 엔드포인트

- `POST /indicators/calculate` - 기술적 지표 계산
- `POST /filter/stocks` - 종목 필터링
- `POST /score/calculate` - 점수 계산
- `POST /signal/buy` - 매수 시그널 생성
- `POST /signal/sell` - 매도 시그널 생성

## 테스트 실행

```bash
# 테스트 실행
python strategy_engine/tests/test_strategy_engine.py
```

## 매매 조건

### 매수 조건
- ✅ 점수 ≥ 75점
- ✅ 거래량 비율 ≥ 1.5배
- ✅ 추세 강도 ≥ 60점
- ✅ 상승 추세
- ✅ RSI < 70 (과매수 아님)
- ✅ MACD 골든크로스

### 매도 조건
- 🎯 목표 수익 도달 (+10%)
- 🛑 손절 기준 도달 (-2%)
- 📉 점수 급락 (20점 이상)
- 📉 점수 < 30점
- ⚠️ RSI > 80 (극단 과매수)
- ⚠️ MACD 강한 데드크로스

## 점수 시스템

### 가중치 (기본값)
- 기술적 지표: 40%
- 거래량: 20%
- 추세: 20%
- 뉴스 감성: 10%
- 재무 성장성: 10%

### 점수 해석
- **75~100점**: BUY (강력 매수)
- **50~74점**: HOLD (보유)
- **0~49점**: SELL (매도)

## 핵심 산출물

### 1. score_stock() 함수
```python
score_result = calculator.score_stock(
    symbol='AAPL',
    df=ohlcv_dataframe,
    news_sentiment=0.5,
    news_count=5,
    revenue_growth=15.0,
    eps_growth=20.0,
    institutional_ownership_change=3.0
)
```

### 2. Signal 생성 로직
```python
signal = signal_generator.generate_buy_signal(
    symbol='AAPL',
    df=ohlcv_dataframe,
    news_sentiment=0.5,
    news_count=5
)
```

## 기술 스택

- **Python 3.8+**
- **pandas**: 데이터 처리
- **numpy**: 수치 계산
- **ta**: 기술적 분석
- **FastAPI**: REST API
- **pydantic**: 데이터 검증

## 통합 방법

### 다른 팀과의 연동

```python
# 데이터 수집 팀 → 전략 엔진
from data_collection import get_stock_data
from strategy_engine import ScoreCalculator, SignalGenerator

# 데이터 가져오기
df = get_stock_data('AAPL')

# 점수 계산
calculator = ScoreCalculator()
score = calculator.score_stock('AAPL', df)

# 시그널 생성
signal_gen = SignalGenerator()
signal = signal_gen.generate_buy_signal('AAPL', df)

# 주문 실행 팀으로 전달
if signal:
    execution_engine.execute_order(signal)
```

## 성능 고려사항

- 지표 계산은 충분한 데이터(최소 200개 데이터포인트) 필요
- 백테스트 시 과최적화(overfitting) 주의
- 리스크 관리 룰은 절대 변경 금지

## 주의사항

⚠️ **중요**: 이 모듈은 **판단만** 수행합니다.
- ✅ 매매 신호 생성
- ✅ 점수 계산
- ❌ 실제 주문 실행 금지
- ❌ 리스크 룰 변경 금지

실제 주문 실행은 **주문 실행 팀(Execution Team)**이 담당합니다.

## 라이선스

MIT License

## 기여

전략 엔진 팀이 관리합니다. 이슈 및 개선 사항은 팀 리더에게 문의하세요.

---

**팀**: Strategy Engine Team
**작성일**: 2024
**버전**: 1.0.0
