"""
워치리스트 자동 생성 모듈

전체 시장을 스캔하여 급등/거래량 급증 종목을 선별합니다.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import pandas as pd
import logging
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus

logger = logging.getLogger(__name__)

# 배치 크기
SNAPSHOT_BATCH_SIZE = 500   # 스냅샷 API: 요청당 최대 심볼 수
BARS_BATCH_SIZE = 200        # 바 API: 요청당 최대 심볼 수

# 캐시 TTL (초)
UNIVERSE_CACHE_TTL = 86400   # 유니버스: 1일
VOLUME_CACHE_TTL = 3600      # 거래량 평균: 1시간


class WatchlistGenerator:
    """
    워치리스트 자동 생성기

    기획서 요구사항:
    - gap > 임계값 (프리마켓 갭)
    - volume_ratio > 임계값 (평균 대비 거래량)
    - 상위 20개 종목 선별
    - Alpaca assets API 기반 동적 유니버스 (전체 미 증시 활성 종목)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        gap_threshold: float = 1.5,           # 완화된 기본값 (기존 3.0)
        volume_ratio_threshold: float = 1.5,   # 완화된 기본값 (기존 3.0)
        max_watchlist_size: int = 20,
        paper: bool = True
    ):
        self.client = StockHistoricalDataClient(api_key, api_secret)
        self.trading_client = TradingClient(api_key, api_secret, paper=paper)
        self.gap_threshold = gap_threshold
        self.volume_ratio_threshold = volume_ratio_threshold
        self.max_watchlist_size = max_watchlist_size

        # 유니버스 캐시 (일 1회 갱신)
        self._universe_cache: List[str] = []
        self._universe_last_refresh: Optional[datetime] = None

        # 거래량 평균 캐시 (시간당 1회 갱신)
        self._volume_cache: Dict[str, float] = {}
        self._volume_last_refresh: Optional[datetime] = None

        # 폴백 유니버스 (Alpaca API 실패 시 사용)
        self._fallback_universe = self._get_default_universe()
        self.universe = self._fallback_universe

    def _get_default_universe(self) -> List[str]:
        """폴백용 기본 종목 유니버스 (Alpaca API 실패 시)"""
        return [
            # 테크
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX',
            # 금융
            'JPM', 'BAC', 'WFC', 'GS', 'MS',
            # 헬스케어
            'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO',
            # 소비재
            'WMT', 'HD', 'DIS', 'NKE', 'SBUX',
            # 에너지
            'XOM', 'CVX', 'COP',
            # 통신
            'T', 'VZ', 'TMUS',
            # 인더스트리얼
            'BA', 'CAT', 'GE', 'UPS',
            # 리테일/기타
            'COST', 'TGT', 'AMD', 'INTC', 'CSCO', 'ORCL', 'ADBE',
            # 고변동성 인기 종목
            'COIN', 'SNAP', 'UBER', 'LYFT', 'SQ', 'ROKU', 'PLTR', 'SOFI'
        ]

    def _is_market_hours(self) -> bool:
        """미국 시장 시간 체크 (간단 버전)"""
        et_tz = timezone(timedelta(hours=-5))
        now_et = datetime.now(et_tz)

        if now_et.weekday() >= 5:
            return False

        market_open = now_et.replace(hour=9, minute=30, second=0)
        market_close = now_et.replace(hour=16, minute=0, second=0)

        return market_open <= now_et <= market_close

    async def _fetch_dynamic_universe(self) -> List[str]:
        """
        Alpaca assets API에서 활성 US 주식 유니버스 동적 조회

        - NASDAQ/NYSE/ARCA/BATS 상장 종목만 포함 (OTC 제외)
        - 거래 가능(tradable) 종목만 포함
        - 일 1회 캐싱
        """
        now = datetime.now(timezone.utc)

        # 캐시 유효 시 재사용
        if (self._universe_last_refresh and
                (now - self._universe_last_refresh).total_seconds() < UNIVERSE_CACHE_TTL and
                self._universe_cache):
            return self._universe_cache

        try:
            logger.info("Alpaca assets API에서 전체 유니버스 갱신 중...")
            request = GetAssetsRequest(
                asset_class=AssetClass.US_EQUITY,
                status=AssetStatus.ACTIVE
            )
            assets = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.trading_client.get_all_assets(request)
            )

            # 필터: 거래 가능 + 메이저 거래소 (OTC/PINK 제외) + 특수 심볼 제외
            valid_exchanges = {'NASDAQ', 'NYSE', 'ARCA', 'BATS'}
            symbols = [
                asset.symbol
                for asset in assets
                if asset.tradable
                and asset.exchange in valid_exchanges
                and '.' not in asset.symbol   # BRK.A 등 클래스 주식 제외
                and '/' not in asset.symbol   # 특수 종목 제외
            ]

            self._universe_cache = symbols
            self._universe_last_refresh = now
            logger.info(f"유니버스 갱신 완료: {len(symbols)}개 종목 (메이저 거래소 기준)")
            return symbols

        except Exception as e:
            logger.error(f"동적 유니버스 조회 실패, 폴백 유니버스 사용: {e}")
            if self._universe_cache:
                return self._universe_cache
            return self._fallback_universe

    async def generate_watchlist(self) -> List[Dict]:
        """
        워치리스트 생성

        Returns:
            List[Dict]: 선별된 종목 정보
        """
        is_market_hours = self._is_market_hours()

        # 동적 유니버스 갱신 (일 1회)
        self.universe = await self._fetch_dynamic_universe()
        logger.info(f"워치리스트 생성 시작 (유니버스: {len(self.universe)}개 종목, 장중: {is_market_hours})")

        try:
            # 1. 스냅샷 수집 (배치 처리)
            snapshots = await self._get_snapshots(self.universe)
            logger.info(f"스냅샷 조회 완료: {len(snapshots)}개")

            # 2. 거래량 평균 계산 (캐시 활용, 배치 처리)
            volume_averages = await self._get_volume_averages(self.universe)
            logger.info(f"거래량 평균 계산 완료: {len(volume_averages)}개")

            # 3. 필터링 및 점수 계산
            candidates = []
            skipped = 0

            for symbol in self.universe:
                try:
                    snapshot = snapshots.get(symbol)
                    vol_avg = volume_averages.get(symbol, 0)

                    if not snapshot:
                        skipped += 1
                        logger.debug(f"{symbol}: 스냅샷 없음")
                        continue

                    if vol_avg == 0:
                        skipped += 1
                        logger.debug(f"{symbol}: 거래량 평균 없음")
                        continue

                    # 갭 계산: 전일 종가 기준 (daily_bar.close는 오늘 현재가이므로 사용 금지)
                    if snapshot.previous_daily_bar:
                        prev_close = snapshot.previous_daily_bar.close
                    else:
                        skipped += 1
                        logger.debug(f"{symbol}: previous_daily_bar 없음 (전일 종가 불명)")
                        continue

                    if snapshot.latest_trade:
                        current_price = snapshot.latest_trade.price
                    elif snapshot.latest_quote and snapshot.latest_quote.ask_price:
                        current_price = snapshot.latest_quote.ask_price
                    else:
                        skipped += 1
                        logger.debug(f"{symbol}: 현재가 없음")
                        continue

                    gap = ((current_price - prev_close) / prev_close) * 100.0

                    # 거래량 비율
                    current_volume = snapshot.daily_bar.volume if snapshot.daily_bar else 0
                    volume_ratio = current_volume / vol_avg if vol_avg > 0 else 0

                    logger.debug(
                        f"{symbol}: 현재={current_volume:,}, 평균={vol_avg:,.0f}, "
                        f"비율={volume_ratio:.2f}배, 갭={gap:.2f}%"
                    )

                    # 필터 조건 (장외 시간에는 거래량 필터 제외)
                    meets_gap = gap > self.gap_threshold
                    meets_volume = volume_ratio > self.volume_ratio_threshold if is_market_hours else False

                    if meets_gap or meets_volume:
                        reason = []
                        if meets_gap:
                            reason.append(f"갭 {gap:.1f}%")
                        if meets_volume:
                            reason.append(f"거래량 {volume_ratio:.1f}배")
                        if not is_market_hours and not meets_volume:
                            reason.append("(장외-거래량 미사용)")

                        candidates.append({
                            'symbol': symbol,
                            'gap': gap,
                            'volume_ratio': volume_ratio,
                            'current_price': current_price,
                            'prev_close': prev_close,
                            'current_volume': current_volume,
                            'avg_volume': vol_avg,
                            'reason': ' + '.join(reason),
                            'score': volume_ratio
                        })

                except Exception as e:
                    logger.warning(f"{symbol} 처리 중 오류: {e}")
                    continue

            # 4. 거래량 비율 기준 정렬 및 상위 N개 선택
            candidates.sort(key=lambda x: x['score'], reverse=True)
            watchlist = candidates[:self.max_watchlist_size]

            logger.info(f"처리 결과: 총 {len(self.universe)}개, 후보 {len(candidates)}개, 스킵 {skipped}개")
            logger.info(f"[OK] 워치리스트 생성 완료: {len(watchlist)}개 종목")

            if watchlist:
                logger.info("상위 5개:")
                for i, stock in enumerate(watchlist[:5], 1):
                    logger.info(f"  {i}. {stock['symbol']}: {stock['reason']}")
            else:
                logger.warning("조건을 만족하는 종목이 없습니다.")
                if is_market_hours:
                    logger.warning(f"조건: gap>{self.gap_threshold}% OR volume>{self.volume_ratio_threshold}배")
                else:
                    logger.warning(f"조건: gap>{self.gap_threshold}% (장외-거래량 필터 미사용)")
                logger.warning("임계값을 낮추거나 장중 시간에 다시 시도하세요.")

            return watchlist

        except Exception as e:
            logger.error(f"워치리스트 생성 실패: {e}")
            return []

    async def _get_snapshots(self, symbols: List[str]) -> Dict:
        """
        종목 스냅샷 배치 조회 (SNAPSHOT_BATCH_SIZE 단위)
        """
        all_snapshots = {}
        total_batches = (len(symbols) + SNAPSHOT_BATCH_SIZE - 1) // SNAPSHOT_BATCH_SIZE

        for batch_idx, i in enumerate(range(0, len(symbols), SNAPSHOT_BATCH_SIZE), 1):
            batch = symbols[i:i + SNAPSHOT_BATCH_SIZE]
            try:
                if total_batches > 1:
                    logger.debug(f"스냅샷 배치 {batch_idx}/{total_batches} ({len(batch)}개)")
                request = StockSnapshotRequest(symbol_or_symbols=batch)
                snapshots = await asyncio.get_event_loop().run_in_executor(
                    None, lambda r=request: self.client.get_stock_snapshot(r)
                )
                all_snapshots.update(snapshots)
            except Exception as e:
                logger.warning(f"스냅샷 배치 {batch_idx} 실패: {e}")

        return all_snapshots

    async def _get_volume_averages(self, symbols: List[str], period: int = 20) -> Dict[str, float]:
        """
        거래량 평균 계산 (VOLUME_CACHE_TTL 캐시, BARS_BATCH_SIZE 단위 배치)
        """
        now = datetime.now(timezone.utc)

        # 캐시 유효 시 재사용
        if (self._volume_last_refresh and
                (now - self._volume_last_refresh).total_seconds() < VOLUME_CACHE_TTL and
                self._volume_cache):
            return self._volume_cache

        logger.info(f"거래량 평균 갱신 중 (캐시 유효기간 {VOLUME_CACHE_TTL // 60}분)...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period + 5)

        all_averages = {}
        total_batches = (len(symbols) + BARS_BATCH_SIZE - 1) // BARS_BATCH_SIZE

        for batch_idx, i in enumerate(range(0, len(symbols), BARS_BATCH_SIZE), 1):
            batch = symbols[i:i + BARS_BATCH_SIZE]
            try:
                if total_batches > 1 and batch_idx % 10 == 0:
                    logger.info(f"거래량 배치 {batch_idx}/{total_batches}...")
                # feed 미지정: 스냅샷과 동일한 피드를 사용해 volume 비율 왜곡 방지
                # (IEX 고정 시 스냅샷 SIP 거래량과 비교되어 ~18배 과장됨)
                request = StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame(1, TimeFrameUnit.Day),
                    start=start_date,
                    end=end_date,
                )
                bars = await asyncio.get_event_loop().run_in_executor(
                    None, lambda r=request: self.client.get_stock_bars(r)
                )
                df = bars.df
                if not df.empty:
                    df = df.reset_index()
                    batch_avgs = df.groupby('symbol')['volume'].mean().to_dict()
                    all_averages.update(batch_avgs)
            except Exception as e:
                logger.warning(f"거래량 배치 {batch_idx} 실패: {e}")

        self._volume_cache = all_averages
        self._volume_last_refresh = now
        logger.info(f"거래량 평균 갱신 완료: {len(all_averages)}개")
        return all_averages

    def update_universe(self, symbols: List[str]):
        """
        종목 유니버스 수동 업데이트

        Args:
            symbols: 새로운 종목 리스트
        """
        self.universe = symbols
        self._universe_cache = symbols
        self._universe_last_refresh = datetime.now(timezone.utc)
        logger.info(f"종목 유니버스 수동 업데이트: {len(symbols)}개")


# 기획서 예시 코드 (참고용)
def select_watchlist_example(stocks):
    """
    기획서의 워치리스트 선별 로직 (예시)
    """
    return sorted(
        [s for s in stocks if s.gap > 3 or s.volume_ratio > 3],
        key=lambda x: x.volume_ratio,
        reverse=True
    )[:20]
