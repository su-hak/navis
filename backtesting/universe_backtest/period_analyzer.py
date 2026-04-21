"""
NAVIS Universe Backtest — Phase 4: 기간별 성과 분석

월별·분기별·연도별 수익률 테이블과
시장 국면(Bull/Bear/VIX) 비교를 제공한다.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PeriodAnalyzer:
    """
    백테스트 결과(거래 내역 + 자본 곡선)를 받아
    다양한 기간 단위로 성과를 분석한다.
    """

    def __init__(self, trade_records: List[dict], equity_curve: List[Tuple[date, float]]):
        """
        Args:
            trade_records:  [{'entry_dt', 'exit_dt', 'symbol', 'pnl', 'pnl_pct',
                               'signal_type', 'entry_price', 'exit_price'}, ...]
            equity_curve:   [(date, capital), ...]
        """
        self.trades_df = pd.DataFrame(trade_records) if trade_records else pd.DataFrame()
        self.equity_df = pd.DataFrame(equity_curve, columns=["date", "capital"])
        if len(self.equity_df) > 0:
            self.equity_df["date"] = pd.to_datetime(self.equity_df["date"], format="mixed")
            self.equity_df.set_index("date", inplace=True)

    # ── 월별 수익률 ───────────────────────────────────────────────────────

    def monthly_returns(self) -> pd.DataFrame:
        """
        월별 수익률 테이블 반환.

            연도  |  1월  |  2월  | ... | 12월 | 연간
            2021  | +3.2% | -1.1% | ... | +2.3%| +18.4%
        """
        if self.trades_df.empty:
            return pd.DataFrame()

        df = self.trades_df.copy()
        df["exit_dt"] = pd.to_datetime(df["exit_dt"], format="mixed", utc=True)
        df["year"]    = df["exit_dt"].dt.year
        df["month"]   = df["exit_dt"].dt.month

        # 월별 PnL 합계
        monthly_pnl = df.groupby(["year", "month"])["pnl"].sum().reset_index()

        # 피벗 테이블
        pivot = monthly_pnl.pivot(index="year", columns="month", values="pnl")
        pivot.columns = [
            "Jan","Feb","Mar","Apr","May","Jun",
            "Jul","Aug","Sep","Oct","Nov","Dec"
        ][:len(pivot.columns)]

        # 연간 합계 추가
        pivot["Annual"] = pivot.sum(axis=1)
        return pivot.round(2)

    def monthly_return_pct(self, initial_capital: float = 1_000_000) -> pd.DataFrame:
        """월별 수익률 (%) 테이블."""
        raw = self.monthly_returns()
        if raw.empty:
            return raw
        return (raw / initial_capital * 100).round(2)

    # ── 분기별 수익률 ─────────────────────────────────────────────────────

    def quarterly_returns(self, initial_capital: float = 1_000_000) -> pd.DataFrame:
        """분기별 수익률 (%) 테이블."""
        if self.trades_df.empty:
            return pd.DataFrame()

        df = self.trades_df.copy()
        df["exit_dt"]  = pd.to_datetime(df["exit_dt"], format="mixed", utc=True)
        df["year"]     = df["exit_dt"].dt.year
        df["quarter"]  = df["exit_dt"].dt.quarter

        pnl_q = df.groupby(["year", "quarter"])["pnl"].sum().reset_index()
        pnl_q["pnl_pct"] = pnl_q["pnl"] / initial_capital * 100

        pivot = pnl_q.pivot(index="year", columns="quarter", values="pnl_pct")
        pivot.columns = ["Q1","Q2","Q3","Q4"][:len(pivot.columns)]
        pivot["Annual"] = pivot.sum(axis=1)
        return pivot.round(2)

    # ── 연도별 요약 ───────────────────────────────────────────────────────

    def annual_summary(self, initial_capital: float = 1_000_000) -> pd.DataFrame:
        """
        연도별 핵심 성과 요약.

        반환 컬럼: year, return_pct, trades, win_rate, sharpe, max_drawdown, profit_factor
        """
        if self.trades_df.empty:
            return pd.DataFrame()

        df = self.trades_df.copy()
        df["exit_dt"] = pd.to_datetime(df["exit_dt"], format="mixed", utc=True)
        df["year"]    = df["exit_dt"].dt.year

        rows = []
        for yr, grp in df.groupby("year"):
            pnl_list  = grp["pnl"].tolist()
            wins      = [p for p in pnl_list if p > 0]
            losses    = [p for p in pnl_list if p <= 0]
            total_pnl = sum(pnl_list)
            win_rate  = len(wins) / len(pnl_list) * 100 if pnl_list else 0
            pf        = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float("inf")

            # Sharpe (일별 수익 기준)
            daily_pnl_series = grp.groupby(df["exit_dt"].dt.date)["pnl"].sum()
            if len(daily_pnl_series) > 1:
                mean_d  = daily_pnl_series.mean()
                std_d   = daily_pnl_series.std()
                sharpe  = (mean_d / std_d * np.sqrt(252)) if std_d > 0 else 0.0
            else:
                sharpe = 0.0

            # MDD (자본 곡선에서 해당 연도 구간)
            yr_equity = self.equity_df[self.equity_df.index.year == yr]["capital"] if len(self.equity_df) > 0 else pd.Series()
            if len(yr_equity) > 1:
                roll_max = yr_equity.cummax()
                drawdown = (yr_equity - roll_max) / roll_max * 100
                mdd = abs(drawdown.min())
            else:
                mdd = 0.0

            rows.append({
                "year":           yr,
                "return_pct":     round(total_pnl / initial_capital * 100, 2),
                "trades":         len(pnl_list),
                "win_rate":       round(win_rate, 1),
                "sharpe":         round(sharpe, 3),
                "max_drawdown":   round(mdd, 2),
                "profit_factor":  round(pf, 2) if pf != float("inf") else 999.0,
            })

        return pd.DataFrame(rows).set_index("year")

    # ── 시장 국면별 성과 ──────────────────────────────────────────────────

    def regime_analysis(
        self,
        spy_daily: pd.DataFrame,
        initial_capital: float = 1_000_000,
    ) -> pd.DataFrame:
        """
        시장 국면(Bull/Bear/High-VIX)별 성과 비교.

        Args:
            spy_daily: SPY 일봉 DataFrame (date index, close 컬럼)
        """
        if self.trades_df.empty or spy_daily is None or len(spy_daily) == 0:
            return pd.DataFrame()

        # SPY SMA200 계산
        spy = spy_daily[["close"]].copy()
        spy["sma200"] = spy["close"].rolling(200).mean()
        spy["regime"] = "neutral"
        spy.loc[spy["close"] > spy["sma200"], "regime"] = "bull"
        spy.loc[spy["close"] < spy["sma200"], "regime"] = "bear"

        df = self.trades_df.copy()
        df["exit_dt"] = pd.to_datetime(df["exit_dt"], format="mixed", utc=True)
        df["exit_date"] = df["exit_dt"].dt.date

        def get_regime(d):
            d_str = str(d)
            if d_str in spy.index.astype(str).tolist():
                idx = spy.index.astype(str).tolist().index(d_str)
                return spy.iloc[idx]["regime"]
            return "unknown"

        df["regime"] = df["exit_date"].apply(get_regime)

        rows = []
        for regime, grp in df.groupby("regime"):
            pnl_list = grp["pnl"].tolist()
            wins     = [p for p in pnl_list if p > 0]
            losses   = [p for p in pnl_list if p <= 0]
            win_rate = len(wins) / len(pnl_list) * 100 if pnl_list else 0
            pf       = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 999.0
            rows.append({
                "regime":        regime,
                "trades":        len(pnl_list),
                "win_rate":      round(win_rate, 1),
                "total_return":  round(sum(pnl_list) / initial_capital * 100, 2),
                "avg_return":    round(np.mean(grp["pnl_pct"].tolist()) * 100, 3)
                                 if "pnl_pct" in grp.columns else 0,
                "profit_factor": round(pf, 2),
            })

        return pd.DataFrame(rows).set_index("regime")

    # ── 종합 리포트 출력 ──────────────────────────────────────────────────

    def print_report(self, initial_capital: float = 1_000_000) -> None:
        """콘솔에 전체 성과 리포트를 출력한다."""
        print("\n" + "=" * 60)
        print("  NAVIS 유니버스 백테스트 성과 리포트")
        print("=" * 60)

        # 전체 요약
        if not self.trades_df.empty:
            total_pnl  = self.trades_df["pnl"].sum()
            total_ret  = total_pnl / initial_capital * 100
            total_tr   = len(self.trades_df)
            wins       = (self.trades_df["pnl"] > 0).sum()
            win_rate   = wins / total_tr * 100
            print(f"\n[전체 기간]")
            print(f"  총 수익률  : {total_ret:+.2f}%  (${total_pnl:+,.0f})")
            print(f"  총 거래수  : {total_tr}회")
            print(f"  승률       : {win_rate:.1f}%  ({wins}승/{total_tr - wins}패)")

        # 연도별 요약
        annual = self.annual_summary(initial_capital)
        if not annual.empty:
            print(f"\n[연도별 성과]")
            print(annual.to_string())

        # 월별 수익률
        monthly = self.monthly_return_pct(initial_capital)
        if not monthly.empty:
            print(f"\n[월별 수익률 (%)]")
            print(monthly.to_string())

        # 분기별
        quarterly = self.quarterly_returns(initial_capital)
        if not quarterly.empty:
            print(f"\n[분기별 수익률 (%)]")
            print(quarterly.to_string())

        print("\n" + "=" * 60)
