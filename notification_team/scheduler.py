"""
알림 / 리포트 팀 - 알림 전용 스케줄러
백엔드 스케줄러와 독립적으로 운영 가능
포함: 일일 리포트, 주간 리포트, 장중 포지션 현황
"""
import logging
from datetime import datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import config
from .notifier import notifier
from .report_builder import report_builder, get_tp_analysis_from_alpaca

logger = logging.getLogger(__name__)


def _alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID": config.ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": config.ALPACA_SECRET_KEY,
    }


async def _get_account_from_alpaca() -> dict:
    """Alpaca API 직접 호출로 계좌 정보 조회"""
    if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
        logger.warning("Alpaca API 키 미설정 - 계좌 조회 불가")
        return {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(
                f"{config.ALPACA_BASE_URL}/v2/account",
                headers=_alpaca_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "equity": data.get("equity", 0),
                "cash": data.get("cash", 0),
                "buying_power": data.get("buying_power", 0),
                "portfolio_value": data.get("portfolio_value", 0),
            }
    except Exception as e:
        logger.warning(f"Alpaca 계좌 조회 실패: {e}")
        return {}


async def _get_positions_from_alpaca() -> list:
    """Alpaca API 직접 호출로 포지션 조회"""
    if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
        logger.warning("Alpaca API 키 미설정 - 포지션 조회 불가")
        return []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(
                f"{config.ALPACA_BASE_URL}/v2/positions",
                headers=_alpaca_headers(),
            )
            resp.raise_for_status()
            positions = resp.json()
            return [
                {
                    "symbol": p.get("symbol"),
                    "unrealized_pl": p.get("unrealized_pl", 0),
                    "unrealized_plpc": p.get("unrealized_plpc", 0),
                    "qty": p.get("qty", 0),
                    "market_value": p.get("market_value", 0),
                }
                for p in positions
            ]
    except Exception as e:
        logger.warning(f"Alpaca 포지션 조회 실패: {e}")
        return []


async def job_daily_report():
    """일일 리포트 발송 (16:10 ET)"""
    logger.info("[스케줄] 일일 리포트 생성 중...")
    account = await _get_account_from_alpaca()
    ending_equity = float(account.get("equity", 0))
    report = report_builder.build_daily_report(ending_equity=ending_equity)
    logger.info(
        f"[리포트] 소스={report.get('source','?')} 총매도={report.get('sell_trades',0)}건 "
        f"승={report.get('winning_trades',0)} 패={report.get('losing_trades',0)} "
        f"PnL=${report['realized_pnl']:+,.2f}"
    )

    # ── TP 수준별 도달 가능 승률 분석 (학습 데이터 저장) ──────
    trade_date = report.get("trade_date", "")
    tp_analysis = None
    if trade_date:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            tp_analysis = await loop.run_in_executor(
                None, get_tp_analysis_from_alpaca, trade_date
            )
            if tp_analysis:
                if report_builder.db.is_connected:
                    report_builder.db.save_tp_analysis(trade_date, tp_analysis)
                    logger.info(f"[TP분석] DB 저장 완료: {trade_date}")
                else:
                    logger.warning("[TP분석] DB 미연결 - 저장 생략")
        except Exception as e:
            logger.warning(f"[TP분석] 실패: {e}")

    await notifier.notify_daily_report(report, tp_analysis=tp_analysis)
    logger.info(f"✓ 일일 리포트 발송 완료 (PnL ${report['realized_pnl']:+,.2f})")


async def job_weekly_report():
    """주간 리포트 발송 (금요일 16:30 ET)"""
    logger.info("[스케줄] 주간 리포트 생성 중...")
    weekly_data = report_builder.build_weekly_report()
    await notifier.notify_weekly_report(weekly_data)
    logger.info(f"✓ 주간 리포트 발송 완료 ({len(weekly_data)}거래일)")


def _is_weekday_et() -> bool:
    """현재 시각이 ET 기준 평일(월~금)인지 확인"""
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    return now_et.weekday() < 5  # 0=월 ~ 4=금


async def job_portfolio_status():
    """장중 포지션 현황 알림 (설정된 간격마다, 주말 제외)"""
    if not _is_weekday_et():
        logger.debug("[스케줄] 주말 - 포지션 현황 알림 생략")
        return

    logger.info("[스케줄] 포지션 현황 알림 발송 중...")
    account = await _get_account_from_alpaca()
    positions = await _get_positions_from_alpaca()

    if not account:
        logger.warning("계좌 정보 없음 (Alpaca API 키 확인 필요) - 포지션 현황 알림 생략")
        return

    # 일중 손익 = 보유 포지션 미실현 손익 합산 (Alpaca 직접 조회)
    daily_pnl = sum(float(p.get("unrealized_pl", 0)) for p in positions)

    await notifier.notify_portfolio_status(
        equity=float(account.get("equity", 0)),
        cash=float(account.get("cash", 0)),
        positions=positions,
        daily_pnl=daily_pnl,
    )
    logger.info("✓ 포지션 현황 알림 발송 완료")


class NotificationScheduler:
    """알림 전용 스케줄러"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="America/New_York")
        self._is_running = False

    def setup_jobs(self):
        """알림 작업 등록"""

        # ── 1. 일일 리포트 (16:10 ET, 월~금) ─────────────────
        self.scheduler.add_job(
            job_daily_report,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=16,
                minute=10,
                timezone="America/New_York",
            ),
            id="daily_report",
            name="일일 리포트",
            replace_existing=True,
            max_instances=1,
        )
        logger.info("✓ 일일 리포트 등록: 월~금 16:10 ET")

        # ── 2. 주간 리포트 (금요일 16:30 ET) ─────────────────
        self.scheduler.add_job(
            job_weekly_report,
            trigger=CronTrigger(
                day_of_week=config.WEEKLY_REPORT_DOW,
                hour=16,
                minute=30,
                timezone="America/New_York",
            ),
            id="weekly_report",
            name="주간 리포트",
            replace_existing=True,
            max_instances=1,
        )
        logger.info(f"✓ 주간 리포트 등록: {config.WEEKLY_REPORT_DOW} 16:30 ET")

        # ── 3. 장중 포지션 현황 (설정된 간격, 장중만) ─────────
        if config.PORTFOLIO_STATUS_INTERVAL_MIN > 0:
            self.scheduler.add_job(
                job_portfolio_status,
                trigger=IntervalTrigger(
                    minutes=config.PORTFOLIO_STATUS_INTERVAL_MIN
                ),
                id="portfolio_status",
                name="포지션 현황",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=60,
            )
            logger.info(
                f"✓ 포지션 현황 등록: 매 {config.PORTFOLIO_STATUS_INTERVAL_MIN}분"
            )

    def start(self):
        if self._is_running:
            return
        self.setup_jobs()
        self.scheduler.start()
        self._is_running = True
        jobs = [job.id for job in self.scheduler.get_jobs()]
        logger.info(f"✓ 알림 스케줄러 시작: {jobs}")

    def stop(self):
        if not self._is_running:
            return
        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("✓ 알림 스케줄러 중지")

    def get_job_status(self) -> list:
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in self.scheduler.get_jobs()
        ]

    @property
    def is_running(self) -> bool:
        return self._is_running


# 전역 인스턴스
notification_scheduler = NotificationScheduler()
