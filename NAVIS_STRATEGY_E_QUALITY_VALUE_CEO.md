# NAVIS 전략 E — Quality + CEO Catalyst
**작성일**: 2026-05-02  
**최종 업데이트**: 2026-05-03 (P17 부분합격 → V-Score 제거, F-Score 기준 ≥6 확정)  
**작성자**: 퀀트 트레이더 (Claude)  
**승인**: 대표님  
**대상**: 개발 1팀  
**연관 문서**: NAVIS_QUANT_ROADMAP.md, NAVIS_DEV_INSTRUCTIONS.md, NAVIS_P18_IMPLEMENTATION.md  
**착수 조건**: Phase 3 (V4 페이퍼 트레이딩) 합격 후 (P18 백테스트는 병행 진행 중)

---

## 1. 전략 철학 — 왜 이 접근인가

Phase 2에서 시도한 5가지 전략은 모두 **가격 패턴**에 기반했습니다.  
갭, 신고가, 모멘텀 팩터, 스프레드 — 전부 시장 구조에 종속된 신호였고, 추세장에서 전부 실패했습니다.

전략 E는 근본적으로 다른 질문에서 출발합니다:

> **"재무제표가 좋은데도 주가가 낮은 기업이 있다면, 그 괴리는 언젠가 해소된다."**

이것이 **비체계적 위험(Idiosyncratic Risk)**의 핵심입니다.  
시장 전체의 흐름(체계적 위험)이 아닌, 특정 기업에만 적용되는 일시적 저평가를 포착하는 것입니다.

### V4와의 근본적 차이

| 항목 | V4 Multi-Day | Quality + CEO Catalyst |
|------|-------------|------------------------|
| 신호 원천 | 가격 이벤트 (갭업) | 기업 본질 가치 |
| 시간 지평 | 1~10거래일 | 3~6개월 |
| 엣지 | 기관 연속 매수 (PEAD) | 재무 건전성 + 내부자 매수 촉매 |
| 빈도 | 연 3건 | 연 20~50건 |
| 시장 의존성 | 강세장 신호 (레짐 필터) | 개별 기업 품질 (시장 독립적) |
| 역할 | 위성 전략 (고PF, 저빈도) | 주 전략 (중PF, 고빈도) |

---

## 2. 전략 구조

### 2-1. 2단계 스크리닝 시스템

> **P17 업데이트 (2026-05-03)**: V-Score(저평가 필터)가 MDD를 7%p 악화시키는 Value Trap 현상 확인.  
> 2단계 Value 필터 **영구 제거**. F-Score 기준 **≥6**으로 확정.

```
[1단계: Quality 필터]  →  [2단계: Catalyst 확인]
  Piotroski F-Score          CEO 내부자 매수 신호
      ≥ 6점                  (진입 우선순위 결정)
```

### 2-2. 유니버스 정의

**대상 조건:**
- 시가총액: $500M ~ $5B (스몰~미드캡)
- 상장: 미국 NYSE / NASDAQ
- 최소 유동성: 20일 평균 거래대금 ≥ $2M/일
- 최소 데이터: 상장 후 4개 분기 이상 재무제표 보유

**제외 조건:**
- 금융업 (Financial Services): P/B 비교 불가, 레버리지 구조 상이
- 부동산 리츠 (REITs): FFO 기반 평가, 일반 PER 부적합
- 바이오테크 (무수익): Piotroski 수익성 점수 불리
- 중국계 미국 상장 (ADR): 재무 신뢰성 리스크

**예상 유니버스 규모**: 약 800~1,200종목 (분기별 재구성)

---

## 3. 1단계 — Quality 필터: Piotroski F-Score

### 개요

Joseph Piotroski (2000) 논문에서 제안한 9개 이진 신호 합산 점수 (0~9점).  
점수가 높을수록 재무 건전성이 높은 기업.  
**합격 기준: F-Score ≥ 7점**

### 9개 신호 상세

**그룹 A — 수익성 (4개 신호)**

| 신호 | 계산식 | 합격 조건 |
|------|--------|---------|
| F1: ROA | 당기순이익 / 기초 총자산 | ROA > 0 |
| F2: 영업현금흐름 | CFO (영업활동 현금흐름) | CFO > 0 |
| F3: ROA 변화 | 당기 ROA − 전기 ROA | ΔROAyoy > 0 |
| F4: 발생주의 품질 | CFO / 총자산 vs ROA | CFO/자산 > ROA |

