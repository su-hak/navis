"""
Alpaca 브로커 구현체
Alpaca Trading API를 사용한 실제 주문 실행
"""
import logging
from typing import List, Optional
from datetime import datetime

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError

from .broker_interface import BrokerInterface
from ..core.order_models import (
    Order, OrderAction, OrderType, TimeInForce, OrderStatus,
    Position, AccountInfo, BrokerError
)

logger = logging.getLogger(__name__)


class AlpacaBroker(BrokerInterface):
    """
    Alpaca 브로커 구현체
    """

    def __init__(self, config: dict):
        """
        초기화

        Args:
            config: {
                'api_key': str,
                'secret_key': str,
                'base_url': str  # paper: https://paper-api.alpaca.markets
            }
        """
        super().__init__(config)
        self.api: Optional[tradeapi.REST] = None

    def connect(self) -> bool:
        """브로커 연결"""
        try:
            api_key = self.config.get('api_key')
            secret_key = self.config.get('secret_key')
            base_url = self.config.get('base_url', 'https://paper-api.alpaca.markets')

            if not api_key or not secret_key:
                raise BrokerError("API 키가 설정되지 않았습니다", retryable=False)

            # Alpaca API 클라이언트 생성
            self.api = tradeapi.REST(
                key_id=api_key,
                secret_key=secret_key,
                base_url=base_url,
                api_version='v2'
            )

            # 연결 테스트
            account = self.api.get_account()
            logger.info(f"Alpaca 연결 성공 - 계좌 ID: {account.id}")

            self._initialized = True
            return True

        except APIError as e:
            logger.error(f"Alpaca 연결 실패: {e}")
            raise BrokerError(f"Alpaca 연결 실패: {str(e)}", retryable=True)
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            raise BrokerError(f"연결 오류: {str(e)}", retryable=False)

    def disconnect(self) -> None:
        """연결 해제"""
        self.api = None
        self._initialized = False
        logger.info("Alpaca 연결 해제")

    def submit_order(self, order: Order) -> str:
        """주문 제출"""
        self.validate_connection()

        try:
            # Order 객체를 Alpaca API 형식으로 변환
            side = 'buy' if order.action == OrderAction.BUY else 'sell'
            order_type = self._convert_order_type(order.order_type)
            time_in_force = self._convert_time_in_force(order.time_in_force)

            # 주문 파라미터 구성
            order_params = {
                'symbol': order.symbol,
                'qty': order.quantity,
                'side': side,
                'type': order_type,
                'time_in_force': time_in_force
            }

            # 지정가 추가
            if order.order_type == OrderType.LIMIT and order.limit_price:
                order_params['limit_price'] = order.limit_price

            # 스탑가 추가
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and order.stop_price:
                order_params['stop_price'] = order.stop_price

            logger.info(f"주문 제출 시도: {order_params}")

            # Alpaca API 호출
            alpaca_order = self.api.submit_order(**order_params)

            broker_order_id = alpaca_order.id
            logger.info(f"주문 제출 성공 - 브로커 ID: {broker_order_id}")

            return broker_order_id

        except APIError as e:
            error_msg = f"주문 제출 실패: {str(e)}"
            logger.error(error_msg)

            # 재시도 가능 여부 판단
            retryable = self._is_retryable_error(e)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=retryable)

        except Exception as e:
            error_msg = f"예상치 못한 오류: {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, retryable=False)

    def get_order(self, broker_order_id: str) -> dict:
        """주문 조회"""
        self.validate_connection()

        try:
            alpaca_order = self.api.get_order(broker_order_id)

            # Alpaca 주문 상태를 내부 상태로 변환
            status = self._convert_order_status(alpaca_order.status)

            order_info = {
                'status': status,
                'filled_quantity': int(alpaca_order.filled_qty or 0),
                'filled_price': float(alpaca_order.filled_avg_price or 0),
                'commission': 0.0,  # Alpaca는 수수료 무료
                'submitted_at': alpaca_order.submitted_at,
                'filled_at': alpaca_order.filled_at,
                'cancelled_at': alpaca_order.cancelled_at,
                'failed_at': alpaca_order.failed_at,
                'replaced_at': alpaca_order.replaced_at,
            }

            logger.debug(f"주문 조회 성공 - ID: {broker_order_id}, 상태: {status}")
            return order_info

        except APIError as e:
            error_msg = f"주문 조회 실패: {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=True)

    def cancel_order(self, broker_order_id: str) -> bool:
        """주문 취소"""
        self.validate_connection()

        try:
            self.api.cancel_order(broker_order_id)
            logger.info(f"주문 취소 성공 - ID: {broker_order_id}")
            return True

        except APIError as e:
            # 이미 체결되었거나 취소된 경우
            if e.status_code == 422:
                logger.warning(f"주문을 취소할 수 없음 - ID: {broker_order_id}")
                return False

            error_msg = f"주문 취소 실패: {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=True)

    def get_account(self) -> AccountInfo:
        """계좌 정보 조회"""
        self.validate_connection()

        try:
            account = self.api.get_account()

            # Alpaca API 버전에 따라 속성명이 다를 수 있으므로 안전하게 접근
            unrealized_pl = getattr(account, 'unrealized_pl', None) or \
                           getattr(account, 'unrealized_plpc', None) or 0
            realized_pl = getattr(account, 'realized_pl', None) or 0
            daytrade_count = getattr(account, 'daytrade_count', 0)
            pattern_day_trader = getattr(account, 'pattern_day_trader', False)

            account_info = AccountInfo(
                account_id=account.id,
                cash=float(account.cash),
                portfolio_value=float(account.portfolio_value),
                buying_power=float(account.buying_power),
                equity=float(account.equity),
                unrealized_pl=float(unrealized_pl),
                realized_pl=float(realized_pl),
                daytrade_count=int(daytrade_count),
                pattern_day_trader=pattern_day_trader,
                last_updated=datetime.now()
            )

            logger.debug(f"계좌 조회 성공 - 자산: ${account_info.equity:,.2f}")
            return account_info

        except APIError as e:
            error_msg = f"계좌 조회 실패: {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=True)

    def get_positions(self) -> List[Position]:
        """포지션 목록 조회"""
        self.validate_connection()

        try:
            alpaca_positions = self.api.list_positions()

            positions = []
            for pos in alpaca_positions:
                # 안전하게 속성 접근
                unrealized_pl = getattr(pos, 'unrealized_pl', 0)
                unrealized_plpc = getattr(pos, 'unrealized_plpc', 0)

                position = Position(
                    symbol=pos.symbol,
                    quantity=int(pos.qty),
                    avg_entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    market_value=float(pos.market_value),
                    unrealized_pl=float(unrealized_pl),
                    unrealized_pl_percent=float(unrealized_plpc) * 100
                )
                positions.append(position)

            logger.debug(f"포지션 조회 성공 - {len(positions)}개")
            return positions

        except APIError as e:
            error_msg = f"포지션 조회 실패: {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=True)

    def get_position(self, symbol: str) -> Optional[Position]:
        """특정 종목 포지션 조회"""
        self.validate_connection()

        try:
            pos = self.api.get_position(symbol)

            # 안전하게 속성 접근
            unrealized_pl = getattr(pos, 'unrealized_pl', 0)
            unrealized_plpc = getattr(pos, 'unrealized_plpc', 0)

            position = Position(
                symbol=pos.symbol,
                quantity=int(pos.qty),
                avg_entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price),
                market_value=float(pos.market_value),
                unrealized_pl=float(unrealized_pl),
                unrealized_pl_percent=float(unrealized_plpc) * 100
            )

            return position

        except APIError as e:
            # 포지션이 없는 경우
            if e.status_code == 404:
                return None

            error_msg = f"포지션 조회 실패: {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=True)

    def is_market_open(self) -> bool:
        """시장 개장 여부"""
        self.validate_connection()

        try:
            clock = self.api.get_clock()
            return clock.is_open

        except APIError as e:
            error_msg = f"시장 상태 조회 실패: {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=True)

    def get_current_price(self, symbol: str) -> float:
        """현재가 조회"""
        self.validate_connection()

        try:
            # 최신 거래 가격 조회
            trade = self.api.get_latest_trade(symbol)
            return float(trade.price)

        except APIError as e:
            error_msg = f"현재가 조회 실패 ({symbol}): {str(e)}"
            logger.error(error_msg)
            raise BrokerError(error_msg, error_code=str(e.status_code), retryable=True)

    # ============ 내부 헬퍼 메서드 ============

    def _convert_order_type(self, order_type: OrderType) -> str:
        """주문 타입 변환"""
        mapping = {
            OrderType.MARKET: 'market',
            OrderType.LIMIT: 'limit',
            OrderType.STOP: 'stop',
            OrderType.STOP_LIMIT: 'stop_limit'
        }
        return mapping[order_type]

    def _convert_time_in_force(self, tif: TimeInForce) -> str:
        """유효기간 변환"""
        mapping = {
            TimeInForce.DAY: 'day',
            TimeInForce.GTC: 'gtc',
            TimeInForce.IOC: 'ioc',
            TimeInForce.FOK: 'fok'
        }
        return mapping[tif]

    def _convert_order_status(self, alpaca_status: str) -> OrderStatus:
        """Alpaca 주문 상태 → 내부 상태"""
        mapping = {
            'new': OrderStatus.SUBMITTED,
            'pending_new': OrderStatus.PENDING,
            'accepted': OrderStatus.SUBMITTED,
            'partially_filled': OrderStatus.PARTIALLY_FILLED,
            'filled': OrderStatus.FILLED,
            'done_for_day': OrderStatus.CANCELLED,
            'canceled': OrderStatus.CANCELLED,
            'expired': OrderStatus.CANCELLED,
            'replaced': OrderStatus.CANCELLED,
            'pending_cancel': OrderStatus.SUBMITTED,
            'pending_replace': OrderStatus.SUBMITTED,
            'rejected': OrderStatus.REJECTED,
            'suspended': OrderStatus.FAILED,
            'stopped': OrderStatus.CANCELLED,
        }
        return mapping.get(alpaca_status, OrderStatus.FAILED)

    def _is_retryable_error(self, error: APIError) -> bool:
        """
        재시도 가능한 에러인지 판단

        재시도 가능:
        - 429: Rate limit
        - 500, 502, 503, 504: 서버 오류
        - 타임아웃

        재시도 불가능:
        - 400: 잘못된 요청
        - 401: 인증 실패
        - 403: 권한 없음
        - 422: 처리 불가능 (잔고 부족, 시장 폐장 등)
        """
        retryable_codes = [429, 500, 502, 503, 504]
        return error.status_code in retryable_codes
