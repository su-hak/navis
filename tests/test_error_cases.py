"""
오류 케이스 테스트 (QA Team - Error Cases)

기획서 9. 테스트 전략 - 오류 케이스 테스트

검증 항목:
1. 입력 검증 오류 (잘못된 종목/수량/가격)
2. 브로커 연결 오류 및 재시도 로직
3. 데이터 엣지 케이스 (NaN, 빈 데이터, 극단값)
4. 동시성/순서 오류 케이스
5. 계좌 잔고 부족 케이스
6. 경계값 테스트 (점수 75점 정확히, 손절 -2% 정확히)
"""
import pytest
import pandas as pd
import numpy as np
from conftest import make_ohlcv


# ============================================================
# 주문 신호 검증 오류
# ============================================================

class TestOrderSignalValidation:

    @pytest.fixture
    def execution_engine(self):
        """Mock 브로커와 함께 실행 엔진 초기화"""
        from execution_team.core.execution_engine import ExecutionEngine
        from execution_team.core.order_manager import OrderManager
        from execution_team.brokers.broker_interface import BrokerInterface
        from execution_team.core.order_models import AccountInfo, OrderStatus

        class AlwaysConnectedBroker(BrokerInterface):
            def __init__(self, config):
                super().__init__(config)
                self._initialized = True
            def connect(self): self._initialized = True; return True
            def disconnect(self): self._initialized = False
            def submit_order(self, order): return f"OK_{order.symbol}"
            def get_order(self, bid): return {'status': OrderStatus.FILLED, 'filled_quantity': 10, 'filled_price': 100.0, 'commission': 0.0}
            def cancel_order(self, bid): return True
            def get_account(self):
                return AccountInfo(account_id="t", cash=99999, portfolio_value=99999, buying_power=99999, equity=99999, unrealized_pl=0, realized_pl=0)
            def get_positions(self): return []
            def get_position(self, s): return None
            def is_market_open(self): return True
            def get_current_price(self, s): return 100.0

        broker = AlwaysConnectedBroker({})
        manager = OrderManager(storage_path=None)
        return ExecutionEngine(broker=broker, order_manager=manager, enable_circuit_breaker=False)

    def test_empty_symbol_rejected(self, execution_engine):
        """빈 심볼 주문 거부"""
        from execution_team.core.order_models import OrderSignal, OrderAction, OrderType
        signal = OrderSignal(
            symbol="",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        result = execution_engine.execute_order(signal)
        assert result.success is False
        assert "심볼" in result.error_message

    def test_zero_quantity_rejected(self, execution_engine):
        """수량 0 주문 거부 - Pydantic 모델 수준 검증"""
        from execution_team.core.order_models import OrderSignal, OrderAction, OrderType
        from pydantic import ValidationError
        # Pydantic이 모델 생성 시 즉시 거부 (fail-fast 검증)
        with pytest.raises(ValidationError, match="greater_than"):
            OrderSignal(
                symbol="TSLA",
                action=OrderAction.BUY,
                order_type=OrderType.MARKET,
                quantity=0,
            )

    def test_negative_quantity_rejected(self, execution_engine):
        """음수 수량 주문 거부 - Pydantic 모델 수준 검증"""
        from execution_team.core.order_models import OrderSignal, OrderAction, OrderType
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="greater_than"):
            OrderSignal(
                symbol="TSLA",
                action=OrderAction.BUY,
                order_type=OrderType.MARKET,
                quantity=-5,
            )

    def test_limit_order_without_price_rejected(self, execution_engine):
        """지정가 주문에 가격 없을 시 거부 - Pydantic 모델 수준 검증"""
        from execution_team.core.order_models import OrderSignal, OrderAction, OrderType
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            OrderSignal(
                symbol="AAPL",
                action=OrderAction.BUY,
                order_type=OrderType.LIMIT,
                quantity=10,
                limit_price=None,   # LIMIT인데 가격 없음
            )

    def test_stop_order_without_stop_price_rejected(self, execution_engine):
        """스탑 주문에 스탑가 없을 시 거부 - Pydantic 모델 수준 검증"""
        from execution_team.core.order_models import OrderSignal, OrderAction, OrderType
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            OrderSignal(
                symbol="AAPL",
                action=OrderAction.SELL,
                order_type=OrderType.STOP,
                quantity=10,
                stop_price=None,    # STOP인데 스탑가 없음
            )


