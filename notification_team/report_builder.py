"""
알림 / 리포트 팀 - 리포트 빌더
우선순위: Alpaca API → DB 순으로 당일 거래 통계 조회
"""
import logging
from collections import defaultdict
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
    Alpaca account 에서 오늘 미실현+실현 손익 합산.
    unrealized_pl (현재 보유 포지션 미실현) +
    오늘 realized_pl 변화분(= 현재 realized_pl - 전날 종가 기준 realized_pl)
    → 단순하게 account.equity - account.last_equity 로 대체
    실패 시 0.0 반환.
    """
    try:
        resp = client.get(
            f"{config.ALPACA_BASE_URL}/v2/account",
            headers=_alpaca_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        # equity: 현재 총 자산
        # last_equity: 전날 종가 기준 총 자산
        equity = float(data.get("equity") or 0)
        last_equity = float(data.get("last_equity") or 0)
        if last_equity > 0:
            return equity - last_equity
    except Exception as e:
        logger.warning(f"Alpaca account 손익 조회 실패: {e}")
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

    # Alpaca FILL API는 partial fill(부분 체결)을 별도 이벤트로 기록하므로
    # order_id 기준으로 중복 제거하여 실제 주문 수 산출
    sell_order_ids = {a.get("order_id") for a in sell_fills if a.get("order_id")}
    sell_count = len(sell_order_ids) if sell_order_ids else len(sell_fills)

    # 개별 거래 pnl을 Alpaca FILL API에서 제공하지 않으므로
    # 승/패를 정확히 계산 불가 → 0으로 설정 (DB 폴백에서 정확한 값 사용 권장)
    winning = 0
    losing  = sell_count  # 일단 모두 패로 표시 → DB 우선 사용 시 이 코드는 폴백으로만 동작

    logger.info(
        f"[Alpaca] 당일({today_et}) 체결: 총 {total_fills}건 "
        f"(매수 {len(buy_fills)} / 매도 {sell_count}건 주문 기준), "
        f"손익 ${today_pnl:+,.2f} (미실현 포함 추정치)"
    )
    logger.warning(
        "[Alpaca] 승/패 카운트 미지원 — DB 없이 Alpaca만 사용 중. "
        "정확한 승/패는 DB 연결 후 확인 필요"
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


# ── TP 수준별 도달 가능 승률 분석 ─────────────────────────────

_TP_LEVELS = [0.02, 0.04, 0.06, 0.10, 0.12]
_ALPACA_DATA_URL = "https://data.alpaca.markets"


def _fetch_fills_for_date(date_str: str) -> list:
    """해당 날짜의 FILL 체결 내역 조회 (UTC 기준 필터링)"""
    after_ts = f"{date_str}T00:00:00Z"
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
        resp = client.get(
            f"{config.ALPACA_BASE_URL}/v2/account/activities/FILL",
            headers=_alpaca_headers(),
            params={"after": after_ts, "direction": "asc", "page_size": 100},
        )
        resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    until = f"{next_day}T00:00:00Z"
    return [f for f in data if f.get("transaction_time", "") < until]


def _fetch_bars_1min(symbol: str, date_str: str) -> list:
    """1분봉 조회 (장 시간 기준 UTC 13:30~20:00, EDT 기준)"""
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            resp = client.get(
                f"{_ALPACA_DATA_URL}/v2/stocks/{symbol}/bars",
                headers=_alpaca_headers(),
                params={
                    "timeframe": "1Min",
                    "start": f"{date_str}T13:30:00Z",
                    "end":   f"{date_str}T20:00:00Z",
                    "limit": 400,
                    "feed": "iex",
                },
            )
            resp.raise_for_status()
        return resp.json().get("bars", [])
    except Exception as e:
        logger.warning(f"[TP분석] {symbol} 분봉 조회 실패: {e}")
        return []


def _weighted_avg_fill(order_fills: list) -> tuple:
    """partial fill 목록에서 가중평균 체결가 및 최종 체결 시각 반환"""
    total_qty = sum(int(f["qty"]) for f in order_fills)
    avg_price = sum(float(f["price"]) * int(f["qty"]) for f in order_fills) / total_qty
    last_time = max(f["transaction_time"] for f in order_fills)
    return avg_price, last_time


def get_tp_analysis_from_alpaca(date_str: str) -> Optional[List[Dict]]:
    """
    당일 체결 내역으로 익절 수준별 도달 가능 승률 분석.

    Returns:
        [{"tp_pct": 2, "reachable": n, "total": t, "win_rate": 14.3}, ...]
        실패 시 None 반환.
    """
    if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
        logger.warning("[TP분석] Alpaca API 키 미설정")
        return None

    try:
        fills = _fetch_fills_for_date(date_str)
    except Exception as e:
        logger.warning(f"[TP분석] FILL 조회 실패: {e}")
        return None

    if not fills:
        logger.info(f"[TP분석] {date_str} 체결 내역 없음")
        return None

    # order_id 기준 partial fill 그룹핑
    order_fills: dict = defaultdict(list)
    for f in fills:
        order_fills[f["order_id"]].append(f)

    # symbol별 매수/매도 주문 분류
    buy_orders_by_sym:  dict = defaultdict(list)
    sell_orders_by_sym: dict = defaultdict(list)
    for order_list in order_fills.values():
        sym  = order_list[0]["symbol"]
        side = order_list[0]["side"]
        order_list.sort(key=lambda x: x["transaction_time"])
        if side == "buy":
            buy_orders_by_sym[sym].append(order_list)
        elif side == "sell":
            sell_orders_by_sym[sym].append(order_list)

    # FIFO 매수-매도 쌍 매칭
    pairs = []
    symbols_needed: set = set()
    for symbol, buy_list in buy_orders_by_sym.items():
        sell_list = sell_orders_by_sym.get(symbol, [])
        for buy_order, sell_order in zip(buy_list, sell_list):
            pairs.append((symbol, buy_order, sell_order))
            symbols_needed.add(symbol)

    if not pairs:
        logger.info(f"[TP분석] {date_str} 매수-매도 쌍 없음 (당일 미청산 포지션일 수 있음)")
        return None

    # 분봉 수집
    bars_cache: dict = {}
    for sym in symbols_needed:
        bars_cache[sym] = _fetch_bars_1min(sym, date_str)

    # 각 쌍에 대해 TP 도달 여부 집계
    tp_counts = {int(tp * 100): 0 for tp in _TP_LEVELS}
    total = 0

    for symbol, buy_order, sell_order in pairs:
        buy_price, buy_time_end   = _weighted_avg_fill(buy_order)
        _,         sell_time_end  = _weighted_avg_fill(sell_order)

        bars = bars_cache.get(symbol, [])
        window = [b for b in bars if buy_time_end <= b["t"] <= sell_time_end]

        for tp in _TP_LEVELS:
            target = buy_price * (1 + tp)
            if any(float(b["h"]) >= target for b in window):
                tp_counts[int(tp * 100)] += 1

        total += 1

    result = []
    for tp in _TP_LEVELS:
        tp_pct = int(tp * 100)
        cnt = tp_counts[tp_pct]
        win_rate = round(cnt / total * 100, 1) if total > 0 else 0.0
        result.append({
            "tp_pct":    tp_pct,
            "reachable": cnt,
            "total":     total,
            "win_rate":  win_rate,
        })

    logger.info(
        f"[TP분석] {date_str} {total}쌍 완료 | " +
        " / ".join(f"TP{r['tp_pct']}%={r['win_rate']:.0f}%" for r in result)
    )
    return result


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

    def save_tp_analysis(self, date_str: str, tp_results: List[Dict]) -> bool:
        """익절 수준별 분석 결과를 tp_analysis 테이블에 저장 (UPSERT)"""
        sql = """
            INSERT INTO tp_analysis
                (trade_date, tp_pct, reachable_count, total_sell_count, win_rate)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                reachable_count  = VALUES(reachable_count),
                total_sell_count = VALUES(total_sell_count),
                win_rate         = VALUES(win_rate)
        """
        try:
            with self.get_cursor() as cursor:
                for r in tp_results:
                    cursor.execute(sql, (
                        date_str,
                        r["tp_pct"],
                        r["reachable"],
                        r["total"],
                        r["win_rate"],
                    ))
            logger.info(f"[DB] TP 분석 결과 저장 완료: {date_str} ({len(tp_results)}건)")
            return True
        except Exception as e:
            logger.warning(f"[DB] TP 분석 결과 저장 실패: {e}")
            return False

    def get_tp_analysis_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """최근 N일간 TP 분석 이력 조회"""
        sql = """
            SELECT trade_date, tp_pct, reachable_count, total_sell_count, win_rate
            FROM tp_analysis
            ORDER BY trade_date DESC, tp_pct ASC
            LIMIT %s
        """
        with self.get_cursor() as cursor:
            cursor.execute(sql, (days * len(_TP_LEVELS),))
            rows = cursor.fetchall()
        result = []
        for row in rows:
            row = dict(row)
            if isinstance(row.get("trade_date"), date):
                row["trade_date"] = row["trade_date"].isoformat()
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
    """리포트 빌더 - DB 우선, Alpaca API 폴백"""

    def __init__(self, db: ReportDatabase):
        self.db = db

    def build_daily_report(self, ending_equity: float = 0.0) -> Dict[str, Any]:
        """
        일일 리포트 데이터 생성.
        1) DB 조회 우선 (거래별 실제 pnl 기반 → 승/패 정확)
        2) Alpaca API 폴백 (DB 없거나 실패 시)
           ※ Alpaca FILL 기반 승/패는 equity 변동 부호만 사용하므로 부정확
              (미실현 손익 포함 + partial fill 중복 카운트 문제)
        3) 둘 다 실패 시 0으로 채운 기본값 반환
        """
        stats: Optional[Dict[str, Any]] = None

        # 1) DB 우선 (per-trade pnl 기반으로 승/패 정확)
        if self.db.is_connected:
            try:
                stats = self.db.get_today_stats()
            except Exception as e:
                logger.warning(f"DB 통계 조회 예외: {e}")

        # 2) Alpaca 폴백 (DB 없거나 실패 시)
        if stats is None:
            try:
                stats = get_today_stats_from_alpaca()
                if stats:
                    logger.warning(
                        "Alpaca 기반 집계 사용 중 — equity 부호로 승/패 판정하므로 부정확할 수 있음"
                    )
            except Exception as e:
                logger.warning(f"Alpaca 통계 조회 예외: {e}")

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
