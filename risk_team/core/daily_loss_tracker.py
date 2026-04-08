"""
일일 손실 추적 모듈
기획서: 하루 최대 손실 제한 (-5%)
"""
import logging
import json
from typing import Optional, Dict
from datetime import datetime, date
from pathlib import Path

from .risk_models import DailyStats

logger = logging.getLogger(__name__)


class DailyLossTracker:
    """
    일일 손실 추적기

    역할:
    - 하루 실현/미실현 손익 누적
    - 최대 손실 한도(-5%) 초과 시 거래 중단
    - 자정(또는 장 시작)에 자동 리셋
    - JSON 파일로 통계 영속화
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 0.05,
        storage_path: Optional[str] = None,
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.storage_path = storage_path
        self._stats: Dict[str, DailyStats] = {}

        if storage_path:
            Path(storage_path).mkdir(parents=True, exist_ok=True)
            self._load_stats()

        logger.info(f"DailyLossTracker 초기화 - 최대 손실: -{max_daily_loss_pct*100:.0f}%")

    # ============ 초기화 ============

    def initialize_day(self, starting_equity: float) -> DailyStats:
        """
        새 거래일 초기화

        Args:
            starting_equity: 장 시작 시 총 자산

        Returns:
            오늘의 DailyStats
        """
        today = self._today_str()

        if today in self._stats:
            logger.info(f"오늘({today}) 이미 초기화됨 - 기존 데이터 유지")
            return self._stats[today]

        stats = DailyStats(
            date=today,
            starting_equity=starting_equity,
            current_equity=starting_equity,
        )
        self._stats[today] = stats
        self._save_stats(stats)

        logger.info(
            f"거래일 초기화 - {today}, "
            f"시작 자산: ${starting_equity:,.2f}, "
            f"손실 한도: -${starting_equity * self.max_daily_loss_pct:,.2f}"
        )
        return stats

    # ============ 손익 기록 ============

    def record_realized_trade(self, pnl: float) -> None:
        """
        실현 손익 기록 (주문 체결 후 호출)

        Args:
            pnl: 실현 손익 (양수=수익, 음수=손실)
        """
        stats = self._get_or_create_today()
        stats.realized_pnl += pnl
        stats.trade_count += 1

        if pnl > 0:
            stats.win_count += 1
        elif pnl < 0:
            stats.loss_count += 1

        self._update_totals(stats)

        logger.info(
            f"실현 손익 기록 - ${pnl:+,.2f} "
            f"(누적: ${stats.realized_pnl:+,.2f}, {stats.total_pnl_pct:+.2f}%)"
        )

        # 한도 초과 체크
        if self.is_limit_reached():
            logger.warning(
                f"일일 손실 한도 초과! "
                f"현재: {stats.total_pnl_pct:.2f}%, "
                f"한도: -{self.max_daily_loss_pct*100:.0f}%"
            )
            stats.is_trading_halted = True

        self._save_stats(stats)

    def update_unrealized_pnl(self, unrealized_pnl: float) -> None:
        """
        미실현 손익 업데이트 (포지션 현황 갱신 시 호출)

        Args:
            unrealized_pnl: 전체 포지션의 미실현 손익 합계
        """
        stats = self._get_or_create_today()
        stats.unrealized_pnl = unrealized_pnl
        self._update_totals(stats)
        self._save_stats(stats)

    # ============ 조회 ============

    def is_limit_reached(self) -> bool:
        """
        일일 손실 한도 초과 여부

        Returns:
            True면 거래 중단해야 함
        """
        stats = self._get_today_stats()
        if not stats:
            return False

        # 실현 손실만 기준 (미실현은 변동 가능하므로 참고용)
        realized_loss_pct = abs(stats.realized_pnl) / stats.starting_equity
        is_loss = stats.realized_pnl < 0

        return is_loss and realized_loss_pct >= self.max_daily_loss_pct

    def get_daily_loss_pct(self) -> float:
        """
        오늘 실현 손익률 반환 (음수면 손실)

        Returns:
            손익률 (예: -0.03 = -3%)
        """
        stats = self._get_today_stats()
        if not stats or stats.starting_equity == 0:
            return 0.0

        return stats.realized_pnl / stats.starting_equity

    def get_remaining_loss_budget(self) -> float:
        """
        남은 손실 허용 금액

        Returns:
            추가로 손실 가능한 금액 (양수)
        """
        stats = self._get_today_stats()
        if not stats:
            return 0.0

        max_loss = stats.starting_equity * self.max_daily_loss_pct
        used_loss = max(0.0, -stats.realized_pnl)  # 손실만 (음수 → 양수)
        remaining = max(0.0, max_loss - used_loss)

        return remaining

    def get_today_stats(self) -> Optional[DailyStats]:
        """오늘 통계 반환"""
        return self._get_today_stats()

    def resume_trading(self) -> None:
        """
        거래 재개 (수동 오버라이드 - 관리자 전용)
        """
        stats = self._get_today_stats()
        if stats:
            stats.is_trading_halted = False
            self._save_stats(stats)
            logger.warning("거래 재개 (수동 오버라이드)")

    # ============ 내부 헬퍼 ============

    def _today_str(self) -> str:
        return date.today().strftime("%Y-%m-%d")

    def _get_today_stats(self) -> Optional[DailyStats]:
        return self._stats.get(self._today_str())

    def _get_or_create_today(self) -> DailyStats:
        today = self._today_str()
        if today not in self._stats:
            # 자산 정보 없이 임시 생성 (initialize_day를 먼저 호출해야 함)
            logger.warning("initialize_day() 없이 거래 기록됨 - 임시 통계 생성")
            self._stats[today] = DailyStats(
                date=today,
                starting_equity=0.0,
                current_equity=0.0,
            )
        return self._stats[today]

    def _update_totals(self, stats: DailyStats) -> None:
        stats.total_pnl = stats.realized_pnl + stats.unrealized_pnl
        if stats.starting_equity > 0:
            stats.total_pnl_pct = (stats.total_pnl / stats.starting_equity) * 100
            stats.current_equity = stats.starting_equity + stats.total_pnl

    def _save_stats(self, stats: DailyStats) -> None:
        if not self.storage_path:
            return
        try:
            file_path = Path(self.storage_path) / f"daily_{stats.date}.json"
            with open(file_path, "w") as f:
                json.dump(stats.dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"일일 통계 저장 실패: {e}")

    def _load_stats(self) -> None:
        if not self.storage_path:
            return
        try:
            storage_dir = Path(self.storage_path)
            for file_path in storage_dir.glob("daily_*.json"):
                with open(file_path, "r") as f:
                    data = json.load(f)
                    stats = DailyStats(**data)
                    self._stats[stats.date] = stats
            logger.info(f"{len(self._stats)}일치 통계 로드 완료")
        except Exception as e:
            logger.error(f"일일 통계 로드 실패: {e}")
