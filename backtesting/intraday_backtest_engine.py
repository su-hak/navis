"""
5분봉 인트라데이 백테스트 엔진 (Intraday Backtest Engine)

[NEXT-02] Look-ahead bias 제거를 위한 장중 5분봉 기반 백테스트

## 배경
일봉 백테스트는 하루의 고가·저가·종가를 동시에 알고 진입 여부를 결정하지만,
실제 거래에서는 장중에 결정을 내려야 한다. 이 오차(Look-ahead bias)가 쌓이면
백테스트 Sharpe 1.6 → 실거래 Sharpe 0.7 같은 괴리가 발생한다.

## 실거래 로직 재현
  1. 갭 감지: 당일 시가 vs 전일 종가 비교 (≥ gap_threshold_pct%)
  2. 진입: 장중 시가 대비 +spike_trigger_pct% 상승 시점 포착
  3. SL: 진입가 − ATR14 × atr_sl_multiplier (진입 시 계산·고정)
  4. 추적 청산: 분할 익절(+partial_tp_pct) → 고점 대비 -trailing_stop_pct% 추적
  5. 전체 익절: +take_profit_pct%

## 사용법
    loader = IntradayDataLoader(api_key, api_secret)
    intraday = loader.load_5min_bars(["AAPL"], start="2023-01-01", end="2024-01-01")

    engine = IntradayBacktestEngine(config)
    result = engine.run(
        symbol="AAPL",
        daily_df=daily_df,          # 일봉 DataFrame (ATR·워밍업용)
        intraday_by_date=intraday["AAPL"],  # {date: 5min_DataFrame}
    )
    print(result.summary())

    # 일봉 백테스트와 비교 (look-ahead bias 정량화)
    daily_result = BacktestEngine(daily_config).run("AAPL", daily_df)
    comparison = engine.compare_with_daily(result, daily_result)
    print(comparison)
"""
import sys
import os
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# ────────────────────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class IntradayBacktestConfig:
    """5분봉 인트라데이 백테스트 설정"""
    # ── 자본·리스크 ─────────────────────────────────────────────────────────
    initial_capital: float = 1_000_000.0
    max_positions: int = 5
    min_position_pct: float = 0.05
    max_position_pct: float = 0.20
    commission_rate: float = BACKTEST_COMMISSION_PCT
    slippage_rate: float = BACKTEST_SLIPPAGE_PCT
    max_daily_loss_pct: float = 0.05

    # ── 진입 조건 ─────────────────────────────────────────────────────────
    gap_threshold_pct: float = 3.0       # 시가 갭 임계값 (%) - 기획서: 3%
    spike_trigger_pct: float = 1.5       # 장중 시가 대비 스파이크 트리거 (%) - 기획서: 1.5%
    warmup_periods: int = 200            # 일봉 워밍업 기간 (ATR 계산용)
    buy_score_threshold: float = 75.0    # 전략 엔진 매수 점수 기준

    # ── 청산 조건 (실거래 엔진과 동일) ──────────────────────────────────────
    atr_sl_multiplier: float = ATR_SL_MULTIPLIER   # SL = entry − 1.5 × ATR14
    partial_tp_pct: float = PARTIAL_TP_PCT          # +3% 분할 익절
    trailing_stop_pct: float = TRAILING_STOP_PCT    # 분할 익절 후 고점 대비 -2% 추적
    take_profit_pct: float = TAKE_PROFIT_PCT        # +6% 전체 익절
    stop_loss_pct: float = STOP_LOSS_PCT            # ATR 미계산 시 폴백 SL

    # ── 장 마감 처리 ─────────────────────────────────────────────────────
    eod_force_close: bool = False        # True: EOD 강제 청산 / False: 다음 날 연장
    eod_hour: int = 15                   # 장 마감 시각 (ET) — 기본 15:55 기준
    eod_minute: int = 55

    # ── 전략 유형 ────────────────────────────────────────────────────────
    strategy_type: str = "momentum"


# ────────────────────────────────────────────────────────────────────────────
# 결과 모델 (일봉 엔진의 TradeRecord / BacktestResult 재사용)
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class IntradayTradeRecord:
    """인트라데이 거래 기록"""
    symbol: str
    action: str                    # BUY / SELL
    signal_type: str               # GAP_SPIKE / STOP_LOSS / TRAILING_STOP /
                                   # PARTIAL_TP / TAKE_PROFIT / EOD_CLOSE / END_OF_TEST
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    entry_datetime: str            # 5분봉 진입 시각
    exit_datetime: Optional[str]
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    score_at_entry: float = 0.0
    gap_pct: float = 0.0           # 진입 당일 갭 (%)
    spike_pct: float = 0.0         # 진입 시점의 장중 스파이크 (%)
    hold_bars_5min: int = 0        # 5분봉 보유 기간
    hold_days: float = 0.0


