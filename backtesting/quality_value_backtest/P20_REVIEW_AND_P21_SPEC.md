# P20 검토 결과 및 P21 개발 지시서

| 항목 | 내용 |
|------|------|
| 문서 버전 | v1.0 |
| 작성일 | 2026-05-07 |
| 작성자 | 퀀트 전략팀 |
| 수신 | NAVIS 개발팀 |
| 참조 문서 | NAVIS_ALPHA_V1_STRATEGY_SPEC.md, P19_REVIEW_AND_P20_SPEC.md |

---

## 1. P20 공식 판정

### 판정: ✅ 인프라 합격 / ⚠️ KPI 조건부 보류

P20의 실패가 아닙니다. PEAD 인프라는 완성되었고, KPI 미달의 원인은 코드가 아닌 **외부 데이터 조달 문제**입니다. 이 둘을 구분하여 판정합니다.

| 항목 | 목표 | 결과 | 판정 |
|------|------|------|------|
| PEAD 인프라 완성 | EarningsCache + calc_pead_score() 구현 | ✅ 완성 | ✅ |
| 기존 성과 보호 | P19 수준 유지 (오염 없음) | ✅ CAGR 15.50%, Sharpe 0.815, MDD -20.97% | ✅ |
| CAGR | ≥ 17.5% | 15.50% (미달) | ⚠️ |
| SPY 초과수익 | ≥ +3.0%p | +0.95%p (미달) | ⚠️ |

**KPI 미달 원인:** Polygon 무료 티어는 실제 EPS만 제공하며 컨센서스 EPS가 없습니다. PEAD 핵심 계산식 `surprise = (actual - consensus) / |consensus|` 에서 분모가 존재하지 않아 PEAD 팩터가 비활성 상태입니다. 컨센서스 EPS 확보 즉시 `n_analysts ≥ 1` 레코드만 교체하면 PEAD가 활성화됩니다.

---

## 2. 컨센서스 EPS 소싱 결정

### 배경

PEAD 알파를 실현하려면 **사전 컨센서스 EPS**(어닝 발표 전 애널리스트 중간값)가 필요합니다. 발표 후 실제치만으로는 서프라이즈 크기 계산이 불가합니다.

### 데이터 소스 비교

| 소스 | 월 비용 | 히스토리 | 종목 수 | 권장 여부 |
|------|--------|---------|--------|---------|
| **Financial Modeling Prep (FMP)** | **$14** | **2010년~** | **전 미국주식** | **✅ 1순위** |
| Alpha Vantage Premium | $50 | 2010년~ | 주요 종목 | 차선 |
| Intrinio | $200+ | 2005년~ | 전 미국주식 | 예산 여유 시 |
| Benzinga Pro | $179 | 2010년~ | 전 미국주식 | 불필요 |
| Yahoo Finance (yfinance) | 무료 | 미래 분기만 | 제한적 | ❌ 히스토리 없음 |

### 권고: FMP Starter 플랜 ($14/월)

이유는 세 가지입니다.

```
1. 비용 대비 데이터 품질
   $14/월로 2010년부터 히스토리 제공
   전 미국주식 커버리지 (현재 유니버스 2,052종목 모두 해당)

2. API 연동 용이성
   /earnings-surprises 엔드포인트에서
   actual_eps, estimated_eps, surprise, surprise_percentage 한 번에 제공
   → EarningsCache와 직접 연동 가능

3. 전략 ROI
   $14/월 투자로 PEAD 알파 +2~4%p 기대
   백만 달러 운용 기준 연 $20,000~$40,000 추가 수익 기대
   비용 대비 수익 수천 배
```

### FMP 연동 스펙

```python
# 수집 엔드포인트
GET https://financialmodelingprep.com/api/v3/earnings-surprises/{SYMBOL}?apikey={KEY}

# 응답 필드 → EarningsCache 컬럼 매핑
{
  "date":                 → report_date
  "symbol":               → symbol
  "actualEarningResult":  → actual_eps
  "estimatedEarning":     → consensus_eps
}

# surprise_pct 계산 (수집 후 로컬 계산)
surprise_pct = (actual_eps - consensus_eps) / abs(consensus_eps + 1e-9)

# n_analysts: FMP 기본 응답에 포함되지 않음
# → n_analysts = 1 로 고정 기입 (컨센서스 유효 레코드 표시 용도)
#   실제 애널리스트 수는 Intrinio 등 고가 소스 필요 — 현 단계 불필요
```

### 수집 범위

```
대상 종목:  유니버스 전체 (약 2,052종목)
수집 기간:  2016-01-01 ~ 현재
우선 순위:  top_pct=10% 편입 이력 종목 우선 수집 후 전체 확장
예상 소요:  약 3~4시간 (요청 속도 제한 준수 시)
저장 경로:  cache/earnings/{SYMBOL}_earnings.parquet (기존 스키마 유지)
```

