"""
리스크 관리 팀 설정
환경변수로 모든 리스크 파라미터 조정 가능
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class RiskConfig:
    """리스크 관리 설정"""

    def __init__(self):
        # ── 손절/익절 ──────────────────────────────────────
        # 기획서: 손절 -2%, Risk:Reward 1:3 → 익절 +6%
        self.stop_loss_pct = float(os.getenv("RISK_STOP_LOSS_PCT", "0.02"))
        self.take_profit_pct = float(os.getenv("RISK_TAKE_PROFIT_PCT", "0.06"))

        # ── 포지션 사이징 ──────────────────────────────────
        # 기획서: 1회 투자금 총 자산의 5~20%
        self.min_position_pct = float(os.getenv("RISK_MIN_POSITION_PCT", "0.05"))
        self.max_position_pct = float(os.getenv("RISK_MAX_POSITION_PCT", "0.20"))

        # ── 일일 손실 한도 ─────────────────────────────────
        # 기획서: 하루 최대 손실 -5%
        self.max_daily_loss_pct = float(os.getenv("RISK_MAX_DAILY_LOSS_PCT", "0.05"))

        # ── 포트폴리오 한도 ────────────────────────────────
        # 기획서: 동시 보유 종목 제한
        self.max_positions = int(os.getenv("RISK_MAX_POSITIONS", "5"))
        self.max_exposure_pct = float(os.getenv("RISK_MAX_EXPOSURE_PCT", "0.80"))
        self.max_single_position_pct = float(os.getenv("RISK_MAX_SINGLE_POSITION_PCT", "0.25"))

        # ── 저장 경로 ──────────────────────────────────────
        self.storage_path: Optional[str] = os.getenv(
            "RISK_STORAGE_PATH", "logs/risk"
        )

        # ── 로깅 ───────────────────────────────────────────
        self.log_level = os.getenv("RISK_LOG_LEVEL", "INFO")
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # ── Execution Team 연동 ────────────────────────────
        self.execution_api_url = os.getenv(
            "EXECUTION_API_URL", "http://localhost:8001"
        )

    def validate(self) -> bool:
        """설정 유효성 검증"""
        import logging
        logger = logging.getLogger(__name__)
        ok = True

        if not (0 < self.stop_loss_pct < 1):
            logger.error(f"RISK_STOP_LOSS_PCT 범위 오류: {self.stop_loss_pct}")
            ok = False

        if not (0 < self.take_profit_pct < 1):
            logger.error(f"RISK_TAKE_PROFIT_PCT 범위 오류: {self.take_profit_pct}")
            ok = False

        if not (0 < self.max_daily_loss_pct < 1):
            logger.error(f"RISK_MAX_DAILY_LOSS_PCT 범위 오류: {self.max_daily_loss_pct}")
            ok = False

        if self.max_positions < 1:
            logger.error(f"RISK_MAX_POSITIONS는 1 이상이어야 합니다: {self.max_positions}")
            ok = False

        if self.take_profit_pct < self.stop_loss_pct:
            logger.warning(
                f"익절({self.take_profit_pct*100:.0f}%)이 손절({self.stop_loss_pct*100:.0f}%)보다 작음 "
                f"- Risk:Reward 비율 확인 필요"
            )

        return ok

    def summary(self) -> dict:
        """설정 요약 (로그/모니터링용)"""
        return {
            "stop_loss_pct": f"-{self.stop_loss_pct*100:.0f}%",
            "take_profit_pct": f"+{self.take_profit_pct*100:.0f}%",
            "risk_reward_ratio": f"1:{self.take_profit_pct / self.stop_loss_pct:.0f}",
            "min_position_pct": f"{self.min_position_pct*100:.0f}%",
            "max_position_pct": f"{self.max_position_pct*100:.0f}%",
            "max_daily_loss_pct": f"-{self.max_daily_loss_pct*100:.0f}%",
            "max_positions": self.max_positions,
            "max_exposure_pct": f"{self.max_exposure_pct*100:.0f}%",
        }


# 전역 설정 인스턴스
config = RiskConfig()