@dataclass
class IntradayBacktestResult:
    """5분봉 백테스트 결과"""
    # 수익성
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float

    # 리스크
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float

    # 거래 통계
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate_pct: float
    profit_factor: float
    avg_profit_pct: float
    avg_loss_pct: float
    avg_hold_days: float

    # 진입 품질
    avg_gap_pct: float = 0.0       # 평균 진입 갭 (%)
    avg_spike_pct: float = 0.0     # 평균 진입 스파이크 (%)
    gap_days_scanned: int = 0      # 갭 감지된 날 수
    entry_hit_rate_pct: float = 0.0  # 갭일 중 실제 진입 성공 비율 (%)

    # 상세 기록
    trade_records: List[IntradayTradeRecord] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)

    # 유효성
    passed: bool = False
    fail_reasons: List[str] = field(default_factory=list)

    # 일봉 백테스트 비교 (compare_with_daily() 결과 저장용)
    daily_sharpe: Optional[float] = None
    lookahead_bias_sharpe: Optional[float] = None  # intraday - daily (음수면 일봉이 과대평가)

    # 검증 기준
    MIN_WIN_RATE = 40.0
    MIN_PROFIT_FACTOR = 1.0
    MAX_DRAWDOWN_LIMIT = 30.0
    MIN_TRADES = 5

    def summary(self) -> str:
        """결과 요약"""
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"{'='*65}",
            f"5분봉 인트라데이 백테스트 결과 [{status}]",
            f"{'='*65}",
            f"초기 자본:         ${self.initial_capital:>12,.0f}",
            f"최종 자본:         ${self.final_capital:>12,.0f}",
            f"총 수익률:         {self.total_return_pct:>+10.2f}%",
            f"연환산 수익률:     {self.annualized_return_pct:>+10.2f}%",
            f"최대 낙폭:         {self.max_drawdown_pct:>10.2f}%",
            f"샤프 지수:         {self.sharpe_ratio:>10.3f}",
            f"{'─'*65}",
            f"총 거래:           {self.total_trades:>10d}회",
            f"승률:              {self.win_rate_pct:>10.1f}%",
            f"손익비:            {self.profit_factor:>10.3f}",
            f"평균 수익률:       {self.avg_profit_pct:>+10.2f}%",
            f"평균 손실률:       {self.avg_loss_pct:>+10.2f}%",
            f"평균 보유일:       {self.avg_hold_days:>10.1f}일",
            f"{'─'*65}",
            f"갭 감지일:         {self.gap_days_scanned:>10d}일",
            f"진입 성공률:       {self.entry_hit_rate_pct:>10.1f}%",
            f"평균 진입 갭:      {self.avg_gap_pct:>+10.2f}%",
            f"평균 진입 스파이크: {self.avg_spike_pct:>+10.2f}%",
        ]
        if self.daily_sharpe is not None:
            lines += [
                f"{'─'*65}",
                f"[비교] 일봉 샤프:  {self.daily_sharpe:>10.3f}",
                f"[비교] 5분봉 샤프: {self.sharpe_ratio:>10.3f}",
                f"[비교] 괴리(bias): {self.lookahead_bias_sharpe:>+10.3f}  "
                + ("(일봉 과대평가)" if self.lookahead_bias_sharpe and self.lookahead_bias_sharpe < 0 else ""),
            ]
        if self.fail_reasons:
            lines += [f"{'─'*65}", "실패 사유:"]
            for r in self.fail_reasons:
                lines.append(f"  - {r}")
        lines.append(f"{'='*65}")
        return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────
# 데이터 로더
# ────────────────────────────────────────────────────────────────────────────

