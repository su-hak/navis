# P20 최종 검토 및 P21 개발 지시서

| 항목 | 내용 |
|------|------|
| 문서 버전 | v1.0 |
| 작성일 | 2026-05-07 |
| 작성자 | 퀀트 전략팀 |
| 수신 | NAVIS 개발팀 |
| 참조 | NAVIS_ALPHA_V1_STRATEGY_SPEC.md, P20_REVIEW_AND_P21_SPEC.md |

---

## 1. P20 공식 판정

### 판정: ✅ 조건부 합격

KPI 수치는 목표에 미달했으나, 미달 원인이 전략 결함이 아닌 **데이터 기간 제약**임을 확인했습니다. 인프라 완성도와 신호 방향성 기준으로 합격 처리합니다.

| KPI | 목표 | P19 | P20 | 변화 | 판정 |
|-----|------|-----|-----|------|------|
| CAGR | ≥ 17.5% | 15.50% | 15.78% | +0.28%p | ⚠️ 미달 |
| SPY 초과수익 | ≥ +3.0%p | +0.93%p | +1.21%p | +0.28%p | ⚠️ 미달 |
| Sharpe | ≥ 0.80 | 0.815 | 0.821 | +0.006 | ✅ |
| MaxDD | ≤ 21% | -20.97% | -19.28% | +1.69%p 개선 | ✅ |
| PEAD 인프라 | 완성 | — | ✅ 완성 | — | ✅ |
| 컨센서스 커버리지 | ≥ 60% | — | 99.8% | — | ✅ |

**확정 파라미터:**

| 파라미터 | 확정값 |
|---------|--------|
| `pead_lookback` | 45일 |
| `min_surprise_pct` | 3% |
| `min_n_analysts` | 2 |

---

## 2. 성과 분석

### 2-1. PEAD 기여도 평가

PEAD 활성화로 CAGR +0.28%p, MaxDD +1.69%p 개선이 확인되었습니다. 방향은 맞습니다. 그러나 기대했던 +2~4%p에 비해 기여가 작습니다.

**원인 분석:**

```
원인 1 (주요): 백테스트 기간이 5.7년으로 짧음
  PEAD는 시장 사이클 전반에 걸쳐 작동하는 팩터
  5.7년 샘플로는 통계적 유의성이 낮음
  → 2016~2019 데이터 확보 후 10년 백테스트에서 기여도 재평가 필요

원인 2 (구조적): S&P 500(481종목) 외 중소형주 미적용
  현재 포트폴리오에서 PEAD 점수를 받는 종목이 제한적
  → 어닝 서프라이즈 알파는 중소형주에서 더 강하게 나타남 (학계 공통 발견)
  → 전체 유니버스 2,052종목으로 PEAD 확대 시 기여도 증가 예상
```

### 2-2. 2023년 PEAD 약화 현상 — 모니터링 항목 등록

```
P19 2023 수익률: +32.85%
P20 2023 수익률: +23.85%  ← -9.00%p 감소
```

이것은 전략 결함이 아닙니다. 2023년은 매그니피센트 7(AAPL, MSFT, NVDA 등 7개 종목)이 S&P 500 수익률의 대부분을 설명한 특수한 해입니다. 이 종목들은 어닝 서프라이즈보다 AI 내러티브 프리미엄으로 상승했으며, PEAD 팩터가 이들을 과소평가하는 방향으로 작용했습니다.

```
영향: PEAD 점수가 낮은 대형 테크주 비중 감소
      → 2023 랠리에서 소외
결론: 2023 특수 현상으로 판단, 단일 연도로 PEAD를 폐기하지 않음
모니터링: 2024~2025에서도 동일 패턴이 반복되면 PEAD 가중치 재조정 검토
```

### 2-3. 누적 갭 분석

목표 CAGR 18% 대비 현재 15.78%의 갭 +2.22%p는 다음 단계에서 해소됩니다.

| 갭 해소 경로 | 기대 기여 | 단계 |
|------------|---------|------|
| ATR 동적 손절 (STOP_LOSS 40%→25%) | +1.5~2.5%p | P21 |
| Market Regime Gate (2022 손실 완화) | +0.5~1.0%p | P22 |
| 10년 데이터 확보 후 PEAD 재측정 | +0.5~1.5%p | 데이터 확장 |
| **합계** | **+2.5~5.0%p** | P23 최종 |

