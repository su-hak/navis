# 전략 엔진 테스트 및 실행 가이드

## 실행 전 준비사항

### 1. 의존성 설치

먼저 프로젝트 루트(navis)에서 필요한 패키지를 설치하세요:

```powershell
# PowerShell에서 실행
pip install pandas numpy ta scikit-learn fastapi uvicorn
```

또는 requirements.txt 사용:

```powershell
pip install -r requirements.txt
```

### 2. 설치 확인

```powershell
python -c "import pandas, numpy; print('패키지 설치 완료')"
```

---

## 테스트 실행 방법

### 방법 1: 프로젝트 루트에서 실행 (권장)

```powershell
# C:\navis 디렉토리로 이동
cd C:\navis

# 테스트 실행
python strategy_engine/tests/test_strategy_engine.py
```

### 방법 2: 예제 파일 실행

```powershell
# C:\navis 디렉토리로 이동
cd C:\navis

# 예제 실행
python strategy_engine/example.py
```

---

## API 서버 실행

```powershell
# C:\navis 디렉토리로 이동
cd C:\navis

# API 서버 시작
python -m strategy_engine.api.strategy_api
```

그런 다음 브라우저에서 다음 주소로 접속:
- API 문서: http://localhost:8001/docs
- API 테스트: http://localhost:8001

---

## 간단한 사용 예시

### Python 인터프리터에서 테스트

```powershell
# C:\navis 디렉토리로 이동
cd C:\navis

# Python 실행
python
```

그런 다음 Python 인터프리터에서:

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 전략 엔진 임포트
from strategy_engine.indicators import TechnicalIndicators
from strategy_engine.scoring import ScoreCalculator
from strategy_engine.signals import SignalGenerator

# 샘플 데이터 생성
dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
close_prices = 100 + np.cumsum(np.random.randn(100) * 2 + 0.3)

df = pd.DataFrame({
    'close': close_prices,
    'volume': [1000000 + int(np.random.randn() * 200000) for _ in range(100)]
})

# 기술적 지표 계산
indicators = TechnicalIndicators.calculate_all_indicators(df)
print(f"RSI: {indicators.rsi:.2f}")
print(f"MACD: {indicators.macd:.4f}")

# 점수 계산
calculator = ScoreCalculator()
score = calculator.score_stock('AAPL', df)
print(f"총점: {score.total_score:.2f}/100")
print(f"추천: {score.recommendation}")

# 매수 시그널 생성
signal_gen = SignalGenerator()
signal = signal_gen.generate_buy_signal('AAPL', df)
if signal:
    print(f"매수 시그널 생성!")
    print(f"신뢰도: {signal.confidence:.2%}")
```

---

## 문제 해결

### 문제 1: ModuleNotFoundError

**오류**:
```
ModuleNotFoundError: No module named 'pandas'
```

**해결**:
```powershell
pip install pandas numpy ta scikit-learn
```

### 문제 2: ImportError (relative import)

**오류**:
```
ImportError: attempted relative import beyond top-level package
```

**해결**:
반드시 **C:\navis 디렉토리**에서 실행하세요:
```powershell
cd C:\navis
python strategy_engine/tests/test_strategy_engine.py
```

### 문제 3: Python 버전

Python 3.8 이상이 필요합니다. 버전 확인:

```powershell
python --version
```

---

## 올바른 실행 구조

```
C:\navis\                          ← 여기서 실행!
├── strategy_engine/
│   ├── __init__.py
│   ├── indicators/
│   ├── filters/
│   ├── scoring/
│   ├── signals/
│   ├── api/
│   ├── tests/
│   │   └── test_strategy_engine.py
│   └── example.py
├── requirements.txt
└── ...
```

**중요**: 반드시 `C:\navis` 디렉토리에서 명령어를 실행하세요!

---

## 빠른 테스트

### 1분 테스트 (의존성만 확인)

```powershell
cd C:\navis
python -c "from strategy_engine.indicators import TechnicalIndicators; print('OK')"
```

이 명령어가 "OK"를 출력하면 모든 것이 정상입니다.

---

## 전체 테스트 실행

```powershell
# 1. C:\navis로 이동
cd C:\navis

# 2. 의존성 설치 확인
pip install pandas numpy ta

# 3. 테스트 실행
python strategy_engine/tests/test_strategy_engine.py

# 4. 예제 실행
python strategy_engine/example.py
```

---

## 추가 지원

문제가 계속 발생하면:
1. Python 버전 확인: `python --version` (3.8 이상)
2. 패키지 설치 확인: `pip list | findstr pandas`
3. 현재 디렉토리 확인: `pwd` (반드시 C:\navis)

---

**참고**: 모든 명령어는 PowerShell 또는 CMD에서 실행하세요.