> F4 해석: 이익이 현금 기반인지 회계 발생 기반인지 구분. CFO가 순이익보다 높으면 이익의 질이 높다.

**그룹 B — 재무 건전성 (3개 신호)**

| 신호 | 계산식 | 합격 조건 |
|------|--------|---------|
| F5: 레버리지 변화 | 장기부채/총자산 당기 vs 전기 | 비율 감소 |
| F6: 유동성 변화 | 유동비율 당기 vs 전기 | 비율 증가 |
| F7: 주식 희석 | 최근 1년 신규 주식 발행 여부 | 신규 발행 없음 |

> F7 해석: 신주 발행은 EPS 희석 + 경영진이 자금 조달이 필요한 상태임을 시사.

**그룹 C — 운영 효율성 (2개 신호)**

| 신호 | 계산식 | 합격 조건 |
|------|--------|---------|
| F8: 매출총이익률 | 매출총이익/매출 당기 vs 전기 | 비율 증가 |
| F9: 자산회전율 | 매출/총자산 당기 vs 전기 | 비율 증가 |

**합격 기준: F-Score ≥ 6점** (P17-3A 최적 결과 기준. F≥7 대비 CAGR +3.3%, PF +0.16)

### F-Score 계산 구현

```python
def calculate_piotroski_fscore(fundamentals: dict) -> int:
    """
    fundamentals: {
        'roa_current':       float,  # 당기 ROA
        'roa_prior':         float,  # 전기 ROA
        'cfo':               float,  # 당기 영업현금흐름
        'total_assets':      float,  # 당기 총자산
        'lt_debt_ratio_cur': float,  # 당기 장기부채/총자산
        'lt_debt_ratio_pri': float,  # 전기 장기부채/총자산
        'current_ratio_cur': float,  # 당기 유동비율
        'current_ratio_pri': float,  # 전기 유동비율
        'shares_issued':     bool,   # 최근 1년 신주 발행 여부
        'gross_margin_cur':  float,  # 당기 매출총이익률
        'gross_margin_pri':  float,  # 전기 매출총이익률
        'asset_turnover_cur':float,  # 당기 자산회전율
        'asset_turnover_pri':float,  # 전기 자산회전율
    }
    """
    score = 0

    # 그룹 A: 수익성
    if fundamentals['roa_current'] > 0:                              score += 1  # F1
    if fundamentals['cfo'] > 0:                                      score += 1  # F2
    if fundamentals['roa_current'] > fundamentals['roa_prior']:      score += 1  # F3
    cfo_ratio = fundamentals['cfo'] / fundamentals['total_assets']
    if cfo_ratio > fundamentals['roa_current']:                      score += 1  # F4

    # 그룹 B: 재무 건전성
    if fundamentals['lt_debt_ratio_cur'] < fundamentals['lt_debt_ratio_pri']:  score += 1  # F5
    if fundamentals['current_ratio_cur'] > fundamentals['current_ratio_pri']:  score += 1  # F6
    if not fundamentals['shares_issued']:                                       score += 1  # F7

    # 그룹 C: 운영 효율성
    if fundamentals['gross_margin_cur'] > fundamentals['gross_margin_pri']:    score += 1  # F8
    if fundamentals['asset_turnover_cur'] > fundamentals['asset_turnover_pri']:score += 1  # F9

    return score
```

---

## 4. ~~2단계 — Value 필터: 상대 저평가 확인~~ ❌ 폐기 (P17 결과)

> **폐기 사유 (2026-05-03)**:  
> P17-2 결과: V-Score 필터 추가 시 MDD 40.26% (F≥7 단독 33.16% 대비 +7.1%p 악화).  
> 원인: 저평가 필터가 Value Trap 종목(약세장에 더 크게 하락하는 종목)을 선별하는 역효과.  
> **결론: V-Score 필터는 이 전략의 구조적 적이다. 영구 제거.**

---

## 5. 2단계 — CEO Catalyst (보조 시스템)

### 역할 정의

CEO Catalyst는 **주 전략이 아닙니다.**  
Quality-Value 스크리닝을 통과한 종목에 한해 **진입 타이밍을 최적화**하는 보조 신호입니다.

```
Quality 통과(F≥6) → CEO Catalyst 신호 있음 → 우선 진입 (1순위)
Quality 통과(F≥6) → CEO Catalyst 신호 없음 → 일반 진입 (2순위, 자본 여유 시)
```

