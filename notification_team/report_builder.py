"""
알림 / 리포트 팀 - 리포트 빌더
우선순위: Alpaca API → DB 순으로 당일 거래 통계 조회
"""
import logging
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
import mysql.connector
from mysql.connector import pooling

from .config import config

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
_ET = timezone(timedelta(hours=-4))   # EDT; 겨울철 EST=-5이지만 Alpaca는 ET 기준


def _today_et() -> str:
    """현재 ET 기준 날짜 문자열 (YYYY-MM-DD)"""
    return datetime.now(_ET).strftime("%Y-%m-%d")


# ── Alpaca 직접 조회 ─────────────────────────────────────────


def _alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID": config.ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": config.ALPACA_SECRET_KEY,
    }


def _get_today_pnl_from_alpaca(client: httpx.Client) -> float:
    """
    Alpaca portfolio/history 로 당일 실현+미실현 손익 조회.
    실패 시 0.0 반환.
    """
    try:
        resp = client.get(
            f"{config.ALPACA_BASE_URL}/v2/account/portfolio/history",
            headers=_alpaca_headers(),
            params={"period": "1D", "timeframe": "1D", "extended_hours": "true"},
        )
        resp.raise_for_status()
        data = resp.json()
        pnl_list = data.get("profit_loss") or []
        if pnl_list:
            return float(pnl_list[-1] or 0)
    except Exception as e:
        logger.warning(f"Alpaca portfolio/history 조회 실패: {e}")
    return 0.0


def get_today_stats_from_alpaca() -> Optional[Dict[str, Any]]:
    """
    Alpaca API로 당일 거래 통계 조회.
      - FILL activities → 체결 횟수 (매수/매도 구분)
      - portfolio/history → 당일 총 손익
    API 키 미설정이거나 조회 실패 시 None 반환.
    """
    if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
        logger.warning("Alpaca API 키 미설정 - Alpaca 기반 통계 조회 불가")
        return None

    today_et = _today_et()
    after_ts = f"{today_et}T00:00:00-04:00"

    try:
        with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
            # ── 1. 당일 체결 내역 ────────────────────────────
            resp = client.get(
                f"{config.ALPACA_BASE_URL}/v2/account/activities/FILL",
                headers=_alpaca_headers(),
                params={"after": after_ts, "direction": "asc", "page_size": 100},
            )
            resp.raise_for_status()
            activities = resp.json()

            # ── 2. 당일 손익 (portfolio history) ─────────────
            today_pnl = _get_today_pnl_from_alpaca(client)

    except Exception as e:
        logger.warning(f"Alpaca activities 조회 실패: {e}")
        return None

    if not isinstance(activities, list):
        logger.warning(f"Alpaca activities 응답 형식 오류: {type(activities)}")
        return None

    total_fills = len(activities)
    sell_fills = [a for a in activities if a.get("side") == "sell"]
    buy_fills  = [a for a in activities if a.get("side") == "buy"]

    # 승/패는 매도 횟수 기준으로 portfolio pnl 부호만 사용
    # (종목별 pnl은 Alpaca FILL API에서 제공 안 됨)
    sell_count = len(sell_fills)
    if sell_count > 0 and today_pnl > 0:
        winning = sell_count
        losing  = 0
    elif sell_count > 0 and today_pnl < 0:
        winning = 0
        losing  = sell_count
    else:
        winning = 0
        losing  = 0

    logger.info(
        f"[Alpaca] 당일({today_et}) 체결: 총 {total_fills}건 "
        f"(매수 {len(buy_fills)} / 매도 {sell_count}), "
        f"손익 ${today_pnl:+,.2f}"
    )

    return {
        "trade_date": today_et,
        "total_trades": total_fills,
        "sell_trades": sell_count,
        "realized_pnl": today_pnl,
        "winning_trades": winning,
        "losing_trades": losing,
        "source": "alpaca",
    }


# ── DB 조회 ──────────────────────────────────────────────────


