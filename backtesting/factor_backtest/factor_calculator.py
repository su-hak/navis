"""
NAVIS 팩터 모멘텀 — 팩터 계산 모듈

12-1 크로스섹셔널 모멘텀 (Jegadeesh & Titman, 1993):
  - 과거 12개월 수익률 계산, 최근 1개월 제외 (단기 반전 회피)
  - 상위 20% 매수, 월말 리밸런싱
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