### 감시 대상 신호

**티어 1 — 강한 신호 (즉시 우선 진입)**

| 신호 | 소스 | 의미 |
|------|------|------|
| CEO 내부자 매수 | SEC EDGAR Form 4 | 경영진이 자사주 직접 매수 — 가장 강한 강세 신호 |
| 자사주 매입 발표 | SEC 8-K 공시 | 기업이 저평가 인식, 주주 환원 의지 |
| 주요 계약/파트너십 | IR 보도자료, 8-K | 매출 성장 가시성 확보 |

**티어 2 — 보조 신호 (다른 신호와 결합 시 유효)**

| 신호 | 소스 | 의미 |
|------|------|------|
| CEO LinkedIn 활동 급증 | LinkedIn API | 신제품/파트너십 발표 준비 가능성 |
| CEO X(트위터) 기술적 언급 | X API | 제품 로드맵 자신감 표현 |
| 컨퍼런스 발표 일정 | IR 캘린더 | 투자자 커뮤니케이션 강화 기간 |

### ⚠️ CEO Catalyst 구현 우선순위

Phase 4 초기에는 티어 1(SEC 공시 기반)만 구현합니다.  
LinkedIn/X API는 접근 제한 및 비용 이슈가 있으므로 Phase 4 안정화 후 별도 검토합니다.

**P17 (완료)**: Quality-Value 단독 검증 → 부분합격 (CAGR 8.98%, PF 1.37)  
**P18-A (진행 중)**: SEC Form 4 내부자 매수 필터 추가 → 목표 CAGR ≥ 12%  
**P18-B (병행)**: F≥6 + 6개월 모멘텀 결합 → 비교군  
**P18 합격 후**: LinkedIn/X 모니터링 시스템 추가 (선택적 고도화)

---

## 6. 진입·청산 규칙

### 진입 규칙

```
1. 매월 말 (월 1회) 또는 분기 재무제표 발표 후: 전 유니버스 스크리닝 실행
2. F-Score ≥ 6 → 후보 목록 생성 (P17 최적 기준)
3. CEO Catalyst 신호(Form 4 내부자 매수 ≥$100K) 있는 종목 → 1순위 진입
4. 신호 없는 종목 → 2순위 (자본 여유 있을 때 진입)
5. 진입: 스크리닝 완료 다음 거래일 시가
6. 포지션 크기: 최대 자본의 7% (분산 목적)
7. 최대 동시 보유: 15종목 (→ 최대 자본의 105% = 레버리지 없이 15 × 7%)
```

### 청산 규칙 (3가지 조건 중 먼저 도달하는 쪽)

```
[조건 1] 목표 달성 (밸류 정상화):
  P/E, P/B, EV/EBITDA 모두 섹터 중간값(50th percentile) 도달
  → 저평가 해소 = 전략 목표 달성 → 즉시 청산

[조건 2] 손절 (밸류 트랩 방지):
  진입가 대비 -15% 도달
  → 재무제표가 좋아도 시장이 더 싸게 볼 이유가 있을 수 있음 → 무조건 손절

[조건 3] 시간 청산 (기회비용 방지):
  진입 후 6개월(약 126거래일) 경과
  → 저평가 해소가 지연되면 자본을 더 좋은 기회에 배분
```

### 포지션 관리 규칙

| 항목 | 규칙 |
|------|------|
| 단일 종목 최대 비중 | 7% |
| 동일 섹터 최대 비중 | 25% (특정 섹터 집중 방지) |
| 현금 최소 유보 | 10% (긴급 상황 대비) |
| V4와 자본 분리 | V4는 별도 버킷 (30~50%), QV는 나머지 |
| 재스크리닝 | 분기마다 전 포지션 F-Score 재검증 |

---

## 7. 백테스트 설계

### 데이터 요구사항

| 데이터 | 소스 | 업데이트 주기 |
|------|------|-----------|
| 재무제표 (분기) | Polygon.io 또는 Financials API | 분기 |
| 주가 일봉 | 기존 시스템 (이미 보유) | 일일 |
| 시가총액 | Polygon.io | 일일 |
| 섹터 분류 | GICS (S&P 기준) | 정적 |
| 주식 수 변동 이력 | Polygon.io | 분기 |

