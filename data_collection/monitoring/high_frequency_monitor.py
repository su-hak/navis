"""
고주기 모니터링 엔진

워치리스트 종목을 5~10초마다 감시하여 급등/급락 감지
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Callable, Optional
import logging
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MonitoredStock:
    """모니터링 중인 종목 정보"""
    symbol: str
    prev_price: float
    current_price: float = 0.0
    last_check_time: datetime = field(default_factory=datetime.now)
    alert_count: int = 0  # 알림 발생 횟수


class HighFrequencyMonitor:
    """
    고주기 모니터링 엔진

    기획서 요구사항:
    - 워치리스트 종목만 5~10초마다 감시
    - 1.5% 변동 감지 시 즉시 실행
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        monitor_interval: int = 10,  # 초
        price_change_threshold: float = 1.5,  # 1.5%
        callback: Optional[Callable] = None
    ):
        """
        초기화

        Args:
            api_key: Alpaca API Key
            api_secret: Alpaca API Secret
            monitor_interval: 모니터링 간격 (초)
            price_change_threshold: 가격 변동 임계값 (%)
            callback: 신호 발생 시 호출할 콜백 함수
        """
        self.client = StockHistoricalDataClient(api_key, api_secret)
        self.monitor_interval = monitor_interval
        self.price_change_threshold = price_change_threshold
        self.callback = callback

        # 모니터링 상태
        self.watchlist: Dict[str, MonitoredStock] = {}
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None

        logger.info(f"고주기 모니터 초기화: {monitor_interval}초 간격, {price_change_threshold}% 변동 감지")

    def set_watchlist(self, watchlist: List[Dict]):
        """
        워치리스트 설정

        Args:
            watchlist: WatchlistGenerator.generate_watchlist() 결과
        """
        self.watchlist.clear()

        for stock in watchlist:
            self.watchlist[stock['symbol']] = MonitoredStock(
                symbol=stock['symbol'],
                prev_price=stock['current_price']
            )

        logger.info(f"워치리스트 설정 완료: {len(self.watchlist)}개 종목")
        for symbol in list(self.watchlist.keys())[:5]:
            logger.info(f"  - {symbol}")

    async def start(self):
        """모니터링 시작"""
        if self.is_running:
            logger.warning("이미 모니터링 중입니다")
            return

        if not self.watchlist:
            logger.warning("워치리스트가 비어있습니다. set_watchlist()를 먼저 호출하세요")
            return

        self.is_running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"🚀 고주기 모니터링 시작 ({len(self.watchlist)}개 종목)")

    async def stop(self):
        """모니터링 중지"""
        if not self.is_running:
            return

        self.is_running = False

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("고주기 모니터링 중지")

    async def _monitor_loop(self):
        """메인 모니터링 루프"""
        loop_count = 0
        while self.is_running:
            try:
                loop_count += 1
                logger.debug(f"[모니터링 루프 #{loop_count}] {len(self.watchlist)}개 종목 체크 중...")

                # 모든 워치리스트 종목 동시 모니터링
                tasks = [self._monitor_stock(symbol, stock) for symbol, stock in self.watchlist.items()]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 에러 체크
                errors = [r for r in results if isinstance(r, Exception)]
                if errors:
                    logger.warning(f"모니터링 중 {len(errors)}개 에러 발생")

                # 간격 대기
                await asyncio.sleep(self.monitor_interval)

            except asyncio.CancelledError:
                logger.info("모니터링 루프 취소됨")
                break
            except Exception as e:
                logger.error(f"모니터링 루프 오류: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(self.monitor_interval)

    async def _monitor_stock(self, symbol: str, stock: MonitoredStock):
        """
        개별 종목 모니터링 (기획서의 monitor 함수)

        기획서 코드:
        async def monitor(stock):
            price = await get_price(stock)
            change = (price - stock.prev_price) / stock.prev_price

            if change > 0.015:  # 1.5%
                execute_trade(stock)
        """
        try:
            # 현재가 조회
            current_price = await self._get_current_price(symbol)

            if current_price is None:
                logger.debug(f"[{symbol}] 현재가 조회 실패")
                return

            # 가격 변동률 계산
            change = ((current_price - stock.prev_price) / stock.prev_price) * 100.0

            # 정기 로그 (변동이 없어도 출력)
            logger.debug(f"[{symbol}] ${stock.prev_price:.2f} → ${current_price:.2f} ({change:+.2f}%)")

            # 임계값 초과 감지
            if abs(change) >= self.price_change_threshold:
                # 신호 생성 및 콜백 호출
                signal = {
                    'symbol': symbol,
                    'prev_price': stock.prev_price,
                    'current_price': current_price,
                    'change_percent': change,
                    'direction': 'UP' if change > 0 else 'DOWN',
                    'timestamp': datetime.now(),
                    'reason': f"{change:+.2f}% 변동 감지"
                }

                logger.warning(f"⚡ [{symbol}] {change:+.2f}% 변동 감지! {stock.prev_price:.2f} → {current_price:.2f}")

                # 콜백 실행 (매매 신호 전달)
                if self.callback:
                    try:
                        if asyncio.iscoroutinefunction(self.callback):
                            await self.callback(signal)
                        else:
                            self.callback(signal)
                    except Exception as e:
                        logger.error(f"콜백 실행 실패: {e}")

                # 알림 카운트 증가
                stock.alert_count += 1

            # 상태 업데이트 (prev_price를 현재가로 갱신하여 다음 루프에서 중복 감지 방지)
            stock.prev_price = current_price
            stock.current_price = current_price
            stock.last_check_time = datetime.now()

        except Exception as e:
            logger.error(f"{symbol} 모니터링 오류: {e}")

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        현재가 조회

        Args:
            symbol: 종목 심볼

        Returns:
            현재가 또는 None
        """
        try:
            # Latest Trade 조회 (가장 최근 체결가)
            request = StockLatestTradeRequest(symbol_or_symbols=[symbol])
            trades = self.client.get_stock_latest_trade(request)

            if symbol in trades:
                return float(trades[symbol].price)

            # Trade가 없으면 Quote 사용 (호가)
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = self.client.get_stock_latest_quote(quote_request)

            if symbol in quotes:
                # 중간가 사용
                bid = quotes[symbol].bid_price
                ask = quotes[symbol].ask_price
                return (bid + ask) / 2.0

            return None

        except Exception as e:
            logger.error(f"{symbol} 현재가 조회 실패: {e}")
            return None

    def get_statistics(self) -> Dict:
        """
        모니터링 통계 반환

        Returns:
            Dict: 통계 정보
        """
        total_alerts = sum(stock.alert_count for stock in self.watchlist.values())

        return {
            'watchlist_size': len(self.watchlist),
            'is_running': self.is_running,
            'monitor_interval': self.monitor_interval,
            'price_change_threshold': self.price_change_threshold,
            'total_alerts': total_alerts,
            'stocks': [
                {
                    'symbol': symbol,
                    'prev_price': stock.prev_price,
                    'current_price': stock.current_price,
                    'alert_count': stock.alert_count,
                    'last_check': stock.last_check_time.isoformat() if stock.last_check_time else None
                }
                for symbol, stock in self.watchlist.items()
            ]
        }


# 기획서 예시 코드 (참고용)
async def monitor_example(stock):
    """
    기획서의 모니터링 로직 (예시)
    """
    price = await get_price(stock)  # noqa
    change = (price - stock.prev_price) / stock.prev_price

    if change > 0.015:
        execute_trade(stock)  # noqa


async def run_example(watchlist):
    """
    기획서의 실행 로직 (예시)
    """
    await asyncio.gather(*[monitor_example(s) for s in watchlist])


async def get_price(stock):
    """예시 함수 (실제로는 API 호출)"""
    pass


def execute_trade(stock):
    """예시 함수 (실제로는 주문 실행)"""
    pass
