# NAVIS 퀀트 트레이딩 로직 재평가 (v3)

> 작성일: 2026-04-18
> 평가자: 퀀트 트레이더 관점 (Claude)
> 기준: NAVIS_CHANGELOG_V2.md 전체 반영 + 실제 소스코드 전수 검토
> 검토 대상: C:\navis (master 브랜치)

---

## 총평 (Executive Summary)

2차 평가에서 지적한 8개 항목 중 **6개가 실제로 구현**됐다.
아키텍처 완성도가 크게 높아졌고, 이제 "복잡한 시스템"에서 "방향이 맞는 시스템"으로 진입했다.
다만 코드를 직접 열어보니 **changelog에 기재된 것과 실제 구현 사이에 미묘한 간극**이 3곳 존재한다.
이것들이 라이브 투입 시 운영 리스크가 된다.

---

## Phase 1 구현 검증 (1차 감사 반영)

### ✅ CRIT-01 | ATR 기반 동적 SL — 구현 확인

```python
# risk_manager.py
def calculate_atr(high, low, close, period=14):
    # 14-period rolling ATR — 정확히 구현됨

def calculate_stops(entry_price, atr=None, atr_sl_multiplier=1.5, atr_tp_multiplier=3.0):
    if atr and atr > 0:
        stop_loss  = entry_price - 1.5 * atr  # 동적
        take_profit = entry_price + 3.0 * atr  # 동적
    else:
        stop_loss  = entry_price * 0.98        # fallback -2%
        take_profit = entry_price * 1.06       # fallback +6%
```

**평가:** 완전 구현. fallback 로직도 있어 ATR 데이터 없는 경우에도 안전.
단, **ATR 계산 성공 여부를 명시적으로 검증하지 않음** — `atr > 0` 체크만으로는 계산 실패를 잡지 못한다.

---

### ✅ CRIT-02 | 포지션 사이징 축소 — 구현 확인

```
변경 전: 20 / 15 / 10 / 8 / 5%
변경 후: 10 / 8  / 6  / 5 / 3%   ← 검증됨
```

**평가:** 정확히 구현. 집중 리스크 제거됨.

---

### ✅ CRIT-03 | 일일 손실 예산 검증 — 구현 확인

```python
# check_order() 내부
if max_loss_this_trade > remaining_daily_budget * 0.5:
    quantity 강제 조정 또는 진입 차단
```

**평가:** 구현됨. 연속 손실 시 자동 베팅 축소 작동.

---

### ✅ IMP-01 | VIX/SPY 하드 게이트 — 구현 확인

```python
# market_gate.py
차단 조건 3개:
  1. VIX > 25.0
  2. SPY < MA200
  3. SPY 당일 변화 ≤ -2%
```

**평가:** 구현 정확. 재시도 로직(3회, 지수 백오프)도 포함.
단, **SPY MA200 계산 시 bars 수 검증 없음** — 데이터가 200봉 미만이면 잘못된 MA200으로 판단할 수 있다.

---

### ✅ IMP-02 | 갭 방향 검증 — 구현 확인

```python
# gap_validator.py
갭 상승 + 9:30~9:35 첫 캔들 양봉 → Gap & Go → 진입 허용
갭 상승 + 9:30~9:35 첫 캔들 음봉 → Gap & Fade → 진입 차단
```

**평가:** 구현됨. 데이터 없을 시 진입 거부(안전 fallback).
단, **프리마켓 갭에 대한 검증은 실행되지 않음** — gap_validator가 시장 시간에만 호출되어 프리마켓 진입 시 우회된다.

---

### ✅ IMP-03 | Trailing Stop + 분할 청산 — 구현 확인

```python
# auto_trading_bot_v2.py
+3% 도달 → 50% 물량 청산 (partial TP)
이후 고점 대비 -2% 하락 → 잔량 전량 청산 (trailing stop)
_highest_price, _partial_tp_done 상태 추적
```

**평가:** 구현됨. +30% 가는 갭 스톡에서 추가 이익 포착 가능해짐.

---

### ✅ NEW-01 | 백테스트 엔진 — 구현 확인

```python
# backtesting/backtest_engine.py
BacktestConfig: slippage_pct, atr_sl_multiplier, trailing_stop_pct, partial_tp_pct
BacktestResult: sharpe_ratio, max_drawdown_pct, profit_factor, win_rate_pct, equity_curve
grid_search(): 파라미터 조합별 Sharpe 정렬
통과 기준: Sharpe ≥ 1.5 AND MDD ≤ 20% AND PF ≥ 1.5
```

**평가:** 핵심 엔진 작동. 슬리피지도 0.5%로 현실화됨.
단, **일봉 기반이라 look-ahead bias 잔존** (미구현 항목으로 명시됨 — 인정).

---

### ✅ NEW-02 | WebSocket 실시간 SL/TP — 구현 확인

