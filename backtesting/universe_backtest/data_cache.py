"""
NAVIS Universe Backtest — Phase 1: 데이터 수집 및 캐시 관리

Alpaca IEX 무료 API로 최초 1회 수집 후 로컬 parquet 캐시에 저장.
이후 백테스트 실행 시에는 캐시만 사용하므로 API 호출 없음.

캐시 구조:
    cache/
      daily/   {SYMBOL}.parquet   ← 일봉 전체 (ATR 계산, 스크리닝용)
      5min/    {SYMBOL}.parquet   ← 5분봉 전체 (진입/청산 시뮬레이션용)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path("cache")
DEFAULT_START     = "2020-07-27"   # Alpaca IEX 최초 가용일


class DataCache:
    """
    Alpaca IEX 데이터 수집 및 로컬 parquet 캐시 관리.

    사용 예:
        cache = DataCache(api_key, api_secret, cache_dir="cache")
        cache.build(symbols, start="2020-07-27", end="2026-04-19")

        daily = cache.load_daily("NVDA")
        five_min = cache.load_5min("NVDA")
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
    ):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.cache_dir  = Path(cache_dir)
        self._daily_dir = self.cache_dir / "daily"
        self._5min_dir  = self.cache_dir / "5min"
        self._daily_dir.mkdir(parents=True, exist_ok=True)
        self._5min_dir.mkdir(parents=True, exist_ok=True)

    # ── 캐시 빌드 ──────────────────────────────────────────────────────────

    def build(
        self,
        symbols: List[str],
        start: str = DEFAULT_START,
        end:   str | None = None,
        force: bool = False,
    ) -> None:
        """
        전체 유니버스 데이터를 수집하여 캐시 저장.

        Args:
            symbols: 종목 리스트
            start:   수집 시작일 (YYYY-MM-DD)
            end:     수집 종료일 (None → 오늘)
            force:   True면 기존 캐시를 무시하고 재수집
        """
        if end is None:
            end = datetime.today().strftime("%Y-%m-%d")

        logger.info(f"[DataCache] 빌드 시작 | {len(symbols)}종목 | {start} ~ {end}")

        daily_needed = [s for s in symbols if force or not self._daily_path(s).exists()]
        fmin_needed  = [s for s in symbols if force or not self._5min_path(s).exists()]

        if daily_needed:
            logger.info(f"[DataCache] 일봉 수집: {len(daily_needed)}종목")
            self._fetch_daily_batch(daily_needed, start, end)

        if fmin_needed:
            logger.info(f"[DataCache] 5분봉 수집: {len(fmin_needed)}종목")
            self._fetch_5min_all(fmin_needed, start, end)

        logger.info("[DataCache] 빌드 완료")

    def update(self, symbols: List[str]) -> None:
        """
        캐시를 오늘 날짜까지 업데이트 (이미 있는 데이터에 이어 붙임).
        """
        today = datetime.today().strftime("%Y-%m-%d")
        for sym in symbols:
            # 일봉 업데이트
            daily_path = self._daily_path(sym)
            if daily_path.exists():
                existing = pd.read_parquet(daily_path)
                last_date = str(existing.index[-1])
                if last_date < today:
                    new_data = self._fetch_daily_single(sym, last_date, today)
                    if new_data is not None and len(new_data) > 0:
                        combined = pd.concat([existing, new_data])
                        combined = combined[~combined.index.duplicated(keep='last')]
                        combined.sort_index(inplace=True)
                        combined.to_parquet(daily_path)
                        logger.info(f"[DataCache] {sym} 일봉 업데이트: +{len(new_data)}봉")
            # 5분봉 업데이트
            fmin_path = self._5min_path(sym)
            if fmin_path.exists():
                existing = pd.read_parquet(fmin_path)
                last_ts  = existing.index[-1]
                last_date = last_ts.strftime("%Y-%m-%d") if hasattr(last_ts, 'strftime') else str(last_ts)[:10]
                if last_date < today:
                    new_data = self._fetch_5min_single(sym, last_date, today)
                    if new_data is not None and len(new_data) > 0:
                        combined = pd.concat([existing, new_data])
                        combined = combined[~combined.index.duplicated(keep='last')]
                        combined.sort_index(inplace=True)
                        combined.to_parquet(fmin_path)
                        logger.info(f"[DataCache] {sym} 5분봉 업데이트: +{len(new_data)}봉")

    # ── 캐시 로드 ──────────────────────────────────────────────────────────

    def load_daily(self, symbol: str) -> Optional[pd.DataFrame]:
        """일봉 로드. 캐시 없으면 None."""
        path = self._daily_path(symbol)
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def load_5min(self, symbol: str) -> Optional[pd.DataFrame]:
        """5분봉 로드. 캐시 없으면 None."""
        path = self._5min_path(symbol)
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def load_5min_by_date(self, symbol: str) -> Optional[Dict[date, pd.DataFrame]]:
        """5분봉을 날짜별 딕셔너리로 변환하여 반환."""
        df = self.load_5min(symbol)
        if df is None or len(df) == 0:
            return None
        by_date: Dict[date, pd.DataFrame] = {}
        df = df.copy()
        df["_date"] = [ts.date() if hasattr(ts, "date") else ts for ts in df.index]
        for d, grp in df.groupby("_date"):
            by_date[d] = grp.drop(columns=["_date"]).sort_index()
        return by_date

    def cached_symbols(self) -> Dict[str, bool]:
        """캐시 현황 반환. {symbol: (daily, 5min) 모두 있으면 True}"""
        result = {}
        for f in self._daily_dir.glob("*.parquet"):
            sym = f.stem
            has_5min = self._5min_path(sym).exists()
            result[sym] = has_5min
        return result

    def cache_stats(self) -> None:
        """캐시 현황 요약 출력."""
        daily_files = list(self._daily_dir.glob("*.parquet"))
        fmin_files  = list(self._5min_dir.glob("*.parquet"))
        print(f"[DataCache] 일봉  캐시: {len(daily_files)}종목")
        print(f"[DataCache] 5분봉 캐시: {len(fmin_files)}종목")
        total_mb = sum(f.stat().st_size for f in daily_files + fmin_files) / 1024 / 1024
        print(f"[DataCache] 총 캐시 크기: {total_mb:.1f} MB")

    # ── 내부 경로 헬퍼 ────────────────────────────────────────────────────

    def _daily_path(self, symbol: str) -> Path:
        return self._daily_dir / f"{symbol}.parquet"

    def _5min_path(self, symbol: str) -> Path:
        return self._5min_dir / f"{symbol}.parquet"

    # ── Alpaca 데이터 수집 ───────────────────────────────────────────────

    def _get_client(self):
        from alpaca.data import StockHistoricalDataClient
        return StockHistoricalDataClient(self.api_key, self.api_secret)

    def _fetch_daily_batch(self, symbols: List[str], start: str, end: str) -> None:
        """일봉 배치 수집 (500종목씩 한 번에)."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = self._get_client()
        batch_size = 500
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                req = StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=datetime.strptime(start, "%Y-%m-%d"),
                    end=datetime.strptime(end, "%Y-%m-%d"),
                    feed="iex",
                )
                raw = self._get_client().get_stock_bars(req)
                for sym in batch:
                    bars = raw.data.get(sym)
                    if not bars:
                        logger.warning(f"[DataCache] {sym}: 일봉 없음")
                        continue
                    df = self._bars_to_daily_df(bars)
                    df.to_parquet(self._daily_path(sym))
                    logger.debug(f"[DataCache] {sym}: 일봉 {len(df)}봉 저장")
                time.sleep(0.3)  # Rate limit 여유
            except Exception as e:
                logger.error(f"[DataCache] 일봉 배치 오류 ({batch[:3]}...): {e}")

    def _fetch_daily_single(self, symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """단일 종목 일봉 수집."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        try:
            req = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame.Day,
                start=datetime.strptime(start, "%Y-%m-%d"),
                end=datetime.strptime(end, "%Y-%m-%d"),
                feed="iex",
            )
            raw = self._get_client().get_stock_bars(req)
            bars = raw.data.get(symbol)
            if not bars:
                return None
            return self._bars_to_daily_df(bars)
        except Exception as e:
            logger.error(f"[DataCache] {symbol} 일봉 수집 오류: {e}")
            return None

    def _fetch_5min_all(self, symbols: List[str], start: str, end: str) -> None:
        """5분봉 수집 (종목별 순차, Rate limit 관리)."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        import pytz

        client = self._get_client()
        tz = pytz.timezone("America/New_York")
        total = len(symbols)

        for idx, sym in enumerate(symbols, 1):
            try:
                req = StockBarsRequest(
                    symbol_or_symbols=[sym],
                    timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                    start=datetime.strptime(start, "%Y-%m-%d"),
                    end=datetime.strptime(end, "%Y-%m-%d"),
                    feed="iex",
                )
                raw = client.get_stock_bars(req)
                bars = raw.data.get(sym)
                if not bars:
                    logger.warning(f"[DataCache] {sym}: 5분봉 없음")
                    continue
                df = self._bars_to_5min_df(bars, tz)
                df.to_parquet(self._5min_path(sym))
                logger.info(f"[DataCache] ({idx}/{total}) {sym}: 5분봉 {len(df)}봉 저장")
                time.sleep(0.35)  # ~170 req/min — Rate limit 여유
            except Exception as e:
                logger.error(f"[DataCache] {sym} 5분봉 수집 오류: {e}")
                time.sleep(1)

    def _fetch_5min_single(self, symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """단일 종목 5분봉 수집."""
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        import pytz
        try:
            req = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                start=datetime.strptime(start, "%Y-%m-%d"),
                end=datetime.strptime(end, "%Y-%m-%d"),
                feed="iex",
            )
            raw = self._get_client().get_stock_bars(req)
            bars = raw.data.get(symbol)
            if not bars:
                return None
            return self._bars_to_5min_df(bars, pytz.timezone("America/New_York"))
        except Exception as e:
            logger.error(f"[DataCache] {symbol} 5분봉 수집 오류: {e}")
            return None

    # ── 변환 헬퍼 ─────────────────────────────────────────────────────────

    @staticmethod
    def _bars_to_daily_df(bars) -> pd.DataFrame:
        rows = []
        for b in bars:
            d = b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp
            rows.append({
                "date":   d,
                "open":   float(b.open),
                "high":   float(b.high),
                "low":    float(b.low),
                "close":  float(b.close),
                "volume": int(b.volume),
            })
        df = pd.DataFrame(rows).sort_values("date")
        df.set_index("date", inplace=True)
        return df

    @staticmethod
    def _bars_to_5min_df(bars, tz) -> pd.DataFrame:
        rows = []
        for b in bars:
            ts = b.timestamp
            ts_et = ts.astimezone(tz) if (hasattr(ts, "tzinfo") and ts.tzinfo) else tz.localize(ts)
            rows.append({
                "timestamp": ts_et,
                "open":      float(b.open),
                "high":      float(b.high),
                "low":       float(b.low),
                "close":     float(b.close),
                "volume":    int(b.volume),
            })
        df = pd.DataFrame(rows).sort_values("timestamp")
        df.set_index("timestamp", inplace=True)
        return df
