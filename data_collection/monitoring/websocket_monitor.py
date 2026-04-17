"""
WebSocket 실시간 가격 스트림 SL/TP 모니터링 (NEW-02)

Alpaca WebSocket 스트림으로 포지션 종목을 실시간 구독하여
SL/TP 히트 시 < 1초 내 즉시 청산 주문을 실행합니다.

기존 30초 폴링(_stop_loss_monitor)은 WebSocket 연결 장애 시 폴백으로만 유지.
"""
import asyncio
import logging
from typing import Dict, Callable, Optional, Set

logger = logging.getLogger(__name__)


class WebSocketPriceMonitor:
    """
    Alpaca WebSocket 실시간 가격 스트림 모니터

    포지션 종목의 quote 스트림을 구독하여
    SL/TP 조건 충족 시 콜백 함수를 즉시 호출합니다.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        on_sl_hit: Callable,    # async def(symbol, price, reason) 콜백
        stop_loss_pct: float = 2.0,
        trailing_stop_pct: float = 2.0,
        partial_tp_pct: float = 3.0,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.on_sl_hit = on_sl_hit
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.partial_tp_pct = partial_tp_pct

        # {symbol: {entry_price, sl_price, highest_price, partial_tp_done}}
        self._positions: Dict[str, dict] = {}
        self._subscribed: Set[str] = set()
        self._ws_task: Optional[asyncio.Task] = None
        self._is_running = False

    def update_positions(self, positions: Dict[str, dict]):
        """
        모니터링 포지션 갱신

        Args:
            positions: {symbol: {entry_price, sl_price, highest_price, partial_tp_done}}
        """
        self._positions = positions
        new_symbols = set(positions.keys())

        added = new_symbols - self._subscribed
        removed = self._subscribed - new_symbols

        if added:
            logger.info(f"[WS] 구독 추가: {added}")
        if removed:
            logger.info(f"[WS] 구독 제거: {removed}")

        self._subscribed = new_symbols

    async def start(self):
        """WebSocket 스트림 시작"""
        if self._is_running:
            return
        self._is_running = True
        self._ws_task = asyncio.create_task(self._stream_loop(), name="ws_price_monitor")
        logger.info("[WS] 실시간 가격 스트림 시작")

    async def stop(self):
        """WebSocket 스트림 중지"""
        self._is_running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        logger.info("[WS] 실시간 가격 스트림 중지")

    async def _stream_loop(self):
        """메인 스트림 루프"""
        while self._is_running:
            if not self._subscribed:
                await asyncio.sleep(5)
                continue
            try:
                await self._subscribe_and_process()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[WS] 스트림 오류, 5초 후 재연결: {e}")
                await asyncio.sleep(5)

    async def _subscribe_and_process(self):
        """Alpaca WebSocket 구독 및 처리"""
        try:
            from alpaca.data.live import StockDataStream
        except ImportError:
            logger.warning("[WS] alpaca-py StockDataStream 없음 - WebSocket 비활성화")
            self._is_running = False
            return

        symbols = list(self._subscribed)
        if not symbols:
            return

        stream = StockDataStream(self.api_key, self.api_secret)

        async def on_quote(quote):
            symbol = quote.symbol
            bid = float(quote.bid_price) if quote.bid_price else 0.0
            ask = float(quote.ask_price) if quote.ask_price else 0.0
            mid = (bid + ask) / 2 if (bid > 0 and ask > 0) else (bid or ask)
            if mid <= 0:
                return
            await self._check_sl_tp(symbol, mid)

        stream.subscribe_quotes(on_quote, *symbols)

        try:
            await asyncio.wait_for(stream._run_forever(), timeout=300)
        except asyncio.TimeoutError:
            pass
        finally:
            try:
                await stream.stop_ws()
            except Exception:
                pass

    async def _check_sl_tp(self, symbol: str, price: float):
        """SL/TP 조건 확인 후 콜백 호출"""
        pos = self._positions.get(symbol)
        if pos is None:
            return

        # 최고가 갱신
        if price > pos.get('highest_price', price):
            pos['highest_price'] = price

        # 손절 체크
        sl_price = pos.get('sl_price', 0)
        if sl_price > 0 and price <= sl_price:
            logger.warning(f"[WS SL] {symbol}: ${price:.2f} ≤ SL ${sl_price:.2f}")
            await self.on_sl_hit(symbol, price, "STOP_LOSS")
            self._positions.pop(symbol, None)
            self._subscribed.discard(symbol)
            return

        # Trailing Stop 체크
        highest = pos.get('highest_price', price)
        trailing_sl = highest * (1 - self.trailing_stop_pct / 100)
        entry_price = pos.get('entry_price', price)
        if price <= trailing_sl and price > entry_price:
            logger.warning(
                f"[WS TS] {symbol}: ${price:.2f} ≤ trailing SL ${trailing_sl:.2f} "
                f"(최고가 ${highest:.2f})"
            )
            await self.on_sl_hit(symbol, price, "TRAILING_STOP")
            self._positions.pop(symbol, None)
            self._subscribed.discard(symbol)
            return

        # 부분 익절 체크
        if not pos.get('partial_tp_done', False):
            partial_tp = entry_price * (1 + self.partial_tp_pct / 100)
            if price >= partial_tp:
                pos['partial_tp_done'] = True
                logger.info(f"[WS TP] {symbol}: ${price:.2f} ≥ 부분익절 ${partial_tp:.2f}")
                await self.on_sl_hit(symbol, price, "PARTIAL_TP")
