"""
워치리스트 자동 생성 모듈

전체 시장을 스캔하여 급등/거래량 급증 종목을 선별합니다.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import logging
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import DataFeed

logger = logging.getLogger(__name__)


class WatchlistGenerator:
    """
    워치리스트 자동 생성기

    기획서 요구사항:
    - gap > 3% (프리마켓 갭)
    - volume_ratio > 3배 (평균 대비 거래량)
    - 상위 20개 종목 선별
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        gap_threshold: float = 3.0,  # 3% 갭
        volume_ratio_threshold: float = 3.0,  # 3배 거래량
        max_watchlist_size: int = 20
    ):
        """
        초기화

        Args:
            api_key: Alpaca API Key
            api_secret: Alpaca API Secret
            gap_threshold: 갭 임계값 (%)
            volume_ratio_threshold: 거래량 비율 임계값
            max_watchlist_size: 워치리스트 최대 크기
        """
        self.client = StockHistoricalDataClient(api_key, api_secret)
        self.gap_threshold = gap_threshold
        self.volume_ratio_threshold = volume_ratio_threshold
        self.max_watchlist_size = max_watchlist_size

        # 기본 유니버스 (S&P 500 일부 + 인기 종목)
        # 실제로는 전체 S&P 500 또는 Alpaca의 활성 종목 리스트 사용
        self.universe = self._get_default_universe()

    def _get_default_universe(self) -> List[str]:
        """
        기본 종목 유니버스 반환

        실제 운영시:
        - S&P 500 전체
        - Alpaca assets API로 활성 종목 가져오기
        - 또는 특정 섹터/시가총액 기준 필터링
        """
        # 주요 종목 예시 (실제로는 더 확장 필요)
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
        from datetime import timezone, timedelta
        et_tz = timezone(timedelta(hours=-5))
        now_et = datetime.now(et_tz)

        # 주말 제외
        if now_et.weekday() >= 5:
            return False

        # 9:30 AM ~ 4:00 PM ET
        market_open = now_et.replace(hour=9, minute=30, second=0)
        market_close = now_et.replace(hour=16, minute=0, second=0)

        return market_open <= now_et <= market_close

    async def generate_watchlist(self) -> List[Dict]:
        """
        워치리스트 생성

        Returns:
            List[Dict]: 선별된 종목 정보
                {
                    'symbol': str,
                    'gap': float,  # 갭 비율 (%)
                    'volume_ratio': float,  # 거래량 비율
                    'current_price': float,
                    'prev_close': float,
                    'reason': str  # 선정 이유
                }
        """
        is_market_hours = self._is_market_hours()
        logger.info(f"워치리스트 생성 시작 (유니버스: {len(self.universe)}개 종목, 장중: {is_market_hours})")

        try:
            # 1. 최근 데이터 수집 (어제 종가 + 오늘 현재가)
            snapshots = await self._get_snapshots(self.universe)
            logger.info(f"스냅샷 조회 완료: {len(snapshots)}개")

            # 2. 거래량 평균 계산 (20일 평균)
            volume_averages = await self._get_volume_averages(self.universe)
            logger.info(f"거래량 평균 계산 완료: {len(volume_averages)}개")

            # 3. 필터링 및 점수 계산
            candidates = []
            processed = 0
            skipped = 0

            for symbol in self.universe:
                try:
                    processed += 1
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

                    # 갭 계산 (프리마켓 또는 현재가 vs 전일 종가)
                    prev_close = snapshot.daily_bar.close if snapshot.daily_bar else snapshot.previous_daily_bar.close
                    current_price = snapshot.latest_trade.price if snapshot.latest_trade else snapshot.latest_quote.ask_price

                    gap = ((current_price - prev_close) / prev_close) * 100.0

                    # 거래량 비율
                    current_volume = snapshot.daily_bar.volume if snapshot.daily_bar else 0
                    volume_ratio = current_volume / vol_avg if vol_avg > 0 else 0

                    # 디버깅: 거래량 상세 로그
                    logger.debug(f"{symbol}: 현재={current_volume:,}, 평균={vol_avg:,.0f}, 비율={volume_ratio:.2f}배, 갭={gap:.2f}%")

                    # 필터링 조건 (장외 시간에는 거래량 필터 제외)
                    meets_gap = gap > self.gap_threshold
                    meets_volume = volume_ratio > self.volume_ratio_threshold if is_market_hours else False

                    if meets_gap or meets_volume:
                        reason = []
                        if meets_gap:
                            reason.append(f"갭 {gap:.1f}%")
                        if meets_volume:
                            reason.append(f"거래량 {volume_ratio:.1f}배")

                        # 장외 시간 표시
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
                            'score': volume_ratio  # 정렬용 점수 (거래량 비율 우선)
                        })

                except Exception as e:
                    logger.warning(f"{symbol} 처리 중 오류: {e}")
                    continue

            # 4. 거래량 비율 기준 정렬 및 상위 N개 선택
            candidates.sort(key=lambda x: x['score'], reverse=True)
            watchlist = candidates[:self.max_watchlist_size]

            logger.info(f"처리 결과: 총 {processed}개, 후보 {len(candidates)}개, 스킵 {skipped}개")
            logger.info(f"[OK] 워치리스트 생성 완료: {len(watchlist)}개 종목")

            if watchlist:
                logger.info(f"상위 5개:")
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
        종목 스냅샷 조회 (현재가, 전일 종가 등)

        Args:
            symbols: 종목 리스트

        Returns:
            Dict[symbol, snapshot]
        """
        try:
            request = StockSnapshotRequest(symbol_or_symbols=symbols)
            snapshots = self.client.get_stock_snapshot(request)
            return snapshots
        except Exception as e:
            logger.error(f"스냅샷 조회 실패: {e}")
            return {}

    async def _get_volume_averages(self, symbols: List[str], period: int = 20) -> Dict[str, float]:
        """
        거래량 평균 계산

        Args:
            symbols: 종목 리스트
            period: 평균 기간 (일)

        Returns:
            Dict[symbol, avg_volume]
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period + 5)  # 여유 기간

            request = StockBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=TimeFrame(1, TimeFrameUnit.Day),
                start=start_date,
                end=end_date,
                feed=DataFeed.IEX
            )

            bars = self.client.get_stock_bars(request)
            df = bars.df

            if df.empty:
                return {}

            # 심볼별 거래량 평균 계산
            df = df.reset_index()
            volume_avgs = df.groupby('symbol')['volume'].mean().to_dict()

            return volume_avgs

        except Exception as e:
            logger.error(f"거래량 평균 계산 실패: {e}")
            return {}

    def update_universe(self, symbols: List[str]):
        """
        종목 유니버스 업데이트

        Args:
            symbols: 새로운 종목 리스트
        """
        self.universe = symbols
        logger.info(f"종목 유니버스 업데이트: {len(symbols)}개")


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
