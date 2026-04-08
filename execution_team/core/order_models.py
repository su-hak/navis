"""
주문 실행 팀 - 데이터 모델
모든 주문 관련 데이터 구조 정의
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid


class OrderAction(str, Enum):
    """주문 액션"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """주문 타입"""
    MARKET = "MARKET"      # 시장가
    LIMIT = "LIMIT"        # 지정가
    STOP = "STOP"          # 스탑
    STOP_LIMIT = "STOP_LIMIT"  # 스탑 리미트


class TimeInForce(str, Enum):
    """주문 유효기간"""
    DAY = "DAY"            # 당일
    GTC = "GTC"            # Good-Til-Cancelled
    IOC = "IOC"            # Immediate-Or-Cancel
    FOK = "FOK"            # Fill-Or-Kill


class OrderStatus(str, Enum):
    """주문 상태"""
    PENDING = "PENDING"              # 대기 중
    VALIDATING = "VALIDATING"        # 검증 중
    SUBMITTED = "SUBMITTED"          # 브로커에 제출됨
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 부분 체결
    FILLED = "FILLED"                # 완전 체결
    CANCELLED = "CANCELLED"          # 취소됨
    REJECTED = "REJECTED"            # 거부됨
    FAILED = "FAILED"                # 실패


class OrderSignal(BaseModel):
    """
    주문 신호 (입력)
    전략 엔진이나 AI 팀에서 전달하는 매매 신호
    """
    symbol: str = Field(..., description="종목 심볼 (예: TSLA)")
    action: OrderAction = Field(..., description="매수/매도")
    order_type: OrderType = Field(default=OrderType.MARKET, description="주문 타입")
    quantity: int = Field(..., gt=0, description="수량 (양수)")
    limit_price: Optional[float] = Field(None, gt=0, description="지정가 (LIMIT인 경우)")
    stop_price: Optional[float] = Field(None, gt=0, description="스탑 가격 (STOP인 경우)")
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY, description="주문 유효기간")

    # 메타데이터
    strategy_id: Optional[str] = Field(None, description="전략 ID")
    reason: Optional[str] = Field(None, description="매매 이유")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 메타데이터")

    @validator('limit_price')
    def validate_limit_price(cls, v, values):
        """LIMIT 주문인 경우 limit_price 필수"""
        if values.get('order_type') == OrderType.LIMIT and v is None:
            raise ValueError("LIMIT 주문은 limit_price가 필요합니다")
        return v

    @validator('stop_price')
    def validate_stop_price(cls, v, values):
        """STOP 주문인 경우 stop_price 필수"""
        order_type = values.get('order_type')
        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and v is None:
            raise ValueError("STOP 주문은 stop_price가 필요합니다")
        return v


class Order(BaseModel):
    """
    주문 객체 (내부 관리용)
    시스템 내부에서 주문을 추적하고 관리하는 모델
    """
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="내부 주문 ID")
    broker_order_id: Optional[str] = Field(None, description="브로커 주문 ID")

    # 주문 정보 (OrderSignal과 동일)
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce

    # 상태 정보
    status: OrderStatus = Field(default=OrderStatus.PENDING)

    # 체결 정보
    filled_quantity: int = Field(default=0, description="체결된 수량")
    filled_price: Optional[float] = Field(None, description="평균 체결가")
    commission: Optional[float] = Field(None, description="수수료")

    # 타임스탬프
    created_at: datetime = Field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    # 메타데이터
    strategy_id: Optional[str] = None
    reason: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = Field(default=0, description="재시도 횟수")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @property
    def is_filled(self) -> bool:
        """완전 체결 여부"""
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        """활성 주문 여부 (체결 대기 중)"""
        return self.status in [OrderStatus.PENDING, OrderStatus.VALIDATING,
                               OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]

    @property
    def is_terminal(self) -> bool:
        """종료 상태 여부"""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED,
                               OrderStatus.REJECTED, OrderStatus.FAILED]


class OrderResult(BaseModel):
    """
    주문 실행 결과 (출력)
    execute_order() 함수의 반환값
    """
    success: bool = Field(..., description="성공 여부")
    order_id: str = Field(..., description="주문 ID")
    broker_order_id: Optional[str] = Field(None, description="브로커 주문 ID")

    status: OrderStatus

    # 체결 정보 (체결된 경우)
    filled_quantity: Optional[int] = None
    filled_price: Optional[float] = None
    commission: Optional[float] = None
    filled_at: Optional[datetime] = None

    # 에러 정보 (실패한 경우)
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # 타이밍
    execution_time_ms: Optional[float] = Field(None, description="실행 시간 (밀리초)")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Position(BaseModel):
    """
    포지션 정보
    현재 보유 중인 종목 정보
    """
    symbol: str
    quantity: int                    # 보유 수량 (음수면 숏)
    avg_entry_price: float          # 평균 진입가
    current_price: float            # 현재가
    market_value: float             # 시장 가치
    unrealized_pl: float            # 미실현 손익
    unrealized_pl_percent: float    # 미실현 손익률 (%)

    @property
    def is_long(self) -> bool:
        """롱 포지션 여부"""
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """숏 포지션 여부"""
        return self.quantity < 0


class AccountInfo(BaseModel):
    """
    계좌 정보
    브로커로부터 받아온 계좌 상태
    """
    account_id: str
    cash: float                      # 현금
    portfolio_value: float           # 포트폴리오 가치
    buying_power: float              # 매수 가능 금액
    equity: float                    # 자산 총액

    # 손익
    unrealized_pl: float             # 미실현 손익
    realized_pl: float               # 실현 손익

    # 제한
    daytrade_count: Optional[int] = None     # 데이트레이드 횟수
    pattern_day_trader: bool = False         # PDT 여부

    # 타임스탬프
    last_updated: datetime = Field(default_factory=datetime.now)


class BrokerError(Exception):
    """
    브로커 에러
    브로커 API 호출 중 발생하는 에러
    """
    def __init__(self, message: str, error_code: Optional[str] = None,
                 retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.retryable = retryable  # 재시도 가능 여부

    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ValidationError(Exception):
    """
    주문 검증 에러
    주문 파라미터가 유효하지 않은 경우
    """
    pass


class ExecutionError(Exception):
    """
    주문 실행 에러
    주문 실행 중 발생하는 일반적인 에러
    """
    pass
