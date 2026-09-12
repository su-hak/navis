# P20 PEAD 무료 활성화 방안

| 항목 | 내용 |
|------|------|
| 문서 버전 | v1.0 |
| 작성일 | 2026-05-07 |
| 작성자 | 퀀트 전략팀 |
| 수신 | NAVIS 개발팀 |
| 목적 | 유료 데이터 없이 PEAD 팩터 활성화 |

---

## 결론 먼저

**유료 결제 없이 진행 가능합니다.**

두 가지 무료 경로가 있으며, 순서대로 시도하십시오.

```
1순위: yfinance 무료 컨센서스 EPS 수집 시도 (1~2일)
       → 커버리지가 충분하면 PEAD 즉시 활성화, 종결

2순위: YoY EPS 성장률 기반 PEAD 프록시 (2~3일)
       → Polygon 실제 EPS만으로 PEAD 근사 계산
       → 유료 데이터 없이 백테스트 완료 가능

유료 소스(FMP $14)는 위 두 방법 모두 불충분할 때 검토합니다.
```

---

## 방법 1 — yfinance 무료 컨센서스 EPS (1순위)

### 원리

yfinance의 `get_earnings_dates()` 메서드는 Yahoo Finance 어닝 캘린더 데이터를 반환하며, 여기에 **EPS Estimate(컨센서스)** 와 **Reported EPS(실제)** 가 함께 포함됩니다. 이미 보유한 Polygon 실제 EPS와 별개로, 이 메서드 하나로 두 값을 모두 무료로 얻을 수 있습니다.

### 테스트 코드

먼저 샘플 종목 10개로 커버리지를 확인하십시오.

```python
import yfinance as yf
import pandas as pd

TEST_SYMBOLS = ["AAPL", "MSFT", "NVDA", "JPM", "XOM",
                "WMT", "BA", "INTC", "PFE", "KO"]

results = []
for sym in TEST_SYMBOLS:
    try:
        df = yf.Ticker(sym).get_earnings_dates(limit=20)
        if df is None or df.empty:
            results.append({"symbol": sym, "rows": 0, "has_estimate": False})
            continue
        has_est = "EPS Estimate" in df.columns and df["EPS Estimate"].notna().any()
        results.append({
            "symbol":       sym,
            "rows":         len(df),
            "has_estimate": has_est,
            "date_range":   f"{df.index.min().date()} ~ {df.index.max().date()}"
        })
    except Exception as e:
        results.append({"symbol": sym, "rows": 0, "error": str(e)})

print(pd.DataFrame(results).to_string())
```

### 판단 기준

```
rows ≥ 8 (2년치 분기) AND has_estimate = True 비율이 70% 이상
→ yfinance로 진행 가능, 방법 2 불필요

비율이 70% 미만
→ 방법 2(YoY 프록시)로 전환
```

### EarningsCache 연동

커버리지 확인 후 yfinance 수집기를 EarningsCache에 추가하십시오.

```python
def collect_from_yfinance(symbol: str) -> list[dict]:
    """
    yfinance에서 historical 어닝 데이터 수집.
    EarningsCache 저장 스키마에 맞게 변환.
    """
    df = yf.Ticker(symbol).get_earnings_dates(limit=40)  # 약 10년치
    if df is None or df.empty:
        return []

    records = []
    for dt, row in df.iterrows():
        actual    = row.get("Reported EPS")
        consensus = row.get("EPS Estimate")
        if pd.isna(actual) or pd.isna(consensus):
            continue
        surprise_pct = (actual - consensus) / (abs(consensus) + 1e-9)
        records.append({
            "symbol":       symbol,
            "report_date":  dt.date(),
            "actual_eps":   float(actual),
            "consensus_eps": float(consensus),
            "surprise_pct": float(surprise_pct),
            "n_analysts":   1,      # yfinance는 애널리스트 수 미제공, 1로 고정
        })
    return records
```

**주의 사항:** Yahoo Finance는 컨센서스 수치를 사후 업데이트하는 경우가 있습니다. 즉, 과거 분기의 "EPS Estimate" 값이 발표 당시 실제 컨센서스와 약간 다를 수 있습니다. 백테스트 결과를 약간 낙관적으로 만드는 방향이지만 정도가 크지 않아 방향성 검증에는 충분합니다. 실전 운용 전 FMP 데이터로 교차 검증을 권장합니다.

---

## 방법 2 — YoY EPS 성장률 프록시 (2순위)

### 원리

컨센서스 EPS가 없을 때 학계에서 사용하는 표준 대안입니다. 이를 **SUE(Standardized Unexpected Earnings)** 시계열 모델이라고 합니다.

```
핵심 아이디어:
  시장은 "이번 분기도 지난해 같은 분기와 비슷하겠지"를 기본으로 예상
  → 지난해 동기 대비 EPS가 크게 증가했다면 = 서프라이즈와 동일한 신호

계산식:
  sue = (EPS_현재분기 - EPS_1년전동기) / std(EPS 변화량, 최근 8분기)
```

