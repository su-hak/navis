"""
NAVIS Universe Backtest - 수익률 극대화 분석

백테스트 결과를 바탕으로 수익률을 높이기 위한
파라미터·전략 분석 및 개선 방향을 제시한다.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ReturnMaximizer:
    """
    백테스트 거래 내역을 분석하여 수익률 극대화 방향을 도출한다.
    """

    def __init__(self, trade_records: List[dict]):
        self.df = pd.DataFrame(trade_records) if trade_records else pd.DataFrame()

    def analyze_all(self, initial_capital: float = 1_000_000) -> None:
        """전체 극대화 분석 출력."""
        if self.df.empty:
            print("거래 내역 없음")
            return

        print("\n" + "=" * 60)
        print("  수익률 극대화 분석 리포트")
        print("=" * 60)

        self.by_signal_type()
        self.by_symbol()
        self.by_entry_time()
        self.by_gap_size()
        self.improvement_suggestions(initial_capital)

    # ── 청산 유형별 분석 ──────────────────────────────────────────────────

    def by_signal_type(self) -> pd.DataFrame:
        """
        청산 유형별 성과 (STOP_LOSS / TRAILING_STOP / PARTIAL_TP / TAKE_PROFIT / EOD
                         / TIME_STOP / NOON_EXIT).
        """
        if self.df.empty:
            return pd.DataFrame()

        grp = self.df.groupby("signal_type").agg(
            count=("pnl", "count"),
            win_rate=("pnl", lambda x: (x > 0).mean() * 100),
            avg_pnl_pct=("pnl_pct", lambda x: x.mean() * 100),
            total_pnl=("pnl", "sum"),
        ).round(3)

        print("\n[청산 유형별 성과]")
        print(grp.to_string())
        return grp

    # ── 종목별 성과 ────────────────────────────────────────────────────────

    def by_symbol(self, top_n: int = 15) -> pd.DataFrame:
        """종목별 성과 (상위 N개, PnL 합계 기준)."""
        if self.df.empty:
            return pd.DataFrame()

        grp = self.df.groupby("symbol").agg(
            trades=("pnl", "count"),
            win_rate=("pnl", lambda x: (x > 0).mean() * 100),
            total_pnl=("pnl", "sum"),
            avg_pnl_pct=("pnl_pct", lambda x: x.mean() * 100),
        ).sort_values("total_pnl", ascending=False).head(top_n).round(3)

        print(f"\n[종목별 성과 Top {top_n}]")
        print(grp.to_string())
        return grp

    # ── 진입 시간대별 분석 ────────────────────────────────────────────────

    def by_entry_time(self) -> pd.DataFrame:
        """
        장 시작 후 진입 시간대별 성과.
        오전 첫 30분 vs 오전 30~60분 vs 오후
        """
        if self.df.empty or "entry_dt" not in self.df.columns:
            return pd.DataFrame()

        df = self.df.copy()
        df["entry_dt_parsed"] = pd.to_datetime(df["entry_dt"], errors="coerce", utc=True)
        df = df.dropna(subset=["entry_dt_parsed"])

        def time_bucket(ts):
            try:
                et = ts.tz_convert("America/New_York")
                h, m = et.hour, et.minute
                minutes_since_open = (h - 9) * 60 + m - 30
                if minutes_since_open < 0:
                    return "pre-market"
                elif minutes_since_open < 30:
                    return "0~30min (9:30-10:00)"
                elif minutes_since_open < 60:
                    return "30~60min (10:00-10:30)"
                elif minutes_since_open < 120:
                    return "60~120min (10:30-11:30)"
                else:
                    return "after 11:30"
            except Exception:
                return "unknown"

        df["time_bucket"] = df["entry_dt_parsed"].apply(time_bucket)

        grp = df.groupby("time_bucket").agg(
            trades=("pnl", "count"),
            win_rate=("pnl", lambda x: (x > 0).mean() * 100),
            avg_pnl_pct=("pnl_pct", lambda x: x.mean() * 100),
            total_pnl=("pnl", "sum"),
        ).round(3)

        print("\n[진입 시간대별 성과]")
        print(grp.to_string())
        return grp

    # ── 갭 크기별 성과 ────────────────────────────────────────────────────

    def by_gap_size(self) -> pd.DataFrame:
        """갭 크기 구간별 성과 비교."""
        if self.df.empty or "pnl_pct" not in self.df.columns:
            return pd.DataFrame()

        # trade_records에 gap_pct가 있으면 사용, 없으면 생략
        if "gap_pct" not in self.df.columns:
            print("\n[갭 크기별 성과] -- gap_pct 필드 없음, 생략")
            return pd.DataFrame()

        df = self.df.copy()
        bins   = [0, 2, 4, 6, 10, 100]
        labels = ["0~2%", "2~4%", "4~6%", "6~10%", "10%+"]
        df["gap_bucket"] = pd.cut(df["gap_pct"].abs(), bins=bins, labels=labels)

        grp = df.groupby("gap_bucket").agg(
            trades=("pnl", "count"),
            win_rate=("pnl", lambda x: (x > 0).mean() * 100),
            avg_pnl_pct=("pnl_pct", lambda x: x.mean() * 100),
            total_pnl=("pnl", "sum"),
        ).round(3)

        print("\n[갭 크기별 성과]")
        print(grp.to_string())
        return grp

    # ── 개선 방향 제시 ────────────────────────────────────────────────────

    def improvement_suggestions(self, initial_capital: float = 1_000_000) -> None:
        """
        분석 결과를 바탕으로 수익률 극대화 방향을 제시한다.
        """
        if self.df.empty:
            return

        total_pnl   = self.df["pnl"].sum()
        total_ret   = total_pnl / initial_capital * 100
        win_rate    = (self.df["pnl"] > 0).mean() * 100
        avg_win     = self.df.loc[self.df["pnl"] > 0, "pnl_pct"].mean() * 100 if (self.df["pnl"] > 0).any() else 0
        avg_loss    = self.df.loc[self.df["pnl"] <= 0, "pnl_pct"].mean() * 100 if (self.df["pnl"] <= 0).any() else 0
        rr_ratio    = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        print("\n" + "=" * 60)
        print("  수익률 극대화 방향 제시")
        print("=" * 60)
        print(f"  현재 총수익률  : {total_ret:+.2f}%")
        print(f"  현재 승률      : {win_rate:.1f}%")
        print(f"  현재 R:R 비율  : 1 : {rr_ratio:.2f}")
        print()

        suggestions = []

        # ── 승률 기반 제안 ────────────────────────────────────────────
        if win_rate < 45:
            suggestions.append((
                "진입 필터 강화",
                f"현재 승률 {win_rate:.1f}%는 낮습니다. "
                "갭 크기 최소 3% 이상 + VIX < 20 조건 추가를 권장합니다. "
                "진입 신호가 줄어들어도 품질이 올라갑니다."
            ))

        # ── R:R 기반 제안 ─────────────────────────────────────────────
        if rr_ratio < 2.0:
            suggestions.append((
                "Trailing Stop 조정",
                f"현재 R:R {rr_ratio:.2f}는 목표(2.5)에 미달합니다. "
                "Trailing Stop을 -2% → -1.5%로 좁히면 이익 보전이 빨라집니다."
            ))

        if rr_ratio > 3.0 and win_rate < 40:
            suggestions.append((
                "TP 앞당기기",
                f"R:R은 높지만 승률이 낮습니다({win_rate:.1f}%). "
                "Partial TP 비율을 50% → 70%로 늘려 확실한 이익을 먼저 취하세요."
            ))

        # ── 총 수익률 기반 제안 ───────────────────────────────────────
        if total_ret < 10:
            suggestions.append((
                "시장 국면 필터",
                "전체 수익률이 낮습니다. "
                "SPY > SMA200 (Bull 국면)일 때만 진입하도록 제한하면 "
                "Bear 시장에서의 손실을 줄일 수 있습니다."
            ))

        if total_ret < 5:
            suggestions.append((
                "종목 유니버스 개선",
                "갭 모멘텀이 강한 섹터(반도체·바이오·소형 테크)를 "
                "유니버스에 더 추가하면 진입 기회 및 수익성이 향상됩니다."
            ))

        # ── 공통 제안 ─────────────────────────────────────────────────
        suggestions.append((
            "스코어 임계값 최적화",
            "buy_score_threshold를 optimize_score_threshold()로 데이터 기반 최적화하면 "
            "불량 진입이 걸러져 승률과 PF가 개선됩니다."
        ))

        suggestions.append((
            "섹터별 성과 분석",
            "by_symbol() 결과에서 지속 손실 종목은 유니버스에서 제외하고, "
            "고성과 종목 비중을 높이는 섹터 집중 전략을 검토하세요."
        ))

        for i, (title, desc) in enumerate(suggestions, 1):
            print(f"  [{i}] {title}")
            print(f"      {desc}")
            print()

        print("=" * 60)
