# P21 최종 사양서 — Value Trap 차단 필터

| 항목 | 내용 |
|------|------|
| 문서 버전 | v1.0 |
| 작성일 | 2026-05-08 |
| 작성자 | 퀀트 전략팀 |
| 수신 | NAVIS 개발팀 |
| 참조 | P21_FACTOR_DIAGNOSIS_AND_P22_SPEC.md |

---

## 1. 진단 결과 확정

### 팩터 기여도 (최종 확정)

| 팩터 | 기여 | 상태 |
|------|------|------|
| Quality | +5.91%p (필수 필터) | ✅ 유지 |
| Value | +11.51%p (핵심 알파) | ✅ 유지 + 트랩 차단 |
| Momentum | +0.69%p (2022 방어 포함) | ✅ 유지 |
| Catalyst | ±0.00%p (Form4 데이터 없음) | ❌ 재배분 |

### 기각된 방향 2가지

**Regime Gate (200MA) 폐기:**
```
실험 결과: 2022 성과 -10.33% → -16.73% (오히려 악화)

원인: Quality+Value 선별이 이미 자연 방어력을 제공
      200MA 신호가 후행하여 품질 종목을 저점 매도 후 고점 재진입 유발
      → 팩터 전략에 시장 타이밍을 덧씌우는 것은 이 전략에 역효과

결론: P22 Market Regime Gate 폐기. 전략의 자연 방어력을 신뢰.
```

**Value 가중치 축소 폐기:**
```
실험 결과: Value 제거 시 CAGR 0.29%로 붕괴
           Value는 제거 대상이 아닌 핵심 알파 소스

결론: "Value가 역선택을 유발한다"는 가설 기각.
      문제는 Value 자체가 아니라 Value Trap (성장 없는 저평가주).
```

---

## 2. 근본 문제 — Value Trap 정의

반복 손실 종목: DVA, CPB, NTAP, CRL, MMM

```
공통 특성:
  - 전통 밸류에이션 지표(EV/EBITDA, P/B)로는 "저평가"로 분류
  - 그러나 ROE 저하, FCF 감소 또는 음전환 진행 중
  - 즉, "싸 보이는 이유"가 구조적 사업 악화
  - F-Score도 통과 가능 (재무 악화 초기에는 9개 항목 중 6개 이상 충족 가능)

결론: 현행 필터가 Value Trap을 걸러내지 못하고 있음
      단순 밸류에이션 지표 + F-Score 만으로는 부족
      수익성 하드 필터가 추가로 필요
```

---

## 3. P21 구현 사양 — Value Trap 차단 필터

### 3-1. 추가 필터 3종

유니버스 필터 단계(Layer 1)에 하드 컷오프로 추가합니다. 이 필터를 통과하지 못하면 팩터 점수 계산 자체를 하지 않습니다.

| 필터 | 기준 | 차단 대상 |
|------|------|---------|
| **ROE > 0** | 최근 4분기 평균 ROE 양수 | 적자 기업 및 자본 잠식 |
| **FCF/Assets > 0** | 최근 4분기 평균 양의 잉여현금흐름 | 현금 소진 기업 |
| **Debt/Equity < 3** | 부채비율 300% 미만 | 고레버리지 가치 함정 |

```python
# 추가 위치: backtesting/factor_backtest/engine.py
# _rebalance() 내 유니버스 필터링 단계

def passes_value_trap_filter(fundamentals) -> bool:
    """
    Value Trap 사전 차단 하드 필터.
    세 조건 모두 충족해야 True.
    """
    roe     = fundamentals.get("roe_ttm")       # TTM ROE
    fcf_a   = fundamentals.get("fcf_to_assets") # FCF / Total Assets
    de      = fundamentals.get("debt_to_equity")# Total Debt / Equity

    if roe   is None or roe   <= 0:   return False
    if fcf_a is None or fcf_a <= 0:   return False
    if de    is None or de    >= 3.0: return False
    return True
```

**DVA, CPB, NTAP, CRL, MMM 각 필터 적용 결과 확인 후 보고서에 포함하십시오.**

### 3-2. 예상 유니버스 변화

```
현재 유니버스:         ~1,800종목 (Layer 1 통과 기준)
필터 추가 후 예상:     ~1,300~1,500종목 (약 15~25% 감소)
top_pct=10% 적용 시:  ~130~150종목 후보 → 상위 40~60종목 편입
```

유니버스가 너무 작아지면 `top_pct`를 10% → 15%로 조정하십시오. 단, 편입 종목 수가 40종목 미만이 되면 분산 부족으로 개별 종목 리스크가 커집니다.

---

## 4. Catalyst 팩터 재배분

### 4-1. 현황

Catalyst(내부자 매수)는 Form4 데이터 부재로 기여가 ±0.00%p입니다. 15점이 공전 중입니다.

### 4-2. 재배분 결정

Catalyst 15점을 Quality로 전량 이전합니다.

