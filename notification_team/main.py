"""
알림 / 리포트 팀 - FastAPI 독립 서버
포트: 8005 (기본)

역할:
  - 텔레그램 알림 발송 (거래 체결, 손절/익절, 오류)
  - 일일/주간 리포트 생성 및 발송
  - 장중 포지션 현황 정기 알림
  - 알림 API (테스트, 즉시 발송, 상태 확인)
"""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import config
from .notifier import notifier
from .report_builder import report_builder, report_db
from .scheduler import notification_scheduler, job_portfolio_status

# ── 로깅 설정 ─────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── 라이프사이클 ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("  Navis 알림/리포트 팀 서버 시작")
    logger.info("=" * 60)

    is_telegram_ok = config.validate()

    # DB 연결 (리포트 조회용)
    db_ok = report_db.connect()
    if not db_ok:
        logger.warning("⚠️ DB 연결 실패 - 리포트 기능 제한")

    # 스케줄러 시작
    notification_scheduler.start()

    # 시작 알림
    await notifier.notify_system_start(mode="알림 서비스 시작")

    # 시작 직후 포지션 현황 1회 발송 (평일만, 주말 제외)
    from .scheduler import _is_weekday_et
    if _is_weekday_et():
        await job_portfolio_status()

    logger.info("✓ 알림/리포트 서버 준비 완료")

    yield

    notification_scheduler.stop()
    logger.info("✓ 알림/리포트 서버 종료")


# ── FastAPI 앱 ────────────────────────────────────────────────
app = FastAPI(
    title="Navis Notification API",
    description=(
        "AI 자동매매 시스템 - 알림/리포트 팀\n\n"
        "텔레그램 알림 발송, 일일/주간 리포트, 포지션 현황 알림"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic 모델 ─────────────────────────────────────────────

class BuyNotifyRequest(BaseModel):
    symbol: str
    filled_price: float
    quantity: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: Optional[str] = None


class SellNotifyRequest(BaseModel):
    symbol: str
    filled_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    sell_type: str = "SELL"


class RiskHaltRequest(BaseModel):
    reason: str
    daily_pnl: float


class ErrorNotifyRequest(BaseModel):
    context: str
    error: str


class SystemStartRequest(BaseModel):
    mode: str = "시뮬레이션"
    watchlist_size: int = 0
    portfolio_count: int = -1


class PortfolioStatusRequest(BaseModel):
    equity: float
    cash: float
    positions: List[Dict[str, Any]] = []
    daily_pnl: float = 0.0


# ── 기본 엔드포인트 ────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "Navis Notification API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "telegram_enabled": notifier.enabled,
        "scheduler_running": notification_scheduler.is_running,
        "scheduler_jobs": notification_scheduler.get_job_status(),
    }


# ── 알림 상태 / 테스트 ─────────────────────────────────────────

@app.get("/status")
async def get_status() -> Dict[str, Any]:
    """알림 서비스 상태"""
    return {
        "telegram_enabled": notifier.enabled,
        "bot_token_set": bool(config.TELEGRAM_BOT_TOKEN),
        "chat_id_set": bool(config.TELEGRAM_CHAT_ID),
        "scheduler_running": notification_scheduler.is_running,
        "jobs": notification_scheduler.get_job_status(),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/test")
async def send_test() -> Dict[str, Any]:
    """테스트 메시지 발송"""
    if not notifier.enabled:
        raise HTTPException(
            status_code=503,
            detail="텔레그램 미설정 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 확인)",
        )
    success = await notifier.notify_test()
    return {"success": success, "timestamp": datetime.now().isoformat()}


# ── 거래 알림 엔드포인트 ───────────────────────────────────────
# 다른 마이크로서비스가 호출하여 알림 발송

@app.post("/notify/buy")
async def notify_buy(req: BuyNotifyRequest) -> Dict[str, Any]:
    """매수 체결 알림"""
    await notifier.notify_buy(
        symbol=req.symbol,
        filled_price=req.filled_price,
        quantity=req.quantity,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        reason=req.reason,
    )
    return {"success": True}


@app.post("/notify/sell")
async def notify_sell(req: SellNotifyRequest) -> Dict[str, Any]:
    """매도 체결 알림"""
    await notifier.notify_sell(
        symbol=req.symbol,
        filled_price=req.filled_price,
        quantity=req.quantity,
        pnl=req.pnl,
        pnl_pct=req.pnl_pct,
        sell_type=req.sell_type,
    )
    return {"success": True}


@app.post("/notify/risk-halt")
async def notify_risk_halt(req: RiskHaltRequest) -> Dict[str, Any]:
    """리스크 중단 알림"""
    await notifier.notify_risk_halt(reason=req.reason, daily_pnl=req.daily_pnl)
    return {"success": True}


@app.post("/notify/error")
async def notify_error(req: ErrorNotifyRequest) -> Dict[str, Any]:
    """오류 알림"""
    await notifier.notify_error(context=req.context, error=req.error)
    return {"success": True}


@app.post("/notify/system-start")
async def notify_system_start(req: SystemStartRequest) -> Dict[str, Any]:
    """시스템 시작 알림"""
    await notifier.notify_system_start(
        mode=req.mode,
        watchlist_size=req.watchlist_size,
        portfolio_count=req.portfolio_count,
    )
    return {"success": True}


@app.post("/notify/portfolio-status")
async def notify_portfolio_status(req: PortfolioStatusRequest) -> Dict[str, Any]:
    """포지션 현황 알림 (외부 호출용)"""
    await notifier.notify_portfolio_status(
        equity=req.equity,
        cash=req.cash,
        positions=req.positions,
        daily_pnl=req.daily_pnl,
    )
    return {"success": True}


# ── 리포트 엔드포인트 ─────────────────────────────────────────

@app.post("/report/daily")
async def send_daily_report(ending_equity: float = 0.0) -> Dict[str, Any]:
    """일일 리포트 즉시 발송"""
    report = report_builder.build_daily_report(ending_equity=ending_equity)
    await notifier.notify_daily_report(report)
    return {"success": True, "report": report}


@app.get("/report/weekly")
async def send_weekly_report() -> Dict[str, Any]:
    """주간 리포트 즉시 발송"""
    weekly_data = report_builder.build_weekly_report()
    await notifier.notify_weekly_report(weekly_data)
    return {"success": True, "days": len(weekly_data), "data": weekly_data}


@app.get("/report/history")
async def get_report_history(limit: int = 10) -> Dict[str, Any]:
    """최근 거래 내역 조회"""
    trades = report_db.get_recent_trades(limit=limit)
    weekly = report_db.get_weekly_summary()
    today = report_db.get_today_stats()
    return {
        "today": today,
        "weekly_summary": weekly,
        "recent_trades": trades,
        "timestamp": datetime.now().isoformat(),
    }


# ── 진입점 ───────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "notification_team.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower(),
    )
