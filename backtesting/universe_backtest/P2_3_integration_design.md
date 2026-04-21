# P2-3 — V4 + 갭 페이드 통합 백테스트 설계안
**작성일**: 2026-04-20  
**작성자**: 개발 1팀  
**연관 문서**: strategy_gap_fade.py, NAVIS_DEV_INSTRUCTIONS.md  
**상태**: 퀀트 트레이더님 검토 및 승인 대기

---

## 1. 사전 조사 결과 (코드 확인 완료)

### 1-A. `prev_close` 이미 제공됨 — 추가 작업 불필요

`backtesting/universe_backtest/screener.py`의 candidate dict 스펙:

```python
{
    'symbol':       str,
    'gap_pct':      float,   # 갭 비율 (%)
    'volume_ratio': float,
    'score':        float,
    'prev_close':   float,   # ← 이미 포함됨
    'day_open':     float,
}
```

갭 페이드 진입 함수(`_try_entry_gap_fade`)에 `prev_close`를 전달하는 데
**스크리너 수정이 필요 없습니다.** 메인 루프에서 `candidate["prev_close"]`를 그대로 사용합니다.

### 1-B. V4 진입 차단 지점 — Gap Fade 개입 포인트 확정

`_try_entry_v4()` 내 line ~597:

```python
# ① 첫 5분봉 방향 필터
if float(first_bar["close"]) < float(first_bar["open"]):
    return None   # ← 현재 여기서 끝남. 갭 페이드 진입 기회를 버리는 지점
```

이 `return None`을 `_try_entry_gap_fade()`로 전환하는 것이
가장 자연스러운 통합 포인트입니다.

### 1-C. 현재 엔진: Long 전용

`_process_position_5min()`의 SL/TP 로직은 모두 "가격 상승 = 수익" 방향으로
설계되어 있습니다. Short 포지션을 지원하려면 수정이 필요합니다.

---

## 2. 핵심 설계 결정 사항 (퀀트 트레이더님 승인 필요)

### 결정 #1 — 방향: Short 시뮬레이션 vs Long 페이드 진입

두 가지 옵션이 있습니다.

#### 옵션 A: Short 시뮬레이션 (권장)

갭업 후 반전 하락을 Short으로 포착합니다.

```
진입: 첫 5분봉 close에서 Short 진입
SL:   첫 바 high × 1.001 (위로 돌파 = 실패)
TP1:  prev_close + gap_size × 0.70 (30% 되돌림)
TP2:  prev_close + gap_size × 0.40 (60% 되돌림)
청산: 11:00 ET Morning Close
```

- **장점**: V4와 진정한 음의 상관관계. 베어마켓 헤지 효과 최대
- **단점**: 엔진 수정 범위 중간 수준 (position dict에 `direction` 필드 추가, SL/TP 로직 분기)
- **백테스트 가능 여부**: 가능 (실제 주식 대차 없이 P&L 계산만 하면 됨)

#### 옵션 B: Long 페이드 진입 (간단)

갭이 50% 메워진 시점에서 Long 반등을 포착합니다.

```
대기: 갭의 50% 되돌림 지점까지 기다림
진입: prev_close + gap_size × 0.50 도달 시 Long 진입
SL:   진입가 × 0.985 (1.5% 고정)
TP:   day_open 수준까지 반등 (갭의 50% → 100% 복원)
청산: 11:30 ET Morning Close
```

- **장점**: 엔진 수정 없음 (Long 로직 그대로 사용)
- **단점**: "갭 페이드 전략"의 본래 의미와 다름. V4와의 상관관계 감소 효과 불확실

**개발팀 의견**: 옵션 A (Short 시뮬레이션)를 권장합니다.
엔진 수정 범위가 합리적이고, 전략의 원래 의도에 부합합니다.

---

## 3. 옵션 A 선택 시: 엔진 구조 변경 계획

### 3-1. 포지션 dict에 `direction` 필드 추가

```python
pos = {
    "symbol":          symbol,
    "direction":       "LONG",   # 또는 "SHORT"  ← 신규
    "entry_price":     buy_price,
    "qty":             qty,
    "sl_price":        sl_price,
    ...
}
```

