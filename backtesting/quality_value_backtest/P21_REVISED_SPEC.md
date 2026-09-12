# P21 수정 사양서 — 변동성 패리티 포지션 사이징

| 항목 | 내용 |
|------|------|
| 문서 버전 | v1.0 |
| 작성일 | 2026-05-08 |
| 작성자 | 퀀트 전략팀 |
| 수신 | NAVIS 개발팀 |
| 참조 | P20_FINAL_REVIEW_AND_P21_SPEC.md |

---

## 1. 상황 재정리 — 전달 필수

### 1-1. 실제 베이스라인 수정

이번 P21 작업 중 P19/P20 결과에 lookahead bias가 포함되어 있었음이 확인되었습니다.
팀 전체가 이 수치를 기준으로 작업해야 합니다.

| 구분 | 기존 인식 | 실제 수정값 |
|------|---------|-----------|
| P19 CAGR | 15.50% | 미확인 (재실행 필요) |
| P20 CAGR | 15.78% | **11.62%** |
| 목표 CAGR | 18.00% | 18.00% (변동 없음) |
| 달성 갭 | +2.22%p | **+6.38%p** |

**원인:** yfinance 컨센서스 EPS가 사후 업데이트된 수치를 반영하여 PEAD 팩터에 lookahead bias 유입.

### 1-2. 병행 필요 작업 — P19 클린 재실행

P21과 별개로, PEAD를 비활성화한 상태에서 P19(Multi-Factor Score만)를 재실행하여 진짜 Multi-Factor 기여도를 측정해야 합니다. 이것이 없으면 이후 모든 수치의 기준이 불명확합니다.

```
실행 조건: PEAD 점수 = 0으로 고정 (calc_pead_score 비활성)
목적:      lookahead bias 없는 Multi-Factor 순수 기여도 확인
우선순위:  P21과 병행 (블로킹 아님)
```

---

## 2. P21 방향 수정 — ATR 스탑 → 변동성 패리티

### 2-1. ATR 스탑 폐기 이유

ATR 손절이 월간 리밸런싱 전략에 해로운 구조적 이유:

```
문제 1: 시간 척도 불일치
  일봉 ATR×15 ≈ 월간 자연 변동폭
  → 손절이 의미 있는 리스크 신호가 아닌 노이즈 반응

문제 2: Winner 조기 청산
  팩터 알파의 핵심은 우량주가 수개월에 걸쳐 복리로 상승하는 것
  ATR 스탑은 이 과정을 중단시킴

문제 3: 베어마켓 역효과
  2022: 스탑 청산 후 비슷한 가격에 재진입 → 거래 비용만 발생

결론: ATR 스탑은 일중·일간 전략에 적합, 월간 전략에는 부적합
```

### 2-2. 변동성 패리티 채택 이유

```
원리: 각 포지션의 "위험 기여도"를 균등하게 만들어 포트폴리오 구성
      저변동 종목 → 더 큰 비중 (위험이 작으므로 더 담아도 됨)
      고변동 종목 → 더 작은 비중 (위험이 크므로 조금만 담음)

기대 효과:
  MDD 개선: 고변동 종목의 급락이 포트폴리오에 미치는 충격 감소
  CAGR 유지: Winner를 청산하지 않으므로 팩터 알파 보호
  샤프 개선: 동일 기대수익에서 변동성 감소
```

---

## 3. 구현 사양

### 3-1. ATR 기반 포지션 가중치 계산

```python
# 추가 위치: backtesting/factor_backtest/factor_calculator.py

def calc_vol_parity_weights(
    symbols: list[str],
    daily_data: dict,
    as_of_date,
    atr_period: int = 21,
    min_weight: float = 0.005,   # 최소 비중 0.5%
    max_weight: float = 0.10,    # 최대 비중 10%
) -> dict[str, float]:
    """
    변동성 패리티 가중치 계산.
    각 종목의 가중치 = (1 / ATR_pct) 정규화
    ATR_pct = ATR / 현재가 (비율 기준 변동성)

    반환: {symbol: weight} 합계 = 1.0
    """
    raw_weights = {}
    for sym in symbols:
        df = daily_data.get(sym)
        if df is None:
            continue
        atr = calc_atr(df, as_of_date, period=atr_period)
        price = _get_close(df, as_of_date)
        if atr is None or price is None or price <= 0:
            continue
        atr_pct = atr / price
        if atr_pct <= 0:
            continue
        raw_weights[sym] = 1.0 / atr_pct  # 변동성 역수

    if not raw_weights:
        return {sym: 1.0 / len(symbols) for sym in symbols}  # fallback: 동일비중

    total = sum(raw_weights.values())
    weights = {sym: w / total for sym, w in raw_weights.items()}

    # 비중 상하한 클리핑 후 재정규화
    weights = {sym: max(min_weight, min(max_weight, w)) for sym, w in weights.items()}
    total = sum(weights.values())
    return {sym: w / total for sym, w in weights.items()}
```