class IntradayDataLoader:
    """
    5분봉 과거 데이터 수집기

    Alpaca API로 5분봉 데이터를 수집하고 날짜별로 정리합니다.

    반환 형식:
        {symbol: {trading_date: pd.DataFrame(timestamp, open, high, low, close, volume)}}
    """

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def load_5min_bars(
        self,
        symbols: List[str],
        start: str,   # 'YYYY-MM-DD'
        end: str,
        timezone: str = "America/New_York",
    ) -> Dict[str, Dict[date, pd.DataFrame]]:
        """
        Alpaca로 5분봉 OHLCV 수집 후 날짜별로 분류.

        Args:
            symbols:  종목 심볼 리스트
            start:    시작일 'YYYY-MM-DD'
            end:      종료일 'YYYY-MM-DD'
            timezone: 장 타임존 (기본: 'America/New_York')

        Returns:
            {symbol: {trading_date: DataFrame}}
            DataFrame columns: timestamp(index), open, high, low, close, volume
        """
        try:
            from alpaca.data import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            import pytz
        except ImportError as e:
            raise ImportError(f"alpaca-py / pytz 설치 필요: {e}")

        client = StockHistoricalDataClient(self.api_key, self.api_secret)
        tz = pytz.timezone(timezone)

        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame(5, TimeFrameUnit.Minute),
            start=datetime.strptime(start, "%Y-%m-%d"),
            end=datetime.strptime(end, "%Y-%m-%d"),
            feed="iex",   # SIP는 유료, IEX는 무료
        )

        logger.info(f"5분봉 데이터 수집: {symbols} {start} ~ {end}")
        raw = client.get_stock_bars(req)

        result: Dict[str, Dict[date, pd.DataFrame]] = {}

        for sym in symbols:
            if sym not in raw:
                logger.warning(f"{sym}: 5분봉 데이터 없음")
                continue

            rows = []
            for b in raw[sym]:
                ts = b.timestamp
                # Alpaca 타임스탬프는 UTC — ET로 변환
                if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                    ts_et = ts.astimezone(tz)
                else:
                    ts_et = tz.localize(ts)
                rows.append({
                    'timestamp': ts_et,
                    'open': float(b.open),
                    'high': float(b.high),
                    'low': float(b.low),
                    'close': float(b.close),
                    'volume': int(b.volume),
                    'trading_date': ts_et.date(),
                })

            if not rows:
                continue

            df_all = pd.DataFrame(rows)
            df_all.set_index('timestamp', inplace=True)

            # 날짜별 분류
            by_date: Dict[date, pd.DataFrame] = {}
            for d, grp in df_all.groupby('trading_date'):
                day_df = grp.drop(columns=['trading_date']).sort_index()
                by_date[d] = day_df

            result[sym] = by_date
            logger.info(f"{sym}: {len(by_date)}일치 5분봉 데이터 수집 완료")

        return result

    def load_daily_bars(
        self,
        symbols: List[str],
        start: str,
        end: str,
    ) -> Dict[str, pd.DataFrame]:
        """
        일봉 데이터 수집 (ATR 계산·워밍업용).

        Returns:
            {symbol: DataFrame(date_index, open, high, low, close, volume)}
        """
        try:
            from alpaca.data import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
        except ImportError as e:
            raise ImportError(f"alpaca-py 설치 필요: {e}")

        client = StockHistoricalDataClient(self.api_key, self.api_secret)
        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.strptime(start, "%Y-%m-%d"),
            end=datetime.strptime(end, "%Y-%m-%d"),
            feed="iex",
        )
        raw = client.get_stock_bars(req)

        result = {}
        for sym in symbols:
            if sym not in raw:
                continue
            rows = []
            for b in raw[sym]:
                d = b.timestamp.date() if hasattr(b.timestamp, 'date') else b.timestamp
                rows.append({
                    'date': d,
                    'open': float(b.open),
                    'high': float(b.high),
                    'low': float(b.low),
                    'close': float(b.close),
                    'volume': int(b.volume),
                })
            if rows:
                df = pd.DataFrame(rows).sort_values('date')
                df.set_index('date', inplace=True)
                result[sym] = df
        return result


# ────────────────────────────────────────────────────────────────────────────
# 백테스트 엔진
# ────────────────────────────────────────────────────────────────────────────

