"""
리스크 관리 팀 - 데이터 모델
모든 리스크 관련 데이터 구조 정의
"""
from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class RiskAction(str, Enum):
    """리스크 결정 액션"""
    ALLOW = "ALLOW"       # 주문 허용
    ADJUST = "ADJUST"     # 수량 조정 후 허용
    REJECT = "REJECT"     # 주문 거부


class RejectReason(str, Enum):
    """거부 사유"""
    DAILY_LOSS_LIMIT     = "DAILY_LOSS_LIMIT"      # 하루 손실 한도 초과
    POSITION_LIMIT       = "POSITION_LIMIT"         # 최대 포지션 수 초과
    EXPOSURE_LIMIT       = "EXPOSURE_LIMIT"         # 포트폴리오 노출도 초과
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"   # 자본 부족
    DUPLICATE_POSITION   = "DUPLICATE_POSITION"     # 이미 보유 중인 종목 재매수
    INVALID_SIGNAL       = "INVALID_SIGNAL"         # 잘못된 신호


class RiskDecision(BaseModel):
    """
    리스크 관리 결정 결과
    check_order()의 반환값
    """
    action: RiskAction
    allowed: bool

    # 조정된 주문 정보
    adjusted_quantity: Optional[int] = Field(None, description="조정된 수량 (ADJUST인 경우)")
    stop_loss_price: Optional[float] = Field(None, description="권장 손절가")
    take_profit_price: Optional[float] = Field(None, description="권장 익절가")

    # 판단 근거
    reason: str = Field(..., description="허용/거부 사유")
    warnings: List[str] = Field(default_factory=list, description="경고 메시지 목록")
    risk_score: Optional[float] = Field(None, description="리스크 점수 0~100 (높을수록 위험)")

    # 포지션 사이징 정보
    recommended_quantity: Optional[int] = Field(None, description="권장 수량")
    invest_amount: Optional[float] = Field(None, description="투자 금액")
    invest_pct: Optional[float] = Field(None, description="총 자산 대비 투자 비율")

    checked_at: datetime = Field(default_factory=datetime.now)


class DailyStats(BaseModel):
    """일일 거래 통계"""
    date: str                           # YYYY-MM-DD
    starting_equity: float              # 장 시작 시 자산
    current_equity: float               # 현재 자산
    realized_pnl: float = 0.0          # 실현 손익
    unrealized_pnl: float = 0.0        # 미실현 손익
    total_pnl: float = 0.0             # 총 손익
    total_pnl_pct: float = 0.0         # 총 손익률 (%)
    trade_count: int = 0                # 거래 횟수
    win_count: int = 0                  # 수익 거래 수
    loss_count: int = 0                 # 손실 거래 수
    is_trading_halted: bool = False     # 거래 중단 여부


class RiskStatus(BaseModel):
    """
    현재 리스크 상태 스냅샷
    get_risk_status()의 반환값
    """
    # 일일 손실
    daily_pnl_pct: float
    daily_loss_limit_pct: float
    is_daily_limit_reached: bool

    # 포지션 수
    position_count: int
    max_positions: int
    is_position_limit_reached: bool

    # 포트폴리오 노출도
    portfolio_exposure_pct: float
    max_exposure_pct: float
    is_exposure_limit_reached: bool

    # 가용 자본
    available_capital: float
    available_capital_pct: float

    # 전반적 거래 가능 여부
    can_trade: bool
    halt_reason: Optional[str] = None

    checked_at: datetime = Field(default_factory=datetime.now)