> ⚠️ **생존 편향 주의**: 백테스트 유니버스는 해당 시점 기준으로 상장되어 있던 종목만 포함해야 합니다. 현재 S&P 500 구성종목 기준으로 역산하면 생존 편향이 심각하게 발생합니다. Point-in-time 데이터 필수.

### 테스트 기간

```
기본 백테스트: 2016-01-01 ~ 2026-04-30 (10년)
이유: 팩터 모멘텀(P15)의 교훈 — 2021~2024 추세장만 테스트하면 불충분
      2018년 금리 인상기, 2020년 COVID 급락 포함 필수
```

### 테스트 시나리오 (순서대로)

**P17-1: Quality 단독** — F-Score ≥ 7만 적용, Value 필터 없음  
→ 기준선 파악: Quality 단독으로 얼마나 되는가

**P17-2: Quality-Value 결합** — F-Score ≥ 7 + Valuation Score ≥ 2  
→ 핵심 검증: 저평가 필터가 실제 알파를 추가하는가

**P17-3: 파라미터 민감도** — F-Score 기준을 6, 7, 8로 변경 / Valuation 기준 변경  
→ 과최적화 방지: 특정 파라미터에만 좋은 결과인지 확인

---

## 8. 구현 지시서

### 신규 모듈 구조

```
backtesting/
└── quality_value_backtest/
    ├── __init__.py
    ├── engine.py                 # 메인 백테스트 엔진
    ├── fundamental_screener.py   # Piotroski F-Score 계산
    ├── valuation_screener.py     # 상대 저평가 계산
    ├── universe_builder.py       # 유니버스 필터링 (시총, 유동성, 섹터 제외)
    └── portfolio_manager.py      # 포지션 진입·청산·재밸런싱
```

```
data/
└── fundamentals/                 # 재무 데이터 캐시
    ├── quarterly/                # 분기별 재무제표
    └── point_in_time/            # 생존 편향 방지 시점 데이터
```

---

### Step 1: `UniverseBuilder` — 유니버스 필터링

**파일**: `backtesting/quality_value_backtest/universe_builder.py`

```python
class UniverseBuilder:
    """
    매 분기 말 기준으로 투자 가능한 스몰~미드캡 유니버스를 구성합니다.
    생존 편향 방지: as_of_date 기준 시점 데이터만 사용.
    """

    EXCLUDED_SECTORS = {
        'Financial Services',
        'Real Estate',
    }

    def build(self, as_of_date: str) -> pd.DataFrame:
        """
        as_of_date: 유니버스 구성 기준일 ('YYYY-MM-DD')
        반환: 조건을 통과한 종목 DataFrame
              컬럼: symbol, market_cap, sector, avg_daily_volume
        """
        df = self._load_all_stocks(as_of_date)

        # 시가총액 $500M ~ $5B
        df = df[(df['market_cap'] >= 500_000_000) &
                (df['market_cap'] <= 5_000_000_000)]

        # 섹터 제외
        df = df[~df['sector'].isin(self.EXCLUDED_SECTORS)]

        # 최소 유동성: 20일 평균 거래대금 $2M 이상
        df = df[df['avg_daily_volume_usd_20d'] >= 2_000_000]

        # 재무 데이터 최소 4분기 보유
        df = df[df['quarters_available'] >= 4]

        return df.reset_index(drop=True)
```

---

### Step 2: `FundamentalScreener` — Piotroski F-Score

**파일**: `backtesting/quality_value_backtest/fundamental_screener.py`

