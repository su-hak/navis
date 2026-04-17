"""
백테스팅 엔진 Phase 1 (NEW-01)

전략 파라미터 검증:
  - gap_threshold, volume_ratio, entry_trigger, atr_multiplier
합격 기준:
  - Sharpe Ratio ≥ 1.5
  - MDD ≤ 20%
  - Profit Factor ≥ 1.5
"""
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """백테스트 설정"""
    # 전략 파라미터 (최적화 대상)
    gap_threshold_pct: float = 3.0       # 갭 임계값 (%)
    volume_ratio_threshold: float = 3.0  # 거래량 비율
    entry_trigger_pct: float = 1.5       # 진입 트리거 변동 (%)
    atr_sl_multiplier: float = 1.5       # ATR SL 배수
    atr_tp_multiplier: float = 3.0       # ATR TP 배수 (trailing stop 전 초기 TP)
    trailing_stop_pct: float = 2.0       # 트레일링 스탑 (%)
    partial_tp_pct: float = 3.0          # 부분 익절 임계값 (%)

    # 리스크 파라미터
    position_pct: float = 0.10           # 포지션 사이징 (자산 대비 %)
    max_positions: int = 5               # 최대 동시 포지션

    # 거래 비용
    slippage_pct: float = 0.1            # 슬리피지 (%)
    commission_pct: float = 0.0          # 커미션 (Alpaca 무료)

    # 기간
    start_date: Optional[str] = None     # 'YYYY-MM-DD'
    end_date: Optional[str] = None


@dataclass
class Trade:
    """거래 기록"""
    symbol: str
    entry_date: datetime
    exit_date: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    side: str = "BUY"
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """백테스트 결과"""
    config: BacktestConfig

    # 기본 통계
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_return_pct: float = 0.0

    # 리스크 지표
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    profit_factor: float = 0.0
    win_rate_pct: float = 0.0

    # 평균 거래 지표
    avg_holding_minutes: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0

    # 거래 목록
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    @property
    def passes_criteria(self) -> bool:
        """합격 기준 충족 여부"""
        return (
            self.sharpe_ratio >= 1.5
            and self.max_drawdown_pct <= 20.0
            and self.profit_factor >= 1.5
        )

    def summary(self) -> str:
        status = "PASS" if self.passes_criteria else "FAIL"
        return (
            f"[{status}] 총거래:{self.total_trades} | "
            f"승률:{self.win_rate_pct:.1f}% | "
            f"Sharpe:{self.sharpe_ratio:.2f} | "
            f"MDD:{self.max_drawdown_pct:.1f}% | "
            f"PF:{self.profit_factor:.2f} | "
            f"수익률:{self.total_return_pct:.1f}%"
        )


