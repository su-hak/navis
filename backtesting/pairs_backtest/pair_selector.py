"""
NAVIS 페어 트레이딩 — 공적분 페어 선정 모듈

선정 기준 (NAVIS_STRATEGY_D_PAIRS_TRADING.md):
  1. 동일 GICS 섹터
  2. 상관계수 > 0.7  (252거래일 일봉 로그 수익률)
  3. Engle-Granger 공적분 검정 p < 0.05
  4. 양 종목 일평균 달러 거래량 $2,000만+

설계 원칙:
  - 공통 거래일 계산은 전체 교집합이 아닌 페어별 교집합으로 수행
    (전체 교집합 시 거래일이 극소가 되어 검정 불가)
  - 공적분 검정 기간: 전체 공통 기간 중 최근 lookback 거래일
"""
from __future__ import annotations

import json
import logging
from itertools import combinations
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

logger = logging.getLogger(__name__)


def find_cointegrated_pairs(
    daily_data: Dict[str, pd.DataFrame],
    sector_map: Dict[str, str],        # {symbol: sector}
    lookback:          int   = 252,    # 공적분 검정 기간 (거래일)
    min_corr:          float = 0.70,   # 최소 상관계수
    coint_pvalue:      float = 0.05,   # 공적분 p-value 상한
    min_dollar_volume: float = 2e7,    # 최소 일평균 달러 거래량
    min_price:         float = 5.0,    # 최소 주가
    as_of_date=None,                   # 기준일 (None = 데이터 최신일)
    cross_sector:      bool  = False,  # True: 섹터 제한 없이 전체 조합
) -> List[dict]:
    """
    공적분 페어 탐색.

    Args:
        daily_data:        {symbol: daily_df}
        sector_map:        {symbol: sector}
        lookback:          공적분 검정 기간 (거래일)
        min_corr:          최소 로그 수익률 상관계수
        coint_pvalue:      EG p-value 상한
        min_dollar_volume: 양 종목 최소 일평균 달러 거래량
        min_price:         최소 주가
        as_of_date:        기준일 (None → 최신)
        cross_sector:      True 시 섹터 무관 전체 조합

    Returns:
        list[dict] — pvalue 오름차순 정렬
    """
    # ── 1. 유효 종목 필터링 ──────────────────────────────────────────────
    valid_symbols = _filter_valid_symbols(
        daily_data, min_dollar_volume, min_price, lookback
    )
    logger.info(
        f"[PairSelector] 유효 종목: {len(valid_symbols)}개 (전체 {len(daily_data)}개 중)"
    )

    if len(valid_symbols) < 2:
        logger.warning("[PairSelector] 유효 종목 부족 — 페어 선정 불가")
        return []

    # ── 2. 섹터별 그룹 구성 ─────────────────────────────────────────────
    if cross_sector:
        pair_groups = [("ALL", valid_symbols)]
    else:
        sector_groups: Dict[str, List[str]] = {}
        for sym in valid_symbols:
            sec = sector_map.get(sym, "Unknown")
            sector_groups.setdefault(sec, []).append(sym)
        pair_groups = list(sector_groups.items())

    total_combo = sum(
        len(lst) * (len(lst) - 1) // 2
        for _, lst in pair_groups if len(lst) >= 2
    )
    logger.info(f"[PairSelector] 총 검정 대상 조합: {total_combo:,}쌍")

    # ── 3. 페어별 공적분 검정 ────────────────────────────────────────────
    results: List[dict] = []
    tested = 0

    for sector, sym_list in pair_groups:
        if len(sym_list) < 2:
            continue
        n_sector_pairs = len(sym_list) * (len(sym_list) - 1) // 2
        logger.info(
            f"[PairSelector] {sector}: {len(sym_list)}종목 → {n_sector_pairs}쌍"
        )

        for sym_a, sym_b in combinations(sym_list, 2):
            tested += 1
            if tested % 500 == 0:
                logger.info(
                    f"[PairSelector] 진행: {tested:,}/{total_combo:,}쌍 | "
                    f"페어 발견: {len(results)}개"
                )

            pair_result = _test_pair(
                sym_a, sym_b, sector,
                daily_data, lookback, min_corr, coint_pvalue
            )
            if pair_result is not None:
                results.append(pair_result)

    logger.info(
        f"[PairSelector] 완료 | 검정: {tested:,}쌍 | "
        f"공적분 페어: {len(results)}개"
    )

    return sorted(results, key=lambda x: x["pvalue"])


def _test_pair(
    sym_a: str,
    sym_b: str,
    sector: str,
    daily_data: Dict[str, pd.DataFrame],
    lookback: int,
    min_corr: float,
    coint_pvalue: float,
) -> Optional[dict]:
    """
    단일 페어 공적분 검정.
    통과 시 dict 반환, 실패 시 None.
    """
    df_a = daily_data.get(sym_a)
    df_b = daily_data.get(sym_b)
    if df_a is None or df_b is None:
        return None

    # 페어 공통 거래일 (각자 인덱스 교집합)
    common_idx = df_a.index.intersection(df_b.index)
    if len(common_idx) < lookback:
        return None

    # 최근 lookback 거래일만 사용
    common_idx = common_idx[-lookback:]

    close_a = df_a.loc[common_idx, "close"].values.astype(float)
    close_b = df_b.loc[common_idx, "close"].values.astype(float)

    # 유효 가격 체크
    if np.any(close_a <= 0) or np.any(close_b <= 0):
        return None

    log_a = np.log(close_a)
    log_b = np.log(close_b)

    # 로그 수익률 상관계수 필터 (빠름)
    ret_a = np.diff(log_a)
    ret_b = np.diff(log_b)
    if len(ret_a) < 30:
        return None
    corr = float(np.corrcoef(ret_a, ret_b)[0, 1])
    if abs(corr) < min_corr:
        return None

    # Engle-Granger 공적분 검정
    try:
        _, pvalue, _ = coint(log_a, log_b)
    except Exception:
        return None

    if pvalue > coint_pvalue:
        return None

    # OLS 헤지 비율: log_A = beta * log_B + alpha
    X = np.column_stack([log_b, np.ones(len(log_b))])
    try:
        coeffs, _, _, _ = np.linalg.lstsq(X, log_a, rcond=None)
        hedge_ratio = float(coeffs[0])
    except Exception:
        hedge_ratio = 1.0

    return {
        "symbol_a":    sym_a,
        "symbol_b":    sym_b,
        "sector":      sector,
        "pvalue":      round(float(pvalue), 6),
        "corr":        round(corr, 4),
        "hedge_ratio": round(hedge_ratio, 6),
    }


def _filter_valid_symbols(
    daily_data: Dict[str, pd.DataFrame],
    min_dollar_volume: float,
    min_price: float,
    lookback: int,
) -> List[str]:
    """유동성/가격/데이터 충분성 필터."""
    valid = []
    for sym, df in daily_data.items():
        if len(df) < lookback:
            continue
        # 최근 21거래일 달러 거래량
        recent = df.iloc[-21:]
        avg_dv = float((recent["close"] * recent["volume"]).mean())
        if avg_dv < min_dollar_volume:
            continue
        # 최근 종가
        last_px = float(df["close"].iloc[-1])
        if last_px < min_price:
            continue
        valid.append(sym)
    return valid


def load_sector_map(sector_cache_path: str) -> Dict[str, str]:
    """sector_cache.json 로드 → {symbol: sector}."""
    try:
        with open(sector_cache_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"[PairSelector] sector_cache 없음: {sector_cache_path}")
        return {}