```python
@dataclass
class FundamentalData:
    """단일 종목의 2개년 재무 데이터"""
    symbol:             str
    # 수익성
    net_income_cur:     float
    net_income_pri:     float
    total_assets_cur:   float
    total_assets_pri:   float
    cfo_cur:            float   # 영업현금흐름
    # 재무 건전성
    lt_debt_cur:        float
    lt_debt_pri:        float
    current_assets_cur: float
    current_assets_pri: float
    current_liab_cur:   float
    current_liab_pri:   float
    shares_outstanding_cur: float
    shares_outstanding_pri: float
    # 운영 효율성
    revenue_cur:        float
    revenue_pri:        float
    gross_profit_cur:   float
    gross_profit_pri:   float


class FundamentalScreener:

    def score(self, fd: FundamentalData) -> int:
        """Piotroski F-Score 계산. 0~9점 반환."""
        s = 0

        roa_cur = fd.net_income_cur / fd.total_assets_cur
        roa_pri = fd.net_income_pri / fd.total_assets_pri
        cfo_ratio = fd.cfo_cur / fd.total_assets_cur

        # A: 수익성
        if roa_cur > 0:                         s += 1  # F1
        if fd.cfo_cur > 0:                      s += 1  # F2
        if roa_cur > roa_pri:                   s += 1  # F3
        if cfo_ratio > roa_cur:                 s += 1  # F4  (현금이익 > 회계이익)

        # B: 재무 건전성
        lev_cur = fd.lt_debt_cur / fd.total_assets_cur
        lev_pri = fd.lt_debt_pri / fd.total_assets_pri
        if lev_cur < lev_pri:                   s += 1  # F5  (부채 감소)

        cr_cur = fd.current_assets_cur / fd.current_liab_cur
        cr_pri = fd.current_assets_pri / fd.current_liab_pri
        if cr_cur > cr_pri:                     s += 1  # F6  (유동성 개선)

        if fd.shares_outstanding_cur <= fd.shares_outstanding_pri:
                                                s += 1  # F7  (희석 없음)

        # C: 운영 효율성
        gm_cur = fd.gross_profit_cur / fd.revenue_cur if fd.revenue_cur else 0
        gm_pri = fd.gross_profit_pri / fd.revenue_pri if fd.revenue_pri else 0
        if gm_cur > gm_pri:                     s += 1  # F8

        at_cur = fd.revenue_cur / fd.total_assets_cur
        at_pri = fd.revenue_pri / fd.total_assets_pri
        if at_cur > at_pri:                     s += 1  # F9

        return s

    def passes(self, fd: FundamentalData, min_score: int = 6) -> bool:
        return self.score(fd) >= min_score
```

---

### ~~Step 3: `ValuationScreener` — 상대 저평가~~ ❌ 폐기

> P17 결과로 ValuationScreener 모듈 불필요. 기존 코드는 보관하되 엔진에서 호출하지 않음.

---

### Step 4: `PortfolioManager` — 포지션 관리

**파일**: `backtesting/quality_value_backtest/portfolio_manager.py`

```python
@dataclass
class Position:
    symbol:          str
    entry_date:      str
    entry_price:     float
    shares:          int
    cost_basis:      float    # 진입 시 투자금
    sector:          str
    fscore_at_entry:    int
    catalyst_at_entry:  bool = False   # CEO Form 4 매수 신호 유무
    max_hold_days:   int = 126      # 6개월
    stop_loss_pct:   float = 0.15   # -15%


class PortfolioManager:
    """
    Quality-Value 포트폴리오 포지션 관리.
    월별 스크리닝 결과를 받아 진입/청산을 결정합니다.
    """

    MAX_POSITION_PCT   = 0.07   # 단일 종목 최대 7%
    MAX_SECTOR_PCT     = 0.25   # 동일 섹터 최대 25%
    MIN_CASH_RESERVE   = 0.10   # 현금 최소 10% 유보

    def should_exit(self, pos: Position, current_price: float,
                    current_date: str, current_valuation: ValuationData,
                    sector_df: pd.DataFrame) -> tuple[bool, str]:
        """
        청산 조건 검사.
        반환: (청산 여부, 청산 유형)
        """
        hold_days = self._trading_days_between(pos.entry_date, current_date)
        pl_pct = (current_price - pos.entry_price) / pos.entry_price

        # 조건 2: 손절 -15%
        if pl_pct <= -self.stop_loss_pct:
            return True, "STOP_LOSS"

        # 조건 3: 최대 보유 기간 (6개월)
        if hold_days >= pos.max_hold_days:
            return True, "MAX_HOLD"

        # 조건 1: 밸류 정상화 (섹터 중간값 도달)
        if self._is_fairly_valued(current_valuation, sector_df):
            return True, "VALUE_REALIZED"

        return False, ""

    def _is_fairly_valued(self, val: ValuationData,
                           sector_df: pd.DataFrame) -> bool:
        """3개 지표 모두 섹터 50th percentile 이상 도달 시 True"""
        for metric in ['pe', 'pb', 'ev_ebitda']:
            v = getattr(val, metric)
            if pd.isna(v) or v <= 0:
                continue
            peers = sector_df[metric].dropna()
            peers = peers[peers > 0]
            percentile = (peers < v).sum() / len(peers)
            if percentile < 0.50:   # 아직 하위 50% → 아직 저평가
                return False
        return True
```

---

### Step 5: 메인 엔진 `QualityValueEngine`