class ReportDatabase:
    """리포트 전용 DB 조회 (READ-ONLY 용도)"""

    def __init__(self):
        self._pool: Optional[pooling.MySQLConnectionPool] = None

    def connect(self) -> bool:
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="notification_pool",
                pool_size=3,
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE,
                charset="utf8mb4",
                autocommit=True,
            )
            logger.info(f"✓ 리포트 DB 연결: {config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}")
            return True
        except Exception as e:
            logger.error(f"✗ DB 연결 실패: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    @contextmanager
    def get_cursor(self):
        if self._pool is None:
            raise RuntimeError("DB 미연결 - report_db.connect() 필요")
        conn = self._pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            yield cursor
        finally:
            cursor.close()
            conn.close()

    def get_today_stats(self) -> Dict[str, Any]:
        """DB에서 오늘 거래 통계 조회"""
        today_et = _today_et()

        # SELL/STOP_LOSS/TAKE_PROFIT 기준 집계 (BUY 제외)
        sql_sell_count = """
            SELECT COUNT(*) AS cnt
            FROM trading_logs
            WHERE DATE(log_time) = CURDATE()
              AND action IN ('SELL', 'STOP_LOSS', 'TAKE_PROFIT')
        """
        sql_total_count = """
            SELECT COUNT(*) AS cnt
            FROM trading_logs
            WHERE DATE(log_time) = CURDATE()
        """
        sql_pnl = """
            SELECT COALESCE(SUM(pnl), 0) AS total_pnl
            FROM trading_logs
            WHERE DATE(log_time) = CURDATE()
              AND action IN ('SELL', 'STOP_LOSS', 'TAKE_PROFIT')
        """
        sql_win_loss = """
            SELECT
                COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) AS winning,
                COALESCE(SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END), 0) AS losing
            FROM trading_logs
            WHERE DATE(log_time) = CURDATE()
              AND action IN ('SELL', 'STOP_LOSS', 'TAKE_PROFIT')
              AND pnl IS NOT NULL
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql_total_count)
            total_row = cursor.fetchone()

            cursor.execute(sql_sell_count)
            sell_row = cursor.fetchone()

            cursor.execute(sql_pnl)
            pnl_row = cursor.fetchone()

            cursor.execute(sql_win_loss)
            wl_row = cursor.fetchone()

        total = int(total_row["cnt"] or 0) if total_row else 0
        sells = int(sell_row["cnt"] or 0) if sell_row else 0

        logger.info(
            f"[DB] 당일({today_et}) 전체 로그 {total}건, "
            f"매도 {sells}건"
        )

        return {
            "trade_date": today_et,
            "total_trades": total,
            "sell_trades": sells,
            "realized_pnl": float(pnl_row["total_pnl"] or 0) if pnl_row else 0.0,
            "winning_trades": int(wl_row["winning"] or 0) if wl_row else 0,
            "losing_trades": int(wl_row["losing"] or 0) if wl_row else 0,
            "source": "db",
        }

    def get_weekly_summary(self) -> List[Dict[str, Any]]:
        """최근 7거래일 daily_summary"""
        sql = """
            SELECT trade_date, total_trades, winning_trades, losing_trades,
                   realized_pnl, ending_equity
            FROM daily_summary
            ORDER BY trade_date DESC
            LIMIT 7
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

        result = []
        for row in rows:
            row = dict(row)
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
            result.append(row)
        return result

    def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 거래 내역"""
        sql = """
            SELECT symbol, action, quantity, price, pnl, log_time
            FROM trading_logs
            ORDER BY log_time DESC
            LIMIT %s
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()

        result = []
        for row in rows:
            row = dict(row)
            for k, v in row.items():
                if isinstance(v, (datetime, date)):
                    row[k] = v.isoformat()
            result.append(row)
        return result


# 전역 인스턴스
report_db = ReportDatabase()


class ReportBuilder:
    """리포트 빌더 - Alpaca API 우선, DB 폴백"""

    def __init__(self, db: ReportDatabase):
        self.db = db

    def build_daily_report(self, ending_equity: float = 0.0) -> Dict[str, Any]:
        """
        일일 리포트 데이터 생성.
        1) Alpaca API로 당일 체결 조회 (가장 정확)
        2) DB 조회 (Alpaca 키 없거나 실패 시)
        3) 둘 다 실패 시 0으로 채운 기본값 반환
        """
        stats: Optional[Dict[str, Any]] = None

        # 1) Alpaca 우선
        try:
            stats = get_today_stats_from_alpaca()
        except Exception as e:
            logger.warning(f"Alpaca 통계 조회 예외: {e}")

        # 2) DB 폴백
        if stats is None and self.db.is_connected:
            try:
                stats = self.db.get_today_stats()
            except Exception as e:
                logger.warning(f"DB 통계 조회 예외: {e}")

        # 3) 기본값
        if stats is None:
            logger.warning("통계 조회 실패 - 기본값 사용")
            stats = {
                "trade_date": _today_et(),
                "total_trades": 0,
                "sell_trades": 0,
                "realized_pnl": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "source": "none",
            }

        stats["ending_equity"] = ending_equity
        return stats

    def build_weekly_report(self) -> List[Dict[str, Any]]:
        """주간 리포트 데이터 생성 (DB에서)"""
        if not self.db.is_connected:
            logger.warning("DB 미연결 - 주간 리포트 데이터 없음")
            return []
        try:
            return self.db.get_weekly_summary()
        except Exception as e:
            logger.warning(f"주간 리포트 조회 실패: {e}")
            return []


# 전역 인스턴스
report_builder = ReportBuilder(report_db)
