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

[NEXT-01] 실거래 엔진과 청산 로직 일치:
  - ATR14 기반 동적 SL (SL = entry − atr_sl_multiplier × ATR14)
  - 분할 익절: +partial_tp_pct 에서 보유량 50% 청산
  - 추적 청산: 분할 익절 후 고점 대비 -trailing_stop_pct 에서 잔여량 청산
  - bar 저가(low)로 SL 검출, 고가(high)로 TP 검출 (look-ahead 최소화)
  - generate_buy_signal() 호출 시 strategy_type 전달
"""
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.trading_constants import (
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT,
    BACKTEST_SLIPPAGE_PCT,
    BACKTEST_COMMISSION_PCT,
    ATR_SL_MULTIPLIER,
    TRAILING_STOP_PCT,
    PARTIAL_TP_PCT,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """백테스트 설정"""
    initial_capital: float = 1_000_000.0          # 초기 자본
    stop_loss_pct: float = STOP_LOSS_PCT           # 손절 -2% (ATR 미계산 시 폴백)
    take_profit_pct: float = TAKE_PROFIT_PCT       # 익절 +6% (BUG-01: 이전 10% → 통합)
    max_daily_loss_pct: float = 0.05              # 일일 최대 손실 -5%
    max_positions: int = 5                         # 최대 동시 보유 종목
    min_position_pct: float = 0.05               # 최소 투자 비율 5%
    max_position_pct: float = 0.20               # 최대 투자 비율 20%
    buy_score_threshold: float = 75.0             # 매수 점수 기준
    commission_rate: float = BACKTEST_COMMISSION_PCT   # 수수료 0.1%
    slippage_rate: float = BACKTEST_SLIPPAGE_PCT       # 슬리피지 0.5% (NEW-02: 이전 0.1%)
    warmup_periods: int = 200                      # 지표 계산을 위한 워밍업 기간 (200일)
    # [NEXT-01] 실거래 엔진과 청산 로직 일치
    atr_sl_multiplier: float = ATR_SL_MULTIPLIER   # ATR SL 승수 (SL = entry − 1.5 × ATR14)
    partial_tp_pct: float = PARTIAL_TP_PCT         # 분할 익절 트리거 (+3%)
    trailing_stop_pct: float = TRAILING_STOP_PCT   # 추적 청산 비율 (고점 대비 -2%)
    strategy_type: str = "momentum"                # 전략 유형 (momentum / reversion / breakout)


@dataclass
class TradeRecord:
    """거래 기록"""
    symbol: str
    action: str                   # BUY / SELL
    signal_type: str              # STOP_LOSS / TRAILING_STOP / TAKE_PROFIT / PARTIAL_TP / SELL / BUY
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

    [NEXT-01] 실거래 엔진과 동일한 청산 로직 적용:
      - ATR14 동적 SL (entry 시점에 계산·고정)
      - 분할 익절(+3%) → 추적 청산(-2% from peak)
      - bar 저가로 SL 검출, 고가로 TP 검출

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

    # ──────────────────────────────────────────────────────────────────────
    # [NEXT-01] ATR14 계산 (pandas DataFrame 입력)
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """
        ATR(Average True Range) 계산.

        Args:
            df:     OHLCV DataFrame (high, low, close 컬럼 필수)
            period: ATR 기간 (기본 14)

        Returns:
            ATR 값 (float) 또는 None (데이터 부족 / 이상값)
        """
        if len(df) < period + 1:
            return None
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        tr_list: List[float] = []
        for idx in range(1, len(highs)):
            tr = max(
                float(highs[idx]) - float(lows[idx]),
                abs(float(highs[idx]) - float(closes[idx - 1])),
                abs(float(lows[idx]) - float(closes[idx - 1])),
            )
            tr_list.append(tr)
        if len(tr_list) < period:
            return None
        atr = float(np.mean(tr_list[-period:]))
        return atr if atr > 0 else None

    # ──────────────────────────────────────────────────────────────────────
    # 내부 헬퍼: 단일 포지션 청산 레코드 생성 + 자본 정산
    # ──────────────────────────────────────────────────────────────────────
    def _close_position_shares(
        self,
        pos: dict,
        n_shares: int,
        exit_raw_price: float,
        signal_type: str,
        bar_idx: int,
        df: pd.DataFrame,
        capital: float,
        daily_pnl: float,
        trade_records: List[TradeRecord],
        symbol: str,
    ) -> Tuple[float, float]:
        """
        n_shares 만큼 청산하고 (capital, daily_pnl) 을 반환한다.
        pos 의 qty 와 entry_commission 을 in-place 로 갱신한다.
        """
        if n_shares <= 0:
            return capital, daily_pnl

        exit_price = exit_raw_price * (1 - self.config.slippage_rate)
        commission = exit_price * n_shares * self.config.commission_rate

        # entry_commission 은 주당 비용으로 할당
        entry_comm_per_share = pos['entry_commission'] / max(pos['entry_qty'], 1)
        allocated_entry_comm = entry_comm_per_share * n_shares

        pnl = ((exit_price - pos['entry_price']) * n_shares
               - commission - allocated_entry_comm)
        pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']

        capital += exit_price * n_shares - commission
        daily_pnl += pnl

        entry_date_str = str(
            df.index[pos['entry_idx']]
            if hasattr(df.index, '__getitem__') else pos['entry_idx']
        )
        exit_date_str = str(
            df.index[bar_idx]
            if hasattr(df.index, '__getitem__') else bar_idx
        )
        trade_records.append(TradeRecord(
            symbol=symbol,
            action="SELL",
            signal_type=signal_type,
            entry_price=pos['entry_price'],
            exit_price=round(exit_price, 4),
            quantity=n_shares,
            entry_date=entry_date_str,
            exit_date=exit_date_str,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct * 100, 2),
            commission=round(commission + allocated_entry_comm, 2),
            score_at_entry=pos.get('score', 0),
            hold_days=bar_idx - pos['entry_idx'],
        ))

        # pos 내 잔여 수량·수수료 갱신
        pos['qty'] -= n_shares
        pos['entry_commission'] -= allocated_entry_comm

        return capital, daily_pnl

    # ──────────────────────────────────────────────────────────────────────
    # 메인 백테스트 루프
    # ──────────────────────────────────────────────────────────────────────
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
            symbol:          종목 심볼
            df:              OHLCV 데이터 (close, open, high, low, volume 컬럼 필수)
            news_sentiment:  뉴스 감성 고정값 (-1.0 ~ 1.0)
            revenue_growth:  매출 성장률 (%)
            eps_growth:      EPS 성장률 (%)

        Returns:
            BacktestResult
        """
        if len(df) < self.config.warmup_periods:
            raise ValueError(
                f"데이터 부족: {len(df)}행 (최소 {self.config.warmup_periods}행 필요)"
            )

        # 상태 초기화
        capital = self.config.initial_capital
        equity_curve = [capital]
        # 포지션 dict 구조:
        #   symbol, qty, entry_qty, entry_price, entry_idx, entry_commission,
        #   score, sl_price, highest_price, partial_tp_done
        positions: List[dict] = []
        trade_records: List[TradeRecord] = []
        daily_start_capital = capital
        daily_pnl = 0.0

        logger.info(f"백테스트 시작 - {symbol}, {len(df)}일 데이터")

        for i in range(self.config.warmup_periods, len(df)):
            row = df.iloc[i]
            current_price = float(row['close'])
            bar_high = float(row.get('high', current_price))
            bar_low = float(row.get('low', current_price))
            window_df = df.iloc[:i + 1]

            # ── 1. 기존 포지션 청산 조건 확인 ──────────────────────────
            closed_positions = []

            for pos in positions:
                entry_price = pos['entry_price']

                # 1-a. 고점 갱신
                if bar_high > pos['highest_price']:
                    pos['highest_price'] = bar_high

                # 1-b. 분할 익절 완료 후: 추적 청산선 갱신
                if pos['partial_tp_done']:
                    trailing_sl = pos['highest_price'] * (1 - self.config.trailing_stop_pct)
                    if trailing_sl > pos['sl_price']:
                        pos['sl_price'] = trailing_sl

                sl_price = pos['sl_price']
                partial_tp_price = entry_price * (1 + self.config.partial_tp_pct)
                full_tp_price = entry_price * (1 + self.config.take_profit_pct)

                # ── 우선순위 1: SL (bar 저가 기준) ──────────────────────
                if bar_low <= sl_price:
                    sl_label = "TRAILING_STOP" if pos['partial_tp_done'] else "STOP_LOSS"
                    # 실현 가격: SL 가격 (단, 갭다운 시 bar_open 사용)
                    bar_open = float(row.get('open', current_price))
                    realized_sl = min(sl_price, bar_open)  # 갭다운 보호
                    capital, daily_pnl = self._close_position_shares(
                        pos=pos,
                        n_shares=pos['qty'],
                        exit_raw_price=realized_sl,
                        signal_type=sl_label,
                        bar_idx=i,
                        df=df,
                        capital=capital,
                        daily_pnl=daily_pnl,
                        trade_records=trade_records,
                        symbol=symbol,
                    )
                    closed_positions.append(pos)
                    continue  # 다음 포지션으로

                # ── 우선순위 2: 분할 익절 (bar 고가 기준, 미완료 시) ──────
                if not pos['partial_tp_done'] and bar_high >= partial_tp_price:
                    partial_qty = max(1, pos['qty'] // 2)
                    capital, daily_pnl = self._close_position_shares(
                        pos=pos,
                        n_shares=partial_qty,
                        exit_raw_price=partial_tp_price,
                        signal_type="PARTIAL_TP",
                        bar_idx=i,
                        df=df,
                        capital=capital,
                        daily_pnl=daily_pnl,
                        trade_records=trade_records,
                        symbol=symbol,
                    )
                    pos['partial_tp_done'] = True
                    # 추적 청산선 초기화: 고점 기준
                    pos['sl_price'] = pos['highest_price'] * (1 - self.config.trailing_stop_pct)

                    # 분할 매도 직후 잔여 수량이 0 이하면 포지션 종료
                    if pos['qty'] <= 0:
                        closed_positions.append(pos)
                        continue

                    # 같은 bar 에서 전체 TP 도달 여부 추가 확인
                    if bar_high >= full_tp_price:
                        capital, daily_pnl = self._close_position_shares(
                            pos=pos,
                            n_shares=pos['qty'],
                            exit_raw_price=full_tp_price,
                            signal_type="TAKE_PROFIT",
                            bar_idx=i,
                            df=df,
                            capital=capital,
                            daily_pnl=daily_pnl,
                            trade_records=trade_records,
                            symbol=symbol,
                        )
                        closed_positions.append(pos)
                    continue

                # ── 우선순위 3: 전체 익절 (분할 완료 후 또는 직접 TP) ─────
                if bar_high >= full_tp_price:
                    capital, daily_pnl = self._close_position_shares(
                        pos=pos,
                        n_shares=pos['qty'],
                        exit_raw_price=full_tp_price,
                        signal_type="TAKE_PROFIT",
                        bar_idx=i,
                        df=df,
                        capital=capital,
                        daily_pnl=daily_pnl,
                        trade_records=trade_records,
                        symbol=symbol,
                    )
                    closed_positions.append(pos)

            for pos in closed_positions:
                if pos in positions:
                    positions.remove(pos)

            # ── 2. 일일 손실 한도 초과 시 신규 매수 중단 ──────────────────
            daily_loss_pct = daily_pnl / daily_start_capital if daily_start_capital > 0 else 0
            if daily_loss_pct <= -self.config.max_daily_loss_pct:
                equity_curve.append(capital + sum(
                    current_price * p['qty'] for p in positions
                ))
                continue

            # ── 3. 매수 시그널 확인 (최대 포지션 미만인 경우) ──────────────
            if len(positions) < self.config.max_positions:
                try:
                    # [NEXT-01] strategy_type 전달
                    signal = self.signal_generator.generate_buy_signal(
                        symbol=symbol,
                        df=window_df,
                        news_sentiment=news_sentiment,
                        news_count=0,
                        revenue_growth=revenue_growth,
                        eps_growth=eps_growth,
                        strategy_type=self.config.strategy_type,
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

                            # [NEXT-01] ATR 기반 동적 SL 계산
                            atr = self._calculate_atr(window_df, period=14)
                            if atr is not None:
                                sl_price = buy_price - (self.config.atr_sl_multiplier * atr)
                                logger.debug(
                                    f"[ATR SL] {symbol} entry={buy_price:.2f} "
                                    f"atr={atr:.4f} sl={sl_price:.2f}"
                                )
                            else:
                                # fallback: 고정 -stop_loss_pct%
                                sl_price = buy_price * (1 - self.config.stop_loss_pct)
                                logger.debug(
                                    f"[Fixed SL fallback] {symbol} entry={buy_price:.2f} "
                                    f"sl={sl_price:.2f}"
                                )

                            positions.append({
                                'symbol': symbol,
                                'qty': qty,
                                'entry_qty': qty,            # 분할 익절 비율 계산용
                                'entry_price': buy_price,
                                'entry_idx': i,
                                'entry_commission': entry_commission,
                                'score': signal.score,
                                'sl_price': sl_price,        # [NEXT-01] ATR 기반 동적 SL
                                'highest_price': buy_price,  # [NEXT-01] 추적 청산 기준 고점
                                'partial_tp_done': False,    # [NEXT-01] 분할 익절 완료 여부
                            })

                except Exception as e:
                    logger.debug(f"시그널 생성 오류 (i={i}): {e}")

            # ── 4. 자산 곡선 업데이트 ──────────────────────────────────────
            unrealized = sum(current_price * p['qty'] for p in positions)
            equity_curve.append(capital + unrealized)

            # ── 5. 날짜 변경 시 일일 손익 리셋 ───────────────────────────────
            # 일봉 시뮬레이션: 매 bar 마다 일일 손익 리셋
            if i % 1 == 0:
                daily_start_capital = capital + unrealized
                daily_pnl = 0.0

        # ── 잔여 포지션 마지막 가격으로 강제 청산 ──────────────────────────
        last_price = float(df.iloc[-1]['close'])
        last_idx = len(df) - 1
        for pos in positions:
            if pos['qty'] <= 0:
                continue
            exit_price = last_price * (1 - self.config.slippage_rate)
            entry_comm_per_share = pos['entry_commission'] / max(pos['entry_qty'], 1)
            allocated_entry_comm = entry_comm_per_share * pos['qty']
            commission = exit_price * pos['qty'] * self.config.commission_rate
            pnl = ((exit_price - pos['entry_price']) * pos['qty']
                   - commission - allocated_entry_comm)
            pnl_pct_actual = (exit_price - pos['entry_price']) / pos['entry_price']
            capital += exit_price * pos['qty'] - commission
            hold_days = last_idx - pos['entry_idx']
            trade_records.append(TradeRecord(
                symbol=symbol,
                action="SELL",
                signal_type="END_OF_TEST",
                entry_price=pos['entry_price'],
                exit_price=round(exit_price, 4),
                quantity=pos['qty'],
                entry_date=str(pos['entry_idx']),
                exit_date="END",
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct_actual * 100, 2),
                commission=round(commission + allocated_entry_comm, 2),
                score_at_entry=pos.get('score', 0),
                hold_days=hold_days,
            ))
        equity_curve.append(capital)

        # ── 성능 지표 계산 ──────────────────────────────────────────────────
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
        # ── 수익률 ─────────────────────────────────────────────────────────
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100
        years = max(total_days / 252, 0.001)
        annualized_return_pct = ((final_capital / initial_capital) ** (1 / years) - 1) * 100

        # ── 최대 낙폭 ──────────────────────────────────────────────────────
        equity_arr = np.array(equity_curve)
        rolling_max = np.maximum.accumulate(equity_arr)
        drawdown_curve = (equity_arr - rolling_max) / rolling_max * 100
        max_drawdown_pct = float(abs(drawdown_curve.min()))

        # ── 샤프 지수 ──────────────────────────────────────────────────────
        if len(equity_arr) > 1:
            daily_returns = np.diff(equity_arr) / equity_arr[:-1]
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            risk_free_daily = 0.04 / 252  # 연 4% 무위험 수익률
            if std_return > 0:
                sharpe_ratio = (mean_return - risk_free_daily) / std_return * np.sqrt(252)
            else:
                sharpe_ratio = 0.0

            # ── 소르티노 지수 (하방 변동성만) ────────────────────────────
            downside_returns = daily_returns[daily_returns < risk_free_daily]
            downside_std = np.std(downside_returns) if len(downside_returns) > 0 else std_return
            sortino_ratio = (
                (mean_return - risk_free_daily) / downside_std * np.sqrt(252)
                if downside_std > 0 else 0.0
            )
        else:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0

        # ── 거래 통계 ──────────────────────────────────────────────────────
        closed_trades = [t for t in trade_records if t.action == "SELL"]
        total_trades = len(closed_trades)

        win_trades = [t for t in closed_trades if t.pnl > 0]
        loss_trades = [t for t in closed_trades if t.pnl <= 0]

        win_rate_pct = len(win_trades) / total_trades * 100 if total_trades > 0 else 0.0

        total_profit = sum(t.pnl for t in win_trades) if win_trades else 0.0
        total_loss = abs(sum(t.pnl for t in loss_trades)) if loss_trades else 0.0
        profit_factor = (
            total_profit / total_loss if total_loss > 0
            else float('inf') if total_profit > 0 else 0.0
        )

        avg_profit_pct = np.mean([t.pnl_pct for t in win_trades]) if win_trades else 0.0
        avg_loss_pct = np.mean([t.pnl_pct for t in loss_trades]) if loss_trades else 0.0
        avg_hold_days = np.mean([t.hold_days for t in closed_trades]) if closed_trades else 0.0

        # ── 전략 유효성 검증 ───────────────────────────────────────────────
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

    def optimize_score_threshold(
        self,
        symbol: str,
        df: pd.DataFrame,
        threshold_range: Tuple[float, float] = (55.0, 85.0),
        step: float = 5.0,
        **run_kwargs,
    ) -> Dict[str, object]:
        """
        매수 점수 임계값(buy_score_threshold) 최적화 (NEW-03)

        지정된 범위를 step 단위로 탐색하여 Sharpe 비율이 가장 높은
        임계값과 그 결과를 반환합니다.

        Args:
            symbol:          종목 심볼
            df:              OHLCV 데이터
            threshold_range: (최솟값, 최댓값) — 기본 (55, 85)
            step:            탐색 간격 — 기본 5
            **run_kwargs:    run() 에 추가로 전달할 인자

        Returns:
            {
                'best_threshold': float,
                'best_sharpe':    float,
                'all_results':    {threshold: BacktestResult},
            }
        """
        low, high = threshold_range
        thresholds = []
        t = low
        while t <= high + 1e-9:
            thresholds.append(round(t, 2))
            t += step

        all_results: Dict[float, BacktestResult] = {}
        best_threshold = thresholds[0]
        best_sharpe = float('-inf')

        logger.info(f"[optimize_score_threshold] {symbol} — 탐색 범위 {thresholds}")

        for threshold in thresholds:
            # 임시로 설정 교체
            original_threshold = self.config.buy_score_threshold
            self.config.buy_score_threshold = threshold
            self._setup_components()

            try:
                result = self.run(symbol=symbol, df=df, **run_kwargs)
                all_results[threshold] = result

                logger.info(
                    f"  threshold={threshold:.0f}: Sharpe={result.sharpe_ratio:.3f}, "
                    f"Win={result.win_rate_pct:.1f}%, MDD={result.max_drawdown_pct:.1f}%, "
                    f"Trades={result.total_trades}"
                )

                if result.sharpe_ratio > best_sharpe and result.total_trades >= self.MIN_TRADES:
                    best_sharpe = result.sharpe_ratio
                    best_threshold = threshold

            except Exception as e:
                logger.warning(f"  threshold={threshold:.0f}: 오류 — {e}")
            finally:
                self.config.buy_score_threshold = original_threshold
                self._setup_components()

        logger.info(
            f"[optimize_score_threshold] 최적 임계값: {best_threshold:.0f} "
            f"(Sharpe={best_sharpe:.3f})"
        )

        return {
            'best_threshold': best_threshold,
            'best_sharpe': best_sharpe,
            'all_results': all_results,
        }