**파일**: `backtesting/quality_value_backtest/engine.py`

```python
@dataclass
class QualityValueConfig:
    start_date:          str   = '2016-01-01'
    end_date:            str   = '2026-04-30'
    min_fscore:          int   = 6       # P17-3A 최적 기준
    # min_vscore 제거 — P17에서 역효과 확인, ValuationScreener 사용 안 함
    use_catalyst_filter: bool  = True    # P18-A: Form 4 내부자 매수 필터
    max_hold_days:       int   = 126     # 6개월
    stop_loss_pct:       float = 0.15
    max_position_pct:    float = 0.07
    max_sector_pct:      float = 0.25
    min_cash_reserve:    float = 0.10
    slippage_pct:        float = 0.001   # 0.1% 슬리피지
    rescreen_frequency:  str   = 'monthly'   # 'monthly' 또는 'quarterly'


class QualityValueEngine:
    """
    Quality-Value 전략 백테스트 메인 엔진.

    동작 흐름:
    1. 매월 말: 유니버스 전체 스크리닝 (F-Score + Valuation)
    2. 통과 종목 중 미보유 종목 → 다음 거래일 시가 진입
    3. 매 거래일: 기존 포지션 청산 조건 확인
    4. 분기마다: 기존 포지션 F-Score 재검증 (품질 악화 시 청산)
    """

    def run(self) -> BacktestResult:
        portfolio = {}      # symbol → Position
        cash = self.initial_capital
        trades = []

        for date in self.trading_days:
            # 1. 월말 스크리닝
            if self._is_month_end(date):
                candidates = self._screen_universe(date)
                new_entries = self._select_entries(candidates, portfolio, cash)
                for symbol in new_entries:
                    pos, cash = self._enter_position(symbol, date, cash)
                    portfolio[symbol] = pos

            # 2. 매일: 청산 조건 확인
            for symbol, pos in list(portfolio.items()):
                should_exit, reason = self.pm.should_exit(
                    pos, self._get_price(symbol, date), date,
                    self._get_valuation(symbol, date),
                    self._get_sector_df(pos.sector, date)
                )
                if should_exit:
                    pnl, cash = self._exit_position(pos, date, cash, reason)
                    trades.append(pnl)
                    del portfolio[symbol]

            # 3. 분기 재검증
            if self._is_quarter_end(date):
                for symbol, pos in list(portfolio.items()):
                    fd = self._get_fundamentals(symbol, date)
                    if self.fs.score(fd) < self.config.min_fscore - 1:
                        pnl, cash = self._exit_position(pos, date, cash,
                                                         "QUALITY_DETERIORATION")
                        trades.append(pnl)
                        del portfolio[symbol]

        return self._compile_results(trades, cash)
```

---

### Step 6: CLI 실행 인터페이스

**파일**: `backtesting/run_quality_value_backtest.py`

```python
parser.add_argument("--min-fscore",      type=int,   default=6,
                    help="최소 Piotroski F-Score (기본 6, P17 최적)")
# --min-vscore 제거됨 (P17 폐기)
parser.add_argument("--catalyst",        action="store_true",
                    help="Form 4 CEO 내부자 매수 필터 활성화 (P18-A)")
parser.add_argument("--momentum",        action="store_true",
                    help="6개월 모멘텀 상위 30% 필터 활성화 (P18-B)")
parser.add_argument("--max-hold",        type=int,   default=126,
                    help="최대 보유 거래일 (기본 126 = 6개월)")
parser.add_argument("--stop-loss",       type=float, default=15.0,
                    help="손절 %% (기본 15.0)")
parser.add_argument("--rescreen",        type=str,   default="monthly",
                    choices=["monthly", "quarterly"],
                    help="스크리닝 주기 (기본 monthly)")
parser.add_argument("--start",           type=str,   default="2016-01-01")
parser.add_argument("--end",             type=str,   default="2026-04-30")
```

---

## 9. 테스트 실행 명령어

```bash
# ── P17 (완료) ─────────────────────────────────────────────────────────────

# P17-3A ★ 최우수 (기준선, 부분합격)
# CAGR 8.98%, MDD 28.81%, PF 1.37
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 \
  --stop-loss 15.0 --max-hold 126 \
  --start 2016-01-01

# ── P18 (진행 중) ──────────────────────────────────────────────────────────

# P18-A: F≥6 + CEO Form 4 내부자 매수 필터 (1순위)
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 --catalyst \
  --stop-loss 15.0 --max-hold 126 \
  --start 2016-01-01

# P18-B: F≥6 + 6개월 모멘텀 상위 30% (2순위)
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 --momentum \
  --stop-loss 15.0 --max-hold 126 \
  --start 2016-01-01
```

