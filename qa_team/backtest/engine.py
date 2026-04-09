"""
백테스트 엔진 (Backtest Engine)

기획서 9. 테스트 전략 - 백테스트 담당

실제 과거 데이터 또는 시뮬레이션 데이터를 이용하여
전략 엔진 + 리스크 관리자의 성능을 검증합니다.

성능 지표:
- 총 수익률 (Total Return)
- 최대 낙폭 (Max Drawdown)
- 샤프 지수 (Sharpe Ratio)
- 승률 (Win Rate)
- 손익비 (Profit Factor)
- 총 거래 수
"""
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """백테스트 설정"""
    initial_capital: float = 1_000_000.0      # 초기 자본 (1,000,000원)
    stop_loss_pct: float = 0.02               # 손절 -2%
    take_profit_pct: float = 0.10             # 익절 +10%
    max_daily_loss_pct: float = 0.05          # 일일 최대 손실 -5%
    max_positions: int = 5                    # 최대 동시 보유 종목
    min_position_pct: float = 0.05            # 최소 투자 비율 5%
    max_position_pct: float = 0.20            # 최대 투자 비율 20%
    buy_score_threshold: float = 75.0         # 매수 점수 기준
    commission_rate: float = 0.001            # 수수료 0.1%
    slippage_rate: float = 0.001              # 슬리피지 0.1%
    warmup_periods: int = 200                 # 지표 계산을 위한 워밍업 기간 (200일)


@dataclass
class TradeRecord:
    """거래 기록"""
    symbol: str
    action: str                   # BUY / SELL
    signal_type: str              # STOP_LOSS / TAKE_PROFIT / SELL / BUY
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    entry_date: str
    exit_date: Optional[str]
    pnl: float = 0.0              # 실현 손익
    pnl_pct: float = 0.0          # 손익률
    commission: float = 0.0
    score_at_entry: float = 0.0
    hold_days: int = 0


