"""
시장 국면 감지 모듈 (Market Regime Detector)

기획서 전략 A: 시장 국면 감지 (필수)

로직:
    if SPY > SMA50 and QQQ > SMA50:
        regime = "BULL"
    elif SPY < SMA50 and QQQ < SMA50:
        regime = "BEAR"
    else:
        regime = "NEUTRAL"

출력:
    {"regime": "BEAR", "confidence": 0.82}
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

import pandas as pd

from ..indicators.technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """시장 국면"""
    BULL = "BULL"      # 상승장: SPY & QQQ 모두 SMA50 위
    BEAR = "BEAR"      # 하락장: SPY & QQQ 모두 SMA50 아래
    NEUTRAL = "NEUTRAL"  # 혼조: 엇갈린 신호


@dataclass
class RegimeResult:
    """시장 국면 감지 결과"""
    regime: MarketRegime
    confidence: float          # 0.0 ~ 1.0
    spy_price: float
    spy_sma50: float
    qqq_price: float
    qqq_sma50: float
    spy_above_sma50: bool
    qqq_above_sma50: bool
    spy_distance_pct: float    # SPY의 SMA50 대비 이격도 (%)
    qqq_distance_pct: float    # QQQ의 SMA50 대비 이격도 (%)

    def to_dict(self) -> Dict:
        return {
            "regime": self.regime.value,
            "confidence": round(self.confidence, 4),
            "spy_price": self.spy_price,
            "spy_sma50": self.spy_sma50,
            "qqq_price": self.qqq_price,
            "qqq_sma50": self.qqq_sma50,
            "spy_above_sma50": self.spy_above_sma50,
            "qqq_above_sma50": self.qqq_above_sma50,
            "spy_distance_pct": round(self.spy_distance_pct, 4),
            "qqq_distance_pct": round(self.qqq_distance_pct, 4),
        }


class MarketRegimeDetector:
    """
    시장 국면 감지기

    SPY와 QQQ의 SMA50 대비 위치로 BULL/BEAR/NEUTRAL을 판단합니다.
    신뢰도(confidence)는 두 지수의 SMA50 이격도로 계산합니다.
    """

    def __init__(self, sma_period: int = 50):
        """
        Args:
            sma_period: 이동평균 기간 (기본값: 50일)
        """
        self.sma_period = sma_period

    def detect(
        self,
        spy_df: pd.DataFrame,
        qqq_df: pd.DataFrame,
    ) -> Optional[RegimeResult]:
        """
        시장 국면 감지

        Args:
            spy_df: SPY OHLCV 데이터프레임 (최소 50 bars)
            qqq_df: QQQ OHLCV 데이터프레임 (최소 50 bars)

        Returns:
            RegimeResult (데이터 부족 시 None)
        """
        try:
            if spy_df is None or qqq_df is None:
                logger.warning("시장 국면 감지: 데이터 없음 (SPY/QQQ)")
                return None

            if len(spy_df) < self.sma_period or len(qqq_df) < self.sma_period:
                logger.warning(
                    f"시장 국면 감지: 데이터 부족 (SPY={len(spy_df)}, QQQ={len(qqq_df)}, 필요={self.sma_period})"
                )
                return None

            # SMA50 계산
            spy_price = float(spy_df["close"].iloc[-1])
            qqq_price = float(qqq_df["close"].iloc[-1])

            spy_sma50 = TechnicalIndicators.calculate_sma(spy_df["close"], self.sma_period)
            qqq_sma50 = TechnicalIndicators.calculate_sma(qqq_df["close"], self.sma_period)

            spy_above = spy_price > spy_sma50
            qqq_above = qqq_price > qqq_sma50

            # 이격도 계산 (%)
            spy_dist_pct = ((spy_price - spy_sma50) / spy_sma50) * 100
            qqq_dist_pct = ((qqq_price - qqq_sma50) / qqq_sma50) * 100

            # 국면 판단
            if spy_above and qqq_above:
                regime = MarketRegime.BULL
            elif not spy_above and not qqq_above:
                regime = MarketRegime.BEAR
            else:
                regime = MarketRegime.NEUTRAL

            # 신뢰도 계산: 이격도 크기 기반 (±5% 이상이면 confidence 1.0)
            avg_abs_dist = (abs(spy_dist_pct) + abs(qqq_dist_pct)) / 2
            confidence = min(1.0, avg_abs_dist / 5.0)

            # NEUTRAL은 신뢰도 낮게
            if regime == MarketRegime.NEUTRAL:
                confidence *= 0.5

            result = RegimeResult(
                regime=regime,
                confidence=round(confidence, 4),
                spy_price=spy_price,
                spy_sma50=spy_sma50,
                qqq_price=qqq_price,
                qqq_sma50=qqq_sma50,
                spy_above_sma50=spy_above,
                qqq_above_sma50=qqq_above,
                spy_distance_pct=spy_dist_pct,
                qqq_distance_pct=qqq_dist_pct,
            )

            logger.info(
                f"[MarketRegime] {regime.value} (신뢰도: {confidence:.2f}) | "
                f"SPY {spy_price:.2f} vs SMA50 {spy_sma50:.2f} ({spy_dist_pct:+.2f}%) | "
                f"QQQ {qqq_price:.2f} vs SMA50 {qqq_sma50:.2f} ({qqq_dist_pct:+.2f}%)"
            )

            return result

        except Exception as e:
            logger.error(f"시장 국면 감지 오류: {e}")
            return None

    def detect_from_prices(
        self,
        spy_prices: list,
        qqq_prices: list,
    ) -> Optional[RegimeResult]:
        """
        가격 리스트로 시장 국면 감지 (간편 버전)

        Args:
            spy_prices: SPY 종가 리스트 (최소 50개)
            qqq_prices: QQQ 종가 리스트 (최소 50개)
        """
        import pandas as pd
        spy_df = pd.DataFrame({"close": spy_prices})
        qqq_df = pd.DataFrame({"close": qqq_prices})
        return self.detect(spy_df, qqq_df)
