# NAVIS ALPHA v1.0 — 전략 개발 사양서

| 항목 | 내용 |
|------|------|
| 문서 버전 | v1.0 |
| 작성일 | 2026-05-07 |
| 작성자 | 퀀트 전략팀 |
| 수신 | NAVIS 개발팀 |
| 분류 | 내부 기밀 |
| 베이스라인 | P18 Strategy E (CAGR 8.98%, MDD 28.81%) |

---

## 목차

1. [배경 및 목표 재설정](#1-배경-및-목표-재설정)
2. [현행 전략 문제 진단](#2-현행-전략-문제-진단)
3. [전략 아키텍처](#3-전략-아키텍처)
4. [Layer 1 — 유니버스 필터](#4-layer-1--유니버스-필터)
5. [Layer 2 — Multi-Factor Scoring](#5-layer-2--multi-factor-scoring)
6. [Layer 3 — Dynamic Risk Engine](#6-layer-3--dynamic-risk-engine)
7. [Layer 4 — Market Regime Gate](#7-layer-4--market-regime-gate)
8. [포트폴리오 운용 프로세스](#8-포트폴리오-운용-프로세스)
9. [구현 로드맵](#9-구현-로드맵)
10. [합격 기준 (KPI)](#10-합격-기준-kpi)
11. [데이터 인프라 요구사항](#11-데이터-인프라-요구사항)
12. [레버리지 로드맵](#12-레버리지-로드맵)

---

## 1. 배경 및 목표 재설정

### 1-1. P18까지의 결과 요약

P17~P18을 통해 F-Score 기반 Quality-Value 전략을 10년 백테스트로 검증한 결과, 최선 성과는 다음과 같습니다.

| 전략 | CAGR | MDD | Sharpe | PF | 판정 |
|------|------|-----|--------|-----|------|
| P17-3A (기준선) | 8.98% | 28.81% | 0.48 | 1.37 | 부분합격 |
| P18-C (최우수 MDD) | 8.46% | 25.21% | 0.45 | 1.34 | FAIL |

기존 합격 기준(CAGR ≥ 12%, MDD ≤ 20%)도 달성하지 못하였으며, S&P 500 장기 CAGR(~13%)에도 미치지 못합니다.

### 1-2. 기존 목표의 문제

기존 목표 "월 수익 5% 이상"은 연환산 CAGR 79.6%에 해당합니다. 이는 세계 최고 퀀트 펀드인 Renaissance Medallion(비용 전 ~66% CAGR)을 상회하는 수준으로, 재무제표 기반 중장기 가치투자 전략으로는 **구조적으로 달성 불가능한 목표**입니다.

### 1-3. 단계별 목표 재설정

| 단계 | 기간 | CAGR 목표 | MDD 목표 | Sharpe 목표 | 월 수익 환산 |
|------|------|---------|---------|-----------|------------|
| Phase 1 | 0~12개월 | ≥ 18% | < 18% | > 0.8 | ~1.4% |
| Phase 2 | 1~2년 | ≥ 25% | < 15% | > 1.0 | ~1.9% |
| Phase 3 | 2년+ | ≥ 30% | < 12% | > 1.2 | ~2.2% |

> Phase 1 달성 후 레버리지 1.5x 가미 시 CAGR 27%, 월 수익 약 2.0%까지 확장 가능.  
> "월 5%" 목표는 레버리지 확장 이후 재평가하는 숫자입니다.

---

## 2. 현행 전략 문제 진단

### 2-1. 단일 팩터의 한계

F-Score는 1990년대 학계에서 발견된 팩터로, 2010년대 이후 기관 투자자들의 광범위한 활용으로 알파가 상당 부분 소진되었습니다. 현재 F-Score 단독 전략의 초과수익(vs SPY)은 약 0~2%p 수준으로 추정됩니다.

**해결:** 알파 소스를 4개로 다각화합니다. 개별 알파가 작더라도 상관관계가 낮은 팩터들을 결합하면 합산 알파는 비선형으로 증가합니다.

### 2-2. 고정 손절이 알파를 훼손

현행 전략의 구조적 문제는 고정 손절 -15%입니다.

```
저변동 우량주 (ATR 0.8%/일): -15%는 너무 넓어 과도한 손실 허용
고변동 성장주 (ATR 2.5%/일): -15%는 너무 좁아 정상 노이즈에 손절

결과: 전 포지션의 40%가 손절 → 수익 포지션의 알파를 갉아먹음
```

**해결:** ATR(Average True Range) 기반 동적 손절로 교체합니다.

### 2-3. 누락된 가장 강력한 팩터 — PEAD

PEAD(Post-Earnings Announcement Drift)는 1968년 Ball & Brown이 발견 후 2026년 현재까지도 작동하는 가장 강력한 시장 이상 현상 중 하나입니다.

```
현상: 어닝 서프라이즈 발생 후 주가가 같은 방향으로 1~3개월 추가 이동
예시: Q1 컨센서스 EPS $1.00 → 실제 발표 $1.30 (+30% 서프라이즈)
     → 발표일 당일 +5% 급등 후 이후 60일간 추가 +5~10% drift
     → 이 drift 구간이 우리의 진입 기회
```

현재 코드베이스에 `build_earnings_cache.py`가 존재하므로 즉시 활용 가능합니다.

### 2-4. 시장 레짐 필터 부재

2022년 전략 손실(-13~-25%)의 주요 원인은 Bear market 진입 후에도 100% 주식 노출을 유지한 것입니다. 시장 레짐 감지 후 포지션 자동 축소 메커니즘이 필요합니다.

---

## 3. 전략 아키텍처

NAVIS ALPHA v1.0은 4층 구조로 설계됩니다. 위 레이어일수록 우선순위가 높으며, 상위 레이어의 조건이 충족되지 않으면 하위 레이어 신호는 무시됩니다.

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 4: Market Regime Gate                                      │
│  역할: 시장 전체 방향성 감지 → Bull/Neutral/Bear 분류             │
│  효과: Bear market 시 포지션 자동 50% 축소                        │
├──────────────────────────────────────────────────────────────────┤
│  Layer 3: Dynamic Risk Engine                                     │
│  역할: ATR 기반 손절/익절 + 포트폴리오 변동성 타겟팅              │
│  효과: 손절 비율 40% → 목표 25%로 감소                           │
├──────────────────────────────────────────────────────────────────┤
│  Layer 2: Multi-Factor Scoring                                    │
│  역할: Quality + Value + Momentum + Catalyst → 0~100점           │
│  효과: 단일 팩터 알파 → 다팩터 복합 알파                         │
├──────────────────────────────────────────────────────────────────┤
│  Layer 1: Universe Filter                                         │
│  역할: 유동성·가격·시총 기준으로 투자 가능 유니버스 확정           │
│  효과: 마이크로캡·저유동 종목 노이즈 사전 제거                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Layer 1 — 유니버스 필터

### 4-1. 필터 기준

| 필터 항목 | 기준값 | 제외 이유 |
|----------|--------|---------|
| 최소 주가 | $5.00 이상 | 펜니스톡 유동성·조작 리스크 |
| 일평균 거래대금(ADV) | $2,000,000 이상 | 슬리피지 통제 불가 |
| 시가총액 | $200,000,000 이상 | 마이크로캡 유동성 리스크 |
| 거래소 | NYSE, NASDAQ | OTC 제외 |
| 제외 섹터 | 금융지주, 부동산리츠 | F-Score 재무구조 왜곡 |

### 4-2. 예상 통과 종목 수

현재 보유 일봉 데이터 2,052종목 기준, 위 필터 적용 후 **약 1,400~1,800종목**이 유니버스로 확정될 것으로 예상됩니다.

### 4-3. 구현 참조

- 유동성 필터: `backtesting/factor_backtest/factor_calculator.py` → `calc_avg_dollar_volume()` 활용
- 기존 `min_dollar_volume = 5e7` 기준을 `2e6`으로 조정 (소형 우량주 포함 확대)

---

## 5. Layer 2 — Multi-Factor Scoring

모든 종목을 0~100점으로 정량화하여 순위를 산출합니다. 이진(Binary) 필터 방식이 아닌 연속 점수 방식을 사용하여 경계값 문제를 해소합니다.

### 5-1. Quality Score (35점 만점)

재무 우량성을 측정합니다.

| 구성 요소 | 배점 | 산출 방법 |
|---------|------|---------|
| F-Score | 15점 | `F_Score / 9 × 15` (기존 바이너리 → 연속 정규화) |
| ROE 섹터 상대 순위 | 8점 | 섹터 내 ROE 백분위 × 8 |
| FCF/Assets | 7점 | 섹터 내 FCF수익률 백분위 × 7 |
| Accruals | 5점 | `Accruals = (Net Income − Operating Cash Flow) / Total Assets`, 값이 낮을수록(음수에 가까울수록) 고점 |

```python
# 의사 코드 (Pseudo-code)
def calc_quality_score(fundamentals, sector_peers):
    f_score_pts  = (fundamentals.f_score / 9) * 15
    roe_pct      = percentile_rank(fundamentals.roe, sector_peers.roe)
    roe_pts      = roe_pct * 8
    fcf_pct      = percentile_rank(fundamentals.fcf_yield, sector_peers.fcf_yield)
    fcf_pts      = fcf_pct * 7
    accruals     = (fundamentals.net_income - fundamentals.cfo) / fundamentals.total_assets
    accruals_pct = 1 - percentile_rank(accruals, sector_peers.accruals)  # 낮을수록 좋음
    accruals_pts = accruals_pct * 5
    return f_score_pts + roe_pts + fcf_pts + accruals_pts  # 0~35
```

### 5-2. Value Score (25점 만점)

절대 밸류에이션이 아닌 **섹터 내 상대 밸류에이션**을 사용합니다. 테크주와 에너지주를 동일 기준으로 비교하는 오류를 방지합니다.

| 구성 요소 | 배점 | 산출 방법 |
|---------|------|---------|
| EV/EBITDA (섹터 상대) | 12점 | 섹터 내 하위 백분위 × 12 (낮을수록 저평가) |
| Price/FCF (섹터 상대) | 8점 | 섹터 내 하위 백분위 × 8 |
| P/B (섹터 상대) | 5점 | 섹터 내 하위 백분위 × 5 |

```python
def calc_value_score(fundamentals, sector_peers):
    ev_ebitda_pct = 1 - percentile_rank(fundamentals.ev_ebitda, sector_peers.ev_ebitda)
    pfcf_pct      = 1 - percentile_rank(fundamentals.p_fcf, sector_peers.p_fcf)
    pb_pct        = 1 - percentile_rank(fundamentals.p_b, sector_peers.p_b)
    return ev_ebitda_pct * 12 + pfcf_pct * 8 + pb_pct * 5  # 0~25
```

### 5-3. Momentum Score (25점 만점)

가격 모멘텀과 어닝 모멘텀 두 가지를 결합합니다.

| 구성 요소 | 배점 | 산출 방법 |
|---------|------|---------|
| 12-1 가격 모멘텀 | 12점 | 기존 `calc_momentum_12_1()` 결과 정규화 |
| PEAD (어닝 서프라이즈 드리프트) | 13점 | 서프라이즈 크기 × 경과일 역가중 |

**PEAD 점수 산출 상세:**

```python
def calc_pead_score(symbol, as_of_date, earnings_cache, lookback_days=90):
    """
    최근 90일 이내 어닝 서프라이즈 발생 시 점수 부여.
    서프라이즈 클수록, 최근일수록 고점.
    """
    recent_earnings = earnings_cache.get_recent(symbol, as_of_date, lookback_days)
    if not recent_earnings:
        return 0.0

    surprise_pct = (recent_earnings.actual_eps - recent_earnings.consensus_eps) \
                   / abs(recent_earnings.consensus_eps + 1e-9)

    days_elapsed  = (as_of_date - recent_earnings.report_date).days
    recency_weight = max(0, 1 - days_elapsed / lookback_days)  # 0~1, 최근일수록 1

    raw_score = np.clip(surprise_pct, -1.0, 1.0) * recency_weight  # -1 ~ 1
    return ((raw_score + 1) / 2) * 13  # 0~13점 정규화
```

### 5-4. Catalyst Score (15점 만점)

내부자 신호의 품질을 개선합니다. 소액 거래($10,000 미만)는 완전 제외하여 베스팅·보너스 주식 등 노이즈 신호를 차단합니다.

| 구성 요소 | 배점 | 기준 |
|---------|------|------|
| 내부자 순매수 | 최대 10점 | $100K+ : 10점, $50K~$100K : 6점, $10K~$50K : 3점, 없음/순매도 : 0점 |
| 자사주 매입 발표 | 최대 5점 | 최근 90일 이내 발표: 5점, 없음: 0점 |

```python
def calc_catalyst_score(symbol, as_of_date, insider_cache, lookback_days=90):
    net_buy_usd = insider_cache.get_net_insider_buy(
        symbol, as_of_date, lookback_days, min_amount=10_000
    )
    if   net_buy_usd >= 100_000: insider_pts = 10
    elif net_buy_usd >=  50_000: insider_pts = 6
    elif net_buy_usd >=  10_000: insider_pts = 3
    else:                        insider_pts = 0

    has_buyback = insider_cache.has_buyback_announcement(
        symbol, as_of_date, lookback_days
    )
    buyback_pts = 5 if has_buyback else 0

    return insider_pts + buyback_pts  # 0~15
```

### 5-5. 최종 점수 및 포트폴리오 선정

```python
Total_Score = Quality_Score + Value_Score + Momentum_Score + Catalyst_Score
            # 0 ~ 100점

# 포트폴리오 선정 기준
MIN_SCORE        = 55       # 절대 컷오프: 55점 미만은 진입 금지
TARGET_HOLDINGS  = 40~60    # 목표 보유 종목 수 (레짐에 따라 조정)
MAX_SECTOR_PCT   = 0.25     # 단일 섹터 최대 25%
MAX_POSITION_PCT = 0.05     # 단일 종목 최대 5%
```

**포지션 가중치:** 기본 동일 비중. Quality Score 상위 20% 종목은 1.5배 오버웨이트 적용 가능 (옵션).

---

## 6. Layer 3 — Dynamic Risk Engine

### 6-1. ATR 기반 동적 손절/익절 (핵심 변경)

고정 손절 -15%를 ATR 기반으로 교체합니다.

```python
ATR_PERIOD      = 14         # 14거래일 ATR
STOP_ATR_MULT   = 2.5        # 손절 = 진입가 - ATR × 2.5
PROFIT_ATR_MULT = 6.0        # 익절 = 진입가 + ATR × 6.0
MAX_ATR_RATIO   = 0.05       # ATR/주가 > 5%면 진입 거부 (과고변동 종목 제외)

def calc_stops(entry_price, atr_14):
    if atr_14 / entry_price > MAX_ATR_RATIO:
        return None, None  # 진입 거부
    stop_loss   = entry_price - atr_14 * STOP_ATR_MULT
    take_profit = entry_price + atr_14 * PROFIT_ATR_MULT
    return stop_loss, take_profit
```

**종목별 손절 예시 (비교):**

| 종목 유형 | ATR/주가 | 기존 고정 손절 | 새 ATR 손절 | 개선 |
|---------|---------|------------|-----------|------|
| 대형 우량주 (ATR 1.2%) | 1.2% | -15% | -3.0% | 훨씬 타이트 |
| 중형 성장주 (ATR 2.5%) | 2.5% | -15% | -6.3% | 적절 |
| 고변동 소형주 (ATR 5.5%) | 5.5% | -15% | 진입 거부 | 위험 종목 차단 |

### 6-2. 트레일링 스탑

포지션이 +15% 이상 수익 발생 시 이익 보호를 위해 활성화됩니다.

```python
TRAILING_ACTIVATE_PCT = 0.15   # +15% 수익 시 트레일링 스탑 활성화
TRAILING_DRAWDOWN_PCT = 0.10   # 고점 대비 -10% 하락 시 청산

def update_trailing_stop(position):
    if position.unrealized_pnl_pct >= TRAILING_ACTIVATE_PCT:
        position.peak_price = max(position.peak_price, current_price)
        trailing_stop = position.peak_price * (1 - TRAILING_DRAWDOWN_PCT)
        if current_price < trailing_stop:
            close_position(position)
```

### 6-3. 포트폴리오 변동성 타겟팅

```python
TARGET_VOL_ANNUAL  = 0.15    # 연 15% 변동성 목표
SCALE_UP_THRESHOLD = 0.12    # 실현 변동성 < 12% → 포지션 확대 허용
SCALE_DOWN_THRESHOLD = 0.18  # 실현 변동성 > 18% → 포지션 규모 축소

# 주 1회 점검
realized_vol = portfolio_realized_volatility(lookback_days=60, annualize=True)
if realized_vol > SCALE_DOWN_THRESHOLD:
    reduce_target_holdings()     # 보유 종목 수 감소
elif realized_vol < SCALE_UP_THRESHOLD:
    increase_target_holdings()   # 보유 종목 수 증가
```

이 메커니즘으로 2020년, 2022년 같은 고변동 구간에서 자동으로 포지션이 줄어들어 MDD가 개선됩니다.

---

## 7. Layer 4 — Market Regime Gate

### 7-1. 레짐 분류 로직

기존 `strategy_engine/market_regime/` 모듈을 활용합니다.

```python
def classify_market_regime(spy_daily_df, as_of_date):
    spy_close  = get_price(spy_daily_df, as_of_date)
    spy_ma200  = sma(spy_daily_df, as_of_date, period=200)
    spy_ma50   = sma(spy_daily_df, as_of_date, period=50)

    if spy_close > spy_ma200 and spy_ma50 > spy_ma200:
        return "BULL"      # 정상 상승장
    elif spy_close < spy_ma200:
        return "BEAR"      # 하락장
    else:
        return "NEUTRAL"   # 혼조
```

### 7-2. 레짐별 포지션 정책

| 레짐 | 주식 노출 | 현금/T-bills | 목표 보유 종목 수 |
|------|---------|------------|--------------|
| BULL | 100% | 0% | 50~60종목 |
| NEUTRAL | 75% | 25% | 38~45종목 |
| BEAR | 50% | 50% | 25~30종목 |

### 7-3. 전환 처리

레짐 전환 시 급격한 매매를 방지하기 위해 **5거래일에 걸쳐 점진적으로 조정**합니다. 단, BULL→BEAR 전환 시에는 3거래일 내 완료하여 하락 방어 속도를 높입니다.

**기대 효과 (2022년 기준):**
```
기존 P18-A 2022 손실: -13.3%
Market Regime Gate 적용 시 예상: -6~-8%  (Bear 신호 시 50% 현금 전환)
```

---

## 8. 포트폴리오 운용 프로세스

### 8-1. 월말 신호 생성 (Signal Generation)

```
T-0 (월 마지막 거래일):
  1. Layer 1 유니버스 필터 실행 → 약 1,400~1,800종목
  2. 전 종목 4팩터 점수 계산 (Quality, Value, Momentum, Catalyst)
  3. Market Regime 확인 → 목표 보유 종목 수 결정
  4. 상위 N종목 선정 (섹터 집중도 제한 적용)
  5. 선정 종목별 ATR 계산 → 손절가/익절가 사전 산출
  6. 기존 포트폴리오 대비 변경 목록 확정 (편입/청산/유지)
```

### 8-2. 익월 첫 거래일 주문 실행 (Execution)

```
T+1 (익월 첫 거래일, 시가 기준):
  1. 청산 목록: 탈락 종목 시가 청산
  2. 편입 목록: 신규 종목 시가 매수
  3. 비중 조정: 기존 보유 종목 목표 비중 재조정
  4. 각 포지션의 손절가/익절가 주문 등록
```

### 8-3. 상시 모니터링 (Intraday / Daily)

```
일중: ATR 손절가 도달 → 즉시 시장가 청산
      트레일링 스탑 갱신 (일 1회, 장 마감 후)
주간: 포트폴리오 실현 변동성 점검 → 포지션 크기 조정
월간: 정기 리밸런싱 (위 T-0 프로세스 반복)
```

---

## 9. 구현 로드맵

### 9-1. 전체 타임라인

```
Week 1~2  : P19 — Multi-Factor Scoring 구축
Week 3~4  : P20 — PEAD Integration
Week 5    : P21 — Dynamic Risk Engine (ATR 손절)
Week 6    : P22 — Market Regime Gate 연동
Week 7~8  : P23 — Walk-Forward 검증 및 최종 튜닝
────────────────────────────────────────────────
총 8주 후: 실전 배포 가능 전략 완성
```

### 9-2. P19 — Multi-Factor Scoring (Week 1~2)

**목표:** F-Score 단일 팩터 → 4팩터 통합 점수 시스템 구축

**담당 파일:**
- `backtesting/factor_backtest/factor_calculator.py` — 팩터 계산 함수 추가
- `backtesting/factor_backtest/engine.py` — 새 점수 시스템으로 리밸런싱 로직 수정

**추가 함수:**
```python
calc_quality_score(fundamentals, sector_peers) -> float   # 0~35
calc_value_score(fundamentals, sector_peers)   -> float   # 0~25
calc_pead_score(symbol, date, earnings_cache)  -> float   # 0~13 (임시 0으로 시작)
calc_composite_score(q, v, m, c)              -> float   # 0~100
```

**백테스트 합격 기준:**
- CAGR ≥ 15%
- Sharpe ≥ 0.7
- MDD < 25%

---

### 9-3. P20 — PEAD Integration (Week 3~4)

**목표:** 어닝 서프라이즈 드리프트 신호 추가

**Week 3 — 데이터 파이프라인:**
- `backtesting/build_earnings_cache.py` 확장
  - 컨센서스 EPS 수집 (Yahoo Finance Earnings 또는 유사 소스)
  - 실제 발표 EPS 수집
  - 서프라이즈 비율 계산: `(actual - consensus) / |consensus|`
  - 발표일 기록 → parquet 저장: `cache/earnings/{SYMBOL}_earnings.parquet`

**Week 4 — 팩터 통합 + 백테스트:**
- `calc_pead_score()` 완성 후 Momentum Score에 통합
- 전체 백테스트 재실행
- **합격 기준:** P19 대비 CAGR +2%p 이상 개선

---

### 9-4. P21 — Dynamic Risk Engine (Week 5)

**목표:** 고정 손절 -15% → ATR 기반 동적 손절

**담당 파일:**
- `risk_team/core/risk_manager.py` — `calc_atr_stop()` 추가
- `risk_team/core/position_sizer.py` — 변동성 타겟팅 로직 추가

**추가 함수:**
```python
calc_atr(daily_df, as_of_date, period=14)          -> float
calc_atr_stop(entry_price, atr)                     -> tuple[float, float]
update_trailing_stop(position, current_price)        -> Optional[float]
calc_portfolio_realized_vol(positions, lookback=60) -> float
```

**백테스트 합격 기준:**
- MDD < 20% (현재 25.21% 대비 개선)
- STOP_LOSS 비율 < 30% (현재 40% 대비 개선)

---

### 9-5. P22 — Market Regime Gate (Week 6)

**목표:** Bear market 자동 방어

**담당 파일:**
- `strategy_engine/market_regime/` 기존 모듈 연동
- `backtesting/factor_backtest/engine.py` — 레짐별 포지션 크기 조정 로직 추가

**합격 기준:**
- 2022년 손실 < -10% (현행 -13~-25% 대비 개선)
- 2020년 손실 개선 (코로나 초기 급락 구간)

---

### 9-6. P23 — Walk-Forward 검증 (Week 7~8)

**목표:** 과최적화 검사 + 최종 합격 확인

**방법:**

```
In-Sample  (훈련): 2016-01-01 ~ 2021-12-31 (6년)
Out-of-Sample(검증): 2022-01-01 ~ 2026-01-01 (4년)

파라미터 튜닝 범위:
  - MIN_SCORE: 50, 55, 60 중 선택
  - STOP_ATR_MULT: 2.0, 2.5, 3.0 중 선택
  - PROFIT_ATR_MULT: 5.0, 6.0, 7.0 중 선택
  - TARGET_HOLDINGS: 30, 40, 50, 60 중 선택

규칙: In-Sample 최적 파라미터를 Out-of-Sample에 그대로 적용
      Out-of-Sample 성과가 In-Sample 대비 30% 이상 열화 시 과최적화로 판정
```

**최종 합격 기준 (NAVIS ALPHA v1.0 공식 합격):**
- CAGR ≥ 18%
- MDD < 18%
- Sharpe ≥ 0.8
- Sortino ≥ 1.2
- PF ≥ 1.50
- SPY 초과수익 ≥ 8%p

---

## 10. 합격 기준 (KPI)

### 10-1. 단계별 합격 기준

| 단계 | 기준 항목 | 목표값 | 현재값 (P18 최우수) |
|------|---------|--------|------------------|
| P19 | CAGR | ≥ 15% | 8.98% |
| P19 | Sharpe | ≥ 0.7 | 0.48 |
| P21 | MDD | < 20% | 25.21% |
| P21 | STOP_LOSS 비율 | < 30% | 40.0% |
| P22 | 2022년 손실 | > -10% | -13.3% |
| **P23 (최종)** | **CAGR** | **≥ 18%** | 8.98% |
| **P23 (최종)** | **MDD** | **< 18%** | 25.21% |
| **P23 (최종)** | **Sharpe** | **≥ 0.8** | 0.48 |
| **P23 (최종)** | **Sortino** | **≥ 1.2** | 미측정 |
| **P23 (최종)** | **PF** | **≥ 1.50** | 1.37 |
| **P23 (최종)** | **SPY 초과수익** | **≥ +8%p** | -4%p |

### 10-2. 실전 운용 진입 조건 (모두 충족 시)

- P23 최종 합격 기준 통과
- Walk-Forward Out-of-Sample 성과 열화 < 30%
- 페이퍼 트레이딩 1개월 결과 백테스트와 유의한 차이 없음

---

## 11. 데이터 인프라 요구사항

### 11-1. 현재 보유 데이터 (활용 가능)

| 데이터 | 현황 | P19 활용 여부 |
|--------|------|------------|
| 재무 데이터 | 5,161종목 parquet (quarterly) | ✅ Quality + Value 팩터 |
| 가격 데이터 | 2,052종목 parquet (daily) | ✅ Momentum + ATR |
| Form4 (OpenInsider) | 5,161종목, 34,824건 | ✅ Catalyst 팩터 |
| 어닝 캐시 | 부분 존재 (`build_earnings_cache.py`) | P20에서 확장 |

### 11-2. P20에서 신규 수집 필요

| 데이터 | 내용 | 우선순위 |
|--------|------|---------|
| 컨센서스 EPS | 어닝 발표 전 애널리스트 컨센서스 | 필수 (PEAD 핵심) |
| 실제 발표 EPS | 어닝 발표 결과 + 발표일 | 필수 (PEAD 핵심) |
| 자사주 매입 공시 | 8-K SEC 공시 | 권장 (Catalyst 보강) |

### 11-3. SEC EDGAR 차단 관련

현재 `data.sec.gov` Akamai IP 차단(403) 상태입니다. Form 4 원본 XML 접근이 차단 해제 후 가능해지면 OpenInsider 대비 **소액 내부자 거래 구분, 베스팅 vs 자발적 매수 분류**가 가능해져 Catalyst Score 정확도가 향상될 것으로 예상됩니다.

차단 해제 후 즉시 실행:
```bash
python data/form4/preload_metadata.py \
  --start 2015-01-01 \
  --universe data/universe/us_stocks_5183.parquet \
  --resume
```

---

## 12. 레버리지 로드맵

P23 최종 합격 후 실전 운용 6개월 트랙레코드 확보 시 단계적 레버리지 적용을 검토합니다.

| 단계 | 레버리지 | 진입 조건 | 예상 CAGR | 예상 MDD |
|------|---------|---------|---------|---------|
| 초기 실전 | 1.0x | P23 합격 | 18% | 18% |
| 레버리지 1 | 1.3x | Sharpe > 0.8, 6개월 실전 | ~23% | ~23% |
| 레버리지 2 | 1.5x | Sharpe > 1.0, 12개월 실전 | ~27% | ~27% |
| 레버리지 3 | 2.0x | Sharpe > 1.2, 18개월 실전 | ~36% | ~36% |

> **경고:** 레버리지는 수익과 손실을 동시에 증폭시킵니다. 각 단계 진입 전 반드시 리스크팀 승인을 받으십시오. MDD 36%는 심리적으로 견디기 어려운 수준이며, 실제 운용 자금 규모와 투자자 위험 감내도를 반드시 고려해야 합니다.

---

## 부록 A. 현행 코드베이스 활용 매핑

| NAVIS ALPHA v1.0 컴포넌트 | 활용할 기존 파일 | 작업 유형 |
|--------------------------|---------------|---------|
| Quality Score | `backtesting/factor_backtest/factor_calculator.py` | 확장 |
| Value Score | `backtesting/factor_backtest/factor_calculator.py` | 신규 추가 |
| Momentum Score (12-1) | `factor_calculator.py:calc_momentum_12_1()` | 재사용 |
| PEAD Score | `backtesting/build_earnings_cache.py` | 확장 |
| Catalyst Score | `data/form4/` OpenInsider 캐시 | 재사용 + 개선 |
| ATR 손절 | `risk_team/core/risk_manager.py` | 확장 |
| 변동성 타겟팅 | `risk_team/core/position_sizer.py` | 확장 |
| Market Regime Gate | `strategy_engine/market_regime/` | 연동 |
| 백테스트 엔진 | `backtesting/factor_backtest/engine.py` | 수정 |
| 유니버스 필터 | `backtesting/factor_backtest/engine.py:_rebalance()` | 수정 |

---

## 부록 B. 용어 정의

| 용어 | 정의 |
|------|------|
| CAGR | Compound Annual Growth Rate. 연평균 복리 성장률 |
| MDD | Maximum Drawdown. 고점 대비 최대 낙폭 |
| Sharpe | 무위험 수익률 초과 수익 / 변동성. 위험 대비 수익 효율성 |
| Sortino | Sharpe와 유사하나 하방 변동성만 사용. 손실 리스크 집중 측정 |
| PF | Profit Factor. 총 수익 / 총 손실. 1.0 초과 시 수익성 있음 |
| ATR | Average True Range. 일정 기간 평균 실제 변동폭 |
| F-Score | Piotroski F-Score. 재무건전성 0~9점 지표 |
| PEAD | Post-Earnings Announcement Drift. 어닝 서프라이즈 후 주가 드리프트 |
| Accruals | 발생주의 이익과 현금 이익의 차이. 낮을수록 이익 품질 높음 |
| ADV | Average Daily Volume. 일평균 거래대금 |
| Walk-Forward | 훈련 기간으로 최적화한 파라미터를 미래 기간에 적용해 과최적화 검증 |
| In-Sample | 파라미터 최적화에 사용한 기간 |
| Out-of-Sample | 최적화 이후 검증에 사용한 미래 기간 |

---

*문서 종료 | NAVIS ALPHA v1.0 전략 개발 사양서 v1.0*  
*작성: 퀀트 전략팀 | 수신: NAVIS 개발팀 | 2026-05-07*
