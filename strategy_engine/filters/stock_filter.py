"""
종목 필터링 로직

거래량 급증, 변동성 증가, 뉴스 이벤트 등을 기반으로
매매 후보 종목을 필터링합니다.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class FilterCriteria:
    """필터링 기준"""
    # 거래량 기준
    min_volume_ratio: float = 1.5  # 평균 대비 최소 거래량 비율
    min_avg_volume: int = 1000000  # 최소 평균 거래량 (유동성 확보)

    # 변동성 기준
    min_volatility: float = 0.02  # 최소 일일 변동성 (2%)
    max_volatility: float = 0.15  # 최대 일일 변동성 (15%, 과도한 변동성 제외)

    # 가격 기준
    min_price: float = 5.0  # 최소 주가 ($5 이상)
    max_price: float = 1000.0  # 최대 주가

    # 추세 기준
    min_trend_strength: float = 40.0  # 최소 추세 강도
    uptrend_only: bool = True  # 상승 추세만 선택

    # 뉴스 이벤트
    has_recent_news: bool = False  # 최근 뉴스 필수 여부
    news_days: int = 7  # 뉴스 검색 기간 (일)

    # 시가총액 (선택적)
    min_market_cap: Optional[float] = None  # 최소 시가총액

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'min_volume_ratio': self.min_volume_ratio,
            'min_avg_volume': self.min_avg_volume,
            'min_volatility': self.min_volatility,
            'max_volatility': self.max_volatility,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'min_trend_strength': self.min_trend_strength,
            'uptrend_only': self.uptrend_only,
            'has_recent_news': self.has_recent_news,
            'news_days': self.news_days,
            'min_market_cap': self.min_market_cap,
        }


@dataclass
class FilterResult:
    """필터링 결과"""
    symbol: str
    passed: bool
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'symbol': self.symbol,
            'passed': self.passed,
            'reasons': self.reasons,
            'metrics': self.metrics,
        }


class StockFilter:
    """
    종목 필터링 클래스

    다양한 기준을 적용하여 매매 후보 종목을 선별합니다.
    """

    def __init__(self, criteria: Optional[FilterCriteria] = None):
        """
        Args:
            criteria: 필터링 기준 (None이면 기본값 사용)
        """
        self.criteria = criteria or FilterCriteria()

    @staticmethod
    def calculate_volatility(prices: pd.Series, period: int = 20) -> float:
        """
        가격 변동성 계산 (표준편차 / 평균)

        Args:
            prices: 가격 시리즈
            period: 계산 기간

        Returns:
            변동성 (0~1)
        """
        if len(prices) < period:
            period = len(prices)

        if period < 2:
            return 0.0

        recent_prices = prices.tail(period)
        returns = recent_prices.pct_change().dropna()

        if len(returns) == 0:
            return 0.0

        volatility = float(returns.std())
        return volatility

    @staticmethod
    def calculate_volume_surge(volumes: pd.Series, period: int = 20) -> float:
        """
        거래량 급증 비율 계산

        Args:
            volumes: 거래량 시리즈
            period: 평균 계산 기간

        Returns:
            현재 거래량 / 평균 거래량 비율
        """
        if len(volumes) < 2:
            return 1.0

        avg_volume = volumes.iloc[:-1].tail(period).mean()
        current_volume = float(volumes.iloc[-1])

        if avg_volume > 0:
            return current_volume / avg_volume
        return 1.0

    def check_volume_criteria(self, df: pd.DataFrame, volume_col: str = 'volume') -> tuple[bool, str, Dict[str, Any]]:
        """
        거래량 기준 확인

        Args:
            df: OHLCV 데이터
            volume_col: 거래량 컬럼명

        Returns:
            (통과 여부, 사유, 메트릭)
        """
        if volume_col not in df.columns:
            return False, "거래량 데이터 없음", {}

        volumes = df[volume_col]

        # 평균 거래량
        avg_volume = float(volumes.mean())

        # 거래량 비율
        volume_ratio = self.calculate_volume_surge(volumes)

        metrics = {
            'avg_volume': avg_volume,
            'current_volume': float(volumes.iloc[-1]),
            'volume_ratio': volume_ratio,
        }

        # 최소 평균 거래량 체크
        if avg_volume < self.criteria.min_avg_volume:
            return False, f"평균 거래량 부족 ({avg_volume:.0f} < {self.criteria.min_avg_volume})", metrics

        # 거래량 급증 체크
        if volume_ratio < self.criteria.min_volume_ratio:
            return False, f"거래량 비율 부족 ({volume_ratio:.2f}x < {self.criteria.min_volume_ratio}x)", metrics

        return True, f"거래량 양호 ({volume_ratio:.2f}x)", metrics

    def check_volatility_criteria(self, df: pd.DataFrame, price_col: str = 'close') -> tuple[bool, str, Dict[str, Any]]:
        """
        변동성 기준 확인

        Args:
            df: OHLCV 데이터
            price_col: 가격 컬럼명

        Returns:
            (통과 여부, 사유, 메트릭)
        """
        if price_col not in df.columns:
            return False, "가격 데이터 없음", {}

        prices = df[price_col]
        volatility = self.calculate_volatility(prices)

        metrics = {
            'volatility': volatility,
        }

        if volatility < self.criteria.min_volatility:
            return False, f"변동성 부족 ({volatility:.2%} < {self.criteria.min_volatility:.2%})", metrics

        if volatility > self.criteria.max_volatility:
            return False, f"변동성 과다 ({volatility:.2%} > {self.criteria.max_volatility:.2%})", metrics

        return True, f"변동성 양호 ({volatility:.2%})", metrics

    def check_price_criteria(self, df: pd.DataFrame, price_col: str = 'close') -> tuple[bool, str, Dict[str, Any]]:
        """
        가격 기준 확인

        Args:
            df: OHLCV 데이터
            price_col: 가격 컬럼명

        Returns:
            (통과 여부, 사유, 메트릭)
        """
        if price_col not in df.columns:
            return False, "가격 데이터 없음", {}

        current_price = float(df[price_col].iloc[-1])

        metrics = {
            'current_price': current_price,
        }

        if current_price < self.criteria.min_price:
            return False, f"주가 너무 낮음 (${current_price:.2f} < ${self.criteria.min_price})", metrics

        if current_price > self.criteria.max_price:
            return False, f"주가 너무 높음 (${current_price:.2f} > ${self.criteria.max_price})", metrics

        return True, f"주가 적정 (${current_price:.2f})", metrics

    def check_trend_criteria(self, df: pd.DataFrame, price_col: str = 'close') -> tuple[bool, str, Dict[str, Any]]:
        """
        추세 기준 확인

        Args:
            df: OHLCV 데이터
            price_col: 가격 컬럼명

        Returns:
            (통과 여부, 사유, 메트릭)
        """
        if price_col not in df.columns or len(df) < 20:
            return False, "추세 분석 데이터 부족", {}

        prices = df[price_col]

        # 추세 강도 계산 (선형 회귀 기울기)
        x = np.arange(len(prices))
        y = prices.values
        slope = np.polyfit(x, y, 1)[0]

        avg_price = float(prices.mean())
        if avg_price > 0:
            normalized_slope = (slope / avg_price) * len(prices) * 100
            trend_strength = max(0, min(100, 50 + normalized_slope))
        else:
            trend_strength = 50.0

        is_uptrend = slope > 0

        metrics = {
            'trend_strength': trend_strength,
            'is_uptrend': is_uptrend,
            'slope': slope,
        }

        # 상승 추세만 허용하는 경우
        if self.criteria.uptrend_only and not is_uptrend:
            return False, f"하락 추세 (강도: {trend_strength:.1f})", metrics

        # 추세 강도 체크
        if trend_strength < self.criteria.min_trend_strength:
            return False, f"추세 강도 부족 ({trend_strength:.1f} < {self.criteria.min_trend_strength})", metrics

        trend_type = "상승" if is_uptrend else "하락"
        return True, f"{trend_type} 추세 양호 (강도: {trend_strength:.1f})", metrics

    def filter_stock(self,
                     symbol: str,
                     df: pd.DataFrame,
                     price_col: str = 'close',
                     volume_col: str = 'volume',
                     news_count: int = 0) -> FilterResult:
        """
        단일 종목 필터링

        Args:
            symbol: 종목 심볼
            df: OHLCV 데이터
            price_col: 가격 컬럼명
            volume_col: 거래량 컬럼명
            news_count: 최근 뉴스 개수

        Returns:
            FilterResult 객체
        """
        reasons = []
        all_metrics = {}
        passed = True

        # 1. 거래량 체크
        volume_pass, volume_reason, volume_metrics = self.check_volume_criteria(df, volume_col)
        all_metrics.update(volume_metrics)
        if not volume_pass:
            passed = False
            reasons.append(f"❌ {volume_reason}")
        else:
            reasons.append(f"✅ {volume_reason}")

        # 2. 변동성 체크
        volatility_pass, volatility_reason, volatility_metrics = self.check_volatility_criteria(df, price_col)
        all_metrics.update(volatility_metrics)
        if not volatility_pass:
            passed = False
            reasons.append(f"❌ {volatility_reason}")
        else:
            reasons.append(f"✅ {volatility_reason}")

        # 3. 가격 체크
        price_pass, price_reason, price_metrics = self.check_price_criteria(df, price_col)
        all_metrics.update(price_metrics)
        if not price_pass:
            passed = False
            reasons.append(f"❌ {price_reason}")
        else:
            reasons.append(f"✅ {price_reason}")

        # 4. 추세 체크
        trend_pass, trend_reason, trend_metrics = self.check_trend_criteria(df, price_col)
        all_metrics.update(trend_metrics)
        if not trend_pass:
            passed = False
            reasons.append(f"❌ {trend_reason}")
        else:
            reasons.append(f"✅ {trend_reason}")

        # 5. 뉴스 체크 (선택적)
        if self.criteria.has_recent_news:
            if news_count == 0:
                passed = False
                reasons.append(f"❌ 최근 뉴스 없음")
            else:
                reasons.append(f"✅ 최근 뉴스 {news_count}건")

        all_metrics['news_count'] = news_count

        return FilterResult(
            symbol=symbol,
            passed=passed,
            reasons=reasons,
            metrics=all_metrics
        )

    def filter_stocks(self,
                      stock_data: Dict[str, pd.DataFrame],
                      news_data: Optional[Dict[str, int]] = None,
                      price_col: str = 'close',
                      volume_col: str = 'volume') -> List[FilterResult]:
        """
        여러 종목을 한 번에 필터링

        Args:
            stock_data: {심볼: OHLCV 데이터} 딕셔너리
            news_data: {심볼: 뉴스 개수} 딕셔너리
            price_col: 가격 컬럼명
            volume_col: 거래량 컬럼명

        Returns:
            FilterResult 리스트
        """
        results = []
        news_data = news_data or {}

        for symbol, df in stock_data.items():
            news_count = news_data.get(symbol, 0)
            result = self.filter_stock(symbol, df, price_col, volume_col, news_count)
            results.append(result)

        return results

    def get_passed_stocks(self, results: List[FilterResult]) -> List[str]:
        """
        필터링을 통과한 종목 심볼 리스트 반환

        Args:
            results: FilterResult 리스트

        Returns:
            통과한 종목 심볼 리스트
        """
        return [r.symbol for r in results if r.passed]

    def get_top_stocks(self, results: List[FilterResult], top_n: int = 10, sort_by: str = 'volume_ratio') -> List[str]:
        """
        필터링 결과를 정렬하여 상위 N개 종목 반환

        Args:
            results: FilterResult 리스트
            top_n: 상위 N개
            sort_by: 정렬 기준 ('volume_ratio', 'volatility', 'trend_strength')

        Returns:
            상위 종목 심볼 리스트
        """
        passed_results = [r for r in results if r.passed]

        if not passed_results:
            return []

        # 정렬
        sorted_results = sorted(
            passed_results,
            key=lambda r: r.metrics.get(sort_by, 0),
            reverse=True
        )

        return [r.symbol for r in sorted_results[:top_n]]
