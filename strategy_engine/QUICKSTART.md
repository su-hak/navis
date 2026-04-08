# 전략 엔진 빠른 시작 가이드

## ✅ 구현 완료 확인

전략 엔진 팀이 구현한 모든 모듈:
- **16개 Python 파일**
- **총 코드: 102,618 bytes (100.2 KB)**
- **핵심 함수**: score_stock(), generate_buy_signal(), generate_sell_signal() ✅

---

## 📋 1단계: 구조 검증 (지금 바로 실행 가능!)

```powershell
# PowerShell에서 실행
cd C:\navis
python strategy_engine/validate_structure.py
```

이 명령어는 **의존성 없이** 모든 파일이 제대로 생성되었는지 확인합니다.

---

## 📦 2단계: 의존성 설치

```powershell
# PowerShell에서 실행
cd C:\navis
pip install pandas numpy ta scikit-learn fastapi uvicorn
```

### 설치 확인

```powershell
python -c "import pandas, numpy; print('설치 완료!')"
```

---

## 🧪 3단계: 테스트 실행

```powershell
# PowerShell에서 실행
cd C:\navis

# 전체 통합 테스트
python strategy_engine/tests/test_strategy_engine.py

# 사용 예시 (6가지 시나리오)
python strategy_engine/example.py
```

---

## 🚀 4단계: API 서버 실행

```powershell
# PowerShell에서 실행
cd C:\navis
python -m strategy_engine.api.strategy_api
```

그런 다음 브라우저에서:
- **API 문서**: http://localhost:8001/docs
- **API 테스트**: http://localhost:8001

---

## 💡 간단한 사용 예시 (Python 코드)

### Python 스크립트 만들기

`test_strategy.py` 파일을 만드세요:

```python
import pandas as pd
import numpy as np
from datetime import datetime

# 전략 엔진 임포트
from strategy_engine.scoring import ScoreCalculator
from strategy_engine.signals import SignalGenerator

# 샘플 데이터 생성 (100일치)
dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
close_prices = 100 + np.cumsum(np.random.randn(100) * 2 + 0.3)

df = pd.DataFrame({
    'timestamp': dates,
    'open': close_prices * 0.99,
    'high': close_prices * 1.02,
    'low': close_prices * 0.98,
    'close': close_prices,
    'volume': [int(1000000 + np.random.randn() * 200000) for _ in range(100)]
})

print("=== 전략 엔진 테스트 ===\n")

# 1. 점수 계산
calculator = ScoreCalculator()
score = calculator.score_stock(
    symbol='AAPL',
    df=df,
    news_sentiment=0.6,
    news_count=8
)

print(f"[점수 계산 결과]")
print(f"총점: {score.total_score:.2f}/100")
print(f"추천: {score.recommendation}")
print(f"기술적 점수: {score.technical_score:.2f}")
print(f"거래량 점수: {score.volume_score:.2f}")
print(f"추세 점수: {score.trend_score:.2f}")

# 2. 매수 시그널 생성
print(f"\n[매수 시그널]")
signal_gen = SignalGenerator()
signal = signal_gen.generate_buy_signal('AAPL', df)

if signal:
    print(f"✅ 매수 시그널 생성!")
    print(f"신뢰도: {signal.confidence:.2%}")
    print(f"진입가: ${signal.entry_price:.2f}")
    print(f"목표가: ${signal.target_price:.2f}")
    print(f"손절가: ${signal.stop_loss_price:.2f}")
else:
    print("⚠️ 매수 조건 미충족")
```

실행:
```powershell
cd C:\navis
python test_strategy.py
```

---

## 📊 주요 기능

### 1. 기술적 지표 계산

```python
from strategy_engine.indicators import TechnicalIndicators

indicators = TechnicalIndicators.calculate_all_indicators(df)
print(f"RSI: {indicators.rsi}")
print(f"MACD: {indicators.macd}")
print(f"추세 강도: {indicators.trend_strength}")
```

### 2. 종목 필터링

```python
from strategy_engine.filters import StockFilter, FilterCriteria

criteria = FilterCriteria(
    min_volume_ratio=1.5,
    min_trend_strength=60.0,
    uptrend_only=True
)

stock_filter = StockFilter(criteria)
results = stock_filter.filter_stocks(stock_data)
passed = stock_filter.get_passed_stocks(results)
```