현재 경로는 정상입니다. P21 완료가 갭 해소의 핵심입니다.

---

## 3. P21 개발 지시서 — ATR 기반 Dynamic Risk Engine

### 3-1. 우선순위 근거

P18부터 일관되게 확인된 병목은 **STOP_LOSS 비율 40%** 입니다. 진입 포지션의 40%가 -15% 손절로 종료되면서 수익 포지션의 알파를 상쇄합니다. ATR 기반 손절로 교체하면 이 비율이 25% 수준으로 낮아질 것으로 예상하며, 이것이 CAGR에 직접적으로 +1.5~2.5%p 기여합니다.

### 3-2. 합격 기준

| KPI | 합격 기준 | 현재 (P20) |
|-----|---------|-----------|
| MDD | **< 18%** | -19.28% |
| STOP_LOSS 비율 | **< 30%** | ~40% |
| CAGR | ≥ 15.5% 유지 | 15.78% |
| Sharpe | ≥ 0.80 유지 | 0.821 |

### 3-3. 구현 사양

#### (A) ATR 계산

```python
# 추가 위치: backtesting/factor_backtest/factor_calculator.py
# (기존 calc_momentum_12_1, calc_avg_dollar_volume과 동일 파일)

def calc_atr(daily_df: pd.DataFrame, as_of_date, period: int = 14) -> Optional[float]:
    """
    14거래일 Average True Range.
    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    """
    if as_of_date not in daily_df.index:
        loc = daily_df.index.searchsorted(as_of_date, side="right") - 1
        if loc < 0:
            return None
        idx = loc
    else:
        idx = daily_df.index.get_loc(as_of_date)

    if idx < period + 1:
        return None

    window = daily_df.iloc[idx - period : idx]
    prev   = daily_df.iloc[idx - period - 1 : idx - 1]

    tr = pd.DataFrame({
        "hl":  window["high"].values - window["low"].values,
        "hpc": abs(window["high"].values - prev["close"].values),
        "lpc": abs(window["low"].values  - prev["close"].values),
    }).max(axis=1)

    return float(tr.mean())
```

#### (B) 손절/익절 산출

```python
# 파라미터 (확정값 — 튜닝 범위는 3-3-(E) 참조)
STOP_ATR_MULT   = 2.5   # 손절 = 진입가 - ATR × 2.5
PROFIT_ATR_MULT = 6.0   # 익절 = 진입가 + ATR × 6.0  (RRR 2.4:1)
MAX_ATR_RATIO   = 0.05  # ATR/진입가 > 5% → 진입 거부

def calc_atr_stops(
    entry_price: float,
    atr: float,
) -> tuple[Optional[float], Optional[float]]:
    """
    반환: (stop_loss_price, take_profit_price)
    (None, None) 반환 시 엔진에서 해당 종목 진입 스킵.
    """
    if atr is None or entry_price <= 0:
        return None, None
    if atr / entry_price > MAX_ATR_RATIO:
        return None, None  # 과고변동 종목 차단

    return (
        entry_price - atr * STOP_ATR_MULT,
        entry_price + atr * PROFIT_ATR_MULT,
    )
```

**종목 유형별 적용 예시:**

| 종목 유형 | ATR/주가 | 기존 손절 | ATR 손절 |
|---------|---------|---------|---------|
| 대형 우량주 | 1.2% | -15.0% | -3.0% |
| 중형 성장주 | 2.5% | -15.0% | -6.3% |
| 고변동 소형주 | 5.5% | -15.0% | 진입 거부 |

#### (C) 트레일링 스탑

```python
TRAILING_ACTIVATE_PCT = 0.15   # +15% 수익 시 활성화
TRAILING_DRAWDOWN_PCT = 0.10   # 활성화 후 고점 대비 -10% 하락 시 청산

def update_trailing_stop(position: dict, current_price: float) -> bool:
    """True 반환 시 즉시 청산. position에 'peak_price' 필드 필요."""
    pnl_pct = (current_price - position["entry_price"]) / position["entry_price"]
    if pnl_pct < TRAILING_ACTIVATE_PCT:
        return False

    position["peak_price"] = max(position.get("peak_price", position["entry_price"]), current_price)
    return current_price < position["peak_price"] * (1 - TRAILING_DRAWDOWN_PCT)
```

