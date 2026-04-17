"""
Gap Direction Validator - Gap & Go vs Gap & Fade 분류 (IMP-02)

장 시작 후 첫 5분 캔들 방향을 확인하여 진입 허용 여부를 결정합니다.
  - 갭 방향 == 첫 캔들 방향 → Gap & Go → 진입 허용
  - 갭 방향 != 첫 캔들 방향 → Gap & Fade → 진입 거부
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class GapValidator:
    """
    갭 방향 검증기

    9:30 ~ 9:35 첫 5분 캔들을 조회하여
    갭 방향과 캔들 방향이 일치하는지 확인합니다.
    """

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def _get_first_5min_candle(self, symbol: str, trade_date: datetime = None):
        """
        9:30 ~ 9:35 첫 5분 캔들 조회

        Returns:
            (open, close) 또는 None
        """
        try:
            from alpaca.data import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            try:
                from zoneinfo import ZoneInfo
                et_tz = ZoneInfo("America/New_York")
            except ImportError:
                import pytz
                et_tz = pytz.timezone("America/New_York")

            client = StockHistoricalDataClient(self.api_key, self.api_secret)
            today = trade_date or datetime.now(et_tz)

            # 9:30 ~ 9:40 구간 조회 (여유 10분)
            market_open = today.replace(hour=9, minute=30, second=0, microsecond=0)
            market_open_end = today.replace(hour=9, minute=40, second=0, microsecond=0)

            req = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame.Minute,
                start=market_open,
                end=market_open_end,
            )
            bars = client.get_stock_bars(req)
            if symbol not in bars or not bars[symbol]:
                return None

            first = bars[symbol][0]
            return float(first.open), float(first.close)

        except Exception as e:
            logger.debug(f"{symbol} 첫 5분 캔들 조회 실패: {e}")
            return None

    def validate_gap_direction(self, symbol: str, gap_pct: float) -> bool:
        """
        갭 방향과 첫 5분 캔들 방향 일치 여부 확인

        Args:
            symbol:   종목 심볼
            gap_pct:  갭 비율 (양수=갭업, 음수=갭다운)

        Returns:
            True  → Gap & Go (진입 허용)
            False → Gap & Fade 또는 데이터 없음 (진입 거부)
        """
        candle = self._get_first_5min_candle(symbol)
        if candle is None:
            logger.debug(f"{symbol} 첫 캔들 없음 - 장 전 호출이거나 데이터 미수신, 진입 거부")
            return False

        open_price, close_price = candle

        if gap_pct > 0:
            # 갭업: 첫 캔들이 양봉(close > open)이어야 Gap & Go
            is_go = close_price > open_price
        else:
            # 갭다운: 첫 캔들이 음봉(close < open)이어야 Gap & Go
            is_go = close_price < open_price

        direction = "양봉" if close_price >= open_price else "음봉"
        gap_dir = "갭업" if gap_pct > 0 else "갭다운"
        result_str = "Gap & Go (진입 허용)" if is_go else "Gap & Fade (진입 거부)"

        logger.info(
            f"[GapValidator] {symbol} {gap_dir}({gap_pct:+.2f}%) | "
            f"첫 캔들={direction}(O:{open_price:.2f}→C:{close_price:.2f}) | {result_str}"
        )
        return is_go
