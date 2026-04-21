"""
NAVIS 페어 트레이딩 백테스트 엔진 (P16)

전략 (NAVIS_STRATEGY_D_PAIRS_TRADING.md):
  - Z > +2.0: A 과대평가 → A Short + B Long
  - Z < -2.0: A 과소평가 → A Long  + B Short
  - 청산: |Z| < 0.5 (평균 회귀)
  - 손절: |Z| > 3.5 (공적분 붕괴 가능성)
  - 강제: 30거래일 초과 보유 시 청산

합격 기준:
  합격:       CAGR ≥ 15% AND Sharpe ≥ 1.2
  부분 합격:  CAGR ≥ 10% AND Sharpe ≥ 0.8
  실패:       위 조건 미달
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .spread_calculator import calc_spread_zscore

logger = logging.getLogger(__name__)


@dataclass
class PairsBacktestConfig:
    # 페어 리스트 (pair_selector 출력)
    pairs: List[dict] = field(default_factory=list)

    # Z-score 임계값
    entry_z:      float = 2.0   # 진입: |Z| > entry_z
    exit_z:       float = 0.5   # 청산: |Z| < exit_z
    stop_z:       float = 3.5   # 손절: |Z| > stop_z

    # 스프레드 계산 창
    zscore_window: int  = 60    # 60거래일 롤링

    # 포지션 관리
    capital_per_pair:  float = 0.05  # 페어당 자본 5% (Long+Short 각각 2.5%)
    max_pairs:         int   = 20    # 동시 최대 활성 페어
    max_hold_days:     int   = 30    # 최대 보유 거래일
    max_sector_pairs:  int   = 5     # 섹터당 최대 동시 활성 페어

    # 비용
    commission_rate: float = 0.001  # 0.1%
    slippage_rate:   float = 0.001  # 0.1%
    borrow_rate:     float = 0.02   # Short 대주 연 2%

    # 백테스트
    initial_capital: float = 1_000_000.0
    start_date:      str   = "2021-01-01"
    end_date:        str   = "2026-04-21"


class PairsBacktestEngine:
    """
    일봉 기반 페어 트레이딩 백테스트 엔진.

    설계 원칙:
      - Z-score는 백테스트 시작 전 전구간 사전 계산 (look-ahead 방지: 롤링 창 사용)
      - 진입/청산 모두 다음 날 시가(open) 기준 체결
      - Long + Short 동시 보유 → 페어당 alloc을 반분하여 양 다리 균등 배분
    """

    def __init__(
        self,
        config: PairsBacktestConfig,
        daily_data: Dict[str, pd.DataFrame],
        spy_daily: Optional[pd.DataFrame] = None,
    ):
        self.config      = config
        self.daily_data  = daily_data
        self.spy_daily   = spy_daily
        self.capital     = config.initial_capital
        self.active_trades: Dict[str, dict] = {}   # {pair_id: trade_dict}
        self.trade_log:  List[dict] = []
        self.equity_curve: List[Tuple[date, float]] = []
        self.daily_returns: List[float] = []

    # ── 메인 실행 ─────────────────────────────────────────────────────────

    def run(self) -> dict:
        """백테스트 실행 → 결과 딕셔너리."""
        all_trade_dates = self._get_all_trade_dates()
        if not all_trade_dates:
            logger.error("[PairsBT] 거래일 목록 없음")
            return {}

        # 페어별 Z-score 사전 계산 (전구간)
        logger.info(f"[PairsBT] {len(self.config.pairs)}개 페어 Z-score 사전 계산 중...")
        zscore_cache = self._precompute_zscores()
        logger.info(f"[PairsBT] Z-score 계산 완료 ({len(zscore_cache)}개 페어)")

        prev_equity = self.config.initial_capital

        for today in all_trade_dates:
            day_start_equity = self._calc_total_equity(today)

            # 1. 기존 포지션 청산 체크
            for pair_id in list(self.active_trades.keys()):
                z_series = zscore_cache.get(pair_id)
                if z_series is None:
                    continue
                z = self._get_z(z_series, today)
                if z is None or np.isnan(z):
                    continue
                trade = self.active_trades[pair_id]
                self._check_exit(pair_id, trade, z, today, all_trade_dates)

            # 2. 신규 진입 체크
            if len(self.active_trades) < self.config.max_pairs:
                # 현재 활성 페어의 섹터별 카운트
                sector_counts: Dict[str, int] = {}
                for t in self.active_trades.values():
                    s = t.get("sector", "Unknown")
                    sector_counts[s] = sector_counts.get(s, 0) + 1

                for pair in self.config.pairs:
                    if len(self.active_trades) >= self.config.max_pairs:
                        break
                    pair_id = f"{pair['symbol_a']}_{pair['symbol_b']}"
                    if pair_id in self.active_trades:
                        continue

                    # 섹터당 최대 페어 캡 체크
                    pair_sector = pair.get("sector", "Unknown")
                    if sector_counts.get(pair_sector, 0) >= self.config.max_sector_pairs:
                        continue

                    z_series = zscore_cache.get(pair_id)
                    if z_series is None:
                        continue
                    z = self._get_z(z_series, today)
                    if z is None or np.isnan(z):
                        continue
                    if abs(z) >= self.config.entry_z:
                        self._open_trade(pair, pair_id, z, today, all_trade_dates)
                        # 진입 시 섹터 카운트 갱신
                        sector_counts[pair_sector] = sector_counts.get(pair_sector, 0) + 1

            # 자산 기록
            equity = self._calc_total_equity(today)
            self.equity_curve.append((today, equity))
            daily_ret = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0.0
            self.daily_returns.append(daily_ret)
            prev_equity = equity

        # 잔여 포지션 강제 청산
        last_date = all_trade_dates[-1]
        for pair_id in list(self.active_trades.keys()):
            trade = self.active_trades[pair_id]
            self._close_trade(pair_id, trade, last_date, all_trade_dates, "EOD_FORCE")

        return self._generate_report()

    # ── Z-score 헬퍼 ──────────────────────────────────────────────────────

    def _precompute_zscores(self) -> Dict[str, pd.Series]:
        """모든 페어의 Z-score를 전구간 사전 계산."""
        cache: Dict[str, pd.Series] = {}
        for pair in self.config.pairs:
            sym_a   = pair["symbol_a"]
            sym_b   = pair["symbol_b"]
            beta    = pair["hedge_ratio"]
            pair_id = f"{sym_a}_{sym_b}"

            df_a = self.daily_data.get(sym_a)
            df_b = self.daily_data.get(sym_b)
            if df_a is None or df_b is None:
                continue

            common_idx = df_a.index.intersection(df_b.index)
            if len(common_idx) < self.config.zscore_window + 10:
                continue

            z = calc_spread_zscore(
                df_a.loc[common_idx, "close"],
                df_b.loc[common_idx, "close"],
                beta,
                self.config.zscore_window,
            )
            cache[pair_id] = z
        return cache

    def _get_z(self, z_series: pd.Series, target_date: date) -> Optional[float]:
        """날짜에 해당하는 Z-score 반환. 없으면 None."""
        if target_date in z_series.index:
            val = z_series[target_date]
            return float(val) if not pd.isna(val) else None
        # ffill: 해당 날짜 없으면 이전 마지막 값
        loc = z_series.index.searchsorted(target_date, side="right") - 1
        if loc < 0:
            return None
        val = z_series.iloc[loc]
        return float(val) if not pd.isna(val) else None

    # ── 진입 ──────────────────────────────────────────────────────────────

    def _open_trade(
        self,
        pair: dict,
        pair_id: str,
        z: float,
        signal_date: date,
        all_trade_dates: List[date],
    ) -> None:
        """
        signal_date에 신호 감지 → 다음 거래일 시가에 체결.
        Z > +entry_z: A Short + B Long
        Z < -entry_z: A Long  + B Short
        """
        exec_date = self._get_next_trade_date(signal_date, all_trade_dates)
        if exec_date is None:
            return

        sym_a = pair["symbol_a"]
        sym_b = pair["symbol_b"]
        beta  = pair["hedge_ratio"]

        price_a = self._get_exec_price(sym_a, exec_date, is_buy=(z < 0))
        price_b = self._get_exec_price(sym_b, exec_date, is_buy=(z > 0))
        if price_a is None or price_b is None:
            return

        # 페어당 자본 배분: 양 다리 합산 = capital × capital_per_pair
        total_equity = self._calc_total_equity(signal_date)
        alloc = total_equity * self.config.capital_per_pair / 2  # 한 다리당

        if z > 0:
            # A 과대평가: A Short, B Long
            direction  = "SHORT_A"
            long_sym,  short_sym  = sym_b, sym_a
            long_px,   short_px   = price_b, price_a
        else:
            # A 과소평가: A Long, B Short
            direction  = "LONG_A"
            long_sym,  short_sym  = sym_a, sym_b
            long_px,   short_px   = price_a, price_b

        long_qty  = max(1, int(alloc / long_px))
        short_qty = max(1, int(alloc / short_px))

        # 커미션 (체결 비용)
        commission = (
            long_px  * long_qty  * self.config.commission_rate
            + short_px * short_qty * self.config.commission_rate
        )
        if commission > self.capital * 0.5:   # 비용이 자본의 50% 초과 방지
            return

        self.capital -= commission

        self.active_trades[pair_id] = {
            "pair_id":    pair_id,
            "sector":     pair.get("sector", "Unknown"),
            "direction":  direction,
            "long_sym":   long_sym,
            "short_sym":  short_sym,
            "long_qty":   long_qty,
            "short_qty":  short_qty,
            "long_px":    long_px,
            "short_px":   short_px,
            "entry_date": exec_date,
            "entry_z":    round(z, 4),
            "hold_days":  0,
        }

        logger.debug(
            f"[PairsBT] OPEN {pair_id} | {direction} | Z={z:.2f} | "
            f"Long {long_sym}×{long_qty}@{long_px:.2f} | "
            f"Short {short_sym}×{short_qty}@{short_px:.2f}"
        )

    # ── 청산 ──────────────────────────────────────────────────────────────

    def _check_exit(
        self,
        pair_id: str,
        trade: dict,
        z: float,
        today: date,
        all_trade_dates: List[date],
    ) -> None:
        """청산/손절/강제 조건 확인 후 청산 실행."""
        entry_date = trade["entry_date"]
        hold_days  = self._count_hold_days(entry_date, today, all_trade_dates)

        if abs(z) < self.config.exit_z:
            reason = "MEAN_REVERT"
        elif abs(z) > self.config.stop_z:
            reason = "STOP_LOSS"
        elif hold_days >= self.config.max_hold_days:
            reason = "MAX_HOLD"
        else:
            return

        self._close_trade(pair_id, trade, today, all_trade_dates, reason)

    def _close_trade(
        self,
        pair_id: str,
        trade: dict,
        signal_date: date,
        all_trade_dates: List[date],
        reason: str,
    ) -> None:
        """포지션 청산 → PnL 계산."""
        exec_date = self._get_next_trade_date(signal_date, all_trade_dates)
        if exec_date is None:
            exec_date = signal_date   # 마지막 날이면 당일 종가 사용

        long_sym  = trade["long_sym"]
        short_sym = trade["short_sym"]

        exit_long  = self._get_exec_price(long_sym,  exec_date, is_buy=False)
        exit_short = self._get_exec_price(short_sym, exec_date, is_buy=True)

        if exit_long  is None: exit_long  = trade["long_px"]
        if exit_short is None: exit_short = trade["short_px"]

        pnl_long  = (exit_long  - trade["long_px"])  * trade["long_qty"]
        pnl_short = (trade["short_px"] - exit_short) * trade["short_qty"]

        # 대주 비용: Short 보유 거래일 × (연 2% / 252)
        hold_days = self._count_hold_days(trade["entry_date"], signal_date, all_trade_dates)
        borrow_cost = (
            trade["short_px"] * trade["short_qty"]
            * self.config.borrow_rate
            * max(hold_days, 1) / 252
        )

        commission = (
            exit_long  * trade["long_qty"]  * self.config.commission_rate
            + exit_short * trade["short_qty"] * self.config.commission_rate
        )

        total_pnl = pnl_long + pnl_short - borrow_cost - commission
        self.capital += total_pnl

        entry_alloc = (trade["long_px"] * trade["long_qty"]
                       + trade["short_px"] * trade["short_qty"])
        pnl_pct = total_pnl / entry_alloc if entry_alloc > 0 else 0.0

        self.trade_log.append({
            "pair_id":    pair_id,
            "entry_date": str(trade["entry_date"]),
            "exit_date":  str(exec_date),
            "direction":  trade["direction"],
            "reason":     reason,
            "pnl":        round(total_pnl, 2),
            "pnl_pct":    round(pnl_pct, 4),
            "hold_days":  hold_days,
            "entry_z":    trade["entry_z"],
            "borrow":     round(borrow_cost, 2),
        })

        logger.debug(
            f"[PairsBT] CLOSE {pair_id} | {reason} | PnL={total_pnl:+.0f} | "
            f"hold={hold_days}일"
        )

        self.active_trades.pop(pair_id, None)

    # ── 헬퍼 ──────────────────────────────────────────────────────────────

    def _get_exec_price(
        self, sym: str, exec_date: date, is_buy: bool
    ) -> Optional[float]:
        """체결 가격 = 시가 ± 슬리피지. 없으면 종가 대체."""
        df = self.daily_data.get(sym)
        if df is None:
            return None

        # exec_date 또는 가장 가까운 이전 거래일
        if exec_date in df.index:
            row = df.loc[exec_date]
        else:
            loc = df.index.searchsorted(exec_date, side="right") - 1
            if loc < 0:
                return None
            row = df.iloc[loc]

        raw = float(row.get("open", row["close"]))
        if is_buy:
            return raw * (1 + self.config.slippage_rate)
        else:
            return raw * (1 - self.config.slippage_rate)

    def _calc_total_equity(self, as_of_date: date) -> float:
        """현금 + 미실현 포지션 시가 평가."""
        equity = self.capital

        for trade in self.active_trades.values():
            # Long 평가
            df_long = self.daily_data.get(trade["long_sym"])
            if df_long is not None:
                px = self._get_close(df_long, as_of_date)
                if px:
                    equity += (px - trade["long_px"]) * trade["long_qty"]

            # Short 평가
            df_short = self.daily_data.get(trade["short_sym"])
            if df_short is not None:
                px = self._get_close(df_short, as_of_date)
                if px:
                    equity += (trade["short_px"] - px) * trade["short_qty"]

        return equity

    def _get_close(self, df: pd.DataFrame, target_date: date) -> Optional[float]:
        if target_date in df.index:
            return float(df.loc[target_date, "close"])
        loc = df.index.searchsorted(target_date, side="right") - 1
        if loc < 0:
            return None
        return float(df.iloc[loc]["close"])

    def _get_all_trade_dates(self) -> List[date]:
        """SPY 또는 첫 번째 종목 일봉에서 거래일 목록 추출."""
        ref_df = self.spy_daily
        if ref_df is None and self.daily_data:
            ref_df = next(iter(self.daily_data.values()))
        if ref_df is None:
            return []
        start = pd.to_datetime(self.config.start_date).date()
        end   = pd.to_datetime(self.config.end_date).date()
        return [d for d in ref_df.index if start <= d <= end]

    def _get_next_trade_date(
        self, ref_date: date, all_trade_dates: List[date]
    ) -> Optional[date]:
        for d in all_trade_dates:
            if d > ref_date:
                return d
        return None

    def _count_hold_days(
        self, entry_date: date, today: date, all_trade_dates: List[date]
    ) -> int:
        """entry_date 이후 today 까지 거래일 수."""
        return sum(1 for d in all_trade_dates if entry_date < d <= today)

    # ── 결과 생성 ─────────────────────────────────────────────────────────

    def _generate_report(self) -> dict:
        if not self.equity_curve:
            return {}

        equity_series = pd.Series(
            [e for _, e in self.equity_curve],
            index=[d for d, _ in self.equity_curve],
        )
        daily_rets = pd.Series(self.daily_returns, index=[d for d, _ in self.equity_curve])

        start_d  = equity_series.index[0]
        end_d    = equity_series.index[-1]
        n_years  = max((end_d - start_d).days / 365.25, 1 / 252)

        initial  = self.config.initial_capital
        final    = equity_series.iloc[-1]
        total_ret_pct = (final / initial - 1) * 100
        cagr          = ((final / initial) ** (1 / n_years) - 1) * 100

        # 드로우다운
        rolling_max = equity_series.cummax()
        drawdown     = (equity_series - rolling_max) / rolling_max
        max_dd       = float(drawdown.min()) * 100
        dd_end_idx   = drawdown.idxmin()
        dd_start_idx = equity_series[:dd_end_idx].idxmax() if len(equity_series[:dd_end_idx]) > 0 else dd_end_idx

        # Sharpe (일 수익률 기반, 연환산, rf=0)
        if len(daily_rets) > 1 and daily_rets.std() > 0:
            sharpe = (daily_rets.mean() / daily_rets.std()) * (252 ** 0.5)
        else:
            sharpe = 0.0

        # Sortino
        downside = daily_rets[daily_rets < 0]
        sortino  = (daily_rets.mean() / downside.std() * (252 ** 0.5)
                    if len(downside) > 1 and downside.std() > 0 else 0.0)

        # 거래 분석
        trades = self.trade_log
        wins   = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_hold = np.mean([t["hold_days"] for t in trades]) if trades else 0

        total_wins_pnl   = sum(t["pnl"] for t in wins)
        total_losses_pnl = abs(sum(t["pnl"] for t in losses))
        profit_factor    = (total_wins_pnl / total_losses_pnl
                            if total_losses_pnl > 0 else float("inf"))

        # 청산 유형 분포
        exit_types: Dict[str, int] = {}
        for t in trades:
            exit_types[t["reason"]] = exit_types.get(t["reason"], 0) + 1

        # 연도별 수익률
        yearly: Dict[int, List[float]] = {}
        for d, ret in zip([d for d, _ in self.equity_curve], self.daily_returns):
            yearly.setdefault(d.year, []).append(ret)
        yearly_ret = {
            yr: (np.prod([1 + r for r in rets]) - 1) * 100
            for yr, rets in sorted(yearly.items())
        }

        # 페어별 PnL
        pair_pnl: Dict[str, float] = {}
        for t in trades:
            pair_pnl[t["pair_id"]] = pair_pnl.get(t["pair_id"], 0) + t["pnl"]
        top10 = sorted(pair_pnl.items(), key=lambda x: -x[1])[:10]
        bot10 = sorted(pair_pnl.items(), key=lambda x:  x[1])[:10]

        # 벤치마크 SPY
        spy_cagr = None
        if self.spy_daily is not None:
            spy_s = self._get_close(self.spy_daily, start_d)
            spy_e = self._get_close(self.spy_daily, end_d)
            if spy_s and spy_e and spy_s > 0:
                spy_cagr = ((spy_e / spy_s) ** (1 / n_years) - 1) * 100

        return {
            "cagr":          round(cagr, 2),
            "total_ret_pct": round(total_ret_pct, 2),
            "final_capital": round(final, 0),
            "sharpe":        round(sharpe, 3),
            "sortino":       round(sortino, 3),
            "max_drawdown":  round(max_dd, 2),
            "mdd_start":     str(dd_start_idx),
            "mdd_end":       str(dd_end_idx),
            "profit_factor": round(profit_factor, 3),
            "win_rate":      round(win_rate, 1),
            "total_trades":  len(trades),
            "avg_hold_days": round(avg_hold, 1),
            "exit_types":    exit_types,
            "yearly_ret":    yearly_ret,
            "top10_pairs":   top10,
            "bot10_pairs":   bot10,
            "spy_cagr":      round(spy_cagr, 2) if spy_cagr is not None else None,
            "n_years":       round(n_years, 2),
            "trade_log":     trades,
            "equity_curve":  [(str(d), round(e, 0)) for d, e in self.equity_curve],
        }
