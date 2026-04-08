"""
주가 데이터 수집 모듈
- 분봉/일봉 데이터 수집
- Alpaca API 활용
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
import pandas as pd
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed


class StockPriceCollector:
    """주가 데이터 수집기"""

    def __init__(self, api_key: str, api_secret: str):
        """
        초기화

        Args:
            api_key: Alpaca API Key
            api_secret: Alpaca API Secret
        """
        self.client = StockHistoricalDataClient(api_key, api_secret)
        self.api_key = api_key
        self.api_secret = api_secret

    async def get_daily_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        일봉 데이터 수집

        Args:
            symbols: 종목 심볼 리스트 (예: ['AAPL', 'TSLA'])
            start_date: 시작 날짜
            end_date: 종료 날짜 (기본값: 현재)

        Returns:
            DataFrame with columns: timestamp, symbol, open, high, low, close, volume
        """
        if end_date is None:
            end_date = datetime.now()

        request_params = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame(1, TimeFrameUnit.Day),
            start=start_date,
            end=end_date,
            feed=DataFeed.IEX  # Free tier uses IEX data
        )

        bars = self.client.get_stock_bars(request_params)
        df = bars.df

        if df.empty:
            return pd.DataFrame()

        # Reset index to get symbol and timestamp as columns
        df = df.reset_index()

        return df

    async def get_minute_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: Optional[datetime] = None,
        minutes: int = 1
    ) -> pd.DataFrame:
        """
        분봉 데이터 수집

        Args:
            symbols: 종목 심볼 리스트
            start_date: 시작 날짜
            end_date: 종료 날짜 (기본값: 현재)
            minutes: 분봉 단위 (1, 5, 15, 30, 60)

        Returns:
            DataFrame with columns: timestamp, symbol, open, high, low, close, volume
        """
        if end_date is None:
            end_date = datetime.now()

        # Alpaca supports 1, 5, 15, 30, 60 minute bars
        valid_minutes = [1, 5, 15, 30, 60]
        if minutes not in valid_minutes:
            raise ValueError(f"minutes must be one of {valid_minutes}")

        request_params = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame(minutes, TimeFrameUnit.Minute),
            start=start_date,
            end=end_date,
            feed=DataFeed.IEX  # Free tier uses IEX data
        )

        bars = self.client.get_stock_bars(request_params)
        df = bars.df

        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()

        return df

    async def get_latest_price(self, symbols: List[str]) -> Dict[str, float]:
        """
        최신 가격 조회

        Args:
            symbols: 종목 심볼 리스트

        Returns:
            {symbol: price} 딕셔너리
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        df = await self.get_minute_bars(symbols, start_date, end_date, minutes=1)

        if df.empty:
            return {}

        # Get the latest price for each symbol
        latest_prices = {}
        for symbol in symbols:
            symbol_data = df[df['symbol'] == symbol]
            if not symbol_data.empty:
                latest_prices[symbol] = float(symbol_data.iloc[-1]['close'])

        return latest_prices

    async def get_price_with_indicators(
        self,
        symbol: str,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        주가 데이터 + 기본 지표 계산

        Args:
            symbol: 종목 심볼
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            DataFrame with price + basic indicators (SMA, EMA, returns)
        """
        df = await self.get_daily_bars([symbol], start_date, end_date)

        if df.empty:
            return pd.DataFrame()

        # Calculate basic indicators
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = pd.Series(index=df.index, data=pd.Series(df['close']).apply(lambda x: pd.Series(x).pct_change().apply(lambda y: pd.Series(y).apply(lambda z: float('nan') if pd.isna(z) else (0 if z == -1 else float('inf') if z == float('inf') else __import__('math').log(1 + z))))))

        # Fix log returns calculation
        df['log_returns'] = df['returns'].apply(
            lambda x: float('nan') if pd.isna(x) else (
                0 if x == -1 else (
                    float('inf') if abs(x) == float('inf') else __import__('math').log(1 + x)
                )
            )
        )

        return df

    def validate_symbols(self, symbols: List[str]) -> List[str]:
        """
        유효한 심볼만 필터링

        Args:
            symbols: 검증할 심볼 리스트

        Returns:
            유효한 심볼 리스트
        """
        valid_symbols = []

        for symbol in symbols:
            try:
                # Try to fetch 1 day of data to validate
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)

                request_params = StockBarsRequest(
                    symbol_or_symbols=[symbol],
                    timeframe=TimeFrame(1, TimeFrameUnit.Day),
                    start=start_date,
                    end=end_date
                )

                bars = self.client.get_stock_bars(request_params)

                if not bars.df.empty:
                    valid_symbols.append(symbol)
            except Exception as e:
                print(f"Invalid symbol {symbol}: {str(e)}")
                continue

        return valid_symbols


# Example usage
async def main():
    """테스트 함수"""
    # Load from environment or config
    import os
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('APCA-API-KEY-ID')
    api_secret = os.getenv('APCA-API-SECRET-KEY')

    if not api_key or not api_secret:
        print("Please set APCA-API-KEY-ID and APCA-API-SECRET-KEY in .env file")
        return

    collector = StockPriceCollector(api_key, api_secret)

    # Test: Get daily bars for AAPL
    symbols = ['AAPL', 'TSLA', 'NVDA']
    start_date = datetime.now() - timedelta(days=30)

    print(f"Fetching daily bars for {symbols}...")
    daily_df = await collector.get_daily_bars(symbols, start_date)
    print(f"Daily bars:\n{daily_df.head()}\n")

    # Test: Get latest prices
    print(f"Fetching latest prices for {symbols}...")
    latest_prices = await collector.get_latest_price(symbols)
    print(f"Latest prices: {latest_prices}\n")

    # Test: Get price with indicators
    print("Fetching AAPL with indicators...")
    indicators_df = await collector.get_price_with_indicators('AAPL', start_date)
    print(f"Price with indicators:\n{indicators_df.tail()}\n")


if __name__ == "__main__":
    asyncio.run(main())