```
변경 전: Quality 35 + Value 25 + Momentum 25 + Catalyst 15 = 100점
변경 후: Quality 50 + Value 25 + Momentum 25 + Catalyst  0 = 100점
```

**이유:**

```
1. Quality가 가장 신뢰할 수 있는 데이터 기반 신호
   (재무제표 데이터는 완전하고 편향이 없음)

2. Quality 50점으로 강화하면 Value Trap 필터와 시너지
   - 하드 필터(ROE>0, FCF>0)로 1차 차단
   - Quality 소프트 스코어(50점)로 2차 정렬
   → 수익성 상위 종목에 집중도 강화

3. Catalyst는 Form4 클린 데이터 확보 후 별도 복원 가능
   (현재 0점이므로 복원 시 추가 알파)
```

### 4-3. 변경된 Score 구성

```python
# 변경 후 composite score 계산
def calc_composite_score(quality, value, momentum):
    """
    Catalyst 제거, Quality 강화 버전.
    quality:  0~50점 (기존 0~35에서 확장)
    value:    0~25점 (변동 없음)
    momentum: 0~25점 (변동 없음)
    """
    return quality + value + momentum  # 0~100점

# Quality Score 재산출 (배점 재분배)
def calc_quality_score_v2(fundamentals, sector_peers):
    f_score_pts  = (fundamentals.f_score / 9) * 20   # 15 → 20점
    roe_pts      = percentile_rank(fundamentals.roe, sector_peers.roe) * 12    # 8 → 12점
    fcf_pts      = percentile_rank(fundamentals.fcf_yield, sector_peers.fcf_yield) * 10  # 7 → 10점
    accruals_pct = 1 - percentile_rank(fundamentals.accruals, sector_peers.accruals)
    accruals_pts = accruals_pct * 8   # 5 → 8점
    return f_score_pts + roe_pts + fcf_pts + accruals_pts  # 0~50점
```

---

## 5. P21 백테스트 실행 순서

```
Step 1: Value Trap 필터만 추가 (Catalyst 재배분 없이)
        → 필터 단독 기여도 측정
        목표: DVA, CPB, NTAP, CRL, MMM 제외 확인 + CAGR 변화 측정

Step 2: Catalyst → Quality 재배분 추가
        → 두 변경 합산 효과 측정
        최종 P21 성과 확정

비교 기준 (P19 클린): CAGR 11.80%, Sharpe 0.647, MDD -20.19%
```

---

## 6. P21 합격 기준

| KPI | 합격 기준 | P19 클린 베이스 |
|-----|---------|--------------|
| CAGR | **≥ 13.5%** | 11.80% |
| Sharpe | ≥ 0.70 | 0.647 |
| MDD | ≤ 19% | -20.19% |
| DVA/CPB/NTAP/CRL/MMM 제외 | 확인 | 포함 중 |

> Value Trap 필터 단독으로 +1.5~2.5%p 기여가 예상됩니다.
> Catalyst 재배분으로 추가 +0.2~0.8%p 기여가 예상됩니다.
> 합산 시 CAGR 13.5~14.5% 범위가 합격 기준입니다.

---

## 7. 이후 갭 해소 경로 (수정)

P22 Regime Gate가 폐기되었으므로 갭 해소 경로를 수정합니다.

| 경로 | 기대 기여 | 단계 |
|------|---------|------|
| Value Trap 필터 | +1.5~2.5%p | P21 |
| Catalyst → Quality 재배분 | +0.2~0.8%p | P21 |
| 10년 데이터 확보 후 재측정 | +1.5~3.0%p | 데이터 확장 |
| Catalyst 복원 (Form4 클린) | +0.5~1.5%p | 미래 과제 |
| **합계 (보수적)** | **15.5%** | |
| **합계 (낙관적)** | **18.6%** | |

> 10년 데이터(2016~2019 포함)가 가장 큰 단일 변수입니다.
> 2016~2019는 Value 팩터 알파가 현 기간보다 강했던 구간으로, 10년 CAGR은 현재 5.7년 수치보다 높을 가능성이 큽니다.

---

## 8. 전체 진행 현황 (수정)

| 단계 | 내용 | 상태 |
|------|------|------|
| P19 | Multi-Factor Scoring | ✅ 완료 (CAGR 11.80%) |
| P20 | PEAD 인프라 | ✅ 완료 (기여 없음) |
| P21 팩터 진단 | 팩터 제거 실험 4종 | ✅ 완료 |
| **P21 최종** | **Value Trap 필터 + Catalyst 재배분** | **🔄 즉시 착수** |
| P22 | ~~Market Regime Gate~~ | ❌ 폐기 (역효과 확인) |
| P22 (신규) | Walk-Forward + 데이터 확장 | ⏳ P21 완료 후 |
| 데이터 확장 | 일봉 2016년 소급 | 🔄 최우선 병행 |

---

*문서 종료 | P21 최종 사양서 v1.0*
*작성: 퀀트 전략팀 | 수신: NAVIS 개발팀 | 2026-05-08*
