"""
포트폴리오 보호 모듈
기획서: 포지션 수 제한, 포트폴리오 리스크 관리
"""
import logging
from typing import List, Optional

from .risk_models import Position

logger = logging.getLogger(__name__)


class PortfolioGuard:
    """
    포트폴리오 보호 감시자

    역할:
    - 동시 보유 종목 수 제한
    - 전체 포트폴리오 노출도 제한
    - 단일 종목 집중 리스크 제한
    - 중복 매수 방지
    """

    def __init__(
        self,
        max_positions: int = 5,
        max_exposure_pct: float = 0.80,
        max_single_position_pct: float = 0.25,
    ):
        """
        Args:
            max_positions: 동시 최대 보유 종목 수
            max_exposure_pct: 포트폴리오 최대 노출도 (80% = 현금 20% 유지)
            max_single_position_pct: 단일 종목 최대 비중 (25%)
        """
        self.max_positions = max_positions
        self.max_exposure_pct = max_exposure_pct
        self.max_single_position_pct = max_single_position_pct

    # ============ 체크 함수 ============

    def check_position_limit(self, positions: List[Position]) -> tuple[bool, str]:
        """
        최대 포지션 수 체크

        Returns:
            (ok, message)
        """
        count = len(positions)
        if count >= self.max_positions:
            msg = f"최대 포지션 수 초과 ({count}/{self.max_positions})"
            logger.warning(msg)
            return False, msg

        return True, f"포지션 수 OK ({count}/{self.max_positions})"

    def check_duplicate_position(
        self, symbol: str, positions: List[Position]
    ) -> tuple[bool, str]:
        """
        중복 포지션 체크 (이미 보유 중인 종목 재매수 방지)

        Returns:
            (ok, message) - ok=True면 중복 없음
        """
        held_symbols = {p.symbol for p in positions}
        if symbol in held_symbols:
            msg = f"이미 보유 중인 종목 - {symbol} (중복 매수 방지)"
            logger.warning(msg)
            return False, msg

        return True, f"{symbol} 중복 없음"

    def check_exposure_limit(
        self, positions: List[Position], equity: float
    ) -> tuple[bool, str]:
        """
        포트폴리오 노출도 체크

        Returns:
            (ok, message)
        """
        if equity <= 0:
            return True, "자산 정보 없음 (스킵)"

        exposure_pct = self.get_portfolio_exposure_pct(positions, equity)

        if exposure_pct >= self.max_exposure_pct:
            msg = (
                f"포트폴리오 노출도 초과 "
                f"({exposure_pct*100:.1f}% / 한도 {self.max_exposure_pct*100:.0f}%)"
            )
            logger.warning(msg)
            return False, msg

        return True, f"노출도 OK ({exposure_pct*100:.1f}%/{self.max_exposure_pct*100:.0f}%)"

    def check_single_position_limit(
        self,
        symbol: str,
        invest_amount: float,
        equity: float,
        positions: List[Position],
    ) -> tuple[bool, str]:
        """
        단일 종목 집중도 체크

        이미 보유한 동일 종목 비중 + 신규 투자 비중이 한도 초과하는지 확인

        Returns:
            (ok, message)
        """
        if equity <= 0:
            return True, "자산 정보 없음 (스킵)"

        # 기존 보유 비중
        existing = next((p for p in positions if p.symbol == symbol), None)
        existing_value = existing.market_value if existing else 0.0

        total_for_symbol = existing_value + invest_amount
        concentration_pct = total_for_symbol / equity

        if concentration_pct > self.max_single_position_pct:
            msg = (
                f"{symbol} 집중도 초과 "
                f"({concentration_pct*100:.1f}% / 한도 {self.max_single_position_pct*100:.0f}%)"
            )
            logger.warning(msg)
            return False, msg

        return True, f"{symbol} 집중도 OK ({concentration_pct*100:.1f}%)"

    # ============ 조회 ============

    def get_portfolio_exposure_pct(
        self, positions: List[Position], equity: float
    ) -> float:
        """
        현재 포트폴리오 노출도 (0.0 ~ 1.0)

        Returns:
            시장 노출 비율 (예: 0.65 = 65% 투자 중)
        """
        if equity <= 0 or not positions:
            return 0.0

        total_market_value = sum(p.market_value for p in positions)
        return total_market_value / equity

    def get_available_slots(self, positions: List[Position]) -> int:
        """추가 진입 가능한 포지션 슬롯 수"""
        return max(0, self.max_positions - len(positions))

    def get_portfolio_summary(
        self, positions: List[Position], equity: float
    ) -> dict:
        """포트폴리오 현황 요약"""
        exposure_pct = self.get_portfolio_exposure_pct(positions, equity)
        total_unrealized = sum(p.unrealized_pl for p in positions)
        total_market_value = sum(p.market_value for p in positions)

        return {
            "position_count": len(positions),
            "max_positions": self.max_positions,
            "available_slots": self.get_available_slots(positions),
            "total_market_value": total_market_value,
            "total_unrealized_pl": total_unrealized,
            "exposure_pct": round(exposure_pct * 100, 2),
            "max_exposure_pct": round(self.max_exposure_pct * 100, 2),
            "symbols": [p.symbol for p in positions],
        }
