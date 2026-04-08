"""
거래량 및 변동성 데이터 수집 모듈
- 거래량 분석
- 변동성 지표 계산
- 이상 거래량 탐지
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from .stock_price_collector import StockPriceCollector


class VolumeVolatilityCollector:
    """거래량 및 변동성 수집기"""

    def __init__(self, stock_collector: StockPriceCollector):
        """
        초기화

        Args:
            stock_collector: 주가 데이터 수집기
        """
        self.stock_collector = stock_collector

    async def get_volume_analysis(
        self,
        symbol: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        lookback_days: int = 30
    ) -> pd.DataFrame:
        """
        거래량 분석 데이터

        Args:
            symbol: 종목 심볼
            start_date: 시작 날짜
            end_date: 종료 날짜
            lookback_days: 평균 계산 기간

        Returns:
            DataFrame with volume analysis
        """
        if end_date is None:
            end_date = datetime.now()

        # Fetch data with extra lookback for moving averages
        extended_start = start_date - timedelta(days=lookback_days)
        df = await self.stock_collector.get_daily_bars([symbol], extended_start, end_date)

        if df.empty:
            return pd.DataFrame()

        # Calculate volume indicators
        df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ma_50'] = df['volume'].rolling(window=50).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_20']

        # Volume surge detection
        df['volume_surge'] = df['volume_ratio'] > 2.0

        # Relative volume
        df['relative_volume'] = df['volume'] / df['volume'].rolling(window=20).mean()

        # Money flow (volume * price)
        df['money_flow'] = df['volume'] * df['close']
        df['money_flow_ma'] = df['money_flow'].rolling(window=20).mean()

        # Filter to requested date range
        df = df[df['timestamp'] >= start_date]

        return df

    async def get_volatility_metrics(
        self,
        symbol: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        window: int = 20
    ) -> pd.DataFrame:
        """
        변동성 지표 계산

        Args:
            symbol: 종목 심볼
            start_date: 시작 날짜
            end_date: 종료 날짜
            window: 계산 윈도우

        Returns:
            DataFrame with volatility metrics
        """
        if end_date is None:
            end_date = datetime.now()

        # Fetch data with extra lookback
        extended_start = start_date - timedelta(days=window * 2)
        df = await self.stock_collector.get_daily_bars([symbol], extended_start, end_date)

        if df.empty:
            return pd.DataFrame()

        # Calculate returns
        df['returns'] = df['close'].pct_change()

        # Historical Volatility (annualized)
        df['volatility'] = df['returns'].rolling(window=window).std() * np.sqrt(252)

        # Average True Range (ATR)
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = np.abs(df['high'] - df['close'].shift())
        df['low_close'] = np.abs(df['low'] - df['close'].shift())
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['true_range'].rolling(window=14).mean()

        # Normalized ATR
        df['atr_percent'] = (df['atr'] / df['close']) * 100

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        df['bb_std'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']

        # Volatility regime
        df['volatility_percentile'] = df['volatility'].rolling(window=252).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else np.nan
        )

        # Filter to requested date range
        df = df[df['timestamp'] >= start_date]

        return df

    async def detect_volume_anomalies(
        self,
        symbols: List[str],
        threshold_multiplier: float = 2.5
    ) -> List[Dict]:
        """
        이상 거래량 탐지

        Args:
            symbols: 검색할 심볼 리스트
            threshold_multiplier: 평균 대비 임계값 배수

        Returns:
            List of anomaly dictionaries
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)

        anomalies = []

        for symbol in symbols:
            try:
                df = await self.get_volume_analysis(symbol, start_date, end_date)

                if df.empty:
                    continue

                # Get latest data
                latest = df.iloc[-1]

                if latest['volume_ratio'] >= threshold_multiplier:
                    anomalies.append({
                        'symbol': symbol,
                        'date': latest['timestamp'],
                        'volume': int(latest['volume']),
                        'avg_volume': int(latest['volume_ma_20']),
                        'volume_ratio': round(latest['volume_ratio'], 2),
                        'price': round(latest['close'], 2),
                        'price_change': round(latest['returns'] * 100, 2) if not pd.isna(latest['returns']) else 0
                    })

            except Exception as e:
                print(f"Error processing {symbol}: {str(e)}")
                continue

        # Sort by volume ratio descending
        anomalies.sort(key=lambda x: x['volume_ratio'], reverse=True)

        return anomalies

    async def get_volatility_ranking(
        self,
        symbols: List[str],
        top_n: int = 20
    ) -> List[Dict]:
        """
        변동성 순위

        Args:
            symbols: 분석할 심볼 리스트
            top_n: 상위 N개

        Returns:
            List of ranked stocks by volatility
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)

        volatility_data = []

        for symbol in symbols:
            try:
                df = await self.get_volatility_metrics(symbol, start_date, end_date)

                if df.empty:
                    continue

                latest = df.iloc[-1]

                if not pd.isna(latest['volatility']):
                    volatility_data.append({
                        'symbol': symbol,
                        'volatility': round(latest['volatility'] * 100, 2),
                        'atr_percent': round(latest['atr_percent'], 2) if not pd.isna(latest['atr_percent']) else 0,
                        'bb_width': round(latest['bb_width'] * 100, 2) if not pd.isna(latest['bb_width']) else 0,
                        'price': round(latest['close'], 2),
                        'volume': int(latest['volume'])
                    })

            except Exception as e:
                print(f"Error processing {symbol}: {str(e)}")
                continue

        # Sort by volatility descending
        volatility_data.sort(key=lambda x: x['volatility'], reverse=True)

        return volatility_data[:top_n]

    async def get_combined_analysis(
        self,
        symbol: str,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        거래량 + 변동성 통합 분석

        Args:
            symbol: 종목 심볼
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            DataFrame with combined analysis
        """
        if end_date is None:
            end_date = datetime.now()

        # Get both analyses
        volume_df = await self.get_volume_analysis(symbol, start_date, end_date)
        volatility_df = await self.get_volatility_metrics(symbol, start_date, end_date)

        if volume_df.empty or volatility_df.empty:
            return pd.DataFrame()

        # Merge on timestamp
        combined = pd.merge(
            volume_df,
            volatility_df[['timestamp', 'volatility', 'atr', 'atr_percent', 'bb_width']],
            on='timestamp',
            how='inner'
        )

        # Add combined signals
        combined['high_volume_high_volatility'] = (
            (combined['volume_ratio'] > 1.5) &
            (combined['volatility'] > combined['volatility'].median())
        )

        return combined