```python
# websocket_monitor.py
Alpaca StockDataStream → quote 이벤트 → _check_sl_tp() 즉시 호출
반응 속도: <1초 (기존 30초 폴링 대비 30배 개선)
```

**평가:** 구현됨. 반응 속도 문제 해결.
⚠️ **단, positions 딕셔너리에 threading.Lock 없음.** 메인 루프와 WebSocket 스레드가 동시에 접근 시 race condition 발생 가능.

---

## Phase 2 구현 검증 (2차 감사 반영)

### ✅ BUG-01 | TP 파라미터 단일 소스 통일 — 부분 구현

```python
# config/trading_constants.py (신규)
TAKE_PROFIT_PCT = 0.06
STOP_LOSS_PCT   = 0.02
```

**평가:** 상수 파일 생성은 됐다. 그러나 **auto_trading_bot_v2.py가 환경변수(TAKE_PROFIT_PERCENT)로 이 값을 여전히 덮어쓸 수 있다.**

```python
# auto_trading_bot_v2.py (현재 상태)
take_profit_pct = float(os.getenv("TAKE_PROFIT_PERCENT", "6.0")) / 100
# → .env에 TAKE_PROFIT_PERCENT=5 설정 시 trading_constants.py를 무시함
```

changelog에 "단일 소스 통일"이라고 명시됐지만, **실질적으로는 여전히 두 경로가 존재**한다. 운영 환경 .env 설정이 상수 파일을 조용히 오버라이드한다.

---

### ⚠️ BUG-02 | RSI 스코어링 전략별 분리 — 구현됐으나 실행 경로에서 끊김

```python
# score_calculator.py (구현됨)
rsi_score_momentum()  → RSI 50-70 구간 최고점 ✅
rsi_score_reversion() → RSI 30-50 구간 최고점 ✅

# signal_generator.py (구현됨)
generate_buy_signal(symbol, df, strategy_type="momentum") ✅
```

**그러나 auto_trading_bot_v2.py의 실제 진입 경로:**

```python
# _execute_buy_signal_inner() 내부
signal = signal_generator.generate_buy_signal(symbol, df)
# → strategy_type 인자를 전달하지 않음
# → default "momentum"으로 항상 고정
```

결론: **momentum 전략은 올바르게 작동하지만, reversion 전략은 strategy_type이 전달되지 않아 사실상 momentum 스코어링으로 평가됨.** reversion 전략이 의도대로 필터링되지 않는다.

---

### ✅ NEW-01 | 전략 유니버스 분리 + 충돌 해결 — 구현 확인

```python
# strategy_manager.py
momentum  유니버스: gap >3% AND volume >3x
breakout  유니버스: 52주 신고가 5% 이내
reversion 유니버스: RSI <35 OR 볼린저 하단

resolve_conflicts(): 동일 종목 다수 전략 등장 시 점수 최고 전략만 진입
```

**평가:** 구조적 헤징 문제 해결됨. 유니버스 분리 정확.

---

### ✅ NEW-02 | 백테스트 슬리피지 현실화 — 구현 확인

```
0.1% → 0.5% 변경 확인됨
```

---

### ✅ NEW-03 | 점수 임계값 최적화 도구 — 구현 확인

```python
BacktestEngine.optimize_score_threshold(
    symbol, df,
    threshold_range=(55.0, 85.0), step=5.0
)
→ best_threshold, best_sharpe 반환
```

**평가:** 임계값 근거를 데이터로 찾을 수 있는 도구 제공됨.

---

## 신규 발견 이슈 (코드 직접 검토에서 추가 확인)

### 🔴 신규-01 | WebSocket race condition

```python
# websocket_monitor.py
self.positions: Dict[str, PositionState] = {}
# threading.Lock 없음
# 메인 루프(포지션 추가) + WS 스레드(가격 체크) 동시 접근 가능
```

SL 트리거 시점에 포지션 딕셔너리가 동시에 수정되면 **KeyError 또는 잘못된 청산** 발생 가능.

**수정 방법 (2줄):**
```python
self._lock = threading.Lock()
with self._lock:  # positions 접근 시마다 적용
```

---

### 🟡 신규-02 | 백테스트 분할 청산 후 trailing stop 로직 불일치

```python
# backtest_engine.py
# partial TP (+3%) 이후 trailing stop 적용 시
# 초기 TP 조건이 재검사되는 구조 → live bot과 exit 순서 미묘하게 다름
```

백테스트 성과와 실거래 성과가 미묘하게 달라지는 원인이 될 수 있다. 현재는 큰 영향이 없지만 실거래 적용 후 tracking error가 쌓이면 파라미터 최적화 방향이 틀어진다.

---

### 🟡 신규-03 | MA200 데이터 충분성 검증 없음

```python
# market_gate.py
spy_bars = data_client.get_stock_bars(...)  # max 300봉
spy_ma200 = spy_bars['close'].rolling(200).mean().iloc[-1]
# bars가 200봉 미만이면 NaN → 조건 판단 오작동
```