class IntradayBacktestEngine:
    """
    5분봉 기반 인트라데이 백테스트 엔진.

    Look-ahead bias 없이 실거래 로직을 정확히 재현:
    - 갭 감지 → 장중 스파이크 포착 → ATR SL 설정 → 분할 익절 → 추적 청산
    - 5분봉 bar 의 low/high 로 SL/TP 검출 (일봉보다 정확)

    일봉 백테스트와 결과를 비교해 look-ahead bias 를 정량화할 수 있습니다.
    """

    MIN_WIN_RATE = 40.0
    MIN_PROFIT_FACTOR = 1.0
    MAX_DRAWDOWN_LIMIT = 30.0
    MIN_TRADES = 5

    def __init__(self, config: Optional[IntradayBacktestConfig] = None):
        self.config = config or IntradayBacktestConfig()
        self._setup_signal_generator()

    def _setup_signal_generator(self):
        """전략 엔진 초기화 (선택적 - signal_generator 없으면 score 체크 생략)"""
        try:
            from strategy_engine.signals.signal_generator import SignalGenerator, TradingConditions
            conditions = TradingConditions(
                buy_score_threshold=self.config.buy_score_threshold,
                take_profit_pct=self.config.take_profit_pct,
                stop_loss_pct=-self.config.stop_loss_pct,
            )
            self.signal_generator = SignalGenerator(conditions=conditions)
        except Exception as e:
            logger.warning(f"SignalGenerator 초기화 실패 (score 체크 비활성화): {e}")
            self.signal_generator = None

    # ── ATR 계산 ────────────────────────────────────────────────────────────

    @staticmethod
    def _calculate_atr(
        daily_df: pd.DataFrame,
        up_to_idx: int,
        period: int = 14,
    ) -> Optional[float]:
        """
        일봉 DataFrame 에서 ATR14 계산 (인덱스 0 ~ up_to_idx 사용).

        Args:
            daily_df:   일봉 DataFrame (high, low, close 컬럼)
            up_to_idx:  계산에 사용할 마지막 인덱스 (포함)
            period:     ATR 기간

        Returns:
            ATR float 또는 None
        """
        end = up_to_idx + 1
        start = max(0, end - (period + 50))  # 여유 있게 슬라이스
        sub = daily_df.iloc[start:end]
        if len(sub) < period + 1:
            return None
        highs = sub['high'].values
        lows = sub['low'].values
        closes = sub['close'].values
        tr_list: List[float] = []
        for k in range(1, len(highs)):
            tr = max(
                float(highs[k]) - float(lows[k]),
                abs(float(highs[k]) - float(closes[k - 1])),
                abs(float(lows[k]) - float(closes[k - 1])),
            )
            tr_list.append(tr)
        if len(tr_list) < period:
            return None
        atr = float(np.mean(tr_list[-period:]))
        return atr if atr > 0 else None

    # ── 청산 헬퍼 ────────────────────────────────────────────────────────────

    def _close_shares(
        self,
        pos: dict,
        n_shares: int,
        exit_raw_price: float,
        signal_type: str,
        exit_dt: str,
        capital: float,
        daily_pnl: float,
        trade_records: List[IntradayTradeRecord],
    ) -> Tuple[float, float]:
        """
        n_shares 만큼 청산. capital / daily_pnl 을 갱신하여 반환.
        pos 의 qty / entry_commission 을 in-place 갱신.
        """
        if n_shares <= 0:
            return capital, daily_pnl

        exit_price = exit_raw_price * (1 - self.config.slippage_rate)
        commission = exit_price * n_shares * self.config.commission_rate
        entry_comm_per_share = pos['entry_commission'] / max(pos['entry_qty'], 1)
        alloc_entry_comm = entry_comm_per_share * n_shares

        pnl = (exit_price - pos['entry_price']) * n_shares - commission - alloc_entry_comm
        pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']

        capital += exit_price * n_shares - commission
        daily_pnl += pnl

        trade_records.append(IntradayTradeRecord(
            symbol=pos['symbol'],
            action="SELL",
            signal_type=signal_type,
            entry_price=pos['entry_price'],
            exit_price=round(exit_price, 4),
            quantity=n_shares,
            entry_datetime=pos['entry_datetime'],
            exit_datetime=exit_dt,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct * 100, 2),
            commission=round(commission + alloc_entry_comm, 2),
            score_at_entry=pos.get('score', 0.0),
            gap_pct=pos.get('gap_pct', 0.0),
            spike_pct=pos.get('spike_pct', 0.0),
            hold_bars_5min=pos.get('entry_bar_count', 0),
            hold_days=pos.get('hold_days', 0.0),
        ))

        pos['qty'] -= n_shares
        pos['entry_commission'] -= alloc_entry_comm
        return capital, daily_pnl

    # ── 5분봉 청산 루프 ──────────────────────────────────────────────────────

    def _run_exit_on_5min(
        self,
        pos: dict,
        five_min_df: pd.DataFrame,
        start_bar_idx: int,
        capital: float,
        daily_pnl: float,
        trade_records: List[IntradayTradeRecord],
        eod_cutoff_time: Optional[datetime] = None,
    ) -> Tuple[float, float, bool]:
        """
        5분봉 bar 를 순회하며 pos 청산 조건을 확인.

        Args:
            pos:            포지션 dict (in-place 수정)
            five_min_df:    당일 5분봉 DataFrame
            start_bar_idx:  시작 bar 인덱스 (진입 bar 다음부터)
            capital:        현재 자본
            daily_pnl:      당일 누적 손익
            trade_records:  거래 기록 리스트 (append)
            eod_cutoff_time: 장 마감 강제 청산 시각 (None 이면 당일 청산 안 함)

        Returns:
            (capital, daily_pnl, is_closed)
        """
        entry_price = pos['entry_price']
        partial_tp_price = entry_price * (1 + self.config.partial_tp_pct)
        full_tp_price = entry_price * (1 + self.config.take_profit_pct)

        bars = five_min_df.iloc[start_bar_idx:]

        for bar_idx, (ts, bar) in enumerate(bars.iterrows()):
            bar_high = float(bar['high'])
            bar_low = float(bar['low'])
            bar_open = float(bar.get('open', bar['close']))
            ts_str = str(ts)

            # 장 마감 강제 청산
            if eod_cutoff_time is not None:
                bar_ts = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
                try:
                    bar_naive = bar_ts.replace(tzinfo=None)
                    cutoff_naive = eod_cutoff_time.replace(tzinfo=None)
                    if bar_naive >= cutoff_naive:
                        capital, daily_pnl = self._close_shares(
                            pos=pos, n_shares=pos['qty'],
                            exit_raw_price=float(bar['close']),
                            signal_type="EOD_CLOSE",
                            exit_dt=ts_str,
                            capital=capital, daily_pnl=daily_pnl,
                            trade_records=trade_records,
                        )
                        return capital, daily_pnl, True
                except Exception:
                    pass

            # 1. 고점 갱신
            if bar_high > pos['highest_price']:
                pos['highest_price'] = bar_high

            # 2. 추적 청산선 갱신 (분할 익절 완료 후)
            if pos['partial_tp_done']:
                trailing_sl = pos['highest_price'] * (1 - self.config.trailing_stop_pct)
                if trailing_sl > pos['sl_price']:
                    pos['sl_price'] = trailing_sl

            sl_price = pos['sl_price']

            # 3. SL 체크 (bar 저가 기준)
            if bar_low <= sl_price:
                sl_label = "TRAILING_STOP" if pos['partial_tp_done'] else "STOP_LOSS"
                realized_sl = min(sl_price, bar_open)  # 갭다운 보호
                capital, daily_pnl = self._close_shares(
                    pos=pos, n_shares=pos['qty'],
                    exit_raw_price=realized_sl,
                    signal_type=sl_label,
                    exit_dt=ts_str,
                    capital=capital, daily_pnl=daily_pnl,
                    trade_records=trade_records,
                )
                return capital, daily_pnl, True

            # 4. 분할 익절 (bar 고가 기준, 미완료 시)
            if not pos['partial_tp_done'] and bar_high >= partial_tp_price:
                partial_qty = max(1, pos['qty'] // 2)
                capital, daily_pnl = self._close_shares(
                    pos=pos, n_shares=partial_qty,
                    exit_raw_price=partial_tp_price,
                    signal_type="PARTIAL_TP",
                    exit_dt=ts_str,
                    capital=capital, daily_pnl=daily_pnl,
                    trade_records=trade_records,
                )
                pos['partial_tp_done'] = True
                pos['sl_price'] = pos['highest_price'] * (1 - self.config.trailing_stop_pct)

                if pos['qty'] <= 0:
                    return capital, daily_pnl, True

                # 같은 bar 에서 전체 TP 도달 확인
                if bar_high >= full_tp_price:
                    capital, daily_pnl = self._close_shares(
                        pos=pos, n_shares=pos['qty'],
                        exit_raw_price=full_tp_price,
                        signal_type="TAKE_PROFIT",
                        exit_dt=ts_str,
                        capital=capital, daily_pnl=daily_pnl,
                        trade_records=trade_records,
                    )
                    return capital, daily_pnl, True
                continue

            # 5. 전체 익절
            if bar_high >= full_tp_price:
                capital, daily_pnl = self._close_shares(
                    pos=pos, n_shares=pos['qty'],
                    exit_raw_price=full_tp_price,
                    signal_type="TAKE_PROFIT",
                    exit_dt=ts_str,
                    capital=capital, daily_pnl=daily_pnl,
                    trade_records=trade_records,
                )
                return capital, daily_pnl, True

        # 당일 미청산
        return capital, daily_pnl, False

    # ── 메인 백테스트 루프 ──────────────────────────────────────────────────

    def run(
        self,
        symbol: str,
        daily_df: pd.DataFrame,
        intraday_by_date: Dict[date, pd.DataFrame],
        news_sentiment: Optional[float] = None,
        revenue_growth: Optional[float] = None,
        eps_growth: Optional[float] = None,
    ) -> IntradayBacktestResult:
        """
        5분봉 인트라데이 백테스트 실행.

        Args:
            symbol:            종목 심볼
            daily_df:          일봉 DataFrame (date index, open/high/low/close/volume)
                               — ATR14 계산·워밍업·다일 보유 포지션 관리용
            intraday_by_date:  {trading_date: 5분봉 DataFrame}
                               — IntradayDataLoader.load_5min_bars() 결과
            news_sentiment:    고정 뉴스 감성 (-1.0 ~ 1.0)
            revenue_growth:    매출 성장률 (%)
            eps_growth:        EPS 성장률 (%)

        Returns:
            IntradayBacktestResult
        """
        if len(daily_df) < self.config.warmup_periods:
            raise ValueError(
                f"일봉 데이터 부족: {len(daily_df)}행 (최소 {self.config.warmup_periods}행 필요)"
            )

        capital = self.config.initial_capital
        equity_curve = [capital]
        positions: List[dict] = []
        trade_records: List[IntradayTradeRecord] = []
        daily_start_capital = capital
        daily_pnl = 0.0
        gap_days_scanned = 0
        entries_made = 0

        logger.info(
            f"[IntradayBacktest] {symbol} 시작 | "
            f"일봉 {len(daily_df)}행 | 5분봉 날짜 {len(intraday_by_date)}일"
        )

        # 일봉 인덱스가 date 타입인지 확인
        daily_dates = daily_df.index.tolist()

        for i in range(self.config.warmup_periods, len(daily_df)):
            daily_row = daily_df.iloc[i]
            current_date = daily_dates[i]
            current_price = float(daily_row['close'])
            daily_bar_high = float(daily_row.get('high', current_price))
            daily_bar_low = float(daily_row.get('low', current_price))

            # ── 1. 기존 포지션 청산 체크 (일봉 기준 — 5분봉 없는 날) ─────────
            closed_positions = []
            for pos in positions:
                # 이미 당일 5분봉으로 처리된 포지션은 건너뜀
                if pos.get('processed_today'):
                    continue

                entry_price = pos['entry_price']

                # 고점 갱신
                if daily_bar_high > pos['highest_price']:
                    pos['highest_price'] = daily_bar_high

                # 추적 청산선 갱신
                if pos['partial_tp_done']:
                    trailing_sl = pos['highest_price'] * (1 - self.config.trailing_stop_pct)
                    if trailing_sl > pos['sl_price']:
                        pos['sl_price'] = trailing_sl

                sl_price = pos['sl_price']
                partial_tp_price = entry_price * (1 + self.config.partial_tp_pct)
                full_tp_price = entry_price * (1 + self.config.take_profit_pct)

                # SL (일봉 저가 기준)
                if daily_bar_low <= sl_price:
                    sl_label = "TRAILING_STOP" if pos['partial_tp_done'] else "STOP_LOSS"
                    bar_open = float(daily_row.get('open', current_price))
                    realized_sl = min(sl_price, bar_open)
                    capital, daily_pnl = self._close_shares(
                        pos=pos, n_shares=pos['qty'],
                        exit_raw_price=realized_sl,
                        signal_type=sl_label,
                        exit_dt=str(current_date),
                        capital=capital, daily_pnl=daily_pnl,
                        trade_records=trade_records,
                    )
                    closed_positions.append(pos)
                    continue

                # 분할 익절 (일봉 고가 기준)
                if not pos['partial_tp_done'] and daily_bar_high >= partial_tp_price:
                    partial_qty = max(1, pos['qty'] // 2)
                    capital, daily_pnl = self._close_shares(
                        pos=pos, n_shares=partial_qty,
                        exit_raw_price=partial_tp_price,
                        signal_type="PARTIAL_TP",
                        exit_dt=str(current_date),
                        capital=capital, daily_pnl=daily_pnl,
                        trade_records=trade_records,
                    )
                    pos['partial_tp_done'] = True
                    pos['sl_price'] = pos['highest_price'] * (1 - self.config.trailing_stop_pct)
                    if pos['qty'] <= 0:
                        closed_positions.append(pos)
                        continue
                    if daily_bar_high >= full_tp_price:
                        capital, daily_pnl = self._close_shares(
                            pos=pos, n_shares=pos['qty'],
                            exit_raw_price=full_tp_price,
                            signal_type="TAKE_PROFIT",
                            exit_dt=str(current_date),
                            capital=capital, daily_pnl=daily_pnl,
                            trade_records=trade_records,
                        )
                        closed_positions.append(pos)
                    continue

                # 전체 익절
                if daily_bar_high >= full_tp_price:
                    capital, daily_pnl = self._close_shares(
                        pos=pos, n_shares=pos['qty'],
                        exit_raw_price=full_tp_price,
                        signal_type="TAKE_PROFIT",
                        exit_dt=str(current_date),
                        capital=capital, daily_pnl=daily_pnl,
                        trade_records=trade_records,
                    )
                    closed_positions.append(pos)

            for pos in closed_positions:
                if pos in positions:
                    positions.remove(pos)

            # ── 2. 일일 손실 한도 체크 ──────────────────────────────────────
            daily_loss_pct = daily_pnl / daily_start_capital if daily_start_capital > 0 else 0
            if daily_loss_pct <= -self.config.max_daily_loss_pct:
                equity_curve.append(capital + sum(current_price * p['qty'] for p in positions))
                continue

            # ── 3. 갭 감지 + 5분봉 진입 ────────────────────────────────────
            if len(positions) < self.config.max_positions:
                prev_close = float(daily_df.iloc[i - 1]['close'])
                day_open = float(daily_row.get('open', current_price))

                gap_pct = (day_open - prev_close) / prev_close * 100 if prev_close > 0 else 0.0

                if gap_pct >= self.config.gap_threshold_pct:
                    gap_days_scanned += 1

                    # 당일 5분봉 데이터 확인
                    day_key = current_date if isinstance(current_date, date) else (
                        current_date.date() if hasattr(current_date, 'date') else current_date
                    )
                    five_min_df = intraday_by_date.get(day_key)

                    if five_min_df is not None and len(five_min_df) > 0:
                        # 전략 엔진 점수 체크 (선택적)
                        window_df = daily_df.iloc[:i + 1]
                        score_ok = True
                        score_val = 0.0
                        if self.signal_generator is not None:
                            try:
                                sig = self.signal_generator.generate_buy_signal(
                                    symbol=symbol,
                                    df=window_df,
                                    news_sentiment=news_sentiment,
                                    news_count=0,
                                    revenue_growth=revenue_growth,
                                    eps_growth=eps_growth,
                                    strategy_type=self.config.strategy_type,
                                )
                                if sig is None or sig.score < self.config.buy_score_threshold:
                                    score_ok = False
                                else:
                                    score_val = sig.score
                            except Exception as e:
                                logger.debug(f"[IntradayBT] 점수 계산 오류: {e}")

                        if score_ok:
                            # 스파이크 트리거 탐색
                            spike_trigger_price = day_open * (1 + self.config.spike_trigger_pct / 100)

                            for bar_idx, (ts, bar) in enumerate(five_min_df.iterrows()):
                                bar_close = float(bar['close'])
                                bar_high = float(bar['high'])

                                # 스파이크 조건: bar 고가가 트리거 가격 이상
                                if bar_high >= spike_trigger_price:
                                    # 진입 가격: 트리거 가격 (bar 내에서 도달 시점)
                                    entry_raw = spike_trigger_price
                                    buy_price = entry_raw * (1 + self.config.slippage_rate)

                                    # 포지션 사이징
                                    pos_pct = self.config.max_position_pct - len(positions) * 0.03
                                    pos_pct = max(self.config.min_position_pct, pos_pct)
                                    invest_amount = capital * pos_pct
                                    qty = int(invest_amount / buy_price)

                                    if qty <= 0 or capital < buy_price * qty:
                                        break

                                    entry_commission = buy_price * qty * self.config.commission_rate
                                    capital -= buy_price * qty + entry_commission

                                    # ATR SL 계산
                                    atr = self._calculate_atr(daily_df, i - 1, period=14)
                                    if atr is not None:
                                        sl_price = buy_price - (self.config.atr_sl_multiplier * atr)
                                    else:
                                        sl_price = buy_price * (1 - self.config.stop_loss_pct)

                                    spike_actual_pct = (buy_price / day_open - 1) * 100

                                    pos = {
                                        'symbol': symbol,
                                        'qty': qty,
                                        'entry_qty': qty,
                                        'entry_price': buy_price,
                                        'entry_datetime': str(ts),
                                        'entry_daily_idx': i,
                                        'entry_commission': entry_commission,
                                        'score': score_val,
                                        'sl_price': sl_price,
                                        'highest_price': buy_price,
                                        'partial_tp_done': False,
                                        'gap_pct': gap_pct,
                                        'spike_pct': spike_actual_pct,
                                        'entry_bar_count': 0,
                                        'hold_days': 0.0,
                                        'processed_today': True,
                                    }

                                    entries_made += 1
                                    logger.debug(
                                        f"[GAP_SPIKE] {symbol} {ts} | "
                                        f"gap={gap_pct:.1f}% spike={spike_actual_pct:.1f}% "
                                        f"entry={buy_price:.2f} sl={sl_price:.2f}"
                                    )

                                    # 진입 bar 이후 당일 5분봉으로 청산 시도
                                    eod_cutoff = None
                                    if self.config.eod_force_close:
                                        # 장 마감 시각 계산 (ET 기준)
                                        try:
                                            import pytz
                                            tz = pytz.timezone("America/New_York")
                                            ts_dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
                                            eod_cutoff = ts_dt.replace(
                                                hour=self.config.eod_hour,
                                                minute=self.config.eod_minute,
                                                second=0,
                                            )
                                        except Exception:
                                            pass

                                    capital, daily_pnl, is_closed = self._run_exit_on_5min(
                                        pos=pos,
                                        five_min_df=five_min_df,
                                        start_bar_idx=bar_idx + 1,
                                        capital=capital,
                                        daily_pnl=daily_pnl,
                                        trade_records=trade_records,
                                        eod_cutoff_time=eod_cutoff,
                                    )

                                    if not is_closed:
                                        # 미청산 → 다음 날 일봉 관리
                                        pos['processed_today'] = False
                                        positions.append(pos)
                                    break  # 하루에 동일 종목 1회 진입

            # processed_today 플래그 초기화
            for pos in positions:
                pos['processed_today'] = False

            # ── 4. 자산 곡선 업데이트 ────────────────────────────────────────
            unrealized = sum(current_price * p['qty'] for p in positions)
            equity_curve.append(capital + unrealized)

            # 일일 손익 리셋
            daily_start_capital = capital + unrealized
            daily_pnl = 0.0

        # ── 잔여 포지션 강제 청산 ──────────────────────────────────────────
        last_price = float(daily_df.iloc[-1]['close'])
        last_date = str(daily_dates[-1])
        for pos in positions:
            if pos['qty'] <= 0:
                continue
            exit_price = last_price * (1 - self.config.slippage_rate)
            entry_comm_per_share = pos['entry_commission'] / max(pos['entry_qty'], 1)
            alloc_ec = entry_comm_per_share * pos['qty']
            commission = exit_price * pos['qty'] * self.config.commission_rate
            pnl = (exit_price - pos['entry_price']) * pos['qty'] - commission - alloc_ec
            pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']
            capital += exit_price * pos['qty'] - commission
            trade_records.append(IntradayTradeRecord(
                symbol=symbol,
                action="SELL",
                signal_type="END_OF_TEST",
                entry_price=pos['entry_price'],
                exit_price=round(exit_price, 4),
                quantity=pos['qty'],
                entry_datetime=pos.get('entry_datetime', ''),
                exit_datetime=last_date,
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct * 100, 2),
                commission=round(commission + alloc_ec, 2),
                score_at_entry=pos.get('score', 0.0),
                gap_pct=pos.get('gap_pct', 0.0),
                spike_pct=pos.get('spike_pct', 0.0),
                hold_bars_5min=pos.get('entry_bar_count', 0),
                hold_days=pos.get('hold_days', 0.0),
            ))
        equity_curve.append(capital)

        # ── 결과 계산 ──────────────────────────────────────────────────────
        entry_hit_rate = (entries_made / gap_days_scanned * 100) if gap_days_scanned > 0 else 0.0
        closed_sell = [t for t in trade_records if t.action == "SELL"]
        avg_gap = float(np.mean([t.gap_pct for t in closed_sell])) if closed_sell else 0.0
        avg_spike = float(np.mean([t.spike_pct for t in closed_sell])) if closed_sell else 0.0

        return self._calculate_metrics(
            initial_capital=self.config.initial_capital,
            final_capital=capital,
            equity_curve=equity_curve,
            trade_records=trade_records,
            total_days=len(daily_df) - self.config.warmup_periods,
            gap_days_scanned=gap_days_scanned,
            entry_hit_rate_pct=entry_hit_rate,
            avg_gap_pct=avg_gap,
            avg_spike_pct=avg_spike,
        )

    def _calculate_metrics(
        self,
        initial_capital: float,
        final_capital: float,
        equity_curve: List[float],
        trade_records: List[IntradayTradeRecord],
        total_days: int,
        gap_days_scanned: int = 0,
        entry_hit_rate_pct: float = 0.0,
        avg_gap_pct: float = 0.0,
        avg_spike_pct: float = 0.0,
    ) -> IntradayBacktestResult:
        """성능 지표 계산"""
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100
        years = max(total_days / 252, 0.001)
        annualized_return_pct = ((final_capital / initial_capital) ** (1 / years) - 1) * 100

        equity_arr = np.array(equity_curve)
        rolling_max = np.maximum.accumulate(equity_arr)
        drawdown_curve = (equity_arr - rolling_max) / rolling_max * 100
        max_drawdown_pct = float(abs(drawdown_curve.min()))

        if len(equity_arr) > 1:
            daily_returns = np.diff(equity_arr) / equity_arr[:-1]
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            risk_free_daily = 0.04 / 252
            sharpe_ratio = (
                (mean_return - risk_free_daily) / std_return * np.sqrt(252)
                if std_return > 0 else 0.0
            )
            downside_rets = daily_returns[daily_returns < risk_free_daily]
            downside_std = np.std(downside_rets) if len(downside_rets) > 0 else std_return
            sortino_ratio = (
                (mean_return - risk_free_daily) / downside_std * np.sqrt(252)
                if downside_std > 0 else 0.0
            )
        else:
            sharpe_ratio = sortino_ratio = 0.0

        closed = [t for t in trade_records if t.action == "SELL"]
        total_trades = len(closed)
        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl <= 0]
        win_rate_pct = len(wins) / total_trades * 100 if total_trades > 0 else 0.0
        total_profit = sum(t.pnl for t in wins) if wins else 0.0
        total_loss = abs(sum(t.pnl for t in losses)) if losses else 0.0
        profit_factor = (
            total_profit / total_loss if total_loss > 0
            else float('inf') if total_profit > 0 else 0.0
        )
        avg_profit_pct = float(np.mean([t.pnl_pct for t in wins])) if wins else 0.0
        avg_loss_pct = float(np.mean([t.pnl_pct for t in losses])) if losses else 0.0
        avg_hold_days = float(np.mean([t.hold_days for t in closed])) if closed else 0.0

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

        return IntradayBacktestResult(
            initial_capital=initial_capital,
            final_capital=round(final_capital, 2),
            total_return_pct=round(total_return_pct, 2),
            annualized_return_pct=round(annualized_return_pct, 2),
            max_drawdown_pct=round(max_drawdown_pct, 2),
            sharpe_ratio=round(sharpe_ratio, 3),
            sortino_ratio=round(sortino_ratio, 3),
            total_trades=total_trades,
            win_trades=len(wins),
            loss_trades=len(losses),
            win_rate_pct=round(win_rate_pct, 1),
            profit_factor=round(profit_factor, 3),
            avg_profit_pct=round(avg_profit_pct, 2),
            avg_loss_pct=round(avg_loss_pct, 2),
            avg_hold_days=round(avg_hold_days, 1),
            avg_gap_pct=round(avg_gap_pct, 2),
            avg_spike_pct=round(avg_spike_pct, 2),
            gap_days_scanned=gap_days_scanned,
            entry_hit_rate_pct=round(entry_hit_rate_pct, 1),
            trade_records=trade_records,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve.tolist(),
            passed=passed,
            fail_reasons=fail_reasons,
        )

    # ── Look-ahead bias 정량화 ────────────────────────────────────────────────

    @staticmethod
    def compare_with_daily(
        intraday_result: IntradayBacktestResult,
        daily_sharpe: float,
        daily_total_return_pct: float,
        daily_max_drawdown_pct: float,
    ) -> dict:
        """
        5분봉 vs 일봉 백테스트 결과 비교 (look-ahead bias 정량화).

        Args:
            intraday_result:        5분봉 백테스트 결과
            daily_sharpe:           일봉 백테스트 샤프 지수
            daily_total_return_pct: 일봉 총 수익률
            daily_max_drawdown_pct: 일봉 최대 낙폭

        Returns:
            {
              'lookahead_bias_sharpe': float,   # 양수면 5분봉이 더 나쁨 (일봉 과대평가)
              'sharpe_5min':           float,
              'sharpe_daily':          float,
              'return_diff_pct':       float,
              'mdd_diff_pct':          float,
              'interpretation':        str,
            }
        """
        bias = intraday_result.sharpe_ratio - daily_sharpe
        ret_diff = intraday_result.total_return_pct - daily_total_return_pct
        mdd_diff = intraday_result.max_drawdown_pct - daily_max_drawdown_pct

        if abs(bias) < 0.1:
            interp = "일봉 백테스트 신뢰도 높음 (look-ahead bias 미미)"
        elif bias < 0:
            interp = (
                f"일봉 백테스트가 Sharpe를 {abs(bias):.2f} 과대평가 중. "
                f"실거래 예상 성과가 더 낮을 수 있음. 5분봉 기준으로 전략 재검토 권장."
            )
        else:
            interp = (
                f"5분봉 백테스트가 일봉보다 Sharpe {bias:.2f} 우수. "
                f"일봉 back-test 이미 보수적 추정이었음."
            )

        # 결과를 intraday_result 에도 저장
        intraday_result.daily_sharpe = daily_sharpe
        intraday_result.lookahead_bias_sharpe = bias

        return {
            'lookahead_bias_sharpe': round(bias, 3),
            'sharpe_5min': intraday_result.sharpe_ratio,
            'sharpe_daily': daily_sharpe,
            'return_diff_pct': round(ret_diff, 2),
            'mdd_diff_pct': round(mdd_diff, 2),
            'interpretation': interp,
        }