# Example usage
async def main():
    """테스트 함수"""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('APCA-API-KEY-ID')
    api_secret = os.getenv('APCA-API-SECRET-KEY')

    if not api_key or not api_secret:
        print("Please set APCA-API-KEY-ID and APCA-API-SECRET-KEY in .env file")
        return

    stock_collector = StockPriceCollector(api_key, api_secret)
    collector = VolumeVolatilityCollector(stock_collector)

    # Test: Volume analysis
    symbol = 'AAPL'
    start_date = datetime.now() - timedelta(days=30)

    print(f"Volume analysis for {symbol}...")
    volume_df = await collector.get_volume_analysis(symbol, start_date)
    print(f"\n{volume_df[['timestamp', 'close', 'volume', 'volume_ratio', 'volume_surge']].tail()}\n")

    # Test: Volatility metrics
    print(f"Volatility metrics for {symbol}...")
    volatility_df = await collector.get_volatility_metrics(symbol, start_date)
    print(f"\n{volatility_df[['timestamp', 'close', 'volatility', 'atr_percent', 'bb_width']].tail()}\n")

    # Test: Volume anomalies
    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']
    print(f"Detecting volume anomalies for {symbols}...")
    anomalies = await collector.detect_volume_anomalies(symbols)
    print(f"\nVolume anomalies: {anomalies}\n")

    # Test: Volatility ranking
    print(f"Volatility ranking for {symbols}...")
    ranking = await collector.get_volatility_ranking(symbols)
    print(f"\nVolatility ranking: {ranking}\n")


if __name__ == "__main__":
    asyncio.run(main())