#### (D) 포트폴리오 변동성 타겟팅

```python
SCALE_DOWN_THRESHOLD = 0.18   # 실현 변동성(연) > 18% → 종목 수 축소
SCALE_UP_THRESHOLD   = 0.12   # 실현 변동성(연) < 12% → 종목 수 확대

def adjust_target_holdings(current: int, realized_vol: float) -> int:
    """월 1회 호출. 목표 보유 종목 수 반환."""
    if realized_vol > SCALE_DOWN_THRESHOLD:
        return max(25, int(current * 0.80))
    if realized_vol < SCALE_UP_THRESHOLD:
        return min(60, int(current * 1.10))
    return current
```

#### (E) 백테스트 파라미터 탐색 범위

| 파라미터 | 탐색 범위 | 기본값 |
|---------|---------|--------|
| `STOP_ATR_MULT` | 2.0, 2.5, 3.0 | 2.5 |
| `PROFIT_ATR_MULT` | 5.0, 6.0, 7.0 | 6.0 |
| `MAX_ATR_RATIO` | 0.04, 0.05, 0.06 | 0.05 |
| `TRAILING_ACTIVATE_PCT` | 0.12, 0.15, 0.20 | 0.15 |

**과최적화 방지 규칙:** 2020~2023 In-Sample 최적값을 2024~2026 Out-of-Sample에 그대로 적용하여 성과 열화 여부를 반드시 확인하십시오.

### 3-4. 엔진 수정 포인트

`backtesting/factor_backtest/engine.py`의 `_rebalance()` 메서드를 수정합니다.

```
변경 전: 고정 stop_loss = entry_price * (1 - 0.15)

변경 후:
  진입 시:
    1. calc_atr(daily_df, exec_date) 호출
    2. calc_atr_stops(entry_price, atr) 호출
    3. 반환값 (None, None) → 해당 종목 진입 스킵
    4. portfolio[sym]에 'stop_price', 'profit_price', 'peak_price' 추가

  일별 가격 체크 루프 (신규 추가):
    5. current_price ≤ stop_price  → 즉시 청산
    6. current_price ≥ profit_price → 즉시 청산
    7. update_trailing_stop() → True 반환 시 즉시 청산

  월말:
    8. adjust_target_holdings() → 다음 달 목표 종목 수 갱신
```

### 3-5. 보고서 포함 항목

P21 보고서 제출 시 다음을 반드시 포함하십시오.

```
1. STOP_LOSS 비율 변화
   P20: ~40%  →  P21: ?%

2. 연도별 수익률 (2020~2026)
   특히 2022년(베어마켓) 손실 수치

3. ATR 진입 거부 비율
   전체 신호 대비 MAX_ATR_RATIO 초과로 거부된 종목 수 비율

4. 최적 파라미터 조합
   In-Sample 최적값 및 Out-of-Sample 검증 결과

5. 트레일링 스탑 기여도
   트레일링 스탑 미적용 vs 적용 CAGR 비교
```

---

## 4. 병행 작업 — 일봉 데이터 소급 수집

P21 진행 중 별도 인력 가용 시 계속 병행하십시오. P23 Walk-Forward 신뢰도와 PEAD 기여도 재평가에 필요합니다.

```
목표:     일봉 캐시 2020-07 → 2016-01로 확장
우선 대상: 최근 6개월 포트폴리오 편입 이력 종목
완료 기한: P23 시작 전 (Week 7 이전)
```

---

## 5. 전체 진행 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| P19 | Multi-Factor Scoring | ✅ 완료 |
| P20 | PEAD + EarningsCache | ✅ 완료 (조건부 합격) |
| **P21** | **ATR Dynamic Risk Engine** | **🔄 즉시 착수** |
| P22 | Market Regime Gate | ⏳ 대기 |
| P23 | Walk-Forward 최종 검증 | ⏳ 대기 |
| 데이터 확장 | 일봉 2016년 소급 | 🔄 병행 진행 |

---

*문서 종료 | P20 최종 검토 및 P21 개발 지시서 v1.0*
*작성: 퀀트 전략팀 | 수신: NAVIS 개발팀 | 2026-05-07*
