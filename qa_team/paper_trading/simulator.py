"""
페이퍼 트레이딩 시뮬레이터 (Paper Trading Simulator)

기획서 9. 테스트 전략 - 페이퍼 트레이딩 검증

실제 브로커 API를 사용하지 않고 전체 시스템 파이프라인을
현실적으로 시뮬레이션합니다.

검증 항목:
1. 전체 파이프라인 통합 (Data → Strategy → Risk → Execution)
2. 주문 실행 흐름 (신호 생성 → 리스크 체크 → 주문 제출 → 체결 확인)
3. 리스크 룰 준수 (손절/일일한도/포지션 한도)
4. 텔레그램 알림 형식
"""
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


@dataclass
class PaperTradingConfig:
    """페이퍼 트레이딩 설정"""
    initial_capital: float = 1_000_000.0
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.06
    max_daily_loss_pct: float = 0.05
    max_positions: int = 5
    commission_rate: float = 0.001
    slippage_rate: float = 0.001
    buy_score_threshold: float = 75.0


@dataclass
class OrderLog:
    """주문 실행 로그"""
    timestamp: str
    symbol: str
    action: str           # BUY / SELL
    quantity: int
    price: float
    total_amount: float
    commission: float
    risk_decision: str    # ALLOW / REJECT / ADJUST
    risk_reason: str
    stop_loss: Optional[float]
    take_profit: Optional[float]
    result: str           # SUCCESS / FAILED
    message: str = ""