---

## 3. P21 개발 지시서 — ATR 기반 Dynamic Risk Engine

### 3-1. 착수 판단

**P21을 즉시 착수합니다. EPS 소싱과 병행 진행입니다.**

이유:
- P21은 PEAD와 완전히 독립적입니다. 리스크 레이어 개선은 팩터 레이어와 무관하게 진행 가능합니다.
- P21 완료 후 FMP EPS 수집이 끝나면 PEAD를 활성화하고 P21+PEAD 통합 백테스트를 1회 실행합니다.
- 이 방식이 P21 완료 후 PEAD 대기하는 것보다 2~3주 빠릅니다.

### 3-2. 목표 및 합격 기준

| KPI | 목표 | 현재 P20 수준 |
|-----|------|------------|
| MDD | **< 20%** | -20.97% (경계선) |
| STOP_LOSS 비율 | **< 30%** | 약 40% (P18 수준 추정) |
| CAGR | P20 수준 유지 (≥ 15%) | 15.50% |
| Sharpe | P20 수준 유지 (≥ 0.8) | 0.815 |

ATR 손절이 제대로 작동하면 STOP_LOSS 비율이 줄고 MDD도 함께 개선됩니다. 반대로 CAGR이 낮아지면 ATR 파라미터를 잘못 설정한 신호이므로 주의하십시오.

---

### 3-3. 구현 사양

#### (A) ATR 계산 — calc_atr()

```python
# 담당 파일: risk_team/core/risk_manager.py 또는
#            backtesting/factor_backtest/factor_calculator.py (기존 위치 통일)

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

    window = daily_df.iloc[idx - period: idx]
    prev   = daily_df.iloc[idx - period - 1: idx - 1]

    tr = pd.DataFrame({
        "hl":  window["high"].values - window["low"].values,
        "hpc": abs(window["high"].values - prev["close"].values),
        "lpc": abs(window["low"].values  - prev["close"].values),
    }).max(axis=1)

    return float(tr.mean())
```

#### (B) ATR 기반 손절/익절 계산 — calc_atr_stops()

```python
STOP_ATR_MULT    = 2.5    # 손절 = 진입가 - ATR × 2.5
PROFIT_ATR_MULT  = 6.0    # 익절 = 진입가 + ATR × 6.0  (RRR = 2.4:1)
MAX_ATR_RATIO    = 0.05   # ATR/진입가 > 5% 시 진입 거부

def calc_atr_stops(
    entry_price: float,
    atr: float,
) -> tuple[Optional[float], Optional[float]]:
    """
    반환: (stop_loss_price, take_profit_price)
    ATR/진입가 > 5% 이면 (None, None) 반환 → 엔진에서 진입 스킵
    """
    if atr is None or entry_price <= 0:
        return None, None
    if atr / entry_price > MAX_ATR_RATIO:
        return None, None  # 과고변동 종목 진입 거부

    stop   = entry_price - atr * STOP_ATR_MULT
    profit = entry_price + atr * PROFIT_ATR_MULT
    return stop, profit
```

**종목 유형별 예시:**

| 종목 유형 | ATR/주가 | 기존 고정 손절 | ATR 손절 | 변화 |
|---------|---------|------------|---------|------|
| 대형 우량주 | 1.2% | -15.0% | -3.0% | 타이트, 조기 청산 감소 |
| 중형 성장주 | 2.5% | -15.0% | -6.3% | 적정 |
| 고변동 소형주 | 5.5% | -15.0% | 진입 거부 | 위험 종목 사전 차단 |

#### (C) 트레일링 스탑 — update_trailing_stop()

```python
TRAILING_ACTIVATE_PCT = 0.15   # +15% 수익 시 트레일링 스탑 활성화
TRAILING_DRAWDOWN_PCT = 0.10   # 활성화 후 고점 대비 -10% 하락 시 청산

def update_trailing_stop(position: dict, current_price: float) -> bool:
    """
    True 반환 시 즉시 청산.
    position 딕셔너리에 'peak_price' 필드 추가 필요.
    """
    entry   = position["entry_price"]
    pnl_pct = (current_price - entry) / entry

    if pnl_pct < TRAILING_ACTIVATE_PCT:
        return False  # 미활성

    # 고점 갱신
    position["peak_price"] = max(position.get("peak_price", entry), current_price)

    # 고점 대비 -10% 하락 시 청산
    trail_stop = position["peak_price"] * (1 - TRAILING_DRAWDOWN_PCT)
    return current_price < trail_stop
```

#### (D) 포트폴리오 변동성 타겟팅

