"""
멀티 전략 관리자

기획서 요구사항:
- 전략 A (모멘텀): 40%
- 전략 B (돌파): 30%
- 전략 C (리버전): 30%
- 동시 실행

NEW-01 (전략별 유니버스 분리):
  각 전략은 서로 다른 스크리너 결과를 유니버스로 사용한다.
  같은 종목이 여러 전략에 동시에 등장하면 점수가 가장 높은 전략만 진입하도록
  충돌 해결 로직을 적용한다.

  momentum  → gap_volume_screener (갭 >3% + 거래량 >3×)
  breakout  → near_52w_high_screener (52주 신고가 5% 이내)
  reversion → oversold_screener (RSI < 35 또는 볼린저 하단 이탈)
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ─── NEW-01: 전략별 스크리너 정의 ──────────────────────────────────────────────

def gap_volume_screener(candidates: List[Dict]) -> List[str]:
    """
    모멘텀 전략 유니버스 스크리너

    조건: pre-market gap > 3% AND volume_ratio >= 3×
    candidates 각 항목: {'symbol', 'gap_pct', 'volume_ratio', ...}
    """
    universe = []
    for c in candidates:
        gap = c.get('gap_pct', 0.0)
        vol = c.get('volume_ratio', 0.0)
        if gap >= 3.0 and vol >= 3.0:
            universe.append(c['symbol'])
    return universe


def near_52w_high_screener(candidates: List[Dict]) -> List[str]:
    """
    브레이크아웃 전략 유니버스 스크리너

    조건: current_price >= 52w_high * 0.95  (52주 신고가 5% 이내)
    candidates 각 항목: {'symbol', 'current_price', 'high_52w', ...}
    """
    universe = []
    for c in candidates:
        price = c.get('current_price', 0.0)
        high_52w = c.get('high_52w', float('inf'))
        if high_52w > 0 and price >= high_52w * 0.95:
            universe.append(c['symbol'])
    return universe


def oversold_screener(candidates: List[Dict]) -> List[str]:
    """
    리버전 전략 유니버스 스크리너

    조건: RSI < 35 OR bb_position < 0.10  (볼린저 하단 10% 이내)
    candidates 각 항목: {'symbol', 'rsi', 'bb_position', ...}
    """
    universe = []
    for c in candidates:
        rsi = c.get('rsi', 50.0)
        bb_pos = c.get('bb_position', 0.5)
        if rsi < 35.0 or bb_pos < 0.10:
            universe.append(c['symbol'])
    return universe


class StrategyType(Enum):
    """전략 유형"""
    MOMENTUM = "momentum"       # 모멘텀 전략 (상승장)
    BREAKOUT = "breakout"       # 돌파 전략 (상승장)
    REVERSION = "reversion"     # 리버전 (평균회귀) 전략 (상승장)
    INVERSE_ETF = "inverse_etf"   # 인버스 ETF 전략 (하락장)
    DEFENSIVE = "defensive"     # 방어형 섹터 전략 (하락장/혼조)


@dataclass
class StrategyConfig:
    """전략 설정"""
    strategy_type: StrategyType
    allocation_percent: float  # 포트폴리오 비중 (%)
    enabled: bool = True
    max_positions: int = 3  # 전략별 최대 포지션
    # NEW-01: 이 전략이 스캔하는 유니버스 (심볼 리스트)
    # 런타임에 screener 가 채운다 — 직접 설정 시 screener 우선순위 무시
    universe: List[str] = field(default_factory=list)


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

    def apply_market_regime(self, regime: str):
        """
        시장 국면에 따라 전략 활성화/비활성화

        Args:
            regime: "BULL" | "BEAR" | "NEUTRAL"

        기획서 분기:
            BULL   → 롱 전략(MOMENTUM, BREAKOUT, REVERSION) 활성, 하락 전략 비활성
            BEAR   → 하락 전략(INVERSE_ETF, DEFENSIVE) 활성, 롱 전략 비활성
            NEUTRAL → DEFENSIVE만 활성, 롱 전략 비활성, 인버스 비활성
        """
        long_strategies = {StrategyType.MOMENTUM, StrategyType.BREAKOUT, StrategyType.REVERSION}
        bear_strategies = {StrategyType.INVERSE_ETF}
        defensive_strategies = {StrategyType.DEFENSIVE}

        if regime == "BULL":
            for st in self.strategies:
                self.strategies[st].enabled = st in long_strategies
        elif regime == "BEAR":
            for st in self.strategies:
                self.strategies[st].enabled = st in (bear_strategies | defensive_strategies)
        else:  # NEUTRAL
            for st in self.strategies:
                self.strategies[st].enabled = st in defensive_strategies

        enabled = [st.value for st, cfg in self.strategies.items() if cfg.enabled]
        logger.info(f"[MarketRegime={regime}] 활성 전략: {enabled}")

    # ─── NEW-01: 유니버스 관리 + 충돌 해결 ──────────────────────────────────

    def update_universes(self, candidates: List[Dict]) -> Dict[str, List[str]]:
        """
        candidates 리스트를 전략별 스크리너로 필터링하여 유니버스를 갱신한다.

        Args:
            candidates: 공통 후보 종목 리스트 (각 항목은 symbol + 지표 포함 dict)
                        예: [{'symbol': 'AAPL', 'gap_pct': 4.5, 'volume_ratio': 5.2,
                               'rsi': 62, 'bb_position': 0.6, 'current_price': 180,
                               'high_52w': 182}, ...]

        Returns:
            {'momentum': [...], 'breakout': [...], 'reversion': [...]}
        """
        universes = {
            StrategyType.MOMENTUM:  gap_volume_screener(candidates),
            StrategyType.BREAKOUT:  near_52w_high_screener(candidates),
            StrategyType.REVERSION: oversold_screener(candidates),
        }

        for st, symbols in universes.items():
            if st in self.strategies:
                self.strategies[st].universe = symbols
                logger.info(f"[{st.value}] 유니버스 갱신: {len(symbols)}종목")

        return {st.value: syms for st, syms in universes.items()}

    def resolve_conflicts(
        self,
        symbol_scores: Dict[str, Dict[str, float]],
    ) -> Dict[str, str]:
        """
        같은 종목이 여러 전략 유니버스에 동시에 나타날 때 충돌을 해결한다.

        점수가 가장 높은 전략이 해당 종목 진입권을 가진다.
        나머지 전략에서 해당 종목은 제거된다.

        Args:
            symbol_scores: {symbol: {strategy_type_value: score}}
                           예: {'NVDA': {'momentum': 82.0, 'breakout': 78.5}}

        Returns:
            {symbol: winning_strategy_type_value}  — 각 종목을 맡을 전략
        """
        winners: Dict[str, str] = {}

        for symbol, strategy_scores in symbol_scores.items():
            if not strategy_scores:
                continue

            # 점수 최고 전략이 승자
            best_strategy = max(strategy_scores, key=lambda k: strategy_scores[k])
            winners[symbol] = best_strategy

            # 패자 전략 유니버스에서 해당 종목 제거
            for st_val, score in strategy_scores.items():
                if st_val != best_strategy:
                    st_enum = StrategyType(st_val)
                    if st_enum in self.strategies:
                        universe = self.strategies[st_enum].universe
                        if symbol in universe:
                            universe.remove(symbol)
                            logger.debug(
                                f"[conflict] {symbol}: {st_val}({score:.1f}) 양보 "
                                f"→ {best_strategy}({strategy_scores[best_strategy]:.1f}) 진입"
                            )

        return winners

    def get_strategy_universe(self, strategy_type: StrategyType) -> List[str]:
        """전략의 현재 유니버스(심볼 리스트) 반환"""
        if strategy_type not in self.strategies:
            return []
        return list(self.strategies[strategy_type].universe)

    # ─────────────────────────────────────────────────────────────────────────

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
    기획서 기본 설정으로 전략 매니저 생성 (전체 전략 등록)

    Args:
        total_capital: 총 자본

    Returns:
        StrategyManager

    BULL 설정:
    - 전략 A (모멘텀): 40%
    - 전략 B (돌파): 30%
    - 전략 C (리버전): 30%

    BEAR 설정:
    - 전략 D (인버스 ETF): 20%
    - 전략 E (방어형 섹터): 30%
    - 현금: 50%
    """
    manager = StrategyManager(total_capital)

    # ── 상승장 전략 ──────────────────────────────────────────
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.MOMENTUM,
        allocation_percent=40.0,
        max_positions=3,
        enabled=True,
    ))
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.BREAKOUT,
        allocation_percent=30.0,
        max_positions=2,
        enabled=True,
    ))
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.REVERSION,
        allocation_percent=30.0,
        max_positions=2,
        enabled=True,
    ))

    # ── 하락장 전략 ──────────────────────────────────────────
    # 기획서: 인버스 ETF 최대 포지션 20%, 하루 2회 제한 → max_positions=2
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.INVERSE_ETF,
        allocation_percent=20.0,
        max_positions=2,
        enabled=False,  # BEAR 국면 진입 시 활성화
    ))
    # 방어형 섹터: 30% (JNJ, PG, XLU)
    manager.add_strategy(StrategyConfig(
        strategy_type=StrategyType.DEFENSIVE,
        allocation_percent=30.0,
        max_positions=3,
        enabled=False,  # BEAR/NEUTRAL 국면 진입 시 활성화
    ))

    logger.info("전체 전략 설정 완료 (BULL + BEAR):")
    logger.info(f"  [BULL] 모멘텀: 40% | 돌파: 30% | 리버전: 30%")
    logger.info(f"  [BEAR] 인버스ETF: 20% | 방어섹터: 30% | 현금: 50%")

    return manager
