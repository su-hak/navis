# 자동매매 봇 V2 사용 가이드

## 📋 개요

기획서 기반 2단계 감시 시스템을 구현한 자동매매 봇입니다.

### 핵심 기능

```
[Stage 1] 전체 시장 스캔 (3~5분) → 워치리스트 생성
    ↓
[Stage 2] 워치리스트 고주기 감시 (5~10초) → 즉시 실행
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# 필수 환경변수 설정
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
AUTO_TRADING_ENABLED=false  # 처음엔 false로 테스트!
```

### 2. 실행

```bash
# V2 봇 실행
python auto_trading_bot_v2.py
```

## 📊 시스템 구조

### Stage 1: 전체 시장 스캔

**주기**: 3~5분 (기본 5분)

**워치리스트 선별 조건**:
- 갭 > 3% (프리마켓 급등)
- 거래량 > 평균의 3배
- 상위 20개 종목 선택

**파일**: `data_collection/monitoring/watchlist_generator.py`

### Stage 2: 고주기 모니터링

**주기**: 5~10초 (기본 10초)

**매매 신호 조건**:
- 가격 변동 ≥ 1.5%
- 즉시 매매 실행

**파일**: `data_collection/monitoring/high_frequency_monitor.py`

## ⚙️ 환경 변수 설정

### 필수 설정

```env
# 브로커 API
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# 자동매매 활성화 (주의!)
AUTO_TRADING_ENABLED=false  # true로 변경 시 실제 주문 실행
```

### Stage 1 설정 (전체 시장 스캔)

```env
MARKET_SCAN_INTERVAL_MINUTES=5    # 스캔 주기 (분)
GAP_THRESHOLD=3.0                  # 갭 임계값 (%)
VOLUME_RATIO_THRESHOLD=3.0         # 거래량 비율
MAX_WATCHLIST_SIZE=20              # 워치리스트 크기
```

### Stage 2 설정 (고주기 모니터링)

```env
MONITOR_INTERVAL_SECONDS=10        # 모니터링 간격 (초)
PRICE_CHANGE_THRESHOLD=1.5         # 변동 임계값 (%)
```

### 리스크 관리 (기획서 규칙)

```env
MAX_INVESTMENT_PERCENT=10.0        # 1회 최대 투자: 10%
STOP_LOSS_PERCENT=2.0              # 손절: -2%
MAX_DAILY_LOSS_PERCENT=5.0         # 일일 손실: -5%
MAX_POSITIONS=5                    # 최대 포지션 수
```

## 🎯 리스크 관리

기획서 기반 리스크 규칙:

| 항목 | 설정 | 설명 |
|------|------|------|
| 1회 투자 | 10% | 현금의 10%만 투자 |
| 손절 | -2% | 개별 포지션 -2% 도달 시 청산 |
| 일일 손실 | -5% | 하루 총 손실 -5% 도달 시 거래 중단 |
| 손익비 | 1:1.5 | 수익 목표는 손실의 1.5배 |

**파일**: `utils/risk_manager.py`

## 📈 멀티 전략 시스템

기획서 포트폴리오 배분:

```
전략 A (모멘텀): 40%  → 상승 추세 추종
전략 B (돌파):   30%  → 저항선 돌파
전략 C (리버전): 30%  → 과매도/과매수 역매매
```

**파일**: `strategy_engine/multi_strategy/`

### 전략별 특징

#### 모멘텀 전략 (40%)
- RSI > 60 (강세)
- 거래량 > 평균 2배
- 가격 > 20일 이동평균

#### 돌파 전략 (30%)
- 20일 최고가 돌파
- 강한 거래량 동반
- 저항선 2% 이상 돌파

#### 리버전 전략 (30%)
- RSI < 30 (과매도) → 매수
- RSI > 70 (과매수) → 매도
- 볼린저 밴드 이탈 복귀

## 🔍 로그 확인

```bash
# V2 봇 로그
tail -f logs/auto_trading_v2.log

# 실행 팀 로그
tail -f logs/execution/execution.log
```

## ⚠️ 주의사항

