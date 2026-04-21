"""
NAVIS 페어 트레이딩 — 스프레드 및 Z-score 계산 모듈
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def calc_spread_zscore(
    price_a: pd.Series,
    price_b: pd.Series,
    hedge_ratio: float,
    window: int = 60,
) -> pd.Series:
    """
    로그 스프레드 Z-score 계산.

    spread  = log(price_A) - hedge_ratio * log(price_B)
    z_score = (spread - rolling_mean(window)) / rolling_std(window)

    Args:
        price_a:     종목 A 종가 시계열
        price_b:     종목 B 종가 시계열
        hedge_ratio: OLS 헤지 비율 (beta)
        window:      롤링 창 거래일 수 (기본 60 = 3개월)

    Returns:
        pd.Series (z_score), 인덱스는 price_a/b 공통 인덱스
    """
    log_a = np.log(price_a.clip(lower=1e-10))
    log_b = np.log(price_b.clip(lower=1e-10))
    spread = log_a - hedge_ratio * log_b

    rolling_mean = spread.rolling(window, min_periods=window).mean()
    rolling_std  = spread.rolling(window, min_periods=window).std()

    # std = 0 인 구간 NaN 처리
    z_score = (spread - rolling_mean) / rolling_std.replace(0, np.nan)
    return z_score
