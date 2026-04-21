"""
NAVIS 팩터 모멘텀 백테스트 엔진 (P15)

전략:
  매월 말 S&P 500 전 종목의 12-1 모멘텀 계산 → 상위 20% 동일 비중 매수
  1개월 보유 후 다음 달 말 리밸런싱 반복.
  5분봉 불필요 — 월말 종가 기준 신호, 익월 첫 거래일 시가 진입/청산.

합격 기준 (NAVIS_STRATEGY_B_FACTOR_MOMENTUM.md):
  합격:       CAGR ≥ 15% AND Sharpe ≥ 0.8
  부분 합격:  CAGR ≥ 10% AND Sharpe ≥ 0.6
  실패:       위 조건 미달
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .factor_calculator import calc_momentum_12_1, calc_avg_dollar_volume, rank_momentum

logger = logging.getLogger(__name__)


@dataclass
class FactorBacktestConfig:
    # 유니버스
    symbols: List[str] = field(default_factory=list)

    # 팩터 파라미터
    momentum_lookback: int   = 252    # 12개월 = 252거래일
    momentum_skip:     int   = 21     # 최근 1개월 제외
    top_pct:           float = 0.20   # 상위 20% 선택

    # 유동성 필터
    min_dollar_volume: float = 5e7    # 일평균 $5,000만 이상
    min_price:         float = 5.0    # $5 이상

    # 포지션 관리
    max_position_pct:  float = 0.05   # 단일 종목 최대 5% (캡)

    # 비용
    commission_rate:   float = 0.001  # 0.1%
    slippage_rate:     float = 0.001  # 0.1% (일봉 시가 슬리피지)

    # 백테스트 기간
    initial_capital:   float = 1_000_000.0
    start_date:        str   = "2021-01-01"
    end_date:          str   = "2026-04-21"


class FactorBacktestEngine:
    """
    월말 리밸런싱 팩터 모멘텀 백테스트 엔진.

    데이터 흐름:
        1. 월 마지막 거래일(rebalance_date)에 전 종목 12-1 모멘텀 계산
        2. 상위 top_pct 종목 선별 → target_portfolio
        3. 기존 보유 종목 중 탈락 → 다음 거래일 시가에 청산
        4. 신규 편입 종목 → 다음 거래일 시가에 매수
        5. 동일 비중 유지 (리밸런싱 시 기존 보유 조정)
    """

    def __init__(
        self,
        config: FactorBacktestConfig,
        daily_data: Dict[str, pd.DataFrame],
        spy_daily: Optional[pd.DataFrame] = None,
    ):
        self.config     = config
        self.daily_data = daily_data
        self.spy_daily  = spy_daily   # 벤치마크 비교용
        self.capital    = config.initial_capital
        self.portfolio: Dict[str, dict] = {}   # {symbol: {"qty", "entry_price", "entry_date"}}
        self.trade_log: List[dict]      = []
        self.equity_curve: List[Tuple[date, float]] = []
        self.monthly_returns: List[dict] = []

    # ── 메인 실행 ─────────────────────────────────────────────────────────

    def run(self) -> dict:
        """백테스트 실행 후 결과 딕셔너리 반환."""
        # 거래 가능한 모든 날짜 집합 (SPY 기준)
        all_trade_dates = self._get_all_trade_dates()
        if not all_trade_dates:
            logger.error("[FactorBT] 거래 가능 날짜를 찾을 수 없음")
            return {}

        # 월말 리밸런싱 날짜 목록
        month_ends = self._get_month_end_dates(all_trade_dates)
        logger.info(
            f"[FactorBT] 리밸런싱 날짜: {len(month_ends)}개 "
            f"({month_ends[0]} ~ {month_ends[-1]})"
        )

        prev_equity = self.config.initial_capital

        for i, rebalance_date in enumerate(month_ends):
            # 리밸런싱 실행
            next_trade_date = self._get_next_trade_date(rebalance_date, all_trade_dates)
            if next_trade_date is None:
                logger.warning(f"[FactorBT] {rebalance_date}: 다음 거래일 없음, 건너뜀")
                continue

            self._rebalance(rebalance_date, next_trade_date)

            # 월말 포트폴리오 가치 기록
            equity = self._calc_total_equity(rebalance_date)
            self.equity_curve.append((rebalance_date, equity))

            # 월 수익률
            monthly_ret = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0.0
            self.monthly_returns.append({
                "date":       rebalance_date,
                "equity":     equity,
                "monthly_ret": monthly_ret,
                "n_holdings":  len(self.portfolio),
            })
            prev_equity = equity

            logger.info(
                f"[FactorBT] {rebalance_date} | 포트폴리오={len(self.portfolio)}종목 "
                f"| 자산={equity:,.0f} | 월 수익={monthly_ret*100:.2f}%"
            )

        # 잔여 포지션 청산 (백테스트 종료)
        last_date = all_trade_dates[-1]
        self._liquidate_all(last_date)
        final_equity = self.capital
        self.equity_curve.append((last_date, final_equity))

        return self._generate_report()

    # ── 리밸런싱 ──────────────────────────────────────────────────────────

    def _rebalance(self, rebalance_date: date, exec_date: date) -> None:
        """
        월말 리밸런싱:
          1. 전 종목 모멘텀 계산
          2. 상위 top_pct 선별
          3. 탈락 종목 청산, 편입 종목 매수
          4. 기존 보유 종목 비중 재조정
        """
        # ── 1. 팩터 계산 ────────────────────────────────────────────────
        scores: Dict[str, float] = {}
        for sym in self.config.symbols:
            df = self.daily_data.get(sym)
            if df is None or len(df) == 0:
                continue

            # 유동성 필터
            dv = calc_avg_dollar_volume(df, rebalance_date, window=21)
            if dv < self.config.min_dollar_volume:
                continue

            # 가격 필터
            price = self._get_price(df, rebalance_date, "close")
            if price is None or price < self.config.min_price:
                continue

            # 12-1 모멘텀
            mom = calc_momentum_12_1(df, rebalance_date)
            if mom is None:
                continue

            scores[sym] = mom

        if not scores:
            logger.warning(f"[FactorBT] {rebalance_date}: 유효 종목 0개, 리밸런싱 건너뜀")
            return

        # ── 2. 상위 top_pct 선별 ────────────────────────────────────────
        target_symbols = set(rank_momentum(scores, self.config.top_pct))
        n_target = len(target_symbols)
        logger.debug(
            f"[FactorBT] {rebalance_date}: 유효={len(scores)}종목, "
            f"선택={n_target}종목 (상위 {self.config.top_pct*100:.0f}%)"
        )

        # ── 3. 전체 자산 계산 (청산 전 기준) ────────────────────────────
        total_equity = self._calc_total_equity(rebalance_date)
        per_position = total_equity / n_target if n_target > 0 else 0
        # 단일 종목 최대 비중 캡
        max_per = total_equity * self.config.max_position_pct
        per_position = min(per_position, max_per)

        # ── 4. 탈락 종목 청산 ───────────────────────────────────────────
        for sym in list(self.portfolio.keys()):
            if sym not in target_symbols:
                self._close_position(sym, exec_date)

        # ── 5. 편입/리밸런싱 매수 ───────────────────────────────────────
        for sym in sorted(target_symbols):
            df = self.daily_data.get(sym)
            if df is None:
                continue

            exec_open = self._get_price(df, exec_date, "open")
            if exec_open is None:
                # exec_date에 데이터 없으면 rebalance_date 종가로 대체 (드문 경우)
                exec_open = self._get_price(df, rebalance_date, "close")
                if exec_open is None:
                    continue

            entry_price = exec_open * (1 + self.config.slippage_rate)
            target_qty  = int(per_position / entry_price)
            if target_qty <= 0:
                continue

            if sym in self.portfolio:
                # 기존 보유 — 수량 조정 (리밸런싱)
                curr_qty   = self.portfolio[sym]["qty"]
                delta_qty  = target_qty - curr_qty
                if delta_qty > 0:
                    # 추가 매수
                    cost = entry_price * delta_qty * (1 + self.config.commission_rate)
                    if cost <= self.capital:
                        self.capital -= cost
                        self.portfolio[sym]["qty"]         = curr_qty + delta_qty
                        self.portfolio[sym]["entry_price"] = entry_price  # 평균가 갱신 (단순화)
                elif delta_qty < 0:
                    # 일부 매도
                    sell_qty   = -delta_qty
                    exit_price = exec_open * (1 - self.config.slippage_rate)
                    proceeds   = exit_price * sell_qty * (1 - self.config.commission_rate)
                    self.capital += proceeds
                    self.portfolio[sym]["qty"] = curr_qty + delta_qty
            else:
                # 신규 진입
                cost = entry_price * target_qty * (1 + self.config.commission_rate)
                if cost > self.capital:
                    continue
                self.capital -= cost
                self.portfolio[sym] = {
                    "qty":         target_qty,
                    "entry_price": entry_price,
                    "entry_date":  str(exec_date),
                }
                self.trade_log.append({
                    "date":   str(exec_date),
                    "symbol": sym,
                    "action": "BUY",
                    "price":  round(entry_price, 4),
                    "qty":    target_qty,
                    "momentum_score": round(scores.get(sym, 0), 4),
                })

    def _close_position(self, sym: str, exec_date: date) -> None:
        """지정 종목 청산."""
        pos = self.portfolio.pop(sym, None)
        if pos is None or pos["qty"] <= 0:
            return

        df = self.daily_data.get(sym)
        exit_price = None
        if df is not None:
            raw = self._get_price(df, exec_date, "open")
            if raw is not None:
                exit_price = raw * (1 - self.config.slippage_rate)

        if exit_price is None:
            # 데이터 없으면 진입가 그대로 (손익 0)
            exit_price = pos["entry_price"]

        proceeds = exit_price * pos["qty"] * (1 - self.config.commission_rate)
        pnl      = (exit_price - pos["entry_price"]) * pos["qty"]
        pnl_pct  = pnl / (pos["entry_price"] * pos["qty"]) if pos["qty"] > 0 else 0
        self.capital += proceeds

        self.trade_log.append({
            "date":        str(exec_date),
            "symbol":      sym,
            "action":      "SELL",
            "price":       round(exit_price, 4),
            "qty":         pos["qty"],
            "pnl":         round(pnl, 2),
            "pnl_pct":     round(pnl_pct, 4),
            "entry_date":  pos.get("entry_date", ""),
        })

    def _liquidate_all(self, last_date: date) -> None:
        """백테스트 종료 시 전 보유 종목 청산."""
        for sym in list(self.portfolio.keys()):
            self._close_position(sym, last_date)

    # ── 헬퍼 ──────────────────────────────────────────────────────────────

    def _get_price(
        self,
        df: pd.DataFrame,
        target_date: date,
        col: str = "close",
    ) -> Optional[float]:
        """지정 날짜의 가격. 없으면 None."""
        if target_date in df.index:
            return float(df.loc[target_date, col])
        # 해당 날짜 없으면 가장 가까운 이전 날짜 사용
        loc = df.index.searchsorted(target_date, side="right") - 1
        if loc < 0:
            return None
        return float(df.iloc[loc][col])

    def _calc_total_equity(self, as_of_date: date) -> float:
        """현금 + 보유 종목 시가 평가."""
        equity = self.capital
        for sym, pos in self.portfolio.items():
            df = self.daily_data.get(sym)
            if df is None:
                equity += pos["entry_price"] * pos["qty"]
                continue
            price = self._get_price(df, as_of_date, "close")
            if price is None:
                price = pos["entry_price"]
            equity += price * pos["qty"]
        return equity

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

    def _get_month_end_dates(self, trade_dates: List[date]) -> List[date]:
        """거래일 목록에서 각 월의 마지막 거래일 추출."""
        if not trade_dates:
            return []
        month_ends = []
        for i, d in enumerate(trade_dates):
            is_last = (
                i == len(trade_dates) - 1
                or trade_dates[i + 1].month != d.month
                or trade_dates[i + 1].year  != d.year
            )
            if is_last:
                month_ends.append(d)
        return month_ends

    def _get_next_trade_date(
        self,
        ref_date: date,
        all_trade_dates: List[date],
    ) -> Optional[date]:
        """ref_date 다음 거래일 반환."""
        for d in all_trade_dates:
            if d > ref_date:
                return d
        return None

    # ── 결과 생성 ─────────────────────────────────────────────────────────

    def _generate_report(self) -> dict:
        """백테스트 결과 딕셔너리 생성."""
        if not self.equity_curve:
            return {}

        equity_series = pd.Series(
            [e for _, e in self.equity_curve],
            index=[d for d, _ in self.equity_curve],
        )

        # 월 수익률
        monthly_rets = pd.Series(
            [r["monthly_ret"] for r in self.monthly_returns],
            index=[r["date"]  for r in self.monthly_returns],
        )

        # 기간 (연 환산)
        start_d = equity_series.index[0]
        end_d   = equity_series.index[-1]
        n_years = max((end_d - start_d).days / 365.25, 1 / 12)

        # 핵심 지표
        initial = self.config.initial_capital
        final   = equity_series.iloc[-1]
        total_ret_pct = (final / initial - 1) * 100
        cagr          = ((final / initial) ** (1 / n_years) - 1) * 100

        # 드로우다운
        rolling_max = equity_series.cummax()
        drawdown     = (equity_series - rolling_max) / rolling_max
        max_dd       = float(drawdown.min()) * 100

        # MDD 발생 기간
        dd_end_idx = drawdown.idxmin()
        dd_start_candidates = equity_series[:dd_end_idx]
        dd_start_idx = dd_start_candidates.idxmax() if len(dd_start_candidates) > 0 else dd_end_idx

        # Sharpe (월 수익률 기반, 연 환산, 무위험 = 0)
        if len(monthly_rets) > 1 and monthly_rets.std() > 0:
            sharpe = (monthly_rets.mean() / monthly_rets.std()) * (12 ** 0.5)
        else:
            sharpe = 0.0

        # Sortino (하방 편차만)
        downside = monthly_rets[monthly_rets < 0]
        if len(downside) > 1 and downside.std() > 0:
            sortino = (monthly_rets.mean() / downside.std()) * (12 ** 0.5)
        else:
            sortino = 0.0

        # 거래 분석
        sells = [t for t in self.trade_log if t["action"] == "SELL" and "pnl" in t]
        wins  = [t for t in sells if t["pnl"] > 0]
        losses = [t for t in sells if t["pnl"] <= 0]
        win_rate = len(wins) / len(sells) * 100 if sells else 0
        avg_win  = np.mean([t["pnl_pct"] for t in wins])  * 100 if wins  else 0
        avg_loss = np.mean([t["pnl_pct"] for t in losses]) * 100 if losses else 0
        total_wins_pnl   = sum(t["pnl"] for t in wins)
        total_losses_pnl = abs(sum(t["pnl"] for t in losses))
        profit_factor    = (total_wins_pnl / total_losses_pnl) if total_losses_pnl > 0 else float("inf")

        # 벤치마크 (SPY) 비교
        spy_ret_pct = None
        spy_cagr    = None
        if self.spy_daily is not None:
            spy_start = self._get_price(self.spy_daily, start_d, "close")
            spy_end   = self._get_price(self.spy_daily, end_d,   "close")
            if spy_start and spy_end and spy_start > 0:
                spy_ret_pct = (spy_end / spy_start - 1) * 100
                spy_cagr    = ((spy_end / spy_start) ** (1 / n_years) - 1) * 100

        # 연도별 수익률
        yearly: Dict[int, List[float]] = {}
        for r in self.monthly_returns:
            yr = r["date"].year
            yearly.setdefault(yr, []).append(r["monthly_ret"])

        yearly_ret = {}
        for yr, rets in sorted(yearly.items()):
            yearly_ret[yr] = (np.prod([1 + r for r in rets]) - 1) * 100

        # 종목별 기여 (SELL 기준 총 PnL)
        symbol_pnl: Dict[str, float] = {}
        for t in sells:
            symbol_pnl[t["symbol"]] = symbol_pnl.get(t["symbol"], 0) + t["pnl"]
        top10  = sorted(symbol_pnl.items(), key=lambda x: -x[1])[:10]
        bot10  = sorted(symbol_pnl.items(), key=lambda x:  x[1])[:10]

        # 월별 수익률 분포
        monthly_values = [r["monthly_ret"] * 100 for r in self.monthly_returns]
        best_month  = max(monthly_values)  if monthly_values else 0
        worst_month = min(monthly_values)  if monthly_values else 0
        avg_month   = np.mean(monthly_values) if monthly_values else 0

        return {
            "cagr":            round(cagr, 2),
            "total_ret_pct":   round(total_ret_pct, 2),
            "final_capital":   round(final, 0),
            "sharpe":          round(sharpe, 3),
            "sortino":         round(sortino, 3),
            "max_drawdown":    round(max_dd, 2),
            "mdd_start":       str(dd_start_idx),
            "mdd_end":         str(dd_end_idx),
            "profit_factor":   round(profit_factor, 3),
            "win_rate":        round(win_rate, 1),
            "avg_win_pct":     round(avg_win, 2),
            "avg_loss_pct":    round(avg_loss, 2),
            "total_trades":    len(sells),
            "n_years":         round(n_years, 2),
            "spy_ret_pct":     round(spy_ret_pct, 2) if spy_ret_pct is not None else None,
            "spy_cagr":        round(spy_cagr, 2)    if spy_cagr    is not None else None,
            "yearly_ret":      yearly_ret,
            "top10_symbols":   top10,
            "bot10_symbols":   bot10,
            "best_month":      round(best_month,  2),
            "worst_month":     round(worst_month, 2),
            "avg_month":       round(avg_month,   2),
            "equity_curve":    [(str(d), round(e, 0)) for d, e in self.equity_curve],
            "trade_log":       self.trade_log,
        }
