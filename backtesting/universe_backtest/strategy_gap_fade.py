"""
갭 페이드 전략 (Gap Fade Strategy)
====================================
작성일: 2026-04-20
작성자: 개발 1팀 (퀀트 트레이더님 지시 P2-2)
연관 문서: NAVIS_DEV_INSTRUCTIONS.md, NAVIS_QUANT_ROADMAP.md

## 전략 개요

V4 갭 모멘텀 전략과 반대 방향의 전략.
갭업 후 첫 5분봉이 실패(음봉)할 경우 갭 되돌림(Fade)을 포착.

V4와의 상관관계가 낮아 포트폴리오 Sharpe를 높이는 보완 전략:
- V4가 수익: 갭 모멘텀 유지 국면 (양봉 지속)
- Gap Fade가 수익: 갭이 실패하는 국면 (음봉, 반전)
- 2022년 베어마켓처럼 갭이 자주 실패하는 환경에서 Gap Fade가 강점

## 진입 조건

1. 전일 종가 대비 갭업 4.0% 이상 (gap_threshold_pct = 0.040)
2. 첫 5분봉 음봉: close < open (갭 유지 실패 신호)
3. 첫 5분봉 종가 < VWAP (가격이 평균 매입 단가 아래로 회귀)
4. Regime 필터: 무관 (SPY 조건 독립)
   - 베어마켓에서 갭 실패 빈도 증가 → 오히려 강함
   - V4와 반대 특성 보유

## 청산 조건

### 목표가 (Partial TP 구조)
- TP1: 갭의 30% 되돌림 → 40% 물량 청산
  target_tp1 = prev_close + gap_size * 0.70  (= 갭의 30% 메워짐)
- TP2: 갭의 60% 되돌림 → 30% 물량 청산
  target_tp2 = prev_close + gap_size * 0.40  (= 갭의 60% 메워짐)
- 잔여 30%: Trailing Stop 또는 시간 청산

### 손절 (Stop Loss)
- 첫 5분봉 고점 + 슬리피지 (기본 0.1%)
  sl_price = first_bar_high * 1.001
- 논리: 갭 고점을 재돌파하면 갭 페이드 실패로 판단

### 시간 청산 (Morning Close)
- 11:00 ET (V4보다 1시간 빠른 청산)
- 갭 되돌림은 주로 첫 1.5시간 내에 완성되거나 포기됨

## 포지션 사이징

- 기본: 자본의 10% 고정 (V4와 동일)
- 리스크 사이징 모드: (자본 × 0.5%) / (진입가 × SL거리)
  cap = 10% (V4와 동일)

## V4와의 우선순위 규칙 (P2-3 설계 예정)

동일 종목, 동일 날짜에 두 신호가 동시 발생할 경우:
- 첫 5분봉 양봉 (close >= open) → V4 진입 (모멘텀 유지)
- 첫 5분봉 음봉 (close < open) → Gap Fade 진입 (반전)
- 한 종목에 동시 양방향 진입 절대 금지

## 백테스트 구현 계획 (P2-3 착수 후 확정)

### 새로 추가할 함수: `_try_entry_gap_fade()`

```python
def _try_entry_gap_fade(
    self,
    symbol:      str,
    prev_close:  float,   # 전일 종가 (갭 계산 기준)
    day_open:    float,   # 당일 시가
    five_min_df: pd.DataFrame,
    capital:     float,
) -> Optional[Tuple[dict, float, pd.DataFrame]]:
    # ① 갭업 확인 (4% 이상)
    gap_pct = (day_open - prev_close) / prev_close
    if gap_pct < self.config.gap_fade_threshold_pct:
        return None

    # ② 첫 5분봉 음봉 확인
    first_bar = five_min_df.iloc[0]
    if float(first_bar["close"]) >= float(first_bar["open"]):
        return None  # 양봉 → V4 영역, Gap Fade 포기

    # ③ 첫 5분봉 종가 < VWAP 확인
    vwap = _calculate_vwap(five_min_df.iloc[:1])
    if float(first_bar["close"]) >= vwap:
        return None

    # ④ 진입 (Short): 첫 5분봉 종가에서 진입
    entry_price = float(first_bar["close"])
    sl_price    = float(first_bar["high"]) * 1.001  # 첫 바 고점 + 0.1%

    # ⑤ 목표가 계산
    gap_size = day_open - prev_close
    tp1_price = prev_close + gap_size * 0.70  # 30% 되돌림
    tp2_price = prev_close + gap_size * 0.40  # 60% 되돌림

    # ⑥ R:R 검증
    sl_distance = (sl_price - entry_price) / entry_price
    tp1_distance = (entry_price - tp1_price) / entry_price
    if tp1_distance <= 0 or sl_distance <= 0:
        return None

    # ⑦ 포지션 사이징 (리스크 사이징 또는 고정 10%)
    ...
```

### UniverseBacktestConfig 추가 필드 (예정)

```python
# Gap Fade 전략 파라미터
gap_fade_enabled:          bool  = False
gap_fade_threshold_pct:    float = 0.040   # 갭업 최소 4%
gap_fade_tp1_ratio:        float = 0.30    # 갭의 30% 되돌림 = TP1
gap_fade_tp2_ratio:        float = 0.60    # 갭의 60% 되돌림 = TP2
gap_fade_morning_close_et: int   = 660     # 11:00 ET (분 단위)
gap_fade_position_pct:     float = 0.10    # 포지션 10%
```

## 예상 효과 및 가설

- V4 손실 구간(2022 베어마켓, 2024 AI 반전장)에서 갭 페이드 수익 발생
- 두 전략 합산 시 Sharpe Ratio 개선 (음의 상관관계 효과)
- 연간 거래 수: V4(35건) + Gap Fade(예상 50~80건) → 합산 85~115건

## 미결 설계 사항 (P2-3 협의 예정)

1. Short vs Long 방향
   - 갭 페이드는 하락 방향 → 현재 엔진은 Long만 지원
   - 선택 A: 엔진에 Short 포지션 지원 추가
   - 선택 B: 갭 페이드 Long 버전 (갭업 실패 → 갭 메운 후 반등 포착)
     → 진입: 갭의 50% 메워진 시점에서 Long 진입
     → 이 경우 방향성 리스크 없음 (현재 엔진 구조 유지 가능)

2. 전일 종가 데이터 제공 방식
   - 현재 엔진: screener가 gap_pct를 계산해 전달
   - Gap Fade용: prev_close를 _try_entry_gap_fade()에 전달 필요
   - screener candidate dict에 prev_close 필드 추가 검토

3. VWAP 계산 시점
   - 첫 5분봉 1개만으로 VWAP 계산 가능 여부 확인 필요
   - 대안: day_open을 VWAP 근사값으로 사용

---
*이 문서는 구현 완료 시 백테스트 결과로 업데이트됩니다.*
*P2-3 착수 전 퀀트 트레이더님 검토 및 승인 필요.*
"""

# ── Gap Fade 전략 상수 (추후 config/trading_constants.py로 이관) ──────────────

GAP_FADE_THRESHOLD_PCT    = 0.040   # 갭업 최소 4%
GAP_FADE_TP1_FADE_RATIO   = 0.30    # 갭의 30% 되돌림 = TP1 목표
GAP_FADE_TP2_FADE_RATIO   = 0.60    # 갭의 60% 되돌림 = TP2 목표
GAP_FADE_TP1_QTY_RATIO    = 0.40    # TP1 도달 시 40% 물량 청산
GAP_FADE_TP2_QTY_RATIO    = 0.30    # TP2 도달 시 30% 물량 청산
GAP_FADE_MORNING_CLOSE_ET = (11, 0) # 11:00 ET 시간 청산 (hour, minute)
GAP_FADE_SL_BUFFER        = 0.001   # 첫 바 고점 + 0.1% SL
GAP_FADE_POSITION_PCT     = 0.10    # 기본 포지션 크기: 자본의 10%
