"""
기술적 지표 계산 모듈

RSI, MACD, Bollinger Bands, 이동평균 등 다양한 기술적 지표를 계산합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class IndicatorResult:
    """기술적 지표 계산 결과"""
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    bb_position: float  # 볼린저 밴드 내 위치 (0~1)
    sma_20: float
    sma_50: float
    sma_200: float
    ema_12: float
    ema_26: float
    volume_ratio: float  # 평균 대비 거래량 비율
    price_change_pct: float  # 가격 변화율
    trend_strength: float  # 추세 강도 (0~100)

    def to_dict(self) -> Dict[str, float]:
        """딕셔너리로 변환"""
        return {
            'rsi': self.rsi,
            'macd': self.macd,
            'macd_signal': self.macd_signal,
            'macd_histogram': self.macd_histogram,
            'bb_upper': self.bb_upper,
            'bb_middle': self.bb_middle,
            'bb_lower': self.bb_lower,
            'bb_position': self.bb_position,
            'sma_20': self.sma_20,
            'sma_50': self.sma_50,
            'sma_200': self.sma_200,
            'ema_12': self.ema_12,
            'ema_26': self.ema_26,
            'volume_ratio': self.volume_ratio,
            'price_change_pct': self.price_change_pct,
            'trend_strength': self.trend_strength,
        }


class TechnicalIndicators:
    """
    기술적 지표 계산 클래스

    주식 데이터를 기반으로 다양한 기술적 지표를 계산합니다.
    """

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
        """
        RSI (Relative Strength Index) 계산

        Args:
            prices: 가격 시리즈
            period: RSI 계산 기간 (기본값: 14)

        Returns:
            RSI 값 (0~100)
        """
        if len(prices) < period + 1:
            return 50.0  # 데이터 부족 시 중립값 반환

        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    @staticmethod
    def calculate_macd(prices: pd.Series,
                       fast_period: int = 12,
                       slow_period: int = 26,
                       signal_period: int = 9) -> Dict[str, float]:
        """
        MACD (Moving Average Convergence Divergence) 계산

        Args:
            prices: 가격 시리즈
            fast_period: 빠른 EMA 기간
            slow_period: 느린 EMA 기간
            signal_period: 시그널 EMA 기간

        Returns:
            MACD, 시그널, 히스토그램 값
        """
        if len(prices) < slow_period:
            return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}

        ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
        ema_slow = prices.ewm(span=slow_period, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'macd': float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0,
            'signal': float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0,
            'histogram': float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0.0,
        }

    @staticmethod
    def calculate_bollinger_bands(prices: pd.Series,
                                   period: int = 20,
                                   std_dev: float = 2.0) -> Dict[str, float]:
        """
        볼린저 밴드 계산

        Args:
            prices: 가격 시리즈
            period: 이동평균 기간
            std_dev: 표준편차 배수

        Returns:
            상단, 중간, 하단 밴드 값 및 현재 가격의 밴드 내 위치
        """
        if len(prices) < period:
            current_price = float(prices.iloc[-1])
            return {
                'upper': current_price * 1.02,
                'middle': current_price,
                'lower': current_price * 0.98,
                'position': 0.5
            }

        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        current_price = float(prices.iloc[-1])
        upper = float(upper_band.iloc[-1]) if not pd.isna(upper_band.iloc[-1]) else current_price * 1.02
        middle = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else current_price
        lower = float(lower_band.iloc[-1]) if not pd.isna(lower_band.iloc[-1]) else current_price * 0.98

        # 밴드 내 위치 계산 (0: 하단, 0.5: 중간, 1: 상단)
        if upper != lower:
            position = (current_price - lower) / (upper - lower)
            # 0~1 범위로 제한 (가격이 밴드를 벗어난 경우)
            position = max(0.0, min(1.0, position))
        else:
            position = 0.5

        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'position': position
        }

    @staticmethod
    def calculate_sma(prices: pd.Series, period: int) -> float:
        """
        단순 이동평균 (Simple Moving Average) 계산

        Args:
            prices: 가격 시리즈
            period: 이동평균 기간

        Returns:
            SMA 값
        """
        if len(prices) < period:
            return float(prices.mean())

        sma = prices.rolling(window=period).mean()
        return float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else float(prices.iloc[-1])

    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> float:
        """
        지수 이동평균 (Exponential Moving Average) 계산

        Args:
            prices: 가격 시리즈
            period: 이동평균 기간

        Returns:
            EMA 값
        """
        if len(prices) < period:
            return float(prices.mean())

        ema = prices.ewm(span=period, adjust=False).mean()
        return float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else float(prices.iloc[-1])

    @staticmethod
    def calculate_volume_ratio(volumes: pd.Series, period: int = 20) -> float:
        """
        거래량 비율 계산 (현재 거래량 / 평균 거래량)

        Args:
            volumes: 거래량 시리즈
            period: 평균 계산 기간

        Returns:
            거래량 비율
        """
        if len(volumes) < 2:
            return 1.0

        avg_volume = volumes.iloc[:-1].tail(period).mean()
        current_volume = float(volumes.iloc[-1])

        if avg_volume > 0:
            return current_volume / avg_volume
        return 1.0

    @staticmethod
    def calculate_trend_strength(prices: pd.Series, period: int = 20) -> float:
        """
        추세 강도 계산 (0~100)

        상승 추세일수록 100에 가깝고, 하락 추세일수록 0에 가까움

        Args:
            prices: 가격 시리즈
            period: 계산 기간

        Returns:
            추세 강도 (0~100)
        """
        if len(prices) < period:
            return 50.0

        # 선형 회귀를 통한 추세선 기울기 계산
        recent_prices = prices.tail(period)
        x = np.arange(len(recent_prices))
        y = recent_prices.values

        # 최소제곱법으로 기울기 계산
        slope = np.polyfit(x, y, 1)[0]

        # 기울기를 0~100 스케일로 변환
        # 양수 기울기: 상승 추세, 음수 기울기: 하락 추세
        avg_price = float(recent_prices.mean())
        if avg_price > 0:
            normalized_slope = (slope / avg_price) * period * 100
            # -50 ~ +50 범위를 0~100으로 변환
            trend_strength = max(0, min(100, 50 + normalized_slope))
        else:
            trend_strength = 50.0

        return float(trend_strength)

    @classmethod
    def calculate_all_indicators(cls,
                                  df: pd.DataFrame,
                                  price_col: str = 'close',
                                  volume_col: str = 'volume') -> IndicatorResult:
        """
        모든 기술적 지표를 한 번에 계산

        Args:
            df: OHLCV 데이터프레임
            price_col: 가격 컬럼명
            volume_col: 거래량 컬럼명

        Returns:
            IndicatorResult 객체
        """
        if df.empty or price_col not in df.columns:
            raise ValueError("유효한 가격 데이터가 필요합니다.")

        prices = df[price_col]
        volumes = df[volume_col] if volume_col in df.columns else pd.Series([1] * len(df))

        # RSI 계산
        rsi = cls.calculate_rsi(prices)

        # MACD 계산
        macd_data = cls.calculate_macd(prices)

        # Bollinger Bands 계산
        bb_data = cls.calculate_bollinger_bands(prices)

        # 이동평균 계산
        sma_20 = cls.calculate_sma(prices, 20)
        sma_50 = cls.calculate_sma(prices, 50)
        sma_200 = cls.calculate_sma(prices, 200)
        ema_12 = cls.calculate_ema(prices, 12)
        ema_26 = cls.calculate_ema(prices, 26)

        # 거래량 비율
        volume_ratio = cls.calculate_volume_ratio(volumes)

        # 가격 변화율
        if len(prices) >= 2:
            price_change_pct = ((prices.iloc[-1] - prices.iloc[-2]) / prices.iloc[-2]) * 100
        else:
            price_change_pct = 0.0

        # 추세 강도
        trend_strength = cls.calculate_trend_strength(prices)

        return IndicatorResult(
            rsi=rsi,
            macd=macd_data['macd'],
            macd_signal=macd_data['signal'],
            macd_histogram=macd_data['histogram'],
            bb_upper=bb_data['upper'],
            bb_middle=bb_data['middle'],
            bb_lower=bb_data['lower'],
            bb_position=bb_data['position'],
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            ema_12=ema_12,
            ema_26=ema_26,
            volume_ratio=volume_ratio,
            price_change_pct=price_change_pct,
            trend_strength=trend_strength,
        )
