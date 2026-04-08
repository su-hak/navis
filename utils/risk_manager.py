"""
리스크 관리 모듈

기획서 요구사항:
- 1회 투자: 10%
- 손절: -2%
- 하루 손실: -5%
"""

from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """리스크 관리 설정"""
    max_position_percent: float = 10.0  # 1회 최대 투자 비율 (%)
    stop_loss_percent: float = 2.0  # 손절 비율 (%)
    max_daily_loss_percent: float = 5.0  # 일일 최대 손실 비율 (%)
    max_positions: int = 5  # 최대 동시 보유 종목 수
    risk_reward_ratio: float = 1.5  # 손익비 (기획서: 1:1.5)


class RiskManager:
    """
    리스크 관리자

    기획서의 리스크 관리 규칙 구현:
    - 포지션 크기 제한
    - 손절 관리
    - 일일 손실 한계
    - 손익비 관리
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        초기화

        Args:
            config: 리스크 설정 (None이면 기본값 사용)
        """
        self.config = config or RiskConfig()

        # 일일 손익 추적
        self.daily_start_equity: Optional[float] = None
        self.today_date: Optional[str] = None

        logger.info(f"리스크 관리자 초기화:")
        logger.info(f"  1회 최대 투자: {self.config.max_position_percent}%")
        logger.info(f"  손절: -{self.config.stop_loss_percent}%")
        logger.info(f"  일일 최대 손실: -{self.config.max_daily_loss_percent}%")
        logger.info(f"  최대 포지션: {self.config.max_positions}개")
        logger.info(f"  손익비: 1:{self.config.risk_reward_ratio}")

    def calculate_position_size(
        self,
        account_cash: float,
        entry_price: float,
        risk_level: float = 1.0
    ) -> int:
        """
        포지션 크기 계산

        Args:
            account_cash: 가용 현금
            entry_price: 진입가
            risk_level: 리스크 레벨 (0.0~1.0, 기본 1.0)

        Returns:
            매수 수량

        기획서: 1회 투자 10%
        """
        # 투자 금액 계산
        investment_amount = account_cash * (self.config.max_position_percent / 100.0) * risk_level

        # 수량 계산
        quantity = int(investment_amount / entry_price)

        logger.debug(f"포지션 크기 계산: ${account_cash:,.2f} x {self.config.max_position_percent}% x {risk_level} = {quantity}주")

        return quantity

    def check_can_open_position(
        self,
        current_positions: List,
        account_cash: float,
        entry_price: float
    ) -> Dict[str, any]:
        """
        포지션 오픈 가능 여부 확인

        Args:
            current_positions: 현재 보유 포지션 리스트
            account_cash: 가용 현금
            entry_price: 진입가

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'max_quantity': int
            }
        """
        # 최대 포지션 수 체크
        if len(current_positions) >= self.config.max_positions:
            return {
                'allowed': False,
                'reason': f'최대 포지션 수 도달 ({len(current_positions)}/{self.config.max_positions})',
                'max_quantity': 0
            }

        # 투자 금액 계산
        max_quantity = self.calculate_position_size(account_cash, entry_price)

        if max_quantity == 0:
            return {
                'allowed': False,
                'reason': f'투자 금액 부족 (현금: ${account_cash:,.2f}, 진입가: ${entry_price:.2f})',
                'max_quantity': 0
            }

        return {
            'allowed': True,
            'reason': 'OK',
            'max_quantity': max_quantity
        }

    def check_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        current_price: float
    ) -> Dict[str, any]:
        """
        손절 체크

        Args:
            symbol: 종목
            entry_price: 진입가
            current_price: 현재가

        Returns:
            {
                'should_stop': bool,
                'loss_percent': float,
                'reason': str
            }

        기획서: -2% 손절
        """
        loss_percent = ((current_price - entry_price) / entry_price) * 100.0

        if loss_percent <= -self.config.stop_loss_percent:
            logger.warning(f"[{symbol}] 손절 신호: {loss_percent:.2f}% (한계: -{self.config.stop_loss_percent}%)")
            return {
                'should_stop': True,
                'loss_percent': loss_percent,
                'reason': f'손절 기준 도달 ({loss_percent:.2f}%)'
            }

        return {
            'should_stop': False,
            'loss_percent': loss_percent,
            'reason': 'OK'
        }

    def check_daily_loss_limit(
        self,
        current_equity: float,
        start_equity: Optional[float] = None
    ) -> Dict[str, any]:
        """
        일일 손실 한계 체크

        Args:
            current_equity: 현재 자산
            start_equity: 시작 자산 (None이면 자동 설정)

        Returns:
            {
                'exceeded': bool,
                'daily_pl': float,
                'daily_pl_percent': float,
                'reason': str
            }

        기획서: -5% 일일 손실 한계
        """
        # 날짜 체크 (날짜가 바뀌면 리셋)
        today = datetime.now().strftime('%Y-%m-%d')
        if self.today_date != today:
            self.today_date = today
            self.daily_start_equity = None

        # 시작 자산 설정
        if self.daily_start_equity is None:
            self.daily_start_equity = start_equity or current_equity
            logger.info(f"일일 시작 자산 설정: ${self.daily_start_equity:,.2f}")

        # 일일 손익 계산
        daily_pl = current_equity - self.daily_start_equity
        daily_pl_percent = (daily_pl / self.daily_start_equity) * 100.0

        # 한계 체크
        if daily_pl_percent <= -self.config.max_daily_loss_percent:
            logger.error(f"⚠️ 일일 최대 손실 도달!")
            logger.error(f"  손익: ${daily_pl:,.2f} ({daily_pl_percent:.2f}%)")
            logger.error(f"  한계: -{self.config.max_daily_loss_percent}%")

            return {
                'exceeded': True,
                'daily_pl': daily_pl,
                'daily_pl_percent': daily_pl_percent,
                'reason': f'일일 최대 손실 도달 ({daily_pl_percent:.2f}%)'
            }

        return {
            'exceeded': False,
            'daily_pl': daily_pl,
            'daily_pl_percent': daily_pl_percent,
            'reason': 'OK'
        }

    def calculate_take_profit_price(
        self,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """
        익절가 계산 (손익비 기반)

        Args:
            entry_price: 진입가
            stop_loss_price: 손절가

        Returns:
            익절가

        기획서: 손익비 1:1.5
        """
        risk = entry_price - stop_loss_price
        reward = risk * self.config.risk_reward_ratio
        take_profit_price = entry_price + reward

        logger.debug(f"익절가 계산: ${entry_price:.2f} + ({self.config.risk_reward_ratio} x ${risk:.2f}) = ${take_profit_price:.2f}")

        return take_profit_price

    def get_statistics(self) -> Dict:
        """
        리스크 관리 통계 반환

        Returns:
            통계 정보
        """
        return {
            'config': {
                'max_position_percent': self.config.max_position_percent,
                'stop_loss_percent': self.config.stop_loss_percent,
                'max_daily_loss_percent': self.config.max_daily_loss_percent,
                'max_positions': self.config.max_positions,
                'risk_reward_ratio': self.config.risk_reward_ratio
            },
            'daily_tracking': {
                'today_date': self.today_date,
                'start_equity': self.daily_start_equity
            }
        }


# 기획서 리스크 관리 예시 (참고용)
"""
기획서 10. 리스크 관리:

- 1회 투자: 10%
- 손절: -2%
- 하루 손실: -5%

11. 수익률 최적화:

핵심 공식: 수익 = 승률 × 손익비

추천 세팅:
- 승률: 55~60%
- 손익비: 1:1.5
"""
