"""
알림 / 리포트 팀 - 리포트 빌더
DB에서 데이터를 읽어 리포트 데이터 구조를 생성
"""
import logging
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import mysql.connector
from mysql.connector import pooling

from .config import config

logger = logging.getLogger(__name__)


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

    @contextmanager
    def get_cursor(self):
        conn = self._pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            yield cursor
        finally:
            cursor.close()
            conn.close()

    def get_today_stats(self) -> Dict[str, Any]:
        """오늘 거래 통계"""
        sql_count = "SELECT COUNT(*) AS cnt FROM trading_logs WHERE DATE(log_time) = CURDATE()"
        sql_pnl = """
            SELECT COALESCE(SUM(pnl), 0) AS total_pnl
            FROM trading_logs
            WHERE DATE(log_time) = CURDATE()
              AND action IN ('SELL', 'STOP_LOSS', 'TAKE_PROFIT')
        """
        sql_win_loss = """
            SELECT
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winning,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) AS losing
            FROM trading_logs
            WHERE DATE(log_time) = CURDATE()
              AND action IN ('SELL', 'STOP_LOSS', 'TAKE_PROFIT')
              AND pnl IS NOT NULL
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql_count)
            count_row = cursor.fetchone()
            cursor.execute(sql_pnl)
            pnl_row = cursor.fetchone()
            cursor.execute(sql_win_loss)
            wl_row = cursor.fetchone()

        return {
            "trade_date": datetime.now().strftime("%Y-%m-%d"),
            "total_trades": int(count_row["cnt"] or 0) if count_row else 0,
            "realized_pnl": float(pnl_row["total_pnl"] or 0) if pnl_row else 0.0,
            "winning_trades": int(wl_row["winning"] or 0) if wl_row else 0,
            "losing_trades": int(wl_row["losing"] or 0) if wl_row else 0,
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
    """리포트 빌더 - DB 데이터 + 포맷팅"""

    def __init__(self, db: ReportDatabase):
        self.db = db

    def build_daily_report(self, ending_equity: float = 0.0) -> Dict[str, Any]:
        """일일 리포트 데이터 생성"""
        stats = self.db.get_today_stats()
        stats["ending_equity"] = ending_equity
        return stats

    def build_weekly_report(self) -> List[Dict[str, Any]]:
        """주간 리포트 데이터 생성"""
        return self.db.get_weekly_summary()


# 전역 인스턴스
report_builder = ReportBuilder(report_db)
