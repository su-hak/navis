"""
리스크 관리 팀 단위 테스트
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from execution_team.core.order_models import (
    OrderSignal, OrderAction, OrderType, AccountInfo, Position
)
from risk_team.core.risk_models import RiskAction
from risk_team.core.risk_manager import RiskManager
from risk_team.core.position_sizer import PositionSizer
from risk_team.core.daily_loss_tracker import DailyLossTracker
from risk_team.core.portfolio_guard import PortfolioGuard


# ============ 픽스처 ============

@pytest.fixture
def risk_manager():
    return RiskManager(
        stop_loss_pct=0.02,
        take_profit_pct=0.06,
        max_daily_loss_pct=0.05,
        max_positions=5,
        max_exposure_pct=0.80,
        min_position_pct=0.05,
        max_position_pct=0.20,
        storage_path=None,
    )


@pytest.fixture
def account():
    return AccountInfo(
        account_id="test-account",
        cash=900_000,
        portfolio_value=1_000_000,
        buying_power=900_000,
        equity=1_000_000,
        unrealized_pl=0.0,
        realized_pl=0.0,
    )


@pytest.fixture
def empty_positions():
    return []


@pytest.fixture
def one_position():
    return [
        Position(
            symbol="AAPL",
            quantity=10,
            avg_entry_price=180.0,
            current_price=185.0,
            market_value=1850.0,
            unrealized_pl=50.0,
            unrealized_pl_percent=2.78,
        )
    ]


def make_buy_signal(symbol="TSLA", quantity=10):
    return OrderSignal(
        symbol=symbol,
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=quantity,
    )


def make_sell_signal(symbol="TSLA", quantity=5):
    return OrderSignal(
        symbol=symbol,
        action=OrderAction.SELL,
        order_type=OrderType.MARKET,
        quantity=quantity,
    )


# ============ 포지션 사이징 테스트 ============

class TestPositionSizer:

    def test_basic_quantity_calculation(self):
        sizer = PositionSizer(min_position_pct=0.05, max_position_pct=0.20)
        qty, amount, pct = sizer.calculate_quantity(
            equity=1_000_000,
            current_price=100.0,
            current_positions=[],
        )
        # 포지션 0개 → 20% → $200,000 / $100 = 2000주
        assert qty == 2000
        assert amount == 200_000.0
        assert pct == pytest.approx(0.20, rel=0.01)

    def test_quantity_reduces_with_more_positions(self):
        sizer = PositionSizer()
        positions_4 = [MagicMock() for _ in range(4)]

        qty_0, _, pct_0 = sizer.calculate_quantity(1_000_000, 100.0, [])
        qty_4, _, pct_4 = sizer.calculate_quantity(1_000_000, 100.0, positions_4)

        assert qty_0 > qty_4
        assert pct_0 > pct_4

    def test_quantity_zero_when_price_too_high(self):
        sizer = PositionSizer(min_position_pct=0.05, max_position_pct=0.20)
        qty, _, _ = sizer.calculate_quantity(
            equity=1_000,
            current_price=100_000.0,  # 주가가 자산보다 높음
            current_positions=[],
        )
        assert qty == 0

    def test_can_afford_sufficient(self):
        sizer = PositionSizer()
        assert sizer.can_afford(buying_power=50_000, quantity=10, price=100.0) is True

    def test_can_afford_insufficient(self):
        sizer = PositionSizer()
        assert sizer.can_afford(buying_power=500, quantity=10, price=100.0) is False


# ============ 일일 손실 추적 테스트 ============

class TestDailyLossTracker:

    def test_initialize_day(self):
        tracker = DailyLossTracker(max_daily_loss_pct=0.05)
        stats = tracker.initialize_day(1_000_000)
        assert stats.starting_equity == 1_000_000
        assert stats.realized_pnl == 0.0
        assert stats.is_trading_halted is False

    def test_limit_not_reached_initially(self):
        tracker = DailyLossTracker(max_daily_loss_pct=0.05)
        tracker.initialize_day(1_000_000)
        assert tracker.is_limit_reached() is False

    def test_limit_reached_after_loss(self):
        tracker = DailyLossTracker(max_daily_loss_pct=0.05)
        tracker.initialize_day(1_000_000)
        tracker.record_realized_trade(-50_001)   # -5.0001%
        assert tracker.is_limit_reached() is True

    def test_limit_not_reached_below_threshold(self):
        tracker = DailyLossTracker(max_daily_loss_pct=0.05)
        tracker.initialize_day(1_000_000)
        tracker.record_realized_trade(-49_999)   # -4.9999%
        assert tracker.is_limit_reached() is False

    def test_win_loss_count(self):
        tracker = DailyLossTracker()
        tracker.initialize_day(1_000_000)
        tracker.record_realized_trade(500)
        tracker.record_realized_trade(-200)
        tracker.record_realized_trade(300)

        stats = tracker.get_today_stats()
        assert stats.win_count == 2
        assert stats.loss_count == 1
        assert stats.trade_count == 3

    def test_remaining_loss_budget(self):
        tracker = DailyLossTracker(max_daily_loss_pct=0.05)
        tracker.initialize_day(1_000_000)
        tracker.record_realized_trade(-20_000)   # -2%

        remaining = tracker.get_remaining_loss_budget()
        # 최대 손실 $50,000 - 사용 $20,000 = 남은 $30,000
        assert remaining == pytest.approx(30_000, rel=0.01)

    def test_resume_trading(self):
        tracker = DailyLossTracker(max_daily_loss_pct=0.05)
        tracker.initialize_day(1_000_000)
        tracker.record_realized_trade(-60_000)
        assert tracker.is_limit_reached() is True

        tracker.resume_trading()
        stats = tracker.get_today_stats()
        assert stats.is_trading_halted is False


# ============ 포트폴리오 가드 테스트 ============

class TestPortfolioGuard:

    def test_position_limit_not_exceeded(self):
        guard = PortfolioGuard(max_positions=5)
        positions = [MagicMock() for _ in range(4)]
        ok, _ = guard.check_position_limit(positions)
        assert ok is True

    def test_position_limit_exceeded(self):
        guard = PortfolioGuard(max_positions=5)
        positions = [MagicMock() for _ in range(5)]
        ok, msg = guard.check_position_limit(positions)
        assert ok is False
        assert "5" in msg

    def test_no_duplicate_position(self):
        guard = PortfolioGuard()
        positions = [
            Position(symbol="AAPL", quantity=10, avg_entry_price=180,
                     current_price=185, market_value=1850, unrealized_pl=50,
                     unrealized_pl_percent=2.78)
        ]
        ok, _ = guard.check_duplicate_position("TSLA", positions)
        assert ok is True

    def test_duplicate_position_detected(self):
        guard = PortfolioGuard()
        positions = [
            Position(symbol="AAPL", quantity=10, avg_entry_price=180,
                     current_price=185, market_value=1850, unrealized_pl=50,
                     unrealized_pl_percent=2.78)
        ]
        ok, msg = guard.check_duplicate_position("AAPL", positions)
        assert ok is False
        assert "AAPL" in msg

    def test_exposure_limit_ok(self):
        guard = PortfolioGuard(max_exposure_pct=0.80)
        positions = [
            Position(symbol="AAPL", quantity=10, avg_entry_price=100,
                     current_price=100, market_value=500_000,
                     unrealized_pl=0, unrealized_pl_percent=0)
        ]
        ok, _ = guard.check_exposure_limit(positions, equity=1_000_000)
        assert ok is True  # 50% < 80%

    def test_exposure_limit_exceeded(self):
        guard = PortfolioGuard(max_exposure_pct=0.80)
        positions = [
            Position(symbol="AAPL", quantity=10, avg_entry_price=100,
                     current_price=100, market_value=850_000,
                     unrealized_pl=0, unrealized_pl_percent=0)
        ]
        ok, msg = guard.check_exposure_limit(positions, equity=1_000_000)
        assert ok is False


# ============ RiskManager 통합 테스트 ============

class TestRiskManager:

    def test_allow_valid_buy(self, risk_manager, account, empty_positions):
        signal = make_buy_signal("TSLA", quantity=5)
        decision = risk_manager.check_order(signal, account, empty_positions, current_price=200.0)

        assert decision.allowed is True
        assert decision.stop_loss_price is not None
        assert decision.take_profit_price is not None
        assert decision.adjusted_quantity > 0

    def test_stop_loss_calculated_correctly(self, risk_manager):
        stop, take = risk_manager.calculate_stops(100.0, "BUY")
        assert stop == pytest.approx(98.0, rel=0.001)   # -2%
        assert take == pytest.approx(106.0, rel=0.001)  # +6%

    def test_reject_daily_loss_limit(self, risk_manager, account, empty_positions):
        # 일일 손실 한도 초과 강제 설정
        risk_manager.daily_tracker.initialize_day(1_000_000)
        risk_manager.daily_tracker.record_realized_trade(-60_000)  # -6%

        signal = make_buy_signal()
        decision = risk_manager.check_order(signal, account, empty_positions, current_price=100.0)

        assert decision.allowed is False
        assert decision.action == RiskAction.REJECT
        assert "일일 손실" in decision.reason

    def test_reject_duplicate_position(self, risk_manager, account, one_position):
        # AAPL 이미 보유 중
        signal = make_buy_signal("AAPL", quantity=5)
        decision = risk_manager.check_order(signal, account, one_position, current_price=185.0)

        assert decision.allowed is False
        assert "중복" in decision.reason

    def test_reject_position_limit(self, risk_manager, account):
        # 5개 포지션 이미 보유
        positions = [
            Position(
                symbol=f"SYM{i}", quantity=10, avg_entry_price=100,
                current_price=100, market_value=1000,
                unrealized_pl=0, unrealized_pl_percent=0,
            )
            for i in range(5)
        ]
        signal = make_buy_signal("NEWSTOCK")
        decision = risk_manager.check_order(signal, account, positions, current_price=100.0)

        assert decision.allowed is False
        assert "포지션" in decision.reason

    def test_reject_sell_without_position(self, risk_manager, account, empty_positions):
        signal = make_sell_signal("TSLA", quantity=5)
        decision = risk_manager.check_order(signal, account, empty_positions, current_price=200.0)

        assert decision.allowed is False
        assert "보유하지 않은" in decision.reason

    def test_allow_sell_with_position(self, risk_manager, account):
        positions = [
            Position(
                symbol="TSLA", quantity=10, avg_entry_price=200,
                current_price=210, market_value=2100,
                unrealized_pl=100, unrealized_pl_percent=5.0,
            )
        ]
        signal = make_sell_signal("TSLA", quantity=5)
        decision = risk_manager.check_order(signal, account, positions, current_price=210.0)

        assert decision.allowed is True

    def test_adjust_sell_quantity_exceeds_holding(self, risk_manager, account):
        positions = [
            Position(
                symbol="TSLA", quantity=3, avg_entry_price=200,
                current_price=210, market_value=630,
                unrealized_pl=30, unrealized_pl_percent=5.0,
            )
        ]
        signal = make_sell_signal("TSLA", quantity=10)  # 10주 매도 시도, 보유는 3주
        decision = risk_manager.check_order(signal, account, positions, current_price=210.0)

        assert decision.allowed is True
        assert decision.action == RiskAction.ADJUST
        assert decision.adjusted_quantity == 3

    def test_risk_status_can_trade(self, risk_manager, account, empty_positions):
        status = risk_manager.get_risk_status(account, empty_positions)
        assert status.can_trade is True
        assert status.is_daily_limit_reached is False

    def test_record_and_check_daily_pnl(self, risk_manager):
        risk_manager.initialize_trading_day(1_000_000)
        risk_manager.record_trade_result(-30_000)

        pnl_pct = risk_manager.daily_tracker.get_daily_loss_pct()
        assert pnl_pct == pytest.approx(-0.03, rel=0.01)


# ============ 실행 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
