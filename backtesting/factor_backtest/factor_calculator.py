"""
NAVIS 팩터 모멘텀 — 팩터 계산 모듈

12-1 크로스섹셔널 모멘텀 (Jegadeesh & Titman, 1993):
  - 과거 12개월 수익률 계산, 최근 1개월 제외 (단기 반전 회피)
  - 상위 10% 매수, 월말 리밸런싱

NAVIS ALPHA v1.0 Multi-Factor Scoring (P24 확정):
  - Quality Score  (0~35): F-Score + ROE + FCF + Accruals
  - Value Score    (0~40): EV/EBITDA(48%) + P/FCF(32%) + P/B(20%) — 섹터 상대
  - Momentum Score (0~25): 12-1 가격 모멘텀 크로스섹셔널 정규화
  - Catalyst Score (0~0):  Form4 데이터 확보 전까지 비활성
  - Composite      (0~100): 위 합산

Layer 3 — Value Trap 하드 필터 (passes_value_trap_filter):
  일반 섹터: ROE_2yr > -0.02, FCF/Assets_2yr > -0.02, D/E < 3.0
  경기순환:  ROE_2yr > -0.10, FCF/Assets_2yr > -0.05, D/E < 3.0

Layer 3 — 성장 필터 (passes_growth_filter):
  rev_cagr_3yr ≥ -0.05 (구조적 매출 감소 종목 제거)

진입 거부 필터 (MAX_ATR_RATIO = 0.05):
  ATR/종가 > 5% 종목 진입 거부 (과고변동성 종목 필터)
  인트라-피리어드 스탑은 없음 — 청산은 월간 리밸런싱 탈락 시에만.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional


def calc_momentum_12_1(daily_df: pd.DataFrame, as_of_date) -> Optional[float]:
    """
    12-1 모멘텀: (t-252일 ~ t-21일) 구간 수익률.
    최근 1개월(t-21 ~ t) 제외 — 단기 반전 회피.

    Args:
        daily_df:    종목 일봉 DataFrame (index=date, columns=[open,high,low,close,volume])
        as_of_date:  계산 기준일 (월말)

    Returns:
        float 수익률, 데이터 부족 시 None
    """
    if as_of_date not in daily_df.index:
        # ffill로 가장 가까운 이전 거래일 찾기
        loc = daily_df.index.searchsorted(as_of_date, side="right") - 1
        if loc < 0:
            return None
        idx = loc
    else:
        idx = daily_df.index.get_loc(as_of_date)

    if idx < 252:
        return None

    price_t21  = daily_df.iloc[idx - 21]["close"]
    price_t252 = daily_df.iloc[idx - 252]["close"]

    if price_t252 <= 0 or price_t21 <= 0:
        return None

    return float(price_t21 / price_t252) - 1.0


def calc_avg_dollar_volume(daily_df: pd.DataFrame, as_of_date, window: int = 21) -> float:
    """
    최근 N거래일 평균 달러 거래량 (유동성 필터용).

    Args:
        daily_df:   종목 일봉 DataFrame
        as_of_date: 기준일
        window:     거래일 수 (기본 21)

    Returns:
        float (달러 거래량 평균), 데이터 부족 시 0.0
    """
    if as_of_date not in daily_df.index:
        loc = daily_df.index.searchsorted(as_of_date, side="right") - 1
        if loc < 0:
            return 0.0
        idx = loc
    else:
        idx = daily_df.index.get_loc(as_of_date)

    if idx < window:
        return 0.0

    window_df = daily_df.iloc[idx - window: idx]
    return float((window_df["close"] * window_df["volume"]).mean())


def _percentile_rank(value: float, peer_values: list) -> float:
    """
    value가 peer_values 내에서 차지하는 백분위 (0.0~1.0).

    피어보다 낮은 값의 비율을 반환. 피어 수가 0이거나 value가 NaN이면 0.5 반환.
    value 자신이 peer_values에 포함되어 있어도 정확히 동작함.
    """
    if value is None or not np.isfinite(value):
        return 0.5
    valid = [v for v in peer_values if v is not None and np.isfinite(v)]
    if not valid:
        return 0.5
    n_below = sum(1 for v in valid if v < value)
    return n_below / len(valid)


def calc_quality_score(
    fundamentals: dict,
    sector_peers: dict,
) -> float:
    """
    Quality Score (0~35점). NAVIS ALPHA v1.0 Layer 2.

    Args:
        fundamentals: 종목 재무 지표
            f_score     : Piotroski F-Score 0~9
            roe         : Return on Equity (소수, e.g. 0.15 = 15%)
            fcf_yield   : FCF / Total Assets
            net_income  : 당기순이익
            cfo         : 영업현금흐름 (Operating Cash Flow)
            total_assets: 총자산
        sector_peers: 섹터 내 동일 지표 값 리스트
            roe         : list[float]
            fcf_yield   : list[float]
            accruals    : list[float]  # (net_income - cfo) / total_assets 기계산값

    Returns:
        float 0~35
    """
    # F-Score (0~15점): 연속 정규화
    f_score = fundamentals.get("f_score") or 0
    f_score_pts = np.clip(f_score / 9, 0.0, 1.0) * 15

    # ROE 섹터 상대 순위 (0~8점)
    roe = fundamentals.get("roe")
    if roe is not None and np.isfinite(roe):
        roe_pts = _percentile_rank(roe, sector_peers.get("roe", [])) * 8
    else:
        roe_pts = 0.0

    # FCF/Assets 섹터 상대 순위 (0~7점)
    fcf_yield = fundamentals.get("fcf_yield")
    if fcf_yield is not None and np.isfinite(fcf_yield):
        fcf_pts = _percentile_rank(fcf_yield, sector_peers.get("fcf_yield", [])) * 7
    else:
        fcf_pts = 0.0

    # Accruals (0~5점): 낮을수록 이익 품질 높음 → 1 - percentile
    net_income   = fundamentals.get("net_income")
    cfo          = fundamentals.get("cfo")
    total_assets = fundamentals.get("total_assets")
    if (net_income is not None and cfo is not None
            and total_assets is not None and total_assets != 0
            and np.isfinite(net_income) and np.isfinite(cfo) and np.isfinite(total_assets)):
        accruals     = (net_income - cfo) / total_assets
        accruals_pts = (1 - _percentile_rank(accruals, sector_peers.get("accruals", []))) * 5
    else:
        accruals_pts = 0.0

    return float(f_score_pts + roe_pts + fcf_pts + accruals_pts)


def calc_value_score(
    fundamentals: dict,
    sector_peers: dict,
) -> float:
    """
    Value Score (0~40점). 섹터 내 상대 밸류에이션. NAVIS ALPHA v1.0 P21 확정.

    P21 ablation 결과: Value 제거 시 CAGR 0.29%로 붕괴 → 핵심 알파 소스.
    배점을 25 → 40으로 상향, 가중치: EV/EBITDA 48%, P/FCF 32%, P/B 20%.

    Args:
        fundamentals: 종목 밸류에이션 지표
            ev_ebitda: EV / EBITDA
            p_fcf    : Price / Free Cash Flow
            p_b      : Price / Book Value
        sector_peers: 섹터 내 동일 지표 값 리스트
            ev_ebitda: list[float]
            p_fcf    : list[float]
            p_b      : list[float]

    Returns:
        float 0~40
    """
    # EV/EBITDA (0~19.2점): 낮을수록 저평가 → 1 - percentile
    ev_ebitda = fundamentals.get("ev_ebitda")
    if ev_ebitda is not None and np.isfinite(ev_ebitda) and ev_ebitda > 0:
        ev_ebitda_pct = 1 - _percentile_rank(ev_ebitda, sector_peers.get("ev_ebitda", []))
    else:
        ev_ebitda_pct = 0.0

    # Price/FCF (0~12.8점): 낮을수록 저평가 → 1 - percentile
    p_fcf = fundamentals.get("p_fcf")
    if p_fcf is not None and np.isfinite(p_fcf) and p_fcf > 0:
        pfcf_pct = 1 - _percentile_rank(p_fcf, sector_peers.get("p_fcf", []))
    else:
        pfcf_pct = 0.0

    # P/B (0~8점): 낮을수록 저평가 → 1 - percentile
    p_b = fundamentals.get("p_b")
    if p_b is not None and np.isfinite(p_b) and p_b > 0:
        pb_pct = 1 - _percentile_rank(p_b, sector_peers.get("p_b", []))
    else:
        pb_pct = 0.0

    return float((ev_ebitda_pct * 0.48 + pfcf_pct * 0.32 + pb_pct * 0.20) * 40)


# ── P21 확정: 경기순환 섹터 분류 ─────────────────────────────────────────────
CYCLICAL_SECTORS = {"Energy", "Materials", "Industrials", "Consumer Discretionary"}


def passes_value_trap_filter(fundamentals: dict, sector: str) -> bool:
    """
    Value Trap 하드 필터. NAVIS ALPHA v1.0 Layer 3.

    저PBR·저EV 종목이 구조적 쇠퇴 기업(Value Trap)인지 걸러냄.
    2년 평균 사용: TTM 단독 사용 시 COVID 저점에서 경기순환주를 과도 제거함.

    Args:
        fundamentals:
            debt_equity   : Debt / Equity (총부채 / 자기자본)
            roe_2yr       : 최근 2개년 평균 ROE
            fcf_yield_2yr : 최근 2개년 평균 FCF / Total Assets
        sector: GICS 섹터 문자열

    Returns:
        True(통과) / False(탈락)
    """
    de = fundamentals.get("debt_equity")
    if de is not None and np.isfinite(de) and de >= 3.0:
        return False

    if sector in CYCLICAL_SECTORS:
        roe_threshold = -0.10
        fcf_threshold = -0.05
    else:
        roe_threshold = -0.02
        fcf_threshold = -0.02

    roe_2yr = fundamentals.get("roe_2yr")
    if roe_2yr is not None and np.isfinite(roe_2yr) and roe_2yr < roe_threshold:
        return False

    fcf_2yr = fundamentals.get("fcf_yield_2yr")
    if fcf_2yr is not None and np.isfinite(fcf_2yr) and fcf_2yr < fcf_threshold:
        return False

    return True


def passes_growth_filter(fundamentals: dict) -> bool:
    """
    성장 필터. NAVIS ALPHA v1.0 Layer 3 (P22-A 추가).

    3년 매출 CAGR ≥ -5% 조건. 구조적 매출 감소 기업(CPB 유형) 제거.
    데이터 없으면 통과(보수적 접근).

    Args:
        fundamentals:
            revenue_cagr_3yr: 최근 3개년 매출 CAGR (소수, e.g. -0.03 = -3%)

    Returns:
        True(통과) / False(탈락)
    """
    rev_cagr = fundamentals.get("revenue_cagr_3yr")
    if rev_cagr is None or not np.isfinite(rev_cagr):
        return True
    return rev_cagr >= -0.05


def calc_pead_score(
    symbol: str,
    as_of_date,
    earnings_cache,
    lookback_days: int = 90,
) -> float:
    """
    PEAD (Post-Earnings Announcement Drift) Score (0~13점).

    P19에서는 0점 반환 (스텁). P20에서 어닝 서프라이즈 데이터 파이프라인 완성 후 구현.

    Args:
        symbol:        종목 심볼
        as_of_date:    기준일
        earnings_cache: 어닝 캐시 객체 (P20에서 활성화)
        lookback_days: 최근 N일 이내 어닝 발표만 반영

    Returns:
        float 0~13 (현재 항상 0.0)
    """
    return 0.0


# ── ATR 진입 거부 필터 ────────────────────────────────────────────────────────
MAX_ATR_RATIO = 0.05   # ATR/종가 > 5% 종목 진입 거부 (P21 확정)


def calc_atr_ratio(daily_df: pd.DataFrame, as_of_date, window: int = 14) -> Optional[float]:
    """
    ATR(14일) / 종가 비율. MAX_ATR_RATIO 초과 시 진입 거부.

    인트라-피리어드 스탑과 무관 — 진입 자체를 막는 필터.
    (인트라-피리어드 스탑은 P24에서 영구 제거됨)

    Returns:
        float 비율(e.g. 0.03 = 3%), 데이터 부족 시 None
    """
    if as_of_date not in daily_df.index:
        loc = daily_df.index.searchsorted(as_of_date, side="right") - 1
        if loc < 0:
            return None
        idx = loc
    else:
        idx = daily_df.index.get_loc(as_of_date)

    if idx < window:
        return None

    window_df = daily_df.iloc[idx - window + 1: idx + 1]
    high = window_df["high"].values
    low  = window_df["low"].values
    close_prev = daily_df.iloc[idx - window: idx]["close"].values

    tr = np.maximum(high - low, np.maximum(
        np.abs(high - close_prev),
        np.abs(low  - close_prev),
    ))
    atr   = tr.mean()
    price = daily_df.iloc[idx]["close"]

    if price <= 0:
        return None
    return float(atr / price)


def calc_composite_score(
    quality: float,
    value: float,
    momentum: float,
    catalyst: float,
) -> float:
    """
    4팩터 통합 점수 (0~100점). NAVIS ALPHA v1.0 P24 확정 배점.

    Args:
        quality:  Quality Score  0~35
        value:    Value Score    0~40  (P21 상향: 핵심 알파 소스)
        momentum: Momentum Score 0~25  (가격 12-1 정규화)
        catalyst: Catalyst Score 0~0   (Form4 대기 — 현재 비활성)

    Returns:
        float 0~100
    """
    return float(np.clip(quality + value + momentum + catalyst, 0.0, 100.0))


def rank_momentum(
    scores: dict[str, float],
    top_pct: float = 0.20,
) -> list[str]:
    """
    모멘텀 점수 딕셔너리에서 상위 top_pct 종목 리스트 반환.

    Args:
        scores:  {symbol: momentum_score}
        top_pct: 상위 선택 비율 (0.20 = 상위 20%)

    Returns:
        선택된 종목 리스트 (모멘텀 내림차순 정렬)
    """
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    n_top = max(1, int(len(ranked) * top_pct))
    return [sym for sym, _ in ranked[:n_top]]