Ball & Brown(1968) 원본 논문부터 현대 연구까지 이 방식은 애널리스트 컨센서스 기반 서프라이즈와 **유사한 알파를 생성**함이 반복 검증되어 있습니다. 컨센서스 기반보다 신호가 약 20~30% 약하지만 무료로 즉시 사용 가능합니다.

### 데이터 요구사항

Polygon 실제 EPS 데이터만 있으면 됩니다. 현재 이미 보유 중입니다.

```python
def calc_pead_score_yoy(
    symbol: str,
    as_of_date,
    earnings_cache,          # 실제 EPS 히스토리만 있으면 됨
    lookback_days: int = 90,
) -> float:
    """
    YoY EPS 성장률 기반 PEAD 프록시.
    컨센서스 EPS 없이 실제 EPS만으로 계산.
    반환: 0 ~ 13점
    """
    # 가장 최근 분기 EPS
    current = earnings_cache.get_most_recent(symbol, as_of_date)
    if current is None:
        return 0.0

    days_since = (as_of_date - current.report_date).days
    if days_since > lookback_days:
        return 0.0  # 90일 초과 → 드리프트 구간 종료

    # 1년 전 동기 EPS (4분기 전)
    prior = earnings_cache.get_year_ago_same_quarter(symbol, current.report_date)
    if prior is None or abs(prior.actual_eps) < 0.01:
        return 0.0  # 기준값이 너무 작으면 성장률 계산 불안정

    # YoY 성장률
    yoy_growth = (current.actual_eps - prior.actual_eps) / abs(prior.actual_eps)

    # 최근성 가중치
    recency_weight = max(0.0, 1.0 - days_since / lookback_days)

    # 정규화: YoY 성장률 -100%~+100% → 0~13점
    clipped = np.clip(yoy_growth, -1.0, 1.0)
    return ((clipped + 1.0) / 2.0) * 13.0 * recency_weight
```

### YoY 방식의 한계와 대응

| 한계 | 영향 | 대응 |
|------|------|------|
| 컨센서스 대비 신호 강도 약 20~30% 약함 | PEAD 알파 감소 | 허용 — 무료 방식의 정상 한계 |
| 주식 분할 시 EPS 왜곡 | 잘못된 신호 | 분할 조정 EPS 사용 (Polygon 제공) |
| 적자 기업(EPS < 0) 계산 불안정 | 노이즈 | `abs(prior_eps) < 0.01` 시 0점 처리 (위 코드에 반영됨) |
| 경기 순환 업종(에너지 등) 오신호 | 섹터 편향 | 섹터 내 상대 YoY 비교로 보완 가능 (선택) |

---

## 실행 계획

### Step 1 — yfinance 커버리지 검증 (1일)

```bash
# 샘플 10개 → 전체 유니버스 순서로 진행
python scripts/test_yfinance_earnings_coverage.py \
  --sample 10 \
  --universe data/universe/us_stocks_5183.parquet
```

커버리지 70% 이상이면 yfinance 수집기를 전체 유니버스에 적용하고 EarningsCache를 갱신합니다. Step 2는 건너뜁니다.

### Step 2 — (Step 1 불충분 시) YoY 프록시 구현 (2일)

```
1. EarningsCache에 get_year_ago_same_quarter() 메서드 추가
2. calc_pead_score_yoy() 구현 및 단위 테스트
3. calc_pead_score() 내부에서 컨센서스 존재 여부에 따라 분기
   → 컨센서스 있으면: 기존 surprise 방식
   → 컨센서스 없으면: YoY 방식 fallback
```

```python
def calc_pead_score(symbol, as_of_date, earnings_cache, lookback_days=90):
    """컨센서스 유무에 따라 자동 분기."""
    recent = earnings_cache.get_most_recent(symbol, as_of_date)
    if recent is None:
        return 0.0

    if recent.n_analysts >= 1 and recent.consensus_eps is not None:
        # 방법 1: 컨센서스 기반 (yfinance 또는 FMP 데이터)
        return _pead_from_consensus(recent, as_of_date, lookback_days)
    else:
        # 방법 2: YoY 프록시 (실제 EPS만으로 계산)
        return calc_pead_score_yoy(symbol, as_of_date, earnings_cache, lookback_days)
```

### Step 3 — PEAD 활성화 백테스트 (1일)

두 방법 중 하나로 PEAD가 활성화되면 P20 목표 KPI 달성 여부를 재측정합니다.

```
목표 재확인:
  CAGR ≥ 17.5%
  SPY 초과수익 ≥ +3.0%p
```

---

## 유료 소스 전환 시점

아래 두 조건을 모두 충족하는 경우에만 FMP 유료 전환을 검토합니다.

```
조건 1: yfinance 커버리지 < 70% AND YoY 프록시로 P20 KPI 미달
조건 2: P23 Walk-Forward 통과 후 실전 운용 직전 단계
```

현 시점에서 유료 결제는 불필요합니다. 위 순서대로 진행 후 결과를 보고하십시오.

---

*문서 종료 | P20 PEAD 무료 활성화 방안 v1.0*
*작성: 퀀트 전략팀 | 수신: NAVIS 개발팀 | 2026-05-07*