### 3-2. `_try_entry_gap_fade()` 신규 함수 추가

`engine.py` 내 `_try_entry_v4()` 아래에 추가:

```python
def _try_entry_gap_fade(
    self,
    symbol:      str,
    prev_close:  float,
    day_open:    float,
    five_min_df: pd.DataFrame,
    capital:     float,
) -> Optional[Tuple[dict, float, pd.DataFrame]]:
    """
    갭 페이드 Short 진입:
      ① 갭업 4% 이상 확인
      ② 첫 5분봉 음봉 확인 (close < open)
      ③ 첫 5분봉 close < VWAP 확인
      ④ Short 진입: 첫 바 close
      ⑤ SL = 첫 바 high × 1.001
      ⑥ TP1 = prev_close + gap_size × 0.70 (30% 되돌림)
      ⑦ TP2 = prev_close + gap_size × 0.40 (60% 되돌림)
    """
    if len(five_min_df) < 1:
        return None

    # ① 갭업 확인
    gap_pct = (day_open - prev_close) / prev_close
    if gap_pct < self.config.gap_fade_threshold_pct:
        return None

    first_ts, first_bar = list(five_min_df.iterrows())[0]
    first_close = float(first_bar["close"])
    first_open  = float(first_bar["open"])
    first_high  = float(first_bar["high"])

    # ② 첫 5분봉 음봉 확인
    if first_close >= first_open:
        return None  # 양봉 = V4 영역, Gap Fade 포기

    # ③ 첫 5분봉 close < VWAP 확인
    vol    = float(first_bar.get("volume", 0))
    tp     = (first_high + float(first_bar["low"]) + first_close) / 3
    vwap   = tp  # 첫 바 1개 = VWAP ≈ 해당 바 typ price
    if first_close >= vwap:
        return None

    # ④ Short 진입
    entry_price = first_close * (1 - self.config.slippage_rate)  # 슬리피지 반영
    sl_price    = first_high * (1 + self.config.gap_fade_sl_buffer)

    sl_distance = (sl_price - entry_price) / entry_price
    if sl_distance <= 0 or sl_distance > self.config.v4_max_sl_distance:
        return None

    # ⑤ 목표가 계산
    gap_size  = day_open - prev_close
    tp1_price = prev_close + gap_size * (1 - self.config.gap_fade_tp1_ratio)
    tp2_price = prev_close + gap_size * (1 - self.config.gap_fade_tp2_ratio)

    # R:R 검증
    tp1_distance = (entry_price - tp1_price) / entry_price
    if tp1_distance <= 0:
        return None  # 이미 TP1 이하에서 진입 — 패스

    # 포지션 사이징 (리스크 사이징 또는 고정 10%)
    if self.config.use_risk_sizing and sl_distance > 0:
        target_risk = capital * self.config.risk_per_trade_pct
        sl_dollar   = entry_price * sl_distance
        qty_risk    = int(target_risk / sl_dollar)
        qty_cap     = int(capital * 0.10 / entry_price)
        qty         = min(qty_risk, qty_cap)
    else:
        qty = int(capital * self.config.gap_fade_position_pct / entry_price)

    if qty <= 0 or capital < entry_price * qty:
        return None

    commission = entry_price * qty * self.config.commission_rate
    total_cost = entry_price * qty + commission  # Short 진입: 증거금 개념

    pos = {
        "symbol":          symbol,
        "direction":       "SHORT",      # ← 핵심
        "entry_price":     entry_price,
        "qty":             qty,
        "sl_price":        sl_price,     # SHORT: 이 위로 돌파 시 손절
        "tp1_price":       tp1_price,
        "tp2_price":       tp2_price,
        "gap_fade_tp1_done": False,
        "gap_fade_tp2_done": False,
        "partial_tp_done": False,
        "pms_tp1_done":    False,
        "pms_tp2_done":    False,
        "highest_price":   entry_price,  # SHORT에서는 lowest_price로 재해석
        "entry_dt":        str(first_ts),
        "strategy":        "GAP_FADE",   # 전략 식별자
    }
    remaining = five_min_df.iloc[1:]
    return pos, total_cost, remaining
```

