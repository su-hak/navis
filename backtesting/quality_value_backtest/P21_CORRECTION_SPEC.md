# P21 수정 지시서 — 방향 교정

| 항목 | 내용 |
|------|------|
| 문서 버전 | v1.0 |
| 작성일 | 2026-05-08 |
| 작성자 | 퀀트 전략팀 |
| 수신 | NAVIS 개발팀 |
| 참조 | P21_FINAL_SPEC.md |

---

## 1. 무엇이 잘못됐나

격리 실험으로 P21_FINAL_SPEC의 두 가지 지시가 역효과임이 확인되었습니다.

### 오류 1 — Catalyst를 Quality로 재배분한 것

```
지시했던 방향:  Quality 35pt → 50pt (Catalyst 15pt 흡수)
실제 효과:     -2.82%p CAGR (P19 베이스라인 대비)

원인:
  팩터 제거 실험 확인값 — Value 기여: +11.51%p (1위)
  Catalyst=0인 상태에서 유효 총점은 이미 85점
  Quality를 50으로 올리면 Value의 실효 비중이:
    35/85 = 41.2% → 25/100 = 25.0% (▼16.2%p 감소)
  최대 알파 소스인 Value를 희석한 것이 원인
```

### 오류 2 — TTM 기준 하드 필터

```
지시했던 방향:  ROE > 0, FCF/Assets > 0 (TTM 기준)
실제 효과:     -1.96%p CAGR

원인:
  COVID 직후(2020 Q2~Q3) 항공·호텔·레저·에너지 등
  일시적 TTM 적자 경기순환주를 2020~2021 반등 직전에 필터 아웃
  → 이후 이들 종목의 300~500% 상승을 전부 누락
  Value Trap(DVA, CPB, MMM 같은 구조적 하락)과
  Cyclical Trough(일시적 적자 후 강력 반등)를 동일하게 처리한 것이 오류
```

---

## 2. 수정 방향

### 수정 1 — Catalyst 15pt를 Value로 재배분

```
변경 전 (P21_FINAL_SPEC):
  Quality 50 + Value 25 + Momentum 25 + Catalyst 0 = 100

변경 후 (본 문서):
  Quality 35 + Value 40 + Momentum 25 + Catalyst 0 = 100
```

**근거:** 팩터 제거 실험에서 Value가 +11.51%p로 입증된 1위 알파 소스입니다. 유일하게 검증된 팩터를 강화하는 것이 올바른 방향입니다.

```python
# 변경 후 composite score 계산
def calc_composite_score(quality, value, momentum):
    """
    quality:  0~35점  (기존 P19 그대로)
    value:    0~40점  (25 → 40으로 상향)
    momentum: 0~25점  (기존 그대로)
    """
    return quality + value + momentum  # 0~100점

# Value Score 재산출 — 배점만 변경, 계산 로직 동일
def calc_value_score_v2(fundamentals, sector_peers):
    ev_ebitda_pct = 1 - percentile_rank(fundamentals.ev_ebitda, sector_peers.ev_ebitda)
    pfcf_pct      = 1 - percentile_rank(fundamentals.p_fcf,    sector_peers.p_fcf)
    pb_pct        = 1 - percentile_rank(fundamentals.p_b,      sector_peers.p_b)

    # 배점 비율 유지하며 40점 만점으로 스케일
    return (ev_ebitda_pct * 0.48 + pfcf_pct * 0.32 + pb_pct * 0.20) * 40
    #       기존 12/25=0.48      기존 8/25=0.32    기존 5/25=0.20
```

### 수정 2 — TTM → 2년 평균 + 경기순환 허용 임계값

Value Trap(구조적 하락)과 Cyclical Trough(일시적 저점)를 분리합니다.

```python
# 수정된 Value Trap 하드 필터

CYCLICAL_SECTORS = {
    "Airlines", "Hotels & Resorts", "Oil & Gas", "Metals & Mining",
    "Leisure", "Retail - Specialty"
}

def passes_value_trap_filter(fundamentals, sector: str) -> bool:
    """
    일반 섹터: 2년 평균 ROE > -0.02 (소폭 일시 적자 허용)
    경기순환 섹터: 2년 평균 ROE > -0.10 (더 큰 일시 적자 허용)
    FCF: 2년 평균 기준 동일 적용
    """
    roe_2yr = fundamentals.get("roe_2yr_avg")    # 2년 평균 ROE
    fcf_2yr = fundamentals.get("fcf_assets_2yr") # 2년 평균 FCF/Assets
    de      = fundamentals.get("debt_to_equity")

    if roe_2yr is None or fcf_2yr is None or de is None:
        return True  # 데이터 없으면 통과 (보수적으로 제외 안 함)

    # 부채비율은 섹터 구분 없이 동일 적용
    if de >= 3.0:
        return False

    # 수익성 임계값: 경기순환 섹터에 더 넓은 허용 범위
    if sector in CYCLICAL_SECTORS:
        roe_threshold = -0.10
        fcf_threshold = -0.05
    else:
        roe_threshold = -0.02
        fcf_threshold = -0.02

    if roe_2yr < roe_threshold: return False
    if fcf_2yr < fcf_threshold: return False
    return True
```

**핵심 변화:**

| 항목 | P21_FINAL_SPEC (오류) | 본 문서 (수정) |
|------|---------------------|-------------|
| 기준 기간 | TTM (1년) | 2년 평균 |
| 일반 섹터 ROE | > 0 | > -0.02 |
| 경기순환 섹터 ROE | > 0 (동일) | > -0.10 |
| FCF 기준 | TTM > 0 | 2년 평균 > -0.02 / -0.05 |

---

## 3. 격리 실험 재실행 순서

두 수정을 격리하여 각각의 기여도를 확인하십시오.

```
Step 1: Value 40pt만 적용 (하드 필터 없음, P19 기준선과 비교)
        예상: 소폭 CAGR 개선 (+0.3~0.8%p)

Step 2: 수정된 하드 필터만 적용 (Value 25pt 그대로, 2년 평균 기준)
        예상: 2022 개선 유지, 2020 회복 (+0.5~1.5%p)
        DVA, CPB, MMM 제외 유지 확인 필수

Step 3: 두 수정 합산 (P21 최종)
        목표: CAGR ≥ 13.0%
```

---

## 4. P21 수정 합격 기준

| KPI | 합격 기준 | P19 베이스 |
|-----|---------|----------|
| CAGR | **≥ 13.0%** | 11.80% |
| 2022 손실 | **> -9%** | 약 -10.33% |
| 2020 수익 | P19 수준 유지 | 확인 필요 |
| DVA/CPB/MMM | 포트폴리오 제외 확인 | 포함 중 |
| Sharpe | ≥ 0.68 | 0.647 |

---

## 5. P21 이후 경로 정리

P22 Regime Gate가 폐기된 상황에서 이후 경로는 다음과 같습니다.

| 단계 | 내용 | 기대 기여 |
|------|------|---------|
| P21 (본 문서) | Value 40pt + 수정 하드 필터 | +1.0~2.0%p |
| 데이터 확장 | 일봉 2016~2019 소급 | +1.5~3.0%p (Value 알파 강했던 구간) |
| Walk-Forward | P23 최종 검증 | 검증 |
| Catalyst 복원 | Form4 클린 데이터 확보 시 | +0.5~1.5%p |

---

*문서 종료 | P21 수정 지시서 v1.0*
*작성: 퀀트 전략팀 | 수신: NAVIS 개발팀 | 2026-05-08*