class BacktestEngine:
    """
    백테스팅 엔진 Phase 1

    OHLCV 데이터를 기반으로 갭 업 전략을 시뮬레이션합니다.
    거래비용(슬리피지), 포지션 사이징, ATR 기반 SL/TP를 포함합니다.
    """

    def __init__(self, initial_capital: float = 100_000.0):
        self.initial_capital = initial_capital

    # ──────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────

    def run(
        self,
        daily_bars: Dict[str, List[dict]],
        config: BacktestConfig,
    ) -> BacktestResult:
        """
        백테스트 실행

        Args:
            daily_bars: {symbol: [{date, open, high, low, close, volume}, ...]}
                        날짜 오름차순 정렬 필수
            config: 백테스트 설정

        Returns:
            BacktestResult
        """
        result = BacktestResult(config=config)
        equity = self.initial_capital
        equity_curve = [equity]
        positions: Dict[str, dict] = {}   # {symbol: position_info}
        all_dates = self._get_all_dates(daily_bars)

        for i, date in enumerate(all_dates):
            if i == 0:
                continue

            # ── 보유 포지션 SL/TP 체크 ─────────────────────
            closed_today = []
            for sym, pos in list(positions.items()):
                bar = self._get_bar(daily_bars, sym, date)
                if bar is None:
                    continue

                exit_price, exit_reason = self._check_exit(bar, pos, config)
                if exit_price is not None:
                    trade = self._close_position(pos, exit_price, date, exit_reason, config)
                    result.trades.append(trade)
                    equity += trade.pnl
                    closed_today.append(sym)
                else:
                    # 최고가 갱신 (trailing stop용)
                    pos['highest_price'] = max(pos['highest_price'], bar['high'])

            for sym in closed_today:
                del positions[sym]

            # ── 신규 진입 스캔 ─────────────────────────────
            if len(positions) < config.max_positions:
                for sym, bars_list in daily_bars.items():
                    if sym in positions:
                        continue

                    bar_idx = self._find_bar_idx(bars_list, date)
                    if bar_idx is None or bar_idx == 0:
                        continue

                    today_bar = bars_list[bar_idx]
                    prev_bar = bars_list[bar_idx - 1]

                    # 갭 계산
                    gap_pct = (today_bar['open'] - prev_bar['close']) / prev_bar['close'] * 100
                    if gap_pct < config.gap_threshold_pct:
                        continue

                    # 거래량 비율
                    avg_vol = self._avg_volume(bars_list, bar_idx - 1, 20)
                    if avg_vol <= 0 or today_bar['volume'] / avg_vol < config.volume_ratio_threshold:
                        continue

                    # 진입 트리거: open 기준 entry_trigger_pct 상승
                    entry_price_raw = today_bar['open'] * (1 + config.entry_trigger_pct / 100)
                    if today_bar['high'] < entry_price_raw:
                        continue

                    # 슬리피지 적용
                    entry_price = entry_price_raw * (1 + config.slippage_pct / 100)

                    # ATR 계산
                    atr = self._calculate_atr(bars_list, bar_idx - 1)

                    # 포지션 사이징
                    invest_amount = equity * config.position_pct
                    quantity = int(invest_amount / entry_price)
                    if quantity <= 0:
                        continue

                    # SL/TP 계산
                    if atr > 0:
                        sl_price = entry_price - config.atr_sl_multiplier * atr
                        tp_price = entry_price + config.atr_tp_multiplier * atr
                    else:
                        sl_price = entry_price * 0.98
                        tp_price = entry_price * 1.05

                    positions[sym] = {
                        'symbol': sym,
                        'entry_date': date,
                        'entry_price': entry_price,
                        'quantity': quantity,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                        'highest_price': entry_price,
                        'partial_tp_done': False,
                    }

                    if len(positions) >= config.max_positions:
                        break

            equity_curve.append(equity)

        # ── 미청산 포지션 강제 청산 ───────────────────────
        last_date = all_dates[-1] if all_dates else None
        for sym, pos in positions.items():
            bar = self._get_bar(daily_bars, sym, last_date) if last_date else None
            close_price = bar['close'] if bar else pos['entry_price']
            trade = self._close_position(pos, close_price, last_date, "END_OF_DATA", config)
            result.trades.append(trade)
            equity += trade.pnl

        # ── 지표 계산 ──────────────────────────────────────
        result.equity_curve = equity_curve
        result.total_trades = len(result.trades)
        result.total_return_pct = (equity - self.initial_capital) / self.initial_capital * 100

        self._calculate_metrics(result)
        logger.info(f"백테스트 완료: {result.summary()}")
        return result

    def grid_search(
        self,
        daily_bars: Dict[str, List[dict]],
        param_grid: dict,
    ) -> List[Tuple[BacktestConfig, BacktestResult]]:
        """
        파라미터 그리드 서치

        Args:
            daily_bars: OHLCV 데이터
            param_grid: {
                'gap_threshold_pct': [2, 3, 4, 5],
                'volume_ratio_threshold': [2, 3, 4],
                'entry_trigger_pct': [1.0, 1.5, 2.0, 2.5],
                'atr_sl_multiplier': [1.0, 1.5, 2.0, 2.5],
            }

        Returns:
            [(config, result)] Sharpe 내림차순 정렬
        """
        import itertools

        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        logger.info(f"그리드 서치 시작: {len(combinations)}개 조합")
        results = []

        for combo in combinations:
            params = dict(zip(keys, combo))
            config = BacktestConfig(**params)
            result = self.run(daily_bars, config)
            results.append((config, result))

        results.sort(key=lambda x: x[1].sharpe_ratio, reverse=True)
        logger.info(f"그리드 서치 완료. 최고 Sharpe: {results[0][1].sharpe_ratio:.2f}")
        return results

    # ──────────────────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────────────────

    def _check_exit(self, bar: dict, pos: dict, config: BacktestConfig):
        """청산 조건 확인. (exit_price, reason) 또는 (None, None)"""
        # 손절
        if bar['low'] <= pos['sl_price']:
            return pos['sl_price'], "STOP_LOSS"

        # 부분 익절 (+3%) 후 트레일링 스탑
        if not pos['partial_tp_done']:
            partial_tp_price = pos['entry_price'] * (1 + config.partial_tp_pct / 100)
            if bar['high'] >= partial_tp_price:
                pos['partial_tp_done'] = True
                pos['highest_price'] = max(pos['highest_price'], bar['high'])

        if pos['partial_tp_done']:
            trailing_sl = pos['highest_price'] * (1 - config.trailing_stop_pct / 100)
            if bar['low'] <= trailing_sl:
                return trailing_sl, "TRAILING_STOP"

        return None, None

    def _close_position(
        self, pos: dict, exit_price: float, exit_date, exit_reason: str, config: BacktestConfig
    ) -> Trade:
        """포지션 청산 및 Trade 생성"""
        exit_price_adj = exit_price * (1 - config.slippage_pct / 100)
        gross_pnl = (exit_price_adj - pos['entry_price']) * pos['quantity']
        commission = pos['entry_price'] * pos['quantity'] * config.commission_pct / 100
        pnl = gross_pnl - commission
        pnl_pct = (exit_price_adj / pos['entry_price'] - 1) * 100

        holding_min = 0.0
        if exit_date and isinstance(pos['entry_date'], datetime) and isinstance(exit_date, datetime):
            holding_min = (exit_date - pos['entry_date']).total_seconds() / 60

        return Trade(
            symbol=pos['symbol'],
            entry_date=pos['entry_date'],
            exit_date=exit_date,
            entry_price=pos['entry_price'],
            exit_price=exit_price_adj,
            quantity=pos['quantity'],
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
        )

    def _calculate_metrics(self, result: BacktestResult):
        """Sharpe, MDD, PF, 승률 계산"""
        trades = result.trades
        if not trades:
            return

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]

        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate_pct = len(wins) / len(trades) * 100

        total_win = sum(t.pnl for t in wins)
        total_loss = abs(sum(t.pnl for t in losses))
        result.profit_factor = total_win / total_loss if total_loss > 0 else float('inf')

        result.avg_win_pct = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        result.avg_loss_pct = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        result.avg_holding_minutes = sum(
            (t.exit_date - t.entry_date).total_seconds() / 60
            for t in trades
            if t.exit_date and isinstance(t.entry_date, datetime)
        ) / len(trades)

        # Sharpe (일별 수익률 기준)
        daily_returns = []
        equity = self.initial_capital
        for t in sorted(trades, key=lambda x: x.exit_date or x.entry_date):
            r = t.pnl / equity
            daily_returns.append(r)
            equity += t.pnl

        if len(daily_returns) >= 2:
            mean_r = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_r = math.sqrt(variance)
            result.sharpe_ratio = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0
        else:
            result.sharpe_ratio = 0.0

        # MDD (equity curve 기반)
        peak = self.initial_capital
        max_dd = 0.0
        eq = self.initial_capital
        for t in sorted(trades, key=lambda x: x.exit_date or x.entry_date):
            eq += t.pnl
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown_pct = max_dd

    @staticmethod
    def _get_all_dates(daily_bars: Dict[str, List[dict]]) -> List:
        dates = set()
        for bars in daily_bars.values():
            for b in bars:
                dates.add(b['date'])
        return sorted(dates)

    @staticmethod
    def _get_bar(daily_bars: Dict[str, List[dict]], symbol: str, date) -> Optional[dict]:
        bars = daily_bars.get(symbol, [])
        for b in bars:
            if b['date'] == date:
                return b
        return None

    @staticmethod
    def _find_bar_idx(bars: List[dict], date) -> Optional[int]:
        for i, b in enumerate(bars):
            if b['date'] == date:
                return i
        return None

    @staticmethod
    def _avg_volume(bars: List[dict], up_to_idx: int, period: int = 20) -> float:
        start = max(0, up_to_idx - period)
        subset = bars[start:up_to_idx]
        if not subset:
            return 0.0
        return sum(b['volume'] for b in subset) / len(subset)

    @staticmethod
    def _calculate_atr(bars: List[dict], up_to_idx: int, period: int = 14) -> float:
        if up_to_idx < period + 1:
            return 0.0
        subset = bars[up_to_idx - period: up_to_idx + 1]
        trs = []
        for i in range(1, len(subset)):
            hl = subset[i]['high'] - subset[i]['low']
            hc = abs(subset[i]['high'] - subset[i - 1]['close'])
            lc = abs(subset[i]['low'] - subset[i - 1]['close'])
            trs.append(max(hl, hc, lc))
        return sum(trs) / len(trs) if trs else 0.0