### 3. 점수 계산

```python
from strategy_engine.scoring import ScoreCalculator

calculator = ScoreCalculator()
score = calculator.score_stock('AAPL', df)

# 75점 이상: BUY
# 50-74점: HOLD
# 50점 미만: SELL
```

### 4. 시그널 생성

```python
from strategy_engine.signals import SignalGenerator

signal_gen = SignalGenerator()

# 매수 시그널
buy_signal = signal_gen.generate_buy_signal('AAPL', df)

# 매도 시그널
sell_signal = signal_gen.generate_sell_signal('AAPL', df, entry_price=100.0)
```

---

## 🔧 API 사용 예시

### curl로 API 호출

```bash
# 점수 계산
curl -X POST "http://localhost:8001/score/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "data": {
      "timestamp": ["2024-01-01", "2024-01-02"],
      "open": [100, 102],
      "high": [105, 107],
      "low": [99, 101],
      "close": [103, 105],
      "volume": [1000000, 1200000]
    }
  }'
```

---

## 📁 프로젝트 구조

```
strategy_engine/
├── indicators/          # 기술적 지표 (RSI, MACD, BB, SMA, EMA)
├── filters/             # 종목 필터링 (거래량, 변동성, 추세)
├── scoring/             # 점수 계산 (score_stock 함수)
├── signals/             # 시그널 생성 (매수/매도)
├── api/                 # REST API (FastAPI)
├── tests/               # 통합 테스트
├── README.md            # 전체 문서
├── example.py           # 6가지 사용 예시
├── quick_test.py        # Import 테스트
└── validate_structure.py # 구조 검증
```

---

## ✅ 체크리스트

실행 전 확인:
- [ ] Python 3.8 이상 설치 (`python --version`)
- [ ] 패키지 설치 (`pip install pandas numpy ta`)
- [ ] 현재 디렉토리 확인 (`pwd` → C:\navis)
- [ ] 구조 검증 완료 (`python strategy_engine/validate_structure.py`)

---

## 🎯 기획서 요구사항 달성

### 전략 엔진 팀 담당 영역 (100% 완료)

✅ **종목 필터링 로직**
- 거래량 급증 감지
- 변동성 분석
- 추세 강도 계산
- 파일: `filters/stock_filter.py`

✅ **점수 계산 알고리즘**
- 기술적 지표 점수 (40%)
- 거래량 점수 (20%)
- 추세 점수 (20%)
- 뉴스 감성 점수 (10%)
- 재무 점수 (10%)
- 파일: `scoring/score_calculator.py`

✅ **매수/매도 조건 정의**
- 매수: 점수 ≥75, 거래량 ≥1.5배, 추세 ≥60
- 매도: 익절(+10%), 손절(-2%), 점수 급락
- 파일: `signals/signal_generator.py`

✅ **기술적 지표 계산**
- RSI, MACD, Bollinger Bands
- SMA (20, 50, 200), EMA (12, 26)
- 거래량 비율, 추세 강도
- 파일: `indicators/technical_indicators.py`

✅ **핵심 산출물**
- `score_stock()` 함수
- `generate_buy_signal()` 함수
- `generate_sell_signal()` 함수

---

## 🚨 문제 해결

### 문제: ModuleNotFoundError

```powershell
pip install pandas numpy ta
```

### 문제: ImportError

반드시 `C:\navis`에서 실행:
```powershell
cd C:\navis
python strategy_engine/...
```

### 문제: API 서버가 안 열림

포트 8001이 이미 사용 중일 수 있습니다:
```powershell
# 다른 포트 사용
python -m uvicorn strategy_engine.api.strategy_api:app --port 8002
```

---

## 📞 지원

모든 구현이 완료되었습니다!

**다음 단계**:
1. 의존성 설치
2. 테스트 실행
3. 다른 팀과 통합 (데이터 수집 팀, 주문 실행 팀)

**팀**: Strategy Engine Team
**상태**: ✅ 구현 완료
**버전**: 1.0.0
