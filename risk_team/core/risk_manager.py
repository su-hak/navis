"""
리스크 관리자 (핵심 모듈)
모든 리스크 체크를 통합하는 메인 오케스트레이터
"""
import logging
from typing import List, Optional, Tuple

from .risk_models import OrderSignal, OrderAction, AccountInfo, Position

from .risk_models import RiskAction, RiskDecision, RiskStatus, RejectReason
from .position_sizer import PositionSizer
from .daily_loss_tracker import DailyLossTracker
from .portfolio_guard import PortfolioGuard

logger = logging.getLogger(__name__)


class RiskManager:
    """
    리스크 관리자

    역할:
    1. 주문 신호의 리스크 사전 검증 (check_order)
    2. 포지션 사이징 (수량 자동 계산)
    3. 손절/익절가 계산
    4. 일일 손실 추적 및 거래 중단
    5. 전체 리스크 상태 제공

    기획서 원칙:
    - 손절 필수 (-2%)
    - 하루 최대 손실 제한 (-5%)
    - 포지션 수 제한 (최대 5개)
    - 슬리피지 고려
    - Risk/Reward = 1:3 (손절 2%, 익절 6%)
    """

    def __init__(
        self,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.06,
        max_daily_loss_pct: float = 0.05,
        max_positions: int = 5,
        max_exposure_pct: float = 0.80,
        min_position_pct: float = 0.05,
        max_position_pct: float = 0.20,
        storage_path: Optional[str] = None,
    ):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        self.position_sizer = PositionSizer(
            min_position_pct=min_position_pct,
            max_position_pct=max_position_pct,
        )
        self.daily_tracker = DailyLossTracker(
            max_daily_loss_pct=max_daily_loss_pct,
            storage_path=f"{storage_path}/daily" if storage_path else None,
        )
        self.portfolio_guard = PortfolioGuard(
            max_positions=max_positions,
            max_exposure_pct=max_exposure_pct,
        )

        logger.info(
            f"RiskManager 초기화 - "
            f"손절: -{stop_loss_pct*100:.0f}%, "
            f"익절: +{take_profit_pct*100:.0f}%, "
            f"일손실한도: -{max_daily_loss_pct*100:.0f}%, "
            f"최대포지션: {max_positions}개"
        )

    # ============ 메인 함수 ============

    def check_order(
        self,
        signal: OrderSignal,
        account: AccountInfo,
        positions: List[Position],
        current_price: float,
        atr: float = None,
    ) -> RiskDecision:
        """
        주문 허용 여부 판단 (메인 함수)

        전략 엔진 또는 AI 팀에서 신호를 받아
        실제 주문 실행 전에 반드시 이 함수를 통과해야 함

        Args:
            signal: 주문 신호 (OrderSignal)
            account: 현재 계좌 정보
            positions: 현재 보유 포지션 목록
            current_price: 종목 현재가

        Returns:
            RiskDecision - allowed=True면 주문 실행 가능
        """
        warnings = []

        # ── 1. 일일 손실 한도 체크 ──────────────────────────
        if self.daily_tracker.is_limit_reached():
            daily_loss_pct = self.daily_tracker.get_daily_loss_pct()
            return RiskDecision(
                action=RiskAction.REJECT,
                allowed=False,
                reason=(
                    f"일일 손실 한도 초과 - "
                    f"현재: {daily_loss_pct*100:.2f}%, "
                    f"한도: -{self.daily_tracker.max_daily_loss_pct*100:.0f}%"
                ),
            )

        # 매수 신호인 경우에만 추가 체크
        if signal.action == OrderAction.BUY:

            # ── 2. 중복 포지션 체크 ──────────────────────────
            ok, msg = self.portfolio_guard.check_duplicate_position(
                signal.symbol, positions
            )
            if not ok:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    allowed=False,
                    reason=msg,
                )

            # ── 3. 포지션 수 한도 체크 ───────────────────────
            ok, msg = self.portfolio_guard.check_position_limit(positions)
            if not ok:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    allowed=False,
                    reason=msg,
                )

            # ── 4. 포트폴리오 노출도 체크 ────────────────────
            ok, msg = self.portfolio_guard.check_exposure_limit(
                positions, account.equity
            )
            if not ok:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    allowed=False,
                    reason=msg,
                )

            # ── 5. 포지션 사이징 ─────────────────────────────
            quantity, invest_amount, invest_pct = self.position_sizer.calculate_quantity(
                equity=account.equity,
                current_price=current_price,
                current_positions=positions,
            )

            if quantity <= 0:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    allowed=False,
                    reason=f"계산된 수량이 0 - 자산 부족 또는 주가 너무 높음 (${current_price:.2f})",
                )

            # ── 6. 매수 가능 금액 체크 ───────────────────────
            if not self.position_sizer.can_afford(account.buying_power, quantity, current_price):
                return RiskDecision(
                    action=RiskAction.REJECT,
                    allowed=False,
                    reason=(
                        f"매수 가능 금액 부족 - "
                        f"필요: ${quantity * current_price:,.2f}, "
                        f"가용: ${account.buying_power:,.2f}"
                    ),
                )

            # ── 7. 단일 종목 집중도 체크 ─────────────────────
            ok, msg = self.portfolio_guard.check_single_position_limit(
                signal.symbol, invest_amount, account.equity, positions
            )
            if not ok:
                warnings.append(msg)
                # 거부 대신 수량 조정
                max_invest = account.equity * self.portfolio_guard.max_single_position_pct
                quantity = int(max_invest / current_price)
                invest_amount = quantity * current_price
                invest_pct = invest_amount / account.equity
                warnings.append(f"수량을 {quantity}주로 조정 (집중도 한도 적용)")

            # ── 8. 신호 수량 vs 계산 수량 조정 ──────────────
            final_quantity = quantity
            action = RiskAction.ALLOW

            if signal.quantity != quantity:
                final_quantity = quantity
                action = RiskAction.ADJUST
                warnings.append(
                    f"수량 조정 - 신호: {signal.quantity}주 → 리스크 계산: {quantity}주"
                )

            # ── 9. 손절/익절가 계산 (ATR 기반 또는 고정%) ───────
            stop_loss, take_profit = self.calculate_stops(current_price, "BUY", atr=atr)

            # ── 10. Daily Loss 여력 대비 포지션 사이징 검증 (CRIT-01) ──
            remaining_budget = self.daily_tracker.get_remaining_loss_budget()
            max_loss_this_trade = invest_amount * self.stop_loss_pct
            if max_loss_this_trade > remaining_budget * 0.5:
                # 여력의 50% 이하로 수량 강제 조정
                max_allowed_invest = (remaining_budget * 0.5) / self.stop_loss_pct
                if max_allowed_invest < current_price:
                    return RiskDecision(
                        action=RiskAction.REJECT,
                        allowed=False,
                        reason=(
                            f"일일 손실 여력 부족 - 이 거래 최대 손실 ${max_loss_this_trade:.2f}이 "
                            f"남은 예산(${remaining_budget:.2f})의 50% 초과. "
                            f"투자 가능 금액: ${max_allowed_invest:.2f}"
                        ),
                    )
                adjusted_qty = int(max_allowed_invest / current_price)
                if adjusted_qty < quantity:
                    quantity = adjusted_qty
                    invest_amount = quantity * current_price
                    invest_pct = invest_amount / account.equity
                    action = RiskAction.ADJUST
                    warnings.append(
                        f"일일 손실 여력 초과로 수량 조정: {quantity}주 "
                        f"(최대 손실 ${invest_amount * self.stop_loss_pct:.2f} ≤ "
                        f"잔여 예산의 50% ${remaining_budget * 0.5:.2f})"
                    )

            return RiskDecision(
                action=action,
                allowed=True,
                adjusted_quantity=final_quantity,
                stop_loss_price=round(stop_loss, 2),
                take_profit_price=round(take_profit, 2),
                reason="리스크 체크 통과",
                warnings=warnings,
                recommended_quantity=final_quantity,
                invest_amount=round(invest_amount, 2),
                invest_pct=round(invest_pct * 100, 2),
            )

        # ── 매도 신호 ─────────────────────────────────────────
        else:
            # 매도는 포지션 보유 여부만 확인
            held = next((p for p in positions if p.symbol == signal.symbol), None)

            if not held:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    allowed=False,
                    reason=f"보유하지 않은 종목 매도 시도 - {signal.symbol}",
                )

            # 매도 수량이 보유 수량 초과 시 조정
            final_quantity = signal.quantity
            action = RiskAction.ALLOW

            if signal.quantity > held.quantity:
                final_quantity = held.quantity
                action = RiskAction.ADJUST
                warnings.append(
                    f"매도 수량 조정 - 신호: {signal.quantity}주 → 보유: {held.quantity}주"
                )

            return RiskDecision(
                action=action,
                allowed=True,
                adjusted_quantity=final_quantity,
                reason="매도 리스크 체크 통과",
                warnings=warnings,
            )

    # ============ 손절/익절 계산 ============

    @staticmethod
    def calculate_atr(high_prices: list, low_prices: list, close_prices: list, period: int = 14) -> float:
        """
        ATR(Average True Range) 계산 - CRIT-03

        Args:
            high_prices: 고가 리스트 (최소 period+1개)
            low_prices:  저가 리스트
            close_prices: 종가 리스트
            period: ATR 기간 (기본 14일)

        Returns:
            ATR 값 (가격 단위)
        """
        if len(close_prices) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, len(close_prices)):
            hl = high_prices[i] - low_prices[i]
            hc = abs(high_prices[i] - close_prices[i - 1])
            lc = abs(low_prices[i] - close_prices[i - 1])
            true_ranges.append(max(hl, hc, lc))

        # 마지막 period개의 TR 평균
        return sum(true_ranges[-period:]) / period

    def calculate_stops(
        self,
        entry_price: float,
        action: str = "BUY",
        atr: float = None,
        atr_sl_multiplier: float = 1.5,
        atr_tp_multiplier: float = 3.0,
    ) -> Tuple[float, float]:
        """
        손절가 / 익절가 계산 - CRIT-03: ATR 기반 동적 SL

        atr이 제공되면 ATR×multiplier 방식으로 계산하여
        변동성에 맞는 동적 SL/TP를 적용합니다.
        atr이 없으면 고정 % 방식으로 fallback.

        Args:
            entry_price: 진입가
            action: "BUY" 또는 "SELL"
            atr: ATR(14일) 값. None이면 고정 % 사용
            atr_sl_multiplier: SL에 곱할 ATR 배수 (기본 1.5)
            atr_tp_multiplier: TP에 곱할 ATR 배수 (기본 3.0, 최소 2:1 R:R 보장)

        Returns:
            (stop_loss_price, take_profit_price)
        """
        if atr and atr > 0:
            if action == "BUY":
                stop_loss = entry_price - (atr_sl_multiplier * atr)
                take_profit = entry_price + (atr_tp_multiplier * atr)
            else:
                stop_loss = entry_price + (atr_sl_multiplier * atr)
                take_profit = entry_price - (atr_tp_multiplier * atr)
            logger.debug(
                f"ATR 기반 손절/익절 - 진입: ${entry_price:.2f}, ATR: ${atr:.4f}, "
                f"손절: ${stop_loss:.2f}, 익절: ${take_profit:.2f}"
            )
        else:
            if action == "BUY":
                stop_loss = entry_price * (1 - self.stop_loss_pct)
                take_profit = entry_price * (1 + self.take_profit_pct)
            else:
                stop_loss = entry_price * (1 + self.stop_loss_pct)
                take_profit = entry_price * (1 - self.take_profit_pct)
            logger.debug(
                f"고정% 손절/익절 - 진입: ${entry_price:.2f}, "
                f"손절: ${stop_loss:.2f}, 익절: ${take_profit:.2f}"
            )

        return stop_loss, take_profit

    # ============ 리스크 상태 조회 ============

    def get_risk_status(
        self, account: AccountInfo, positions: List[Position]
    ) -> RiskStatus:
        """
        현재 전체 리스크 상태 스냅샷

        Returns:
            RiskStatus
        """
        daily_loss_pct = self.daily_tracker.get_daily_loss_pct()
        daily_limit_reached = self.daily_tracker.is_limit_reached()

        position_count = len(positions)
        position_limit_reached = position_count >= self.portfolio_guard.max_positions

        exposure_pct = self.portfolio_guard.get_portfolio_exposure_pct(
            positions, account.equity
        )
        exposure_limit_reached = exposure_pct >= self.portfolio_guard.max_exposure_pct

        can_trade = not (daily_limit_reached or position_limit_reached or exposure_limit_reached)

        halt_reason = None
        if daily_limit_reached:
            halt_reason = f"일일 손실 한도 초과 ({daily_loss_pct*100:.2f}%)"
        elif position_limit_reached:
            halt_reason = f"최대 포지션 수 도달 ({position_count}개)"
        elif exposure_limit_reached:
            halt_reason = f"포트폴리오 노출도 한도 ({exposure_pct*100:.1f}%)"

        available_capital = account.buying_power
        available_capital_pct = (available_capital / account.equity * 100) if account.equity > 0 else 0.0

        return RiskStatus(
            daily_pnl_pct=round(daily_loss_pct * 100, 2),
            daily_loss_limit_pct=round(self.daily_tracker.max_daily_loss_pct * 100, 2),
            is_daily_limit_reached=daily_limit_reached,
            position_count=position_count,
            max_positions=self.portfolio_guard.max_positions,
            is_position_limit_reached=position_limit_reached,
            portfolio_exposure_pct=round(exposure_pct * 100, 2),
            max_exposure_pct=round(self.portfolio_guard.max_exposure_pct * 100, 2),
            is_exposure_limit_reached=exposure_limit_reached,
            available_capital=round(available_capital, 2),
            available_capital_pct=round(available_capital_pct, 2),
            can_trade=can_trade,
            halt_reason=halt_reason,
        )

    # ============ 손익 기록 ============

    def record_trade_result(self, pnl: float) -> None:
        """
        거래 결과 기록 (체결 후 호출)

        Args:
            pnl: 실현 손익 (양수=수익, 음수=손실)
        """
        self.daily_tracker.record_realized_trade(pnl)

    def initialize_trading_day(self, starting_equity: float) -> None:
        """
        거래일 시작 초기화 (장 시작 시 호출)

        Args:
            starting_equity: 오늘 시작 자산
        """
        self.daily_tracker.initialize_day(starting_equity)
        logger.info(f"거래일 시작 - 시작 자산: ${starting_equity:,.2f}")

    def update_unrealized_pnl(self, unrealized_pnl: float) -> None:
        """미실현 손익 업데이트"""
        self.daily_tracker.update_unrealized_pnl(unrealized_pnl)