@dataclass
class SimulationResult:
    """시뮬레이션 결과"""
    total_orders_attempted: int
    total_orders_executed: int
    total_orders_rejected: int
    total_orders_adjusted: int

    pipeline_errors: List[str] = field(default_factory=list)
    risk_rule_violations: List[str] = field(default_factory=list)
    order_logs: List[OrderLog] = field(default_factory=list)

    # 파이프라인 검증 항목
    strategy_engine_ok: bool = False
    risk_manager_ok: bool = False
    execution_engine_ok: bool = False
    notification_format_ok: bool = False

    @property
    def all_passed(self) -> bool:
        return (
            self.strategy_engine_ok
            and self.risk_manager_ok
            and self.execution_engine_ok
            and len(self.pipeline_errors) == 0
        )

    def summary(self) -> str:
        status = "PASS" if self.all_passed else "FAIL"
        lines = [
            f"{'='*60}",
            f"페이퍼 트레이딩 검증 [{status}]",
            f"{'='*60}",
            f"주문 시도:     {self.total_orders_attempted:>6}건",
            f"주문 실행:     {self.total_orders_executed:>6}건",
            f"주문 거부:     {self.total_orders_rejected:>6}건",
            f"수량 조정:     {self.total_orders_adjusted:>6}건",
            f"{'─'*60}",
            f"전략 엔진:     {'OK' if self.strategy_engine_ok else 'FAIL'}",
            f"리스크 관리:   {'OK' if self.risk_manager_ok else 'FAIL'}",
            f"실행 엔진:     {'OK' if self.execution_engine_ok else 'FAIL'}",
            f"알림 형식:     {'OK' if self.notification_format_ok else 'FAIL'}",
        ]
        if self.pipeline_errors:
            lines.append(f"{'─'*60}")
            lines.append("파이프라인 오류:")
            for err in self.pipeline_errors:
                lines.append(f"  - {err}")
        if self.risk_rule_violations:
            lines.append(f"{'─'*60}")
            lines.append("리스크 룰 위반:")
            for v in self.risk_rule_violations:
                lines.append(f"  - {v}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)


class PaperTradingSimulator:
    """
    페이퍼 트레이딩 시뮬레이터

    실제 브로커 API 없이 전체 파이프라인을 테스트합니다.
    Mock 브로커를 사용하여 주문 실행 흐름 전체를 검증합니다.
    """

    def __init__(self, config: Optional[PaperTradingConfig] = None):
        self.config = config or PaperTradingConfig()
        self._setup_pipeline()

    def _setup_pipeline(self):
        """전체 파이프라인 초기화"""
        from strategy_engine.signals.signal_generator import SignalGenerator, TradingConditions
        from risk_team.core.risk_manager import RiskManager
        from execution_team.core.execution_engine import ExecutionEngine
        from execution_team.core.order_manager import OrderManager

        # 전략 엔진
        conditions = TradingConditions(
            buy_score_threshold=self.config.buy_score_threshold,
            take_profit_pct=self.config.take_profit_pct,
            stop_loss_pct=-self.config.stop_loss_pct,
        )
        self.signal_generator = SignalGenerator(conditions=conditions)

        # 리스크 관리자
        self.risk_manager = RiskManager(
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            max_daily_loss_pct=self.config.max_daily_loss_pct,
            max_positions=self.config.max_positions,
        )

        # Mock 브로커 + 실행 엔진
        self.mock_broker = self._create_mock_broker()
        self.order_manager = OrderManager(storage_path=None)
        self.execution_engine = ExecutionEngine(
            broker=self.mock_broker,
            order_manager=self.order_manager,
            enable_circuit_breaker=False,
        )

    def _create_mock_broker(self):
        """Mock 브로커 생성 (실제 Alpaca API 대체)"""
        from execution_team.brokers.broker_interface import BrokerInterface
        from execution_team.core.order_models import AccountInfo, OrderStatus

        class PaperBroker(BrokerInterface):
            def __init__(self, config, capital):
                super().__init__(config)
                self.capital = capital
                self._initialized = True
                self._order_counter = 0
                self._filled_orders = {}

            def connect(self) -> bool:
                self._initialized = True
                return True

            def disconnect(self) -> None:
                self._initialized = False

            def submit_order(self, order) -> str:
                self._order_counter += 1
                broker_id = f"PAPER_{self._order_counter:04d}"
                self._filled_orders[broker_id] = {
                    'status': OrderStatus.FILLED,
                    'filled_quantity': order.quantity,
                    'filled_price': order.limit_price or 200.0,
                    'commission': order.quantity * 0.01,
                }
                return broker_id

            def get_order(self, broker_order_id: str) -> dict:
                return self._filled_orders.get(broker_order_id, {
                    'status': OrderStatus.FILLED,
                    'filled_quantity': 10,
                    'filled_price': 200.0,
                    'commission': 0.0,
                })

            def cancel_order(self, broker_order_id: str) -> bool:
                return True

            def get_account(self):
                return AccountInfo(
                    account_id="PAPER_ACCOUNT",
                    cash=self.capital,
                    portfolio_value=self.capital,
                    buying_power=self.capital,
                    equity=self.capital,
                    unrealized_pl=0.0,
                    realized_pl=0.0,
                )

            def get_positions(self):
                return []

            def get_position(self, symbol: str):
                return None

            def is_market_open(self) -> bool:
                return True

            def get_current_price(self, symbol: str) -> float:
                return 200.0

        return PaperBroker({'paper': True}, self.config.initial_capital)

    def run_scenario(
        self,
        scenario_name: str,
        signals_data: List[Dict[str, Any]],
    ) -> SimulationResult:
        """
        시나리오 기반 페이퍼 트레이딩 실행

        Args:
            scenario_name: 시나리오 이름
            signals_data: 시그널 데이터 목록
                [{'symbol': 'AAPL', 'action': 'BUY', 'quantity': 10,
                  'price': 180.0, 'score': 80.0}, ...]

        Returns:
            SimulationResult
        """
        from risk_team.core.risk_models import (
            OrderSignal, OrderAction, OrderType, AccountInfo, Position
        )
        from execution_team.core.order_models import (
            OrderSignal as ExecSignal, OrderAction as ExecAction, OrderType as ExecType
        )

        logger.info(f"페이퍼 트레이딩 시나리오: {scenario_name}")

        result = SimulationResult(
            total_orders_attempted=0,
            total_orders_executed=0,
            total_orders_rejected=0,
            total_orders_adjusted=0,
        )
        # 파이프라인 구성요소 접근 가능 시 기본 OK (실제 오류 발생 시 False로 전환)
        result.strategy_engine_ok = True
        result.risk_manager_ok = True
        result.execution_engine_ok = True

        self.risk_manager.initialize_trading_day(self.config.initial_capital)
        positions: List[Position] = []

        for signal_data in signals_data:
            result.total_orders_attempted += 1
            symbol = signal_data['symbol']
            action_str = signal_data['action']
            quantity = signal_data['quantity']
            price = signal_data['price']

            # ── 1. 리스크 체크 ──────────────────────────────────
            account = AccountInfo(
                account_id="PAPER",
                cash=self.config.initial_capital,
                portfolio_value=self.config.initial_capital,
                buying_power=self.config.initial_capital,
                equity=self.config.initial_capital,
                unrealized_pl=0.0,
                realized_pl=0.0,
            )
            risk_signal = OrderSignal(
                symbol=symbol,
                action=OrderAction.BUY if action_str == "BUY" else OrderAction.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
            )

            try:
                risk_decision = self.risk_manager.check_order(
                    signal=risk_signal,
                    account=account,
                    positions=positions,
                    current_price=price,
                )
            except Exception as e:
                result.risk_manager_ok = False
                result.pipeline_errors.append(f"리스크 매니저 오류: {e}")
                risk_decision = None

            if risk_decision is None:
                result.total_orders_rejected += 1
                result.order_logs.append(OrderLog(
                    timestamp=datetime.now().isoformat(),
                    symbol=symbol,
                    action=action_str,
                    quantity=quantity,
                    price=price,
                    total_amount=price * quantity,
                    commission=0.0,
                    risk_decision="ERROR",
                    risk_reason="리스크 매니저 오류",
                    stop_loss=None,
                    take_profit=None,
                    result="FAILED",
                    message="리스크 매니저 예외 발생",
                ))
                continue

            if not risk_decision.allowed:
                result.total_orders_rejected += 1
                result.order_logs.append(OrderLog(
                    timestamp=datetime.now().isoformat(),
                    symbol=symbol,
                    action=action_str,
                    quantity=quantity,
                    price=price,
                    total_amount=price * quantity,
                    commission=0.0,
                    risk_decision="REJECT",
                    risk_reason=risk_decision.reason,
                    stop_loss=None,
                    take_profit=None,
                    result="REJECTED",
                    message=risk_decision.reason,
                ))
                continue

            # 수량 조정 여부
            final_quantity = risk_decision.adjusted_quantity or quantity
            if final_quantity != quantity:
                result.total_orders_adjusted += 1

            # ── 2. 주문 실행 ─────────────────────────────────────
            exec_signal = ExecSignal(
                symbol=symbol,
                action=ExecAction.BUY if action_str == "BUY" else ExecAction.SELL,
                order_type=ExecType.LIMIT,
                quantity=final_quantity,
                limit_price=price,
                strategy_id="paper_trading",
            )

            # Mock 브로커 가격 설정
            self.mock_broker._filled_orders[f"PAPER_{self.mock_broker._order_counter + 1:04d}"] = {
                'status': None,
                'filled_quantity': final_quantity,
                'filled_price': price,
                'commission': price * final_quantity * self.config.commission_rate,
            }

            try:
                from execution_team.core.order_models import OrderStatus as ExecStatus
                self.mock_broker._filled_orders[f"PAPER_{self.mock_broker._order_counter + 1:04d}"]["status"] = ExecStatus.FILLED

                order_result = self.execution_engine.execute_order(exec_signal)

                commission = price * final_quantity * self.config.commission_rate

                if order_result.success:
                    result.total_orders_executed += 1

                    # 포지션 업데이트 (매수)
                    if action_str == "BUY":
                        positions.append(Position(
                            symbol=symbol,
                            quantity=final_quantity,
                            avg_entry_price=price,
                            current_price=price,
                            market_value=price * final_quantity,
                            unrealized_pl=0.0,
                            unrealized_pl_percent=0.0,
                        ))

                    result.order_logs.append(OrderLog(
                        timestamp=datetime.now().isoformat(),
                        symbol=symbol,
                        action=action_str,
                        quantity=final_quantity,
                        price=price,
                        total_amount=price * final_quantity,
                        commission=commission,
                        risk_decision=risk_decision.action,
                        risk_reason=risk_decision.reason,
                        stop_loss=risk_decision.stop_loss_price,
                        take_profit=risk_decision.take_profit_price,
                        result="SUCCESS",
                        message=f"체결 완료 @ ${price:.2f}",
                    ))
                else:
                    result.total_orders_rejected += 1
                    result.order_logs.append(OrderLog(
                        timestamp=datetime.now().isoformat(),
                        symbol=symbol,
                        action=action_str,
                        quantity=final_quantity,
                        price=price,
                        total_amount=price * final_quantity,
                        commission=0.0,
                        risk_decision=risk_decision.action,
                        risk_reason=risk_decision.reason,
                        stop_loss=None,
                        take_profit=None,
                        result="FAILED",
                        message=order_result.error_message or "실행 실패",
                    ))
            except Exception as e:
                result.execution_engine_ok = False
                result.pipeline_errors.append(f"실행 엔진 오류 ({symbol}): {e}")
                result.total_orders_rejected += 1

        # ── 알림 형식 검증 ──────────────────────────────────────
        result.notification_format_ok = self._validate_notification_format(result)

        return result

    def _validate_notification_format(self, result: SimulationResult) -> bool:
        """텔레그램 알림 형식 검증"""
        for log in result.order_logs:
            if log.result == "SUCCESS":
                # 필수 필드 존재 확인
                msg = self._format_notification(log)
                required_fields = ['종목', '가격', '수량']
                for field_name in required_fields:
                    if field_name not in msg:
                        return False
        return True

    def _format_notification(self, log: OrderLog) -> str:
        """텔레그램 알림 메시지 포맷 (기획서 8. 텔레그램 연동 형식)"""
        if log.action == "BUY":
            msg = (
                f"[매수 체결]\n"
                f"종목: {log.symbol}\n"
                f"가격: ${log.price:.2f}\n"
                f"수량: {log.quantity}주\n"
                f"금액: ${log.total_amount:,.0f}\n"
                f"손절가: ${log.stop_loss:.2f}" if log.stop_loss else ""
            )
        else:
            msg = (
                f"[매도 체결]\n"
                f"종목: {log.symbol}\n"
                f"가격: ${log.price:.2f}\n"
                f"수량: {log.quantity}주\n"
                f"금액: ${log.total_amount:,.0f}"
            )
        return msg

    def run_full_pipeline_test(
        self,
        symbol: str,
        df: pd.DataFrame,
    ) -> SimulationResult:
        """
        실제 전략 엔진을 사용한 전체 파이프라인 테스트

        Args:
            symbol: 종목 심볼
            df: OHLCV 데이터 (최소 200일)

        Returns:
            SimulationResult
        """
        signals_data = []

        # 전략 엔진으로 시그널 생성
        if len(df) >= 200:
            try:
                signal = self.signal_generator.generate_buy_signal(
                    symbol=symbol,
                    df=df,
                )
                if signal:
                    price = float(df['close'].iloc[-1])
                    signals_data.append({
                        'symbol': symbol,
                        'action': 'BUY',
                        'quantity': 10,
                        'price': price,
                        'score': signal.score,
                    })
            except Exception as e:
                logger.error(f"시그널 생성 실패: {e}")

        return self.run_scenario(
            scenario_name=f"full_pipeline_{symbol}",
            signals_data=signals_data,
        )