### 3-3. `_try_entry()` 통합 로직

```python
def _try_entry(self, symbol, day_open, five_min_df, capital, n_positions, atr,
               prev_close=None):  # prev_close 파라미터 추가
    
    if self.config.pms_mode and self.config.v4_pullback:
        # V4 시도
        v4_result = self._try_entry_v4(symbol, day_open, five_min_df, capital, atr=atr)
        if v4_result is not None:
            return v4_result
        
        # V4 실패(음봉 등) → Gap Fade 시도
        if self.config.gap_fade_enabled and prev_close is not None:
            return self._try_entry_gap_fade(
                symbol, prev_close, day_open, five_min_df, capital
            )
        return None
    
    # 표준 Spike 진입 (기존 코드 유지)
    ...
```

### 3-4. `_process_position_5min()` SHORT 분기 추가

SHORT 포지션의 경우 SL/TP 방향이 반전됩니다:

```python
# SHORT 전용 청산 처리 분기
if pos.get("direction") == "SHORT":
    return self._process_short_position_5min(pos, five_min_df, capital, daily_pnl, trade_records)
```

`_process_short_position_5min()` 핵심 로직:

```python
for ts, bar in five_min_df.iterrows():
    bar_high = float(bar["high"])
    bar_low  = float(bar["low"])
    bar_open = float(bar.get("open", bar["close"]))

    # SL: 고점이 sl_price 돌파 시 손절
    if bar_high >= pos["sl_price"]:
        exit_px = max(pos["sl_price"], bar_open)
        # Short 손익: (entry - exit) × qty
        return _close_short(pos, exit_px, "STOP_LOSS", ...)
    
    # Morning Close: 11:00 ET
    bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
    mc_minutes = self.config.gap_fade_morning_close_et[0] * 60 + \
                 self.config.gap_fade_morning_close_et[1]
    if bar_et.hour * 60 + bar_et.minute >= mc_minutes:
        return _close_short(pos, bar_open, "NOON_EXIT", ...)
    
    # TP1: 가격이 tp1_price 이하로 하락
    if not pos["gap_fade_tp1_done"] and bar_low <= pos["tp1_price"]:
        tp1_qty = max(1, int(pos["qty"] * self.config.gap_fade_tp1_qty_ratio))
        _close_short_partial(pos, tp1_qty, pos["tp1_price"], "PARTIAL_TP", ...)
        pos["gap_fade_tp1_done"] = True
        pos["partial_tp_done"]   = True
    
    # TP2: 가격이 tp2_price 이하로 하락
    if pos["gap_fade_tp1_done"] and not pos["gap_fade_tp2_done"] \
            and bar_low <= pos["tp2_price"]:
        tp2_qty = max(1, int(pos["qty"] * self.config.gap_fade_tp2_qty_ratio))
        _close_short_partial(pos, tp2_qty, pos["tp2_price"], "PARTIAL_TP", ...)
        pos["gap_fade_tp2_done"] = True
    
    # 잔여 포지션 Trailing Stop (TP2 이후)
    ...
```

### 3-5. `UniverseBacktestConfig` 신규 필드

```python
# ── 갭 페이드 전략 ─────────────────────────────────────────────────────
gap_fade_enabled:            bool  = False
gap_fade_threshold_pct:      float = 0.040    # 갭업 최소 4%
gap_fade_tp1_ratio:          float = 0.30     # 30% 되돌림 = TP1
gap_fade_tp2_ratio:          float = 0.60     # 60% 되돌림 = TP2
gap_fade_tp1_qty_ratio:      float = 0.40     # TP1 시 40% 청산
gap_fade_tp2_qty_ratio:      float = 0.30     # TP2 시 30% 청산
gap_fade_morning_close_et:   tuple = (11, 0)  # 11:00 ET
gap_fade_sl_buffer:          float = 0.001    # 첫 바 고점 + 0.1%
gap_fade_position_pct:       float = 0.10     # 기본 포지션 10%
```

### 3-6. `run_universe_backtest.py` CLI 플래그