### 3-2. ATR 진입 거부 필터 유지

기존에 구현된 `MAX_ATR_RATIO` 필터는 유지합니다. 이것은 과고변동 종목 자체를 제외하는 별개의 로직입니다.

```python
MAX_ATR_RATIO = 0.05   # ATR/주가 > 5% 종목은 유니버스에서 제외

# 변동성 패리티 계산 전에 적용
eligible = [sym for sym in candidates if atr_ratio(sym) <= MAX_ATR_RATIO]
weights  = calc_vol_parity_weights(eligible, daily_data, rebalance_date)
```

### 3-3. 엔진 수정 포인트

`backtesting/factor_backtest/engine.py`의 `_rebalance()` 메서드를 수정합니다.

```
변경 전:
  per_position = total_equity / n_target  # 동일 비중
  target_qty   = int(per_position / entry_price)

변경 후:
  weights    = calc_vol_parity_weights(target_symbols, daily_data, rebalance_date)
  per_symbol = {sym: total_equity * w for sym, w in weights.items()}
  target_qty = int(per_symbol[sym] / entry_price)
```

손절/익절 로직은 기존 그대로 유지합니다 (스탑이 없는 구조였으므로 변경 없음).

### 3-4. 파라미터 탐색 범위

| 파라미터 | 탐색 범위 | 기본값 |
|---------|---------|--------|
| `atr_period` | 14, 21, 42 | 21 |
| `max_weight` | 0.08, 0.10, 0.15 | 0.10 |
| `MAX_ATR_RATIO` | 0.04, 0.05, 0.06 | 0.05 |

---

## 4. 합격 기준

실제 베이스라인(11.62%)을 기준으로 합격 기준을 재설정합니다.

| KPI | 합격 기준 | 실제 베이스라인 |
|-----|---------|--------------|
| CAGR | ≥ 12.5% | 11.62% |
| Sharpe | ≥ 0.70 | 0.662 |
| MDD | < 18% | -19.96% |
| 동일비중 대비 Sharpe | 개선 | 기준 |

> CAGR 목표를 18%로 유지하되, P21 단계의 합격 기준은 12.5%로 설정합니다.
> 나머지 갭(+5.5%p)은 P22(레짐 게이트) + 데이터 확장 + PEAD 재검증으로 해소합니다.

---

## 5. P21 보고서 포함 항목

```
1. 변동성 패리티 vs 동일 비중 성과 비교
   CAGR, Sharpe, MDD 각각 명시

2. 연도별 수익률 (2020~2026 전체)

3. 포지션 가중치 분포
   평균 최대 비중, 평균 최소 비중, 비중 표준편차

4. P19 클린 재실행 결과 (병행 작업)
   PEAD 비활성 상태의 순수 Multi-Factor CAGR
```

---

## 6. 전체 진행 현황 및 갭 해소 경로

| 단계 | 기대 CAGR 기여 | 상태 |
|------|-------------|------|
| 실제 베이스라인 | 11.62% | 확인 완료 |
| P21 변동성 패리티 | +0.5~1.5%p | 🔄 즉시 착수 |
| P22 Market Regime Gate | +1.0~2.0%p | ⏳ 대기 |
| PEAD 클린 재검증 | +0.5~1.5%p | ⏳ P19 재실행 후 |
| 10년 데이터 확장 | +0.5~1.0%p | 🔄 병행 |
| **합계 (보수적)** | **14.12%** | |
| **합계 (낙관적)** | **17.62%** | |

> 목표 CAGR 18%는 낙관적 시나리오의 상단입니다.
> P22까지 완료한 후 수치를 보고 목표 현실성을 재평가합니다.

---

*문서 종료 | P21 수정 사양서 v1.0*
*작성: 퀀트 전략팀 | 수신: NAVIS 개발팀 | 2026-05-08*