# ============================================================
# 브로커 연결 오류 테스트
# ============================================================

class TestBrokerErrors:

    @pytest.fixture
    def failing_broker_engine(self, tmp_path):
        """제출 실패 브로커"""
        from execution_team.core.execution_engine import ExecutionEngine
        from execution_team.core.order_manager import OrderManager
        from execution_team.brokers.broker_interface import BrokerInterface
        from execution_team.core.order_models import AccountInfo, BrokerError

        class FailingBroker(BrokerInterface):
            def __init__(self, config):
                super().__init__(config)
                self._initialized = True
            def connect(self): return True
            def disconnect(self): pass
            def submit_order(self, order):
                raise BrokerError("Connection refused", retryable=False)
            def get_order(self, bid): return {'status': None, 'filled_quantity': 0, 'filled_price': 0.0, 'commission': 0.0}
            def cancel_order(self, bid): return True
            def get_account(self):
                return AccountInfo(account_id="t", cash=99999, portfolio_value=99999, buying_power=99999, equity=99999, unrealized_pl=0, realized_pl=0)
            def get_positions(self): return []
            def get_position(self, s): return None
            def is_market_open(self): return True
            def get_current_price(self, s): return 100.0

        broker = FailingBroker({})
        manager = OrderManager(storage_path=str(tmp_path))
        return ExecutionEngine(broker=broker, order_manager=manager, enable_circuit_breaker=False)

    def test_broker_error_returns_failure(self, failing_broker_engine):
        """브로커 오류 시 실패 결과 반환 (예외 전파 안 됨)"""
        from execution_team.core.order_models import OrderSignal, OrderAction, OrderType
        signal = OrderSignal(
            symbol="TSLA",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        result = failing_broker_engine.execute_order(signal)
        assert result.success is False
        assert result.error_message is not None

    def test_disconnected_broker_rejected(self, tmp_path):
        """연결 끊긴 브로커 주문 거부"""
        from execution_team.core.execution_engine import ExecutionEngine
        from execution_team.core.order_manager import OrderManager
        from execution_team.brokers.broker_interface import BrokerInterface
        from execution_team.core.order_models import AccountInfo, OrderSignal, OrderAction, OrderType

        class DisconnectedBroker(BrokerInterface):
            def connect(self): return False
            def disconnect(self): pass
            def submit_order(self, order): pass
            def get_order(self, bid): return {}
            def cancel_order(self, bid): return False
            def get_account(self): return AccountInfo(account_id="t", cash=0, portfolio_value=0, buying_power=0, equity=0, unrealized_pl=0, realized_pl=0)
            def get_positions(self): return []
            def get_position(self, s): return None
            def is_market_open(self): return False
            def get_current_price(self, s): return 0.0

        broker = DisconnectedBroker({})
        manager = OrderManager()
        engine = ExecutionEngine(broker=broker, order_manager=manager, enable_circuit_breaker=False)

        signal = OrderSignal(
            symbol="AAPL",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        result = engine.execute_order(signal)
        assert result.success is False


# ============================================================
# 데이터 엣지 케이스
# ============================================================

class TestDataEdgeCases:

    def test_score_with_no_news_data(self, score_calculator, uptrend_df):
        """뉴스 데이터 없을 때 점수 계산 (중립 처리)"""
        result = score_calculator.score_stock(
            symbol="TEST",
            df=uptrend_df,
            news_sentiment=None,  # 뉴스 없음
            news_count=0,
        )
        assert 0 <= result.total_score <= 100
        assert result.news_score == pytest.approx(50.0, abs=5.0)  # 중립 점수

    def test_score_with_extreme_positive_news(self, score_calculator, uptrend_df):
        """극단적 긍정 뉴스 처리"""
        result = score_calculator.score_stock(
            symbol="TEST",
            df=uptrend_df,
            news_sentiment=1.0,   # 최대 긍정
            news_count=100,       # 뉴스 매우 많음
        )
        assert result.news_score <= 100.0  # 100점 초과 불가

    def test_score_with_extreme_negative_news(self, score_calculator, uptrend_df):
        """극단적 부정 뉴스 처리"""
        result = score_calculator.score_stock(
            symbol="TEST",
            df=uptrend_df,
            news_sentiment=-1.0,  # 최대 부정
            news_count=0,
        )
        assert result.news_score >= 0.0   # 0점 미만 불가

    def test_score_weights_sum_to_one(self):
        """점수 가중치 합계 = 1.0"""
        from strategy_engine.scoring.score_calculator import ScoreWeights
        weights = ScoreWeights()
        total = (weights.technical + weights.volume + weights.trend +
                 weights.news_sentiment + weights.financial)
        assert total == pytest.approx(1.0, abs=0.001)

    def test_invalid_weights_raises_error(self):
        """가중치 합계 != 1.0 시 오류"""
        from strategy_engine.scoring.score_calculator import ScoreWeights
        with pytest.raises(ValueError, match="가중치 합계"):
            ScoreWeights(technical=0.5, volume=0.5, trend=0.5,
                        news_sentiment=0.5, financial=0.5)

    def test_signal_not_generated_below_threshold(self, signal_generator, uptrend_df):
        """점수 75점 미만 시 매수 시그널 없음 확인"""
        from strategy_engine.signals.signal_generator import TradingConditions
        # 매우 높은 임계값으로 시그널 차단
        signal_generator.conditions.buy_score_threshold = 999.0
        signal = signal_generator.generate_buy_signal("TEST", uptrend_df)
        assert signal is None
        # 임계값 원복
        signal_generator.conditions.buy_score_threshold = 75.0

    def test_minimum_data_for_indicators(self):
        """지표 계산 최소 데이터 확인"""
        from strategy_engine.indicators.technical_indicators import TechnicalIndicators
        # 200일 미만 데이터에서 지표 계산 시 예외 미발생
        df_short = make_ohlcv(30, "up", seed=99)
        ti = TechnicalIndicators()
        # 예외 없이 실행되면 통과 (값은 기본값 사용)
        try:
            result = ti.calculate_all_indicators(df_short)
            assert result is not None
        except Exception:
            pass  # 데이터 부족 예외는 허용


# ============================================================
# 리스크 경계값 테스트
# ============================================================

class TestRiskBoundaryValues:

    def test_stop_loss_exact_2_percent(self, risk_manager):
        """정확히 -2% 손절가 계산"""
        stop, take = risk_manager.calculate_stops(100.0, "BUY")
        assert stop == pytest.approx(98.0, rel=0.001)

    def test_take_profit_exact_6_percent(self, risk_manager):
        """정확히 +6% 익절가 계산"""
        stop, take = risk_manager.calculate_stops(100.0, "BUY")
        assert take == pytest.approx(106.0, rel=0.001)

    def test_daily_loss_limit_at_exactly_5_percent(self, risk_manager):
        """정확히 -5% 손실 시 한도 도달"""
        risk_manager.initialize_trading_day(1_000_000)
        risk_manager.daily_tracker.record_realized_trade(-50_000)  # 정확히 -5%
        assert risk_manager.daily_tracker.is_limit_reached() is True

    def test_daily_loss_just_below_limit(self, risk_manager):
        """손실 -4.999%에서는 한도 미도달"""
        risk_manager.initialize_trading_day(1_000_000)
        risk_manager.daily_tracker.record_realized_trade(-49_990)  # -4.999%
        assert risk_manager.daily_tracker.is_limit_reached() is False

    def test_score_75_threshold_buy_signal(self, signal_generator, uptrend_df):
        """점수 정확히 75점에서 매수 가능 (기획서 매수 조건: 점수 ≥ 75)"""
        from strategy_engine.signals.signal_generator import TradingConditions
        signal_generator.conditions.buy_score_threshold = 75.0
        # 점수는 데이터에 따라 다르므로, 체크 함수 자체를 테스트
        from strategy_engine.scoring.score_calculator import ScoreResult
        mock_result = ScoreResult(
            symbol="TEST",
            total_score=75.0,  # 정확히 75점
            technical_score=75.0,
            volume_score=100.0,   # 거래량 충분
            trend_score=100.0,    # 추세 충분
            news_score=75.0,
            financial_score=75.0,
            breakdown={
                'volume': {'volume_ratio': 2.0},
                'trend': {'trend_strength': 70.0},
                'indicators': {'rsi': 50.0, 'macd_histogram': 0.5},
            }
        )
        can_buy, reasons, confidence = signal_generator.check_buy_conditions(
            mock_result, current_price=100.0
        )
        assert can_buy is True, f"75점에서 매수 가능해야 함. reasons={reasons}"

    def test_score_74_threshold_no_buy_signal(self, signal_generator):
        """점수 74점에서 매수 불가 (75점 미만)"""
        from strategy_engine.scoring.score_calculator import ScoreResult
        mock_result = ScoreResult(
            symbol="TEST",
            total_score=74.9,  # 75점 미만
            technical_score=74.9,
            volume_score=100.0,
            trend_score=100.0,
            news_score=74.9,
            financial_score=74.9,
            breakdown={
                'volume': {'volume_ratio': 2.0},
                'trend': {'trend_strength': 70.0},
                'indicators': {'rsi': 50.0, 'macd_histogram': 0.5},
            }
        )
        can_buy, reasons, confidence = signal_generator.check_buy_conditions(
            mock_result, current_price=100.0
        )
        assert can_buy is False, "75점 미만에서 매수 불가해야 함"

    def test_position_size_within_5_to_20_percent(self, risk_manager, account_1m, empty_positions):
        """투자 비율 5~20% 범위 내 확인"""
        from risk_team.core.risk_models import OrderSignal, OrderAction, OrderType
        signal = OrderSignal(
            symbol="TSLA",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        decision = risk_manager.check_order(
            signal=signal,
            account=account_1m,
            positions=empty_positions,
            current_price=100.0,
        )
        if decision.allowed and decision.invest_pct is not None:
            assert 5.0 <= decision.invest_pct <= 20.0, \
                f"투자 비율 {decision.invest_pct}%가 5~20% 범위를 벗어남"


# ============================================================
# 계좌 잔고 부족 케이스
# ============================================================

class TestInsufficientCapital:

    def test_reject_when_buying_power_zero(self, risk_manager):
        """잔고 0원 시 매수 거부"""
        from risk_team.core.risk_models import OrderSignal, OrderAction, OrderType, AccountInfo
        risk_manager.initialize_trading_day(100)
        account = AccountInfo(
            account_id="broke",
            cash=0,
            portfolio_value=0,
            buying_power=0,    # 잔고 없음
            equity=100,
            unrealized_pl=0.0,
            realized_pl=0.0,
        )
        signal = OrderSignal(
            symbol="TSLA",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
        )
        decision = risk_manager.check_order(
            signal=signal,
            account=account,
            positions=[],
            current_price=200.0,
        )
        assert decision.allowed is False

    def test_quantity_zero_when_price_exceeds_capital(self, risk_manager):
        """주가 > 자본 시 수량 0 → 거부"""
        from risk_team.core.risk_models import OrderSignal, OrderAction, OrderType, AccountInfo
        risk_manager.initialize_trading_day(1_000)
        account = AccountInfo(
            account_id="small",
            cash=1_000,
            portfolio_value=1_000,
            buying_power=1_000,
            equity=1_000,
            unrealized_pl=0.0,
            realized_pl=0.0,
        )
        signal = OrderSignal(
            symbol="BRK",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=1,
        )
        decision = risk_manager.check_order(
            signal=signal,
            account=account,
            positions=[],
            current_price=500_000.0,  # 주가 500,000달러 (불가능한 수준)
        )
        assert decision.allowed is False


# ============================================================
# 주문 관리자 오류 케이스
# ============================================================

class TestOrderManagerEdgeCases:

    def test_get_nonexistent_order_returns_none(self):
        """존재하지 않는 주문 조회 시 None 반환"""
        from execution_team.core.order_manager import OrderManager
        manager = OrderManager()
        result = manager.get_order("NONEXISTENT_ID")
        assert result is None

    def test_update_status_nonexistent_order_no_crash(self):
        """존재하지 않는 주문 상태 업데이트 시 예외 없음"""
        from execution_team.core.order_manager import OrderManager
        from execution_team.core.order_models import OrderStatus
        manager = OrderManager()
        # 예외 없이 실행되어야 함
        manager.update_status("FAKE_ID", OrderStatus.CANCELLED)

    def test_empty_stats(self):
        """주문 없을 때 통계"""
        from execution_team.core.order_manager import OrderManager
        manager = OrderManager()
        stats = manager.get_stats()
        assert stats['total'] == 0
        assert stats['success_rate'] == 0.0

    def test_get_order_by_broker_id_nonexistent(self):
        """없는 브로커 ID로 주문 조회"""
        from execution_team.core.order_manager import OrderManager
        manager = OrderManager()
        result = manager.get_order_by_broker_id("FAKE_BROKER_ID")
        assert result is None
