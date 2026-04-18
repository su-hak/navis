"""
점수 계산 알고리즘

기술적 지표, 뉴스 감성, 재무 성장성, 수급 등을 종합하여
매매 적합도 점수를 계산합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..indicators.technical_indicators import TechnicalIndicators, IndicatorResult

# ─── BUG-02: 전략별 RSI 스코어링 함수 ─────────────────────────────────────────

def rsi_score_momentum(rsi: float) -> float:
    """
    갭 모멘텀 / 브레이크아웃 전략용 RSI 스코어 (BUG-02)

    강한 모멘텀 = RSI 50-70 구간에서 최고점.
    RSI 30-50 은 모멘텀 부족 → 낮은 점수.
    RSI > 80 = 과매수, 진입 금지.
    """
    if 50 <= rsi <= 70:
        # 정중앙 60 부근에서 최고점(100) → 양 끝에서 80
        distance_from_60 = abs(rsi - 60)
        score = 100 - distance_from_60 * 2  # 60→100, 50/70→80
    elif 70 < rsi <= 80:
        score = 80 - (rsi - 70) * 3.0        # 70→80, 80→50
    elif rsi > 80:
        score = max(0.0, 50 - (rsi - 80) * 5.0)  # 80→50, 90→0
    elif 40 <= rsi < 50:
        score = 30 + (rsi - 40) * 2.0        # 40→30, 50→50 (부드럽게 연결)
    else:
        score = max(0.0, 30 - (50 - rsi) * 1.0)  # rsi<40 = 매우 낮음
    return float(min(100.0, max(0.0, score)))


def rsi_score_reversion(rsi: float) -> float:
    """
    평균회귀(리버전) 전략용 RSI 스코어 (BUG-02)

    과매도(RSI 30) = 최고점. RSI 50-70 = 낮은 점수.
    기존 calculate_technical_score 의 RSI 로직과 동일 방향.
    """
    if 30 <= rsi <= 50:
        # 30일 때 100점, 50일 때 60점
        score = 60 + (50 - rsi) * 2.0
    elif rsi < 30:
        score = 50 + rsi * 0.5  # 0→50, 30→65
    else:  # rsi > 50
        score = max(0.0, 60 - (rsi - 50) * 1.5)  # 50→60, 70→30, 90→0
    return float(min(100.0, max(0.0, score)))


@dataclass
class ScoreWeights:
    """점수 가중치 설정"""
    technical: float = 0.40  # 기술적 지표 40%
    volume: float = 0.20  # 거래량 20%
    trend: float = 0.20  # 추세 20%
    news_sentiment: float = 0.10  # 뉴스 감성 10%
    financial: float = 0.10  # 재무 성장성 10%

    def __post_init__(self):
        """가중치 합계가 1.0인지 확인"""
        total = self.technical + self.volume + self.trend + self.news_sentiment + self.financial
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"가중치 합계는 1.0이어야 합니다 (현재: {total})")

    def to_dict(self) -> Dict[str, float]:
        """딕셔너리로 변환"""
        return {
            'technical': self.technical,
            'volume': self.volume,
            'trend': self.trend,
            'news_sentiment': self.news_sentiment,
            'financial': self.financial,
        }


@dataclass
class ScoreResult:
    """점수 계산 결과"""
    symbol: str
    total_score: float  # 총점 (0~100)
    technical_score: float  # 기술적 점수
    volume_score: float  # 거래량 점수
    trend_score: float  # 추세 점수
    news_score: float  # 뉴스 점수
    financial_score: float  # 재무 점수
    breakdown: Dict[str, Any] = field(default_factory=dict)  # 세부 점수
    recommendation: str = ""  # 추천 (BUY/HOLD/SELL)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'symbol': self.symbol,
            'total_score': self.total_score,
            'technical_score': self.technical_score,
            'volume_score': self.volume_score,
            'trend_score': self.trend_score,
            'news_score': self.news_score,
            'financial_score': self.financial_score,
            'breakdown': self.breakdown,
            'recommendation': self.recommendation,
        }


class ScoreCalculator:
    """
    점수 계산 클래스

    다양한 지표를 종합하여 종목의 매매 적합도를 0~100점으로 평가합니다.
    """

    def __init__(self, weights: Optional[ScoreWeights] = None):
        """
        Args:
            weights: 점수 가중치 (None이면 기본값 사용)
        """
        self.weights = weights or ScoreWeights()
        self.technical_indicators = TechnicalIndicators()

    def calculate_technical_score(
        self,
        indicators: IndicatorResult,
        strategy_type: str = "momentum",
    ) -> tuple[float, Dict[str, Any]]:
        """
        기술적 지표 점수 계산 (0~100)

        Args:
            indicators:    기술적 지표 결과
            strategy_type: 전략 종류 — "momentum" | "breakout" | "reversion"
                           momentum/breakout → rsi_score_momentum()
                           reversion         → rsi_score_reversion()   (BUG-02)

        Returns:
            (점수, 세부 점수)
        """
        scores = {}

        # 1. RSI 점수 — 전략 방향에 맞는 스코어 함수 선택 (BUG-02)
        rsi = indicators.rsi
        if strategy_type in ("momentum", "breakout"):
            rsi_score = rsi_score_momentum(rsi)
        else:
            rsi_score = rsi_score_reversion(rsi)

        scores['rsi_score'] = rsi_score
        scores['rsi_scorer'] = strategy_type  # 디버깅용

        # 2. MACD 점수
        macd_histogram = indicators.macd_histogram
        if macd_histogram > 0:
            # 골든 크로스 (상승 시그널)
            macd_score = 70 + min(30, abs(macd_histogram) * 10)
        else:
            # 데드 크로스 (하락 시그널)
            macd_score = max(0, 50 - abs(macd_histogram) * 10)

        scores['macd_score'] = min(100, max(0, macd_score))

        # 3. 볼린저 밴드 점수
        bb_position = indicators.bb_position
        # 하단 근처(0~0.3): 매수 기회
        # 상단 근처(0.7~1.0): 과열
        if bb_position < 0.3:
            bb_score = 80 + (0.3 - bb_position) * 66  # 하단일수록 높은 점수
        elif bb_position > 0.7:
            bb_score = max(0, 80 - (bb_position - 0.7) * 266)  # 상단일수록 낮은 점수
        else:
            bb_score = 60  # 중간: 중립

        scores['bb_score'] = min(100, max(0, bb_score))

        # 4. 이동평균 점수 (골든크로스/데드크로스)
        current_price = indicators.sma_20  # 현재 가격 근사값
        ma_score = 50

        # SMA 정렬 확인
        if indicators.sma_20 > indicators.sma_50 > indicators.sma_200:
            ma_score = 90  # 강한 상승 추세
        elif indicators.sma_20 > indicators.sma_50:
            ma_score = 70  # 상승 추세
        elif indicators.sma_20 < indicators.sma_50 < indicators.sma_200:
            ma_score = 10  # 강한 하락 추세
        elif indicators.sma_20 < indicators.sma_50:
            ma_score = 30  # 하락 추세

        scores['ma_score'] = ma_score

        # 종합 기술적 점수 (가중 평균)
        technical_score = (
            scores['rsi_score'] * 0.25 +
            scores['macd_score'] * 0.30 +
            scores['bb_score'] * 0.25 +
            scores['ma_score'] * 0.20
        )

        return technical_score, scores

    def calculate_volume_score(self, volume_ratio: float) -> tuple[float, Dict[str, Any]]:
        """
        거래량 점수 계산 (0~100)

        Args:
            volume_ratio: 평균 대비 거래량 비율

        Returns:
            (점수, 세부 점수)
        """
        # 거래량 비율에 따른 점수
        # 1.0x: 50점 (평균)
        # 1.5x: 70점
        # 2.0x: 85점
        # 3.0x+: 100점

        if volume_ratio >= 3.0:
            score = 100
        elif volume_ratio >= 2.0:
            score = 85 + (volume_ratio - 2.0) * 15
        elif volume_ratio >= 1.5:
            score = 70 + (volume_ratio - 1.5) * 30
        elif volume_ratio >= 1.0:
            score = 50 + (volume_ratio - 1.0) * 40
        else:
            score = volume_ratio * 50

        volume_score = min(100, max(0, score))

        breakdown = {
            'volume_ratio': volume_ratio,
            'volume_score': volume_score,
        }

        return volume_score, breakdown

    def calculate_trend_score(self, trend_strength: float, price_change_pct: float) -> tuple[float, Dict[str, Any]]:
        """
        추세 점수 계산 (0~100)

        Args:
            trend_strength: 추세 강도 (0~100)
            price_change_pct: 가격 변화율

        Returns:
            (점수, 세부 점수)
        """
        # 추세 강도 점수 (70%)
        trend_score_component = trend_strength * 0.7

        # 가격 변화율 점수 (30%)
        # 양수 변화: 50~100점
        # 음수 변화: 0~50점
        if price_change_pct >= 5:
            price_score_component = 100 * 0.3
        elif price_change_pct >= 2:
            price_score_component = (70 + (price_change_pct - 2) * 10) * 0.3
        elif price_change_pct >= 0:
            price_score_component = (50 + price_change_pct * 10) * 0.3
        elif price_change_pct >= -2:
            price_score_component = (50 + price_change_pct * 10) * 0.3
        else:
            price_score_component = max(0, 30 + (price_change_pct + 2) * 10) * 0.3

        trend_score = min(100, max(0, trend_score_component + price_score_component))

        breakdown = {
            'trend_strength': trend_strength,
            'price_change_pct': price_change_pct,
            'trend_score': trend_score,
        }

        return trend_score, breakdown

    def calculate_news_score(self, news_sentiment: Optional[float] = None, news_count: int = 0) -> tuple[float, Dict[str, Any]]:
        """
        뉴스 감성 점수 계산 (0~100)

        Args:
            news_sentiment: 뉴스 감성 (-1.0 ~ 1.0, None이면 중립)
            news_count: 뉴스 개수

        Returns:
            (점수, 세부 점수)
        """
        # 뉴스 감성이 없으면 중립 점수
        if news_sentiment is None:
            sentiment_score = 50
        else:
            # -1.0 ~ 1.0을 0~100으로 변환
            sentiment_score = (news_sentiment + 1.0) * 50

        # 뉴스 개수 보너스 (최대 20점)
        news_count_bonus = min(20, news_count * 5)

        news_score = min(100, sentiment_score + news_count_bonus)

        breakdown = {
            'news_sentiment': news_sentiment,
            'news_count': news_count,
            'sentiment_score': sentiment_score,
            'news_count_bonus': news_count_bonus,
            'news_score': news_score,
        }

        return news_score, breakdown

    def calculate_financial_score(self,
                                   revenue_growth: Optional[float] = None,
                                   eps_growth: Optional[float] = None,
                                   institutional_ownership_change: Optional[float] = None) -> tuple[float, Dict[str, Any]]:
        """
        재무 성장성 및 수급 점수 계산 (0~100)

        Args:
            revenue_growth: 매출 성장률 (%)
            eps_growth: EPS 성장률 (%)
            institutional_ownership_change: 기관 보유 변화율 (%)

        Returns:
            (점수, 세부 점수)
        """
        scores = []
        breakdown = {}

        # 1. 매출 성장률
        if revenue_growth is not None:
            if revenue_growth >= 20:
                rev_score = 100
            elif revenue_growth >= 10:
                rev_score = 70 + (revenue_growth - 10) * 3
            elif revenue_growth >= 0:
                rev_score = 50 + revenue_growth * 2
            else:
                rev_score = max(0, 50 + revenue_growth * 2)
            scores.append(rev_score)
            breakdown['revenue_growth'] = revenue_growth
            breakdown['revenue_score'] = rev_score

        # 2. EPS 성장률
        if eps_growth is not None:
            if eps_growth >= 25:
                eps_score = 100
            elif eps_growth >= 15:
                eps_score = 80 + (eps_growth - 15) * 2
            elif eps_growth >= 0:
                eps_score = 50 + eps_growth * 2
            else:
                eps_score = max(0, 50 + eps_growth)
            scores.append(eps_score)
            breakdown['eps_growth'] = eps_growth
            breakdown['eps_score'] = eps_score

        # 3. 기관 보유 변화
        if institutional_ownership_change is not None:
            if institutional_ownership_change >= 5:
                inst_score = 100
            elif institutional_ownership_change >= 2:
                inst_score = 70 + (institutional_ownership_change - 2) * 10
            elif institutional_ownership_change >= 0:
                inst_score = 50 + institutional_ownership_change * 10
            else:
                inst_score = max(0, 50 + institutional_ownership_change * 10)
            scores.append(inst_score)
            breakdown['institutional_ownership_change'] = institutional_ownership_change
            breakdown['institutional_score'] = inst_score

        # 점수가 없으면 중립 점수
        if not scores:
            financial_score = 50.0
        else:
            financial_score = sum(scores) / len(scores)

        breakdown['financial_score'] = financial_score

        return financial_score, breakdown

    def calculate_total_score(self,
                              symbol: str,
                              df: pd.DataFrame,
                              news_sentiment: Optional[float] = None,
                              news_count: int = 0,
                              revenue_growth: Optional[float] = None,
                              eps_growth: Optional[float] = None,
                              institutional_ownership_change: Optional[float] = None,
                              price_col: str = 'close',
                              volume_col: str = 'volume',
                              strategy_type: str = "momentum") -> ScoreResult:
        """
        종합 점수 계산 (score_stock 함수)

        Args:
            symbol: 종목 심볼
            df: OHLCV 데이터
            news_sentiment: 뉴스 감성 (-1.0 ~ 1.0)
            news_count: 뉴스 개수
            revenue_growth: 매출 성장률
            eps_growth: EPS 성장률
            institutional_ownership_change: 기관 보유 변화율
            price_col: 가격 컬럼명
            volume_col: 거래량 컬럼명
            strategy_type: "momentum" | "breakout" | "reversion"  (BUG-02)

        Returns:
            ScoreResult 객체
        """
        # 1. 기술적 지표 계산
        indicators = self.technical_indicators.calculate_all_indicators(df, price_col, volume_col)

        # 2. 각 카테고리 점수 계산 (RSI 방향은 strategy_type 에 따라 결정)
        technical_score, technical_breakdown = self.calculate_technical_score(indicators, strategy_type)
        volume_score, volume_breakdown = self.calculate_volume_score(indicators.volume_ratio)
        trend_score, trend_breakdown = self.calculate_trend_score(indicators.trend_strength, indicators.price_change_pct)
        news_score, news_breakdown = self.calculate_news_score(news_sentiment, news_count)
        financial_score, financial_breakdown = self.calculate_financial_score(
            revenue_growth, eps_growth, institutional_ownership_change
        )

        # 3. 가중 평균으로 총점 계산
        total_score = (
            technical_score * self.weights.technical +
            volume_score * self.weights.volume +
            trend_score * self.weights.trend +
            news_score * self.weights.news_sentiment +
            financial_score * self.weights.financial
        )

        # 4. 추천 판단
        if total_score >= 75:
            recommendation = "BUY"
        elif total_score >= 50:
            recommendation = "HOLD"
        else:
            recommendation = "SELL"

        # 5. 세부 점수 통합
        breakdown = {
            'technical': technical_breakdown,
            'volume': volume_breakdown,
            'trend': trend_breakdown,
            'news': news_breakdown,
            'financial': financial_breakdown,
            'indicators': indicators.to_dict(),
        }

        return ScoreResult(
            symbol=symbol,
            total_score=round(total_score, 2),
            technical_score=round(technical_score, 2),
            volume_score=round(volume_score, 2),
            trend_score=round(trend_score, 2),
            news_score=round(news_score, 2),
            financial_score=round(financial_score, 2),
            breakdown=breakdown,
            recommendation=recommendation,
        )

    def score_stock(self, *args, **kwargs) -> ScoreResult:
        """
        score_stock() 함수 (calculate_total_score의 별칭)

        기획서에서 요구하는 score_stock() 함수입니다.
        strategy_type kwarg 를 그대로 전달하면 BUG-02 RSI 방향이 적용됩니다.
        """
        return self.calculate_total_score(*args, **kwargs)