@dataclass
class BacktestResult:
    """백테스트 결과"""
    # 수익성
    initial_capital: float
    final_capital: float
    total_return_pct: float       # 총 수익률 (%)
    annualized_return_pct: float  # 연환산 수익률 (%)

    # 리스크
    max_drawdown_pct: float       # 최대 낙폭 (%)
    sharpe_ratio: float           # 샤프 지수
    sortino_ratio: float          # 소르티노 지수

    # 거래 통계
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate_pct: float           # 승률 (%)
    profit_factor: float          # 손익비 (총수익 / 총손실)
    avg_profit_pct: float         # 평균 수익률 (%)
    avg_loss_pct: float           # 평균 손실률 (%)
    avg_hold_days: float          # 평균 보유 기간

    # 상세 기록
    trade_records: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)

    # 검증 결과
    passed: bool = False          # 전략 유효성 (기준 통과 여부)
    fail_reasons: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """결과 요약 문자열"""
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"{'='*60}",
            f"백테스트 결과 [{status}]",
            f"{'='*60}",
            f"초기 자본:     ${self.initial_capital:>12,.0f}",
            f"최종 자본:     ${self.final_capital:>12,.0f}",
            f"총 수익률:     {self.total_return_pct:>+10.2f}%",
            f"연환산 수익률: {self.annualized_return_pct:>+10.2f}%",
            f"최대 낙폭:     {self.max_drawdown_pct:>10.2f}%",
            f"샤프 지수:     {self.sharpe_ratio:>10.3f}",
            f"{'─'*60}",
            f"총 거래:       {self.total_trades:>10d}회",
            f"승률:          {self.win_rate_pct:>10.1f}%",
            f"손익비:        {self.profit_factor:>10.3f}",
            f"평균 수익률:   {self.avg_profit_pct:>+10.2f}%",
            f"평균 손실률:   {self.avg_loss_pct:>+10.2f}%",
            f"평균 보유일:   {self.avg_hold_days:>10.1f}일",
        ]
        if self.fail_reasons:
            lines.append(f"{'─'*60}")
            lines.append("실패 사유:")
            for reason in self.fail_reasons:
                lines.append(f"  - {reason}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)


class BacktestEngine:
    """
    백테스트 엔진

    전략 엔진 + 리스크 관리자를 과거 데이터로 실행하여
    성능을 검증합니다.

    사용법:
        engine = BacktestEngine(config)
        result = engine.run(symbol="AAPL", df=historical_df)
        print(result.summary())
    """

    # 전략 유효성 기준
    MIN_WIN_RATE = 40.0           # 최소 승률 40%
    MIN_PROFIT_FACTOR = 1.0       # 최소 손익비 1.0 (손익 균형)
    MAX_DRAWDOWN_LIMIT = 30.0     # 최대 허용 낙폭 30%
    MIN_TRADES = 5                # 최소 거래 수

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self._setup_components()

    def _setup_components(self):
        """전략 엔진 + 리스크 관리자 초기화"""
        from strategy_engine.scoring.score_calculator import ScoreCalculator
        from strategy_engine.signals.signal_generator import SignalGenerator, TradingConditions
        from risk_team.core.risk_manager import RiskManager
        from risk_team.core.risk_models import AccountInfo

        self.score_calculator = ScoreCalculator()
        conditions = TradingConditions(
            buy_score_threshold=self.config.buy_score_threshold,
            take_profit_pct=self.config.take_profit_pct,
            stop_loss_pct=-self.config.stop_loss_pct,
        )
        self.signal_generator = SignalGenerator(conditions=conditions)
        self.risk_manager = RiskManager(
            stop_loss_pct=self.config.stop_loss_pct,
            take_profit_pct=self.config.take_profit_pct,
            max_daily_loss_pct=self.config.max_daily_loss_pct,
            max_positions=self.config.max_positions,
            min_position_pct=self.config.min_position_pct,
            max_position_pct=self.config.max_position_pct,
        )

    def run(
        self,
        symbol: str,
        df: pd.DataFrame,
        news_sentiment: Optional[float] = None,
        revenue_growth: Optional[float] = None,
        eps_growth: Optional[float] = None,
    ) -> BacktestResult:
        """
        단일 종목 백테스트 실행

        Args:
            symbol: 종목 심볼
            df: OHLCV 데이터 (close, open, high, low, volume 컬럼 필수)
            news_sentiment: 뉴스 감성 고정값 (-1.0 ~ 1.0)
            revenue_growth: 매출 성장률 (%)
            eps_growth: EPS 성장률 (%)

        Returns:
            BacktestResult
        """
        from risk_team.core.risk_models import AccountInfo, Position, OrderSignal, OrderAction, OrderType

        if len(df) < self.config.warmup_periods:
            raise ValueError(
                f"데이터 부족: {len(df)}행 (최소 {self.config.warmup_periods}행 필요)"
            )

        # 상태 초기화
        capital = self.config.initial_capital
        equity_curve = [capital]
        positions: List[dict] = []   # [{symbol, qty, entry_price, entry_idx, score}]
        trade_records: List[TradeRecord] = []
        daily_start_capital = capital
        daily_pnl = 0.0

        logger.info(f"백테스트 시작 - {symbol}, {len(df)}일 데이터")

        for i in range(self.config.warmup_periods, len(df)):
            row = df.iloc[i]
            current_price = float(row['close'])
            window_df = df.iloc[:i+1]

            # ── 1. 기존 포지션 청산 조건 확인 ──────────────────
            closed_positions = []
            for pos in positions:
                entry_price = pos['entry_price']
                pnl_pct = (current_price - entry_price) / entry_price

                should_close = False
                signal_type = "HOLD"

                # 손절
                if pnl_pct <= -self.config.stop_loss_pct:
                    should_close = True
                    signal_type = "STOP_LOSS"
                # 익절
                elif pnl_pct >= self.config.take_profit_pct:
                    should_close = True
                    signal_type = "TAKE_PROFIT"

                if should_close:
                    exit_price = current_price * (1 - self.config.slippage_rate)
                    commission = exit_price * pos['qty'] * self.config.commission_rate
                    pnl = (exit_price - entry_price) * pos['qty'] - commission - pos['entry_commission']
                    pnl_pct_actual = (exit_price - entry_price) / entry_price

                    capital += exit_price * pos['qty'] - commission
                    daily_pnl += pnl

                    hold_days = i - pos['entry_idx']
                    trade_records.append(TradeRecord(
                        symbol=symbol,
                        action="SELL",
                        signal_type=signal_type,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        quantity=pos['qty'],
                        entry_date=str(df.index[pos['entry_idx']] if hasattr(df.index, '__getitem__') else pos['entry_idx']),
                        exit_date=str(df.index[i] if hasattr(df.index, '__getitem__') else i),
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct_actual * 100, 2),
                        commission=round(commission + pos['entry_commission'], 2),
                        score_at_entry=pos.get('score', 0),
                        hold_days=hold_days,
                    ))
                    closed_positions.append(pos)

            for pos in closed_positions:
                positions.remove(pos)

            # ── 2. 일일 손실 한도 초과 시 신규 매수 중단 ────────
            daily_loss_pct = daily_pnl / daily_start_capital if daily_start_capital > 0 else 0
            if daily_loss_pct <= -self.config.max_daily_loss_pct:
                equity_curve.append(capital + sum(
                    current_price * p['qty'] for p in positions
                ))
                continue

            # ── 3. 매수 시그널 확인 (최대 포지션 미만인 경우) ────
            if len(positions) < self.config.max_positions:
                try:
                    signal = self.signal_generator.generate_buy_signal(
                        symbol=symbol,
                        df=window_df,
                        news_sentiment=news_sentiment,
                        news_count=0,
                        revenue_growth=revenue_growth,
                        eps_growth=eps_growth,
                    )

                    if signal and signal.score >= self.config.buy_score_threshold:
                        # 포지션 사이징
                        position_pct = self.config.max_position_pct - (
                            len(positions) * 0.03
                        )
                        position_pct = max(self.config.min_position_pct, position_pct)
                        invest_amount = capital * position_pct

                        buy_price = current_price * (1 + self.config.slippage_rate)
                        qty = int(invest_amount / buy_price)

                        if qty > 0 and capital >= buy_price * qty:
                            entry_commission = buy_price * qty * self.config.commission_rate
                            capital -= buy_price * qty + entry_commission

                            positions.append({
                                'symbol': symbol,
                                'qty': qty,
                                'entry_price': buy_price,
                                'entry_idx': i,
                                'entry_commission': entry_commission,
                                'score': signal.score,
                            })

                except Exception as e:
                    logger.debug(f"시그널 생성 오류 (i={i}): {e}")

            # ── 4. 자산 곡선 업데이트 ──────────────────────────
            unrealized = sum(current_price * p['qty'] for p in positions)
            equity_curve.append(capital + unrealized)

            # ── 5. 날짜 변경 시 일일 손익 리셋 ────────────────
            # 간단히 매 100번째 봉마다 일일 리셋 (일봉 시뮬레이션)
            if i % 1 == 0:
                daily_start_capital = capital + unrealized
                daily_pnl = 0.0

        # ── 잔여 포지션 마지막 가격으로 강제 청산 ──────────────
        last_price = float(df.iloc[-1]['close'])
        for pos in positions:
            exit_price = last_price * (1 - self.config.slippage_rate)
            commission = exit_price * pos['qty'] * self.config.commission_rate
            pnl = (exit_price - pos['entry_price']) * pos['qty'] - commission - pos['entry_commission']
            pnl_pct_actual = (exit_price - pos['entry_price']) / pos['entry_price']
            capital += exit_price * pos['qty'] - commission
            hold_days = len(df) - 1 - pos['entry_idx']
            trade_records.append(TradeRecord(
                symbol=symbol,
                action="SELL",
                signal_type="END_OF_TEST",
                entry_price=pos['entry_price'],
                exit_price=exit_price,
                quantity=pos['qty'],
                entry_date=str(pos['entry_idx']),
                exit_date="END",
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct_actual * 100, 2),
                commission=round(commission + pos['entry_commission'], 2),
                score_at_entry=pos.get('score', 0),
                hold_days=hold_days,
            ))
        equity_curve.append(capital)

        # ── 성능 지표 계산 ─────────────────────────────────────
        return self._calculate_metrics(
            initial_capital=self.config.initial_capital,
            final_capital=capital,
            equity_curve=equity_curve,
            trade_records=trade_records,
            total_days=len(df) - self.config.warmup_periods,
        )

    def _calculate_metrics(
        self,
        initial_capital: float,
        final_capital: float,
        equity_curve: List[float],
        trade_records: List[TradeRecord],
        total_days: int,
    ) -> BacktestResult:
        """성능 지표 계산"""
        # ── 수익률 ──────────────────────────────────────────────
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100
        years = max(total_days / 252, 0.001)
        annualized_return_pct = ((final_capital / initial_capital) ** (1 / years) - 1) * 100

        # ── 최대 낙폭 ───────────────────────────────────────────
        equity_arr = np.array(equity_curve)
        rolling_max = np.maximum.accumulate(equity_arr)
        drawdown_curve = (equity_arr - rolling_max) / rolling_max * 100
        max_drawdown_pct = float(abs(drawdown_curve.min()))

        # ── 샤프 지수 ───────────────────────────────────────────
        if len(equity_arr) > 1:
            daily_returns = np.diff(equity_arr) / equity_arr[:-1]
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            risk_free_daily = 0.04 / 252  # 연 4% 무위험 수익률
            if std_return > 0:
                sharpe_ratio = (mean_return - risk_free_daily) / std_return * np.sqrt(252)
            else:
                sharpe_ratio = 0.0

            # ── 소르티노 지수 (하방 변동성만) ──────────────────
            downside_returns = daily_returns[daily_returns < risk_free_daily]
            downside_std = np.std(downside_returns) if len(downside_returns) > 0 else std_return
            sortino_ratio = (mean_return - risk_free_daily) / downside_std * np.sqrt(252) if downside_std > 0 else 0.0
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

        # ── 거래 통계 ───────────────────────────────────────────
        closed_trades = [t for t in trade_records if t.action == "SELL"]
        total_trades = len(closed_trades)

        win_trades = [t for t in closed_trades if t.pnl > 0]
        loss_trades = [t for t in closed_trades if t.pnl <= 0]

        win_rate_pct = len(win_trades) / total_trades * 100 if total_trades > 0 else 0.0

        total_profit = sum(t.pnl for t in win_trades) if win_trades else 0.0
        total_loss = abs(sum(t.pnl for t in loss_trades)) if loss_trades else 0.0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0.0

        avg_profit_pct = np.mean([t.pnl_pct for t in win_trades]) if win_trades else 0.0
        avg_loss_pct = np.mean([t.pnl_pct for t in loss_trades]) if loss_trades else 0.0
        avg_hold_days = np.mean([t.hold_days for t in closed_trades]) if closed_trades else 0.0

        # ── 전략 유효성 검증 ────────────────────────────────────
        passed = True
        fail_reasons = []

        if total_trades < self.MIN_TRADES:
            passed = False
            fail_reasons.append(f"거래 수 부족: {total_trades}회 (최소 {self.MIN_TRADES}회)")

        if win_rate_pct < self.MIN_WIN_RATE and total_trades >= self.MIN_TRADES:
            passed = False
            fail_reasons.append(f"승률 미달: {win_rate_pct:.1f}% (최소 {self.MIN_WIN_RATE}%)")

        if profit_factor < self.MIN_PROFIT_FACTOR and total_trades >= self.MIN_TRADES:
            passed = False
            fail_reasons.append(f"손익비 미달: {profit_factor:.3f} (최소 {self.MIN_PROFIT_FACTOR})")

        if max_drawdown_pct > self.MAX_DRAWDOWN_LIMIT:
            passed = False
            fail_reasons.append(f"최대 낙폭 초과: {max_drawdown_pct:.1f}% (최대 {self.MAX_DRAWDOWN_LIMIT}%)")

        return BacktestResult(
            initial_capital=initial_capital,
            final_capital=round(final_capital, 2),
            total_return_pct=round(total_return_pct, 2),
            annualized_return_pct=round(annualized_return_pct, 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            sharpe_ratio=round(sharpe_ratio, 3),
            sortino_ratio=round(sortino_ratio, 3),
            total_trades=total_trades,
            win_trades=len(win_trades),
            loss_trades=len(loss_trades),
            win_rate_pct=round(win_rate_pct, 1),
            profit_factor=round(profit_factor, 3),
            avg_profit_pct=round(float(avg_profit_pct), 2),
            avg_loss_pct=round(float(avg_loss_pct), 2),
            avg_hold_days=round(float(avg_hold_days), 1),
            trade_records=trade_records,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve.tolist(),
            passed=passed,
            fail_reasons=fail_reasons,
        )

    def run_multi_symbol(
        self,
        stock_data: Dict[str, pd.DataFrame],
        **kwargs,
    ) -> Dict[str, BacktestResult]:
        """
        다중 종목 백테스트

        Args:
            stock_data: {심볼: DataFrame} 딕셔너리

        Returns:
            {심볼: BacktestResult} 딕셔너리
        """
        results = {}
        for symbol, df in stock_data.items():
            try:
                result = self.run(symbol=symbol, df=df, **kwargs)
                results[symbol] = result
                logger.info(f"{symbol}: {result.total_return_pct:+.2f}%, MDD={result.max_drawdown_pct:.1f}%")
            except Exception as e:
                logger.error(f"{symbol} 백테스트 실패: {e}")
        return results
