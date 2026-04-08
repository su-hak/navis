"""
리스크 관리 팀 API
FastAPI 서버 (port 8002)

흐름:
  전략 엔진/AI 팀 → POST /risk/check → RiskDecision
                                      ↓ allowed=True
                                 Execution Team API (port 8001)
"""
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .core import RiskManager, RiskDecision, RiskStatus
from .core.risk_models import OrderSignal, OrderAction, OrderType, AccountInfo, Position
from .config import config

logging.basicConfig(level=config.log_level, format=config.log_format)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Risk Management API",
    description="리스크 관리 팀 API - 주문 사전 승인 및 리스크 상태 조회",
    version="1.0.0",
)

# 전역 RiskManager 인스턴스
risk_manager: Optional[RiskManager] = None


# ============ 요청/응답 모델 ============

class CheckOrderRequest(BaseModel):
    """주문 리스크 체크 요청"""
    symbol: str
    action: str                     # "BUY" or "SELL"
    quantity: int
    current_price: float

    # 계좌 정보
    account_id: str
    equity: float
    cash: float
    buying_power: float

    # 현재 포지션 (간소화)
    open_positions: List[dict] = []  # [{symbol, quantity, avg_entry_price, market_value, unrealized_pl, ...}]

    # 메타
    strategy_id: Optional[str] = None
    reason: Optional[str] = None


class StopsRequest(BaseModel):
    """손절/익절가 계산 요청"""
    entry_price: float
    action: str = "BUY"


class StopsResponse(BaseModel):
    """손절/익절가 계산 결과"""
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_pct: float
    take_profit_pct: float
    risk_reward_ratio: str


class TradeResultRequest(BaseModel):
    """거래 결과 기록 요청"""
    pnl: float
    symbol: Optional[str] = None
    order_id: Optional[str] = None


class InitDayRequest(BaseModel):
    """거래일 초기화 요청"""
    starting_equity: float


# ============ 초기화 ============

@app.on_event("startup")
async def startup_event():
    global risk_manager

    config.validate()

    risk_manager = RiskManager(
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        max_daily_loss_pct=config.max_daily_loss_pct,
        max_positions=config.max_positions,
        max_exposure_pct=config.max_exposure_pct,
        min_position_pct=config.min_position_pct,
        max_position_pct=config.max_position_pct,
        storage_path=config.storage_path,
    )

    logger.info(f"RiskManager 시작 완료 - 설정: {config.summary()}")


# ============ API 엔드포인트 ============

@app.get("/")
async def root():
    return {
        "service": "Risk Management API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "risk_manager": risk_manager is not None,
        "config": config.summary(),
    }


@app.post("/risk/check", response_model=RiskDecision)
async def check_order(req: CheckOrderRequest):
    """
    주문 리스크 사전 검증 (핵심 엔드포인트)

    전략 엔진이나 AI 팀에서 주문 실행 전에 반드시 호출.
    allowed=True인 경우에만 Execution Team에 주문 전달.

    응답의 adjusted_quantity, stop_loss_price, take_profit_price를 사용할 것.
    """
    if not risk_manager:
        raise HTTPException(status_code=503, detail="RiskManager 초기화 안됨")

    try:
        # OrderSignal 변환
        signal = OrderSignal(
            symbol=req.symbol,
            action=OrderAction(req.action.upper()),
            order_type=OrderType.MARKET,
            quantity=req.quantity,
            strategy_id=req.strategy_id,
            reason=req.reason,
        )

        # AccountInfo 변환
        account = AccountInfo(
            account_id=req.account_id,
            cash=req.cash,
            portfolio_value=req.equity,
            buying_power=req.buying_power,
            equity=req.equity,
            unrealized_pl=0.0,
            realized_pl=0.0,
        )

        # Position 목록 변환
        positions = []
        for p in req.open_positions:
            positions.append(Position(
                symbol=p["symbol"],
                quantity=p.get("quantity", 0),
                avg_entry_price=p.get("avg_entry_price", 0.0),
                current_price=p.get("current_price", p.get("avg_entry_price", 0.0)),
                market_value=p.get("market_value", 0.0),
                unrealized_pl=p.get("unrealized_pl", 0.0),
                unrealized_pl_percent=p.get("unrealized_pl_percent", 0.0),
            ))

        decision = risk_manager.check_order(signal, account, positions, req.current_price)

        logger.info(
            f"리스크 체크 - {req.action} {req.symbol}: "
            f"{decision.action.value} ({decision.reason})"
        )

        return decision

    except Exception as e:
        logger.error(f"리스크 체크 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/risk/stops", response_model=StopsResponse)
