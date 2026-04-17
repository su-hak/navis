"""
포지션 사이징 모듈
기획서: 1회 투자금 = 총 자산의 5~20%
"""
import logging
from typing import List

from .risk_models import Position

logger = logging.getLogger(__name__)


class PositionSizer:
    """
    포지션 사이징 계산기

    원칙:
    - 미검증 전략에서 Kelly Criterion 원칙: 축소된 사이징
    - 보유 포지션이 많을수록 비율 축소
    - 최소 3%, 최대 10%
    """

    def __init__(
        self,
        min_position_pct: float = 0.03,
        max_position_pct: float = 0.10,
        base_position_pct: float = 0.06,
    ):
        self.min_position_pct = min_position_pct
        self.max_position_pct = max_position_pct
        self.base_position_pct = base_position_pct

    def calculate_position_pct(self, current_positions: List[Position]) -> float:
        """
        현재 포지션 수에 따른 투자 비율 결정

        CRIT-02: Kelly Criterion 위반 방지 - 사이징 상한 축소
        0개→10%, 1개→8%, 2개→6%, 3개→5%, 4+개→3%

        Returns:
            투자 비율 (0.03 ~ 0.10)
        """
        count = len(current_positions)

        if count == 0:
            pct = self.max_position_pct       # 0.10
        elif count == 1:
            pct = 0.08
        elif count == 2:
            pct = self.base_position_pct      # 0.06
        elif count == 3:
            pct = 0.05
        else:
            pct = self.min_position_pct       # 0.03

        logger.debug(f"포지션 비율 결정 - 보유 {count}개 → {pct*100:.0f}%")
        return pct

    def calculate_quantity(
        self,
        equity: float,
        current_price: float,
        current_positions: List[Position],
        override_pct: float = None,
    ) -> tuple[int, float, float]:
        """
        매수 수량 계산

        Args:
            equity: 총 자산
            current_price: 종목 현재가
            current_positions: 현재 보유 포지션 목록
            override_pct: 비율 강제 지정 (None이면 자동 계산)

        Returns:
            (quantity, invest_amount, invest_pct)
            - quantity: 매수 수량
            - invest_amount: 투자 금액
            - invest_pct: 투자 비율
        """
        if equity <= 0 or current_price <= 0:
            logger.warning(f"유효하지 않은 값 - equity: {equity}, price: {current_price}")
            return 0, 0.0, 0.0

        invest_pct = override_pct if override_pct else self.calculate_position_pct(current_positions)
        invest_pct = max(self.min_position_pct, min(self.max_position_pct, invest_pct))

        invest_amount = equity * invest_pct
        quantity = int(invest_amount / current_price)

        if quantity <= 0:
            logger.warning(
                f"수량 0 - equity: ${equity:,.0f}, "
                f"price: ${current_price:,.2f}, pct: {invest_pct*100:.0f}%"
            )
            return 0, 0.0, invest_pct

        actual_invest = quantity * current_price
        actual_pct = actual_invest / equity

        logger.info(
            f"포지션 사이징 - {quantity}주 @ ${current_price:.2f} "
            f"= ${actual_invest:,.2f} ({actual_pct*100:.1f}%)"
        )

        return quantity, actual_invest, actual_pct

    def can_afford(self, buying_power: float, quantity: int, price: float) -> bool:
        """매수 가능 여부 확인"""
        required = quantity * price * 1.02  # 2% 여유
        affordable = buying_power >= required

        if not affordable:
            logger.warning(
                f"자본 부족 - 필요: ${required:,.2f}, 가용: ${buying_power:,.2f}"
            )

        return affordable
