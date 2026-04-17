"""
백테스팅용 과거 OHLCV 데이터 수집기

Alpaca 또는 yfinance로 최대 2년치 일봉 데이터를 수집합니다.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BacktestDataLoader:
    """과거 데이터 로더"""

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def load_alpaca(
        self,
        symbols: List[str],
        start: str,   # 'YYYY-MM-DD'
        end: str,
    ) -> Dict[str, List[dict]]:
        """
        Alpaca로 일봉 OHLCV 수집

        Returns:
            {symbol: [{date, open, high, low, close, volume}, ...]}
        """
        from alpaca.data import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(self.api_key, self.api_secret)
        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.strptime(start, "%Y-%m-%d"),
            end=datetime.strptime(end, "%Y-%m-%d"),
        )
        raw = client.get_stock_bars(req)

        result = {}
        for sym in symbols:
            if sym not in raw:
                continue
            bars = []
            for b in raw[sym]:
                bars.append({
                    'date': b.timestamp.date() if hasattr(b.timestamp, 'date') else b.timestamp,
                    'open': float(b.open),
                    'high': float(b.high),
                    'low': float(b.low),
                    'close': float(b.close),
                    'volume': int(b.volume),
                })
            result[sym] = sorted(bars, key=lambda x: x['date'])
        return result

    def load_yfinance(
        self,
        symbols: List[str],
        start: str,
        end: str,
    ) -> Dict[str, List[dict]]:
        """yfinance로 일봉 OHLCV 수집 (Alpaca 대안)"""
        import yfinance as yf

        result = {}
        for sym in symbols:
            df = yf.download(sym, start=start, end=end, auto_adjust=True, progress=False)
            if df.empty:
                continue
            bars = []
            for dt, row in df.iterrows():
                bars.append({
                    'date': dt.date(),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']),
                })
            result[sym] = bars
        return result