---

## 10. 보고 요구사항

각 테스트 완료 후 아래 형식으로 보고:

```
P18-X 결과 보고

[전략 설정]
F-Score 기준: X점 이상
Valuation 기준: 3지표 중 X개 이상
최대 보유: X거래일
손절: -X%

[성과 지표]
CAGR:          X.X%
MDD:           X.X%
Sharpe Ratio:  X.XX
Profit Factor: X.XX
총 거래 수:    X건 (연평균 X건)
승률:          X.X%
평균 보유 기간: X거래일

[연도별 수익률]
2016: X.X%
2017: X.X%
...

[청산 유형 분포]
VALUE_REALIZED:          X건 (X%)
STOP_LOSS:               X건 (X%)
MAX_HOLD:                X건 (X%)
QUALITY_DETERIORATION:   X건 (X%)

[섹터 분포]
상위 5개 섹터: ...

[판단]
합격 / 파라미터 조정 필요 / 실패
```

---

## 11. 합격 기준

| 결과 | 조건 | 다음 행동 |
|------|------|---------|
| **합격** | CAGR ≥ 12% AND MDD ≤ 20% AND PF ≥ 1.20 AND 거래 ≥ 20건/년 | V4 + Quality+Catalyst 통합 포트폴리오 설계 (Phase 5) |
| **부분 합격** | CAGR ≥ 8% AND PF ≥ 1.10 | 추가 필터 조합 후 재검증 (P19) |
| **실패** | 위 조건 미달 | 퀀트 트레이더 재보고 후 방향 결정 |

> **기준 설정 근거**:  
> CAGR 12%+: V4(8~18%)와 결합 시 전체 목표(15~25%) 달성 가능  
> MDD 20%: Quality-Value는 3~6개월 보유 → 단기 전략보다 MDD 여유 허용  
> PF 1.20: 실전 투입 최소 기준 (Phase 2 합격 기준 PF 1.30에서 하향 — 빈도가 높으므로)

---

## 12. CEO Catalyst 시스템 설계 (P18-A)

> P17 부분합격 확인 → P18-A에서 즉시 적용 중입니다.  
> **상세 구현 지시**: `NAVIS_P18_IMPLEMENTATION.md` 참조

### SEC Form 4 내부자 매수 모니터링

```python
class InsiderBuyMonitor:
    """
    SEC EDGAR의 Form 4 (내부자 거래 신고) 실시간 모니터링.
    CEO/CFO/이사회 임원의 매수 신고를 감지합니다.
    """

    # 의미 있는 내부자 매수 조건
    MIN_PURCHASE_USD    = 100_000   # $10만 이상
    ROLES               = {'CEO', 'President', 'Chief Executive Officer',
                           'CFO', 'Director'}
    LOOKBACK_DAYS       = 90        # 최근 90일 내 신고 (P18-A 기준)

    def get_recent_buys(self, symbol: str) -> list[InsiderBuy]:
        """
        반환: 최근 30일 내 CEO/CFO/이사가 $10만 이상 자사주 매수한 기록
        """
        ...
```

**SEC EDGAR API**: `https://data.sec.gov/submissions/{cik}.json` (무료 공개 API)

### 신호 통합 우선순위 로직

```python
def prioritize_candidates(candidates: list[str],
                          insider_monitor: InsiderBuyMonitor) -> list[str]:
    """
    Quality-Value 통과 종목들을 CEO Catalyst 신호 유무로 정렬.
    신호 있는 종목을 먼저 진입.
    """
    tier1 = []  # 내부자 매수 있음
    tier2 = []  # 신호 없음

    for symbol in candidates:
        buys = insider_monitor.get_recent_buys(symbol)
        if buys:
            tier1.append(symbol)
        else:
            tier2.append(symbol)

    return tier1 + tier2  # 티어1 우선, 자본 여유 있으면 티어2도 진입
```

---

*P17 완료 (부분합격). P18-A (Form 4 Catalyst) 및 P18-B (Momentum) 병행 진행 중.*  
*상세 구현 지시서: `NAVIS_P18_IMPLEMENTATION.md`*