장 초반 또는 신규 상장 종목 유니버스 사용 시 MA200이 NaN으로 반환될 수 있다.

---

## 3차 종합 평가 점수표

| 영역 | 1차 | 2차 | 3차 | 변화 |
|------|-----|-----|-----|------|
| 아키텍처 | ★★★★☆ | ★★★★★ | ★★★★★ | → 유지 |
| 알파 소스 / 진입 타이밍 | ★★★☆☆ | ★★★☆☆ | ★★★★☆ | ↑ 갭 방향 검증 추가 |
| 기술적 지표 활용 | ★☆☆☆☆ | ★★★☆☆ | ★★★★☆ | ↑ RSI 전략별 분리 (단, 실행 경로 오류) |
| 리스크 관리 | ★★★☆☆ | ★★★★☆ | ★★★★★ | ↑ ATR SL + 예산 검증 완성 |
| 포지션 사이징 | ★★☆☆☆ | ★★☆☆☆ | ★★★★☆ | ↑ 테이블 축소 완료 |
| 백테스팅 | ★☆☆☆☆ | ★★★☆☆ | ★★★★☆ | ↑ 엔진 완성, 슬리피지 현실화 |
| 전략 일관성 | ★★☆☆☆ | ★★☆☆☆ | ★★★★☆ | ↑ 유니버스 분리, 충돌 해결 |
| 실행 레이어 | ★★★★☆ | ★★★★☆ | ★★★★☆ | → WebSocket 추가됐으나 race condition |
| AI 활용 | ★★★☆☆ | ★★★☆☆ | ★★★★☆ | ↑ 뉴스 타이밍 필터 추가 |
| **종합** | **★★★☆☆** | **★★★½☆** | **★★★★☆** | **↑ 실질적 도약** |

---

## 라이브 배포 전 필수 수정 (Blocking Issues)

### [BLOCK-01] WebSocket race condition 수정 (30분 작업)

```python
# websocket_monitor.py
import threading

class WebSocketPriceMonitor:
    def __init__(self):
        self._lock = threading.Lock()
        self.positions = {}

    def update_position(self, symbol, state):
        with self._lock:
            self.positions[symbol] = state

    def _check_sl_tp(self, symbol, price):
        with self._lock:
            pos = self.positions.get(symbol)
        if pos is None:
            return
        # ... 이하 로직
```

---

### [BLOCK-02] reversion 전략에 strategy_type 전달 (1시간 작업)

```python
# auto_trading_bot_v2.py _execute_buy_signal_inner()
# 현재
signal = signal_generator.generate_buy_signal(symbol, df)

# 수정
strategy_type = self._get_strategy_type(symbol)  # momentum/reversion/breakout
signal = signal_generator.generate_buy_signal(symbol, df, strategy_type=strategy_type)
```

---

### [BLOCK-03] TP 파라미터 환경변수 오버라이드 제거 (30분 작업)

```python
# auto_trading_bot_v2.py
# 현재 (문제)
take_profit_pct = float(os.getenv("TAKE_PROFIT_PERCENT", "6.0")) / 100

# 수정
from config.trading_constants import TAKE_PROFIT_PCT
take_profit_pct = TAKE_PROFIT_PCT
# .env에서 이 값을 바꾸려면 trading_constants.py를 수정하도록 정책 변경
```

---

## 미구현 항목 현황 (Changelog 기준)

| 항목 | 상태 | 비고 |
|------|------|------|
| qa_team 백테스트 ATR SL 반영 | 🔴 미구현 | qa_team 엔진은 여전히 고정 SL |
| 5분봉 백테스트 | 🔴 미구현 | look-ahead bias 잔존 |
| 재무 팩터 10% 구현 | 🟡 미구현 | reserved, 중립 50점 고정 |
| Kelly Criterion 포지션 사이징 | 🟡 미구현 | 포지션 수 기반 테이블 유지 |
| Walk-forward 최적화 | 🟡 미구현 | 과적합 방지 미완 |

---

## 결론

**1차 → 2차 → 3차 진화 요약:**

- 1차: 단순하지만 검증 없는 gap+volume 추종 봇
- 2차: 복잡해졌지만 RSI 방향 오류, TP 불일치, 백테스트 없음
- 3차: **방향이 올바른 시스템** — ATR SL, VIX 게이트, 갭 방향 검증, 분할 청산, WebSocket 모두 구현됨

**지금 상태:** Blocking Issue 3개만 수정하면 페이퍼 트레이딩 투입 가능.
라이브 실전 투입은 **백테스트 통과 확인 (Sharpe ≥ 1.5, MDD ≤ 20%)** 이후 권장.

> 전반적으로 상당히 좋은 시스템이 됐다. 2차 평가에서 "더 복잡해진 시스템"이라고 했던 말을 수정한다 — 이제는 **복잡도가 알파에 기여하는 시스템**이다. Blocking Issue 3개 처리 후 백테스트 결과를 보자.
