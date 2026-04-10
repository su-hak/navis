"""
알림 / 리포트 팀 설정
백엔드와 독립적으로 환경변수로 구성
"""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


class NotificationConfig:
    """알림 서비스 설정"""

    # ── 서버 ──────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("NOTIFICATION_PORT", "8005"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── 텔레그램 ──────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # ── MySQL ─────────────────────────────────────────────────
    _db_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")

    if _db_url and _db_url.startswith("mysql://"):
        _parsed = urlparse(_db_url)
        MYSQL_HOST: str = _parsed.hostname or "localhost"
        MYSQL_PORT: int = _parsed.port or 3306
        MYSQL_USER: str = _parsed.username or "root"
        MYSQL_PASSWORD: str = _parsed.password or ""
        MYSQL_DATABASE: str = (_parsed.path[1:] if _parsed.path else "trading_db")
    else:
        MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
        MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
        MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
        MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
        MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "trading_db")

    # ── 백엔드 URL (daily report 트리거용) ────────────────────
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

    # ── Alpaca API (포지션/계좌 직접 조회용) ──────────────────
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    # ── 알림 스케줄 ───────────────────────────────────────────
    # 장중 포지션 현황 알림 주기 (분, 0이면 비활성)
    PORTFOLIO_STATUS_INTERVAL_MIN: int = int(
        os.getenv("PORTFOLIO_STATUS_INTERVAL_MIN", "60")
    )
    # 주간 리포트 발송 요일 (0=월 ~ 4=금)
    WEEKLY_REPORT_DOW: str = os.getenv("WEEKLY_REPORT_DOW", "fri")

    @classmethod
    def validate(cls) -> bool:
        errors = []
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN 미설정")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID 미설정")
        for err in errors:
            print(f"[NotificationConfig Warning] {err}")
        return len(errors) == 0


config = NotificationConfig()