### 급등 포착 문제 해결

**기존 문제**:
```
60분마다 AI 분석 → 급등 종목 놓침
```

**V2 해결책**:
```
5분마다 워치리스트 갱신
  ↓
10초마다 실시간 감시
  ↓
1.5% 변동 시 즉시 매매
```

### 안전 체크리스트

- [ ] `AUTO_TRADING_ENABLED=false`로 시뮬레이션 먼저 테스트
- [ ] Paper Trading API 사용 확인 (`paper-api.alpaca.markets`)
- [ ] 리스크 한계 설정 확인
- [ ] 로그 파일 모니터링
- [ ] 소액으로 시작

## 🧪 테스트 모드

```bash
# 시뮬레이션 모드 (주문 실행 안 함)
AUTO_TRADING_ENABLED=false python auto_trading_bot_v2.py
```

**출력 예시**:
```
⚠️⚠️⚠️ 자동매매가 비활성화되어 있습니다 ⚠️⚠️⚠️
시뮬레이션 모드로 실행됩니다 (실제 주문 없음)
```

## 📚 코드 구조

```
auto_trading_bot_v2.py          # 메인 봇 (2단계 구조)
├── data_collection/monitoring/
│   ├── watchlist_generator.py  # Stage 1: 워치리스트 생성
│   └── high_frequency_monitor.py # Stage 2: 고주기 감시
├── utils/
│   └── risk_manager.py         # 리스크 관리
├── strategy_engine/multi_strategy/
│   ├── strategy_manager.py     # 멀티 전략 관리자
│   └── strategies.py           # 개별 전략 (모멘텀/돌파/리버전)
└── execution_team/             # 주문 실행
    └── core/
        └── execution_engine.py
```

## 🔧 고급 설정

### 워치리스트 종목 유니버스 변경

`data_collection/monitoring/watchlist_generator.py:57`

```python
def _get_default_universe(self) -> List[str]:
    # 여기에 원하는 종목 추가
    return ['AAPL', 'TSLA', 'NVDA', ...]
```

### 전략 비중 조정

`strategy_engine/multi_strategy/strategy_manager.py:240`

```python
# 모멘텀 40% → 50%로 변경
manager.add_strategy(StrategyConfig(
    strategy_type=StrategyType.MOMENTUM,
    allocation_percent=50.0,  # 변경
    max_positions=3
))
```

## 📞 문제 해결

### "워치리스트가 비어있습니다"
- 시장 시간 확인 (미국 동부시간 9:30 AM ~ 4:00 PM)
- 임계값 낮추기 (`GAP_THRESHOLD`, `VOLUME_RATIO_THRESHOLD`)

### "리스크 한계 초과"
- 일일 손실 한계 도달
- 포지션 수동 청산 또는 다음 날까지 대기

### "API 호출 실패"
- API 키 확인
- API Rate Limit 확인 (Alpaca 무료: 200 req/min)

## 📖 기획서 참조

전체 기획서: `.claude/ai_trading_master_plan.md`

**핵심 요구사항**:
- ✅ 2단계 감시 (3~5분 / 5~10초)
- ✅ 워치리스트 자동 생성 (gap>3%, volume>3배)
- ✅ 고주기 모니터링 (asyncio, 1.5% 변동)
- ✅ 리스크 관리 (10%, -2%, -5%)
- ✅ 멀티 전략 (40%/30%/30%)

## 🎯 수익률 최적화 (기획서)

**핵심 공식**:
```
수익 = 승률 × 손익비
```

**추천 세팅**:
- 승률: 55~60%
- 손익비: 1:1.5

## 🚧 향후 확장 (기획서 5번)

### WebSocket 실시간 감시 (준 HFT)

```python
# 향후 구현 예정
import websocket

def on_message(ws, message):
    data = json.loads(message)
    if detect_spike(data['price']):
        execute_trade(data['symbol'])
```

**장점**:
- Tick 단위 실시간 감시
- 지연 시간 최소화 (<1초)
- REST API 대비 효율적

## 📝 라이선스

MIT License
