"""
멀티 전략 관리자

기획서 요구사항:
- 전략 A (모멘텀): 40%
- 전략 B (돌파): 30%
- 전략 C (리버전): 30%
- 동시 실행
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """전략 유형"""
    MOMENTUM = "momentum"  # 모멘텀 전략
    BREAKOUT = "breakout"  # 돌파 전략
    REVERSION = "reversion"  # 리버전 (평균회귀) 전략


@dataclass
class StrategyConfig:
    """전략 설정"""
    strategy_type: StrategyType
    allocation_percent: float  # 포트폴리오 비중 (%)
    enabled: bool = True
    max_positions: int = 3  # 전략별 최대 포지션


class StrategyManager:
    """
    멀티 전략 관리자

    여러 전략을 동시에 실행하고 포트폴리오 비중을 관리합니다.

    기획서 예시:
    - 전략 A (모멘텀): 40%
    - 전략 B (돌파): 30%
    - 전략 C (리버전): 30%
    """

    def __init__(self, total_capital: float):
        """
        초기화

        Args:
            total_capital: 총 자본
        """
        self.total_capital = total_capital
        self.strategies: Dict[StrategyType, StrategyConfig] = {}
        self.active_positions: Dict[StrategyType, List] = {}

        logger.info(f"멀티 전략 관리자 초기화: 총 자본 ${total_capital:,.2f}")

    def add_strategy(self, config: StrategyConfig):
        """
        전략 추가

        Args:
            config: 전략 설정
        """
        self.strategies[config.strategy_type] = config
        self.active_positions[config.strategy_type] = []

        logger.info(f"전략 추가: {config.strategy_type.value} ({config.allocation_percent}%)")

    def get_strategy_capital(self, strategy_type: StrategyType) -> float:
        """
        전략별 할당 자본 계산

        Args:
            strategy_type: 전략 유형

        Returns:
            할당 자본

        기획서 예시:
        - 모멘텀: 총 자본의 40%
        - 돌파: 총 자본의 30%
        - 리버전: 총 자본의 30%
        """
        if strategy_type not in self.strategies:
            return 0.0

        config = self.strategies[strategy_type]
        allocated_capital = self.total_capital * (config.allocation_percent / 100.0)

        return allocated_capital

    def can_open_position(
        self,
        strategy_type: StrategyType,
        required_capital: float
    ) -> Dict[str, any]:
        """
        포지션 오픈 가능 여부 확인

        Args:
            strategy_type: 전략 유형
            required_capital: 필요한 자본

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'allocated_capital': float,
                'used_capital': float,
                'available_capital': float
            }
        """
        if strategy_type not in self.strategies:
            return {
                'allowed': False,
                'reason': f'전략 {strategy_type.value} 미등록',
                'allocated_capital': 0,
                'used_capital': 0,
                'available_capital': 0
            }

        config = self.strategies[strategy_type]

        # 전략이 비활성화된 경우
        if not config.enabled:
            return {
                'allowed': False,
                'reason': f'전략 {strategy_type.value} 비활성화',
                'allocated_capital': 0,
                'used_capital': 0,
                'available_capital': 0
            }

        # 할당 자본 계산
        allocated_capital = self.get_strategy_capital(strategy_type)

        # 사용 중인 자본 계산
        positions = self.active_positions[strategy_type]
        used_capital = sum(p.get('cost_basis', 0) for p in positions)
        available_capital = allocated_capital - used_capital

        # 최대 포지션 수 체크
        if len(positions) >= config.max_positions:
            return {
                'allowed': False,
                'reason': f'전략 최대 포지션 수 도달 ({len(positions)}/{config.max_positions})',
                'allocated_capital': allocated_capital,
                'used_capital': used_capital,
                'available_capital': available_capital
            }

        # 자본 부족 체크
        if required_capital > available_capital:
            return {
                'allowed': False,
                'reason': f'전략 자본 부족 (필요: ${required_capital:,.2f}, 가용: ${available_capital:,.2f})',
                'allocated_capital': allocated_capital,
                'used_capital': used_capital,
                'available_capital': available_capital
            }

        return {
            'allowed': True,
            'reason': 'OK',
            'allocated_capital': allocated_capital,
            'used_capital': used_capital,
            'available_capital': available_capital
        }

    def add_position(self, strategy_type: StrategyType, position: Dict):
        """
        포지션 추가

        Args:
            strategy_type: 전략 유형
            position: 포지션 정보
        """
        if strategy_type in self.active_positions:
            self.active_positions[strategy_type].append(position)
            logger.info(f"[{strategy_type.value}] 포지션 추가: {position.get('symbol', 'Unknown')}")

    def remove_position(self, strategy_type: StrategyType, symbol: str):
        """
        포지션 제거

        Args:
            strategy_type: 전략 유형
            symbol: 종목 심볼
        """
        if strategy_type in self.active_positions:
            self.active_positions[strategy_type] = [
                p for p in self.active_positions[strategy_type]
                if p.get('symbol') != symbol
            ]
            logger.info(f"[{strategy_type.value}] 포지션 제거: {symbol}")

    def get_portfolio_allocation(self) -> Dict:
        """
        포트폴리오 배분 현황

        Returns:
            전략별 배분 현황
        """
        allocation = {}

        for strategy_type, config in self.strategies.items():
            allocated_capital = self.get_strategy_capital(strategy_type)
            positions = self.active_positions[strategy_type]
            used_capital = sum(p.get('cost_basis', 0) for p in positions)

            allocation[strategy_type.value] = {
                'allocation_percent': config.allocation_percent,
                'allocated_capital': allocated_capital,
                'used_capital': used_capital,
                'available_capital': allocated_capital - used_capital,
                'position_count': len(positions),
                'max_positions': config.max_positions,
                'enabled': config.enabled
            }

        return allocation

    def get_statistics(self) -> Dict:
        """
        멀티 전략 통계

        Returns:
            통계 정보
        """
        total_positions = sum(len(positions) for positions in self.active_positions.values())
        total_used_capital = sum(
            sum(p.get('cost_basis', 0) for p in positions)
            for positions in self.active_positions.values()
        )

        return {
            'total_capital': self.total_capital,
            'total_positions': total_positions,
            'total_used_capital': total_used_capital,
            'available_capital': self.total_capital - total_used_capital,
            'strategy_count': len(self.strategies),
            'strategies': self.get_portfolio_allocation()
        }


# 기획서 예시 설정 함수
def create_default_strategy_manager(total_capital: float) -> StrategyManager:
    """
    기획서 기본 설정으로 전략 매니저 생성

    Args:
        total_capital: 총 자본

    Returns:
        StrategyManager

    기획서 설정:
    - 전략 A (모멘텀): 40%
    - 전략 B (돌파): 30%
    - 전략 C (리버전): 30%
    """
    manager = StrategyManager(total_capital)

    # 모멘텀 전략 (40%)
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.MOMENTUM,
        allocation_percent=40.0,
        max_positions=3
    ))

    # 돌파 전략 (30%)
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.BREAKOUT,
        allocation_percent=30.0,
        max_positions=2
    ))

    # 리버전 전략 (30%)
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.REVERSION,
        allocation_percent=30.0,
        max_positions=2
    ))

    logger.info("기획서 기본 전략 설정 완료:")
    logger.info(f"  모멘텀: 40% (${total_capital * 0.4:,.2f})")
    logger.info(f"  돌파: 30% (${total_capital * 0.3:,.2f})")
    logger.info(f"  리버전: 30% (${total_capital * 0.3:,.2f})")

    return manager
