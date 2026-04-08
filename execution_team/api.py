"""
주문 실행 팀 API
FastAPI 엔드포인트
"""
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from .core import (
    ExecutionEngine, OrderManager, OrderSignal, OrderResult,
    OrderStatus, Position, AccountInfo
)
from .brokers import AlpacaBroker
from .config import config

# 로깅 설정
logging.basicConfig(
    level=config.logging.log_level,
    format=config.logging.log_format
)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(
    title="Execution Team API",
    description="주문 실행 팀 API - 실제 매매 실행",
    version="1.0.0"
)

# 전역 인스턴스
broker: Optional[AlpacaBroker] = None
order_manager: Optional[OrderManager] = None
execution_engine: Optional[ExecutionEngine] = None


# ============ 초기화 ============

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    global broker, order_manager, execution_engine

    try:
        logger.info("주문 실행 엔진 초기화 중...")

        # 설정 검증 (경고만 출력, 실패해도 계속 진행)
        is_valid = config.validate()

        if not is_valid:
            logger.warning("⚠️ 브로커 설정이 불완전합니다. API는 시작되지만 주문 실행은 불가능합니다.")
            logger.info("✓ API 서버 시작 완료 (브로커 미연결 모드)")
            return

        # 브로커 초기화
        broker_config = {
            'api_key': config.broker.api_key,
            'secret_key': config.broker.secret_key,
            'base_url': config.broker.base_url
        }
        broker = AlpacaBroker(broker_config)
        broker.connect()

        # 주문 관리자 초기화
        order_manager = OrderManager(storage_path=config.execution.order_storage_path)

        # 실행 엔진 초기화
        execution_engine = ExecutionEngine(
            broker=broker,
            order_manager=order_manager,
            enable_circuit_breaker=config.execution.enable_circuit_breaker
        )

        logger.info("✓ 주문 실행 엔진 초기화 완료")

    except Exception as e:
        logger.error(f"✗ 초기화 실패: {e}")
        logger.warning("⚠️ API는 시작되지만 주문 실행은 불가능합니다.")
        # 에러를 발생시키지 않고 계속 진행
        pass


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 정리"""
    global broker

    if broker:
        broker.disconnect()
        logger.info("브로커 연결 해제")


def get_engine() -> ExecutionEngine:
    """실행 엔진 의존성"""
    if not execution_engine:
        raise HTTPException(
            status_code=503,
            detail="Execution engine not initialized. Please set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables and restart the service."
        )
    return execution_engine


# ============ API 엔드포인트 ============

@app.get("/")
async def root():
    """루트"""
    return {
        "service": "Execution Team API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    broker_connected = broker and broker.is_connected() if broker else False

    return {
        "status": "healthy",
        "broker_connected": broker_connected,
        "broker_configured": bool(config.broker.api_key),
        "message": "OK" if broker_connected else "API running but broker not connected. Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables."
    }


@app.post("/orders/execute", response_model=OrderResult)
async def execute_order(
    signal: OrderSignal,
    engine: ExecutionEngine = Depends(get_engine)
):
    """
    주문 실행

    전략 엔진이나 AI 팀에서 신호를 받아 실제 주문 실행
    """
    try:
        logger.info(f"주문 실행 요청 - {signal.action.value} {signal.quantity} {signal.symbol}")
        result = engine.execute_order(signal)
        return result

    except Exception as e:
        logger.error(f"주문 실행 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders/{order_id}/status")
async def get_order_status(
    order_id: str,
    engine: ExecutionEngine = Depends(get_engine)
):
    """주문 상태 조회"""
    status = engine.get_order_status(order_id)
    if not status:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")

    order = engine.order_manager.get_order(order_id)
    return {
        "order_id": order_id,
        "status": status.value,
        "order": order.dict() if order else None
    }


@app.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    engine: ExecutionEngine = Depends(get_engine)
):
    """주문 취소"""
    success = engine.cancel_order(order_id)
    if not success:
        raise HTTPException(status_code=400, detail="주문을 취소할 수 없습니다")

    return {
        "order_id": order_id,
        "cancelled": True
    }


@app.get("/positions", response_model=List[Position])
async def get_positions(engine: ExecutionEngine = Depends(get_engine)):
    """현재 포지션 목록 조회"""
    positions = engine.get_positions()
    return positions


@app.get("/account", response_model=AccountInfo)
async def get_account(engine: ExecutionEngine = Depends(get_engine)):
    """계좌 정보 조회"""
    account = engine.get_account()
    if not account:
        raise HTTPException(status_code=503, detail="계좌 정보를 가져올 수 없습니다")
    return account


@app.get("/stats")
async def get_stats(engine: ExecutionEngine = Depends(get_engine)):
    """주문 실행 통계"""
    stats = engine.get_execution_stats()
    return stats


@app.post("/circuit-breaker/reset")
async def reset_circuit_breaker(engine: ExecutionEngine = Depends(get_engine)):
    """서킷 브레이커 리셋"""
    engine.reset_circuit_breaker()
    return {"message": "서킷 브레이커가 리셋되었습니다"}


# ============ 실행 ============

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