async def calculate_stops(req: StopsRequest):
    """손절가 / 익절가 계산"""
    if not risk_manager:
        raise HTTPException(status_code=503, detail="RiskManager 초기화 안됨")

    stop_loss, take_profit = risk_manager.calculate_stops(req.entry_price, req.action)
    rr_ratio = config.take_profit_pct / config.stop_loss_pct

    return StopsResponse(
        entry_price=req.entry_price,
        stop_loss_price=round(stop_loss, 2),
        take_profit_price=round(take_profit, 2),
        stop_loss_pct=config.stop_loss_pct * 100,
        take_profit_pct=config.take_profit_pct * 100,
        risk_reward_ratio=f"1:{rr_ratio:.0f}",
    )


@app.get("/risk/status")
async def get_risk_status(
    equity: float = 0.0,
    buying_power: float = 0.0,
    position_count: int = 0,
):
    """
    현재 리스크 상태 조회

    실시간 계좌 정보 없이도 호출 가능 (간이 체크용)
    """
    if not risk_manager:
        raise HTTPException(status_code=503, detail="RiskManager 초기화 안됨")

    account = AccountInfo(
        account_id="query",
        cash=buying_power,
        portfolio_value=equity,
        buying_power=buying_power,
        equity=equity,
        unrealized_pl=0.0,
        realized_pl=0.0,
    )

    status = risk_manager.get_risk_status(account, [])

    # 일일 통계 추가
    daily_stats = risk_manager.daily_tracker.get_today_stats()

    return {
        "risk_status": status.dict(),
        "daily_stats": daily_stats.dict() if daily_stats else None,
        "config": config.summary(),
    }


@app.post("/risk/record-trade")
async def record_trade_result(req: TradeResultRequest):
    """거래 결과 기록 (체결 후 Execution Team에서 호출)"""
    if not risk_manager:
        raise HTTPException(status_code=503, detail="RiskManager 초기화 안됨")

    risk_manager.record_trade_result(req.pnl)

    daily_stats = risk_manager.daily_tracker.get_today_stats()
    daily_limit_reached = risk_manager.daily_tracker.is_limit_reached()

    return {
        "recorded": True,
        "pnl": req.pnl,
        "daily_pnl": daily_stats.realized_pnl if daily_stats else 0.0,
        "daily_limit_reached": daily_limit_reached,
        "trading_halted": daily_stats.is_trading_halted if daily_stats else False,
    }


@app.post("/risk/init-day")
async def init_trading_day(req: InitDayRequest):
    """거래일 시작 초기화 (장 시작 시 호출)"""
    if not risk_manager:
        raise HTTPException(status_code=503, detail="RiskManager 초기화 안됨")

    risk_manager.initialize_trading_day(req.starting_equity)

    return {
        "initialized": True,
        "starting_equity": req.starting_equity,
        "max_daily_loss": req.starting_equity * config.max_daily_loss_pct,
        "max_daily_loss_pct": f"-{config.max_daily_loss_pct*100:.0f}%",
    }


@app.post("/risk/resume-trading")
async def resume_trading():
    """거래 재개 (수동 오버라이드 - 관리자 전용)"""
    if not risk_manager:
        raise HTTPException(status_code=503, detail="RiskManager 초기화 안됨")

    risk_manager.daily_tracker.resume_trading()
    return {"resumed": True, "message": "거래 재개 완료 (수동 오버라이드)"}


# ============ 실행 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info",
    )