```python
TARGET_VOL_ANNUAL    = 0.15   # 연 15% 변동성 목표
SCALE_DOWN_THRESHOLD = 0.18   # 실현 변동성 > 18% → 보유 종목 수 축소
SCALE_UP_THRESHOLD   = 0.12   # 실현 변동성 < 12% → 보유 종목 수 확대

def adjust_target_holdings(
    current_holdings: int,
    realized_vol_annual: float,
    base_holdings: int = 50,
) -> int:
    """
    월 1회 변동성 점검 후 목표 보유 종목 수 반환.
    """
    if realized_vol_annual > SCALE_DOWN_THRESHOLD:
        return max(25, int(current_holdings * 0.80))   # 20% 축소
    elif realized_vol_annual < SCALE_UP_THRESHOLD:
        return min(60, int(current_holdings * 1.10))   # 10% 확대
    return current_holdings                              # 유지
```

---

### 3-4. 백테스트 엔진 수정 포인트

`backtesting/factor_backtest/engine.py`의 `_rebalance()` 메서드를 다음과 같이 수정합니다.

```
수정 전: 진입 시 고정 손절 -15% 하드코딩
수정 후:
  1. calc_atr() 호출 → ATR 값 산출
  2. calc_atr_stops() 호출 → 손절가/익절가 산출
  3. 반환값이 (None, None)이면 해당 종목 진입 스킵
  4. 포지션 딕셔너리에 stop_price, profit_price, peak_price 필드 추가
  5. 일별 루프에서 update_trailing_stop() 호출 (기존 손절 체크와 동일 위치)
  6. 월말 변동성 점검: adjust_target_holdings() 호출
```

---

### 3-5. 파라미터 튜닝 범위

백테스트 실행 시 아래 범위에서 최적 파라미터를 탐색하십시오.

| 파라미터 | 탐색 범위 | 기본값 |
|---------|---------|--------|
| `STOP_ATR_MULT` | 2.0, 2.5, 3.0 | 2.5 |
| `PROFIT_ATR_MULT` | 5.0, 6.0, 7.0 | 6.0 |
| `MAX_ATR_RATIO` | 0.04, 0.05, 0.06 | 0.05 |
| `TRAILING_ACTIVATE_PCT` | 0.12, 0.15, 0.20 | 0.15 |

**규칙:** In-Sample(2020~2023) 최적값을 Out-of-Sample(2024~2026)에 그대로 적용하여 과최적화 여부를 확인하십시오.

---

## 4. 병행 작업 정리

| 작업 | 담당 | 기한 | 비고 |
|------|------|------|------|
| P21 ATR Risk Engine 구현 | 개발 1팀 | Week 5 | 본 문서 3절 기준 |
| FMP EPS 수집기 구현 + 전수 수집 | 개발 2팀 | Week 5 | 2절 FMP 스펙 기준 |
| 일봉 데이터 2016년 소급 수집 | 개발 2팀 | Week 6 이전 | P23 준비 |

**P21 완료 + FMP EPS 수집 완료 시점에 PEAD 활성화 후 통합 백테스트 1회 실행합니다.** 이 통합 결과가 P20 KPI(CAGR ≥ 17.5%, SPY +3%p) 달성 여부를 최종 판정합니다.

---

## 5. 전체 진행 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| P19 | Multi-Factor Scoring | ✅ 완료 |
| P20 | PEAD 인프라 + EarningsCache | ✅ 인프라 완료 / ⚠️ EPS 데이터 대기 |
| **P21** | **ATR Dynamic Risk Engine** | **🔄 즉시 착수** |
| P20-EPS | FMP 컨센서스 EPS 수집 | **🔄 P21과 병행** |
| P20+P21 통합 | PEAD 활성화 + ATR 통합 백테스트 | ⏳ P21 완료 후 |
| P22 | Market Regime Gate | ⏳ 대기 |
| P23 | Walk-Forward 최종 검증 | ⏳ 대기 |

---

## 6. P21 합격 기준

| KPI | 합격 기준 |
|-----|---------|
| MDD | **< 20.0%** (P20의 -20.97% 대비 개선) |
| STOP_LOSS 비율 | **< 30%** |
| CAGR | ≥ 15.0% (P20 수준 유지) |
| Sharpe | ≥ 0.80 (P20 수준 유지) |

> CAGR이 P20 대비 하락하면 ATR 파라미터 재조정이 필요합니다.
> 손절이 너무 타이트하면(STOP_ATR_MULT < 2.0) 정상 변동에 손절이 남발되어 CAGR이 감소합니다.

---

*문서 종료 | P20 검토 결과 및 P21 개발 지시서 v1.0*
*작성: 퀀트 전략팀 | 수신: NAVIS 개발팀 | 2026-05-07*