```python
parser.add_argument("--gap-fade", action="store_true",
                    help="갭 페이드 전략 활성화 (V4와 병행 운용)")
```

메인 루프 candidate 처리 부분:

```python
result = self._try_entry(
    symbol=sym,
    day_open=day_open,
    five_min_df=five_min_df,
    capital=capital,
    n_positions=len(positions),
    atr=atr,
    prev_close=candidate.get("prev_close"),  # ← 추가
)
```

---

## 4. V4 + Gap Fade 우선순위 규칙 (재확인)

```
동일 종목, 동일 날짜에 신호 충돌 시:

첫 5분봉 close >= open (양봉)
  → V4 진입 (모멘텀 유지)

첫 5분봉 close < open (음봉)
  → Gap Fade 진입 시도
  → V4는 이미 내부에서 None 반환 (기존 코드 그대로)
  → gap_fade_enabled = True 이면 _try_entry_gap_fade() 호출
  → gap_fade_enabled = False 이면 진입 없음 (기존 동작 유지)
```

**한 종목에 V4 + Gap Fade 동시 포지션 보유 불가능**
(메인 루프의 `if any(p["symbol"] == sym for p in positions): continue` 가드가 이미 처리)

---

## 5. `_close_position()` 수정 — Short 손익 계산

현재 `_close_position()`은 Long 기준:
```python
pnl = (exit_price - entry_price) * qty - commission
```

Short 분기 추가:
```python
if pos.get("direction") == "SHORT":
    pnl = (entry_price - exit_price) * qty - commission
else:
    pnl = (exit_price - entry_price) * qty - commission
```

---

## 6. 구현 공수 및 위험도 평가

| 항목 | 공수 | 위험도 |
|------|------|--------|
| `_try_entry_gap_fade()` 신규 작성 | 소 | 낮음 |
| `UniverseBacktestConfig` 필드 추가 | 소 | 낮음 |
| `_try_entry()` prev_close 연결 | 소 | 낮음 |
| `_process_short_position_5min()` 신규 작성 | 중 | 중간 |
| `_close_position()` direction 분기 | 소 | 낮음 |
| CLI 플래그 추가 | 소 | 낮음 |
| 기존 Long 로직 영향 | **없음** | **없음** |

**기존 V4/PMS 동작에 영향 없음**: `gap_fade_enabled = False` (기본값)이면
새 코드가 일절 실행되지 않습니다. 기존 테스트 재현성 완전 보장.

---

## 7. 예상 테스트 명령어 (승인 후 실행)

```bash
# V4 단독 (기존 최선 결과 재현 확인)
python backtesting/run_universe_backtest.py \
  --pms --tier1 --gap 3.0 --v4-pullback \
  --no-morning-close --exclude TSLA \
  --start 2021-01-01

# V4 + 갭 페이드 병행 (갭 페이드 효과 측정)
python backtesting/run_universe_backtest.py \
  --pms --tier1 --gap 3.0 --v4-pullback \
  --no-morning-close --exclude TSLA \
  --gap-fade \
  --start 2021-01-01

# 전략별 PnL 비교를 위해 --deep-analysis 추가 검토 가능
```

---

## 8. 미결 사항 (퀀트 트레이더님 결정 필요)

| 번호 | 사항 | 개발팀 의견 |
|------|------|------------|
| ① | 방향: Short 시뮬레이션 vs Long 페이드 | Short 권장 (섹션 2) |
| ② | TP2 이후 잔여 30% 처리: Trailing Stop vs Morning Close 강제 | Morning Close 강제 권장 (단순) |
| ③ | Gap Fade도 Regime 필터 적용? | 미적용 권장 (P2-2 문서 원칙: 베어마켓에서 강점) |
| ④ | V4 max_positions 2개 유지? Gap Fade 포지션 포함? | 공유 한도 사용 권장 (total ≤ 2) |

---

*퀀트 트레이더님 승인 후 P2-3 구현 착수하겠습니다.*
*설계 변경 요청 사항이 있으시면 이 문서를 기준으로 피드백 주시면 반영하겠습니다.*
