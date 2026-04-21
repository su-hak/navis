"""
NAVIS Universe Backtest — Phase 3: 메인 백테스트 엔진

NAVIS 종목 선정 시스템(갭+거래량 스크리너)을 과거에 재현하고
선정된 종목의 5분봉으로 실제 진입/청산을 시뮬레이션한다.

실행 순서:
    1. DataCache.build()    → 데이터 수집 & 캐시
    2. HistoricalScreener.run() → 날짜별 워치리스트 생성
    3. UniverseBacktestEngine.run() → 백테스트 실행
    4. PeriodAnalyzer.print_report() → 기간별 성과 출력
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.trading_constants import (
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT,
    ATR_SL_MULTIPLIER,
    TRAILING_STOP_PCT,
    PARTIAL_TP_PCT,
    BACKTEST_SLIPPAGE_PCT,
    BACKTEST_COMMISSION_PCT,
    REGIME_FILTER_ON,
    TIME_STOP_MINUTES,
    TIME_STOP_MIN_PROFIT_PCT,
    NOON_RULE_ENABLED,
    PMS_POSITION_PCT,
    PMS_SL_PCT,
    PMS_PARTIAL_TP1_PCT,
    PMS_PARTIAL_TP1_RATIO,
    PMS_PARTIAL_TP2_PCT,
    PMS_PARTIAL_TP2_RATIO,
    PMS_TRAILING_STOP_PCT,
    PMS_FULL_TP_PCT,
    PMS_ENTRY_START_MINUTE,
    PMS_ENTRY_END_HOUR,
    PMS_ENTRY_END_MINUTE,
    PMS_MORNING_CLOSE_HOUR,
    PMS_MORNING_CLOSE_MINUTE,
    PMS_TIME_STOP_MINUTES,
    PMS_TIME_STOP_LOSS_PCT,
    PMS_MAX_DAILY_LOSS,
)

logger = logging.getLogger(__name__)


@dataclass
class UniverseBacktestConfig:
    # 자본
    initial_capital:        float = 1_000_000.0

    # 포지션 관리
    max_positions:          int   = 5
    max_position_pct:       float = 0.10   # 첫 포지션 10%
    min_position_pct:       float = 0.03   # 최소 3%
    position_step:          float = 0.02   # 포지션 수 증가 시 2%씩 감소

    # 진입 조건
    gap_threshold_pct:      float = 2.0
    spike_trigger_pct:      float = 1.0    # 백테스트 결과 기반: 1.5% → 1.0%
    volume_ratio_threshold: float = 2.0

    # 청산
    take_profit_pct:        float = TAKE_PROFIT_PCT
    stop_loss_pct:          float = STOP_LOSS_PCT
    atr_sl_multiplier:      float = ATR_SL_MULTIPLIER
    trailing_stop_pct:      float = TRAILING_STOP_PCT
    partial_tp_pct:         float = PARTIAL_TP_PCT

    # 일일 한도
    max_daily_loss_pct:     float = 0.05
    max_entries_per_day:    int   = 5

    # 비용
    slippage_rate:          float = BACKTEST_SLIPPAGE_PCT
    commission_rate:        float = BACKTEST_COMMISSION_PCT

    # 기타
    warmup_periods:         int   = 200
    eod_force_close:        bool  = True   # 장 마감 시 강제 청산 여부

    # ── V3: 시장 국면 필터 ────────────────────────────────────────────
    regime_filter_enabled:    bool  = REGIME_FILTER_ON  # SPY > SMA200 = Bull만 진입
    regime_sma50:             bool  = False              # True: SMA200 AND SMA50 이중 기준
    # ── V3: Time Stop (잠자는 포지션 차단) ──────────────────────────
    time_stop_enabled:        bool  = True
    time_stop_minutes:        int   = TIME_STOP_MINUTES           # 45분
    time_stop_min_profit_pct: float = TIME_STOP_MIN_PROFIT_PCT    # 0.5%
    # ── V3: Noon Rule (오후 미수익 청산) ─────────────────────────────
    noon_rule_enabled:        bool  = NOON_RULE_ENABLED

    # ── PMS 모드 ──────────────────────────────────────────────────────
    pms_mode:              bool  = False
    pms_position_pct:      float = PMS_POSITION_PCT        # 0.30
    pms_sl_pct:            float = PMS_SL_PCT              # 0.015
    pms_partial_tp1_pct:   float = PMS_PARTIAL_TP1_PCT     # 0.015
    pms_partial_tp1_ratio: float = PMS_PARTIAL_TP1_RATIO   # 0.40
    pms_partial_tp2_pct:   float = PMS_PARTIAL_TP2_PCT     # 0.025
    pms_partial_tp2_ratio: float = PMS_PARTIAL_TP2_RATIO   # 0.30
    pms_trailing_stop_pct: float = PMS_TRAILING_STOP_PCT   # 0.012
    pms_full_tp_pct:       float = PMS_FULL_TP_PCT         # 0.050
    entry_start_minute:    int   = PMS_ENTRY_START_MINUTE  # 5 (09:35)
    entry_end_hour:        int   = PMS_ENTRY_END_HOUR      # 10
    entry_end_minute:      int   = PMS_ENTRY_END_MINUTE    # 30 (10:30)
    morning_close_enabled: bool  = True                      # PMS Morning Close 활성화 여부
    morning_close_hour:    int   = PMS_MORNING_CLOSE_HOUR  # 11
    morning_close_minute:  int   = PMS_MORNING_CLOSE_MINUTE  # 30
    pms_time_stop_minutes: int   = PMS_TIME_STOP_MINUTES   # 120
    pms_time_stop_loss_pct: float = PMS_TIME_STOP_LOSS_PCT # 0.015
    pms_max_daily_loss:    float = PMS_MAX_DAILY_LOSS      # 0.010

    # ── V4 풀백 진입 ──────────────────────────────────────────────────
    # v4_first_bar_filter: 첫 5분봉 close < open이면 갭 페이드로 판정, 진입 포기
    # v4_pullback: 풀백 감지 후 재돌파 + VWAP 위에서 진입 (v4_first_bar_filter 포함)
    v4_first_bar_filter:   bool  = False
    v4_pullback:           bool  = False
    v4_pullback_pct:       float = 0.005  # spike_high × (1 - 0.5%) 이하 = 풀백 확인
    v4_rebreak_pct:        float = 0.001  # spike_high × (1 + 0.1%) 돌파 = 재진입 트리거
    v4_max_sl_distance:    float = 0.020  # 구조적 SL 거리 > 2% → 셋업 패스
    v4_max_atr_pct:        float = 0.030  # ATR/진입가 > 3% 이면 해당 날 진입 차단
    v4_min_rel_volume:     float = 0.0   # 갭업일 상대 거래량 최소값 (0=비활성, 1.5=20일 평균 150%)

    # ── 리스크 기반 포지션 사이징 ─────────────────────────────────────────
    # 고정 비율(pms_position_pct) 대신 "거래당 리스크 금액"으로 수량 결정.
    # qty = (capital × risk_per_trade_pct) / (entry_price × sl_distance)
    # pms_position_pct는 최대 포지션 상한(cap)으로만 사용됨.
    use_risk_sizing:    bool  = False
    risk_per_trade_pct: float = 0.005   # 거래당 목표 리스크: 자본의 0.5%

    # ── ORB 전략 (Opening Range Breakout, Long) ──────────────────────────
    # 갭 여부와 무관하게 Tier 1 전체를 매일 스캔.
    # OR: 09:30~09:45 ET 첫 3개 5분봉의 고/저점
    # 진입: 09:45 이후 OR_high 상향 돌파 + 거래량 확인
    orb_enabled:              bool  = False
    orb_volume_ratio:         float = 1.5    # OR 평균 거래량의 몇 배 이상 시 유효
    orb_tp_ratio:             float = 1.5    # TP = OR_high + OR_range × orb_tp_ratio
    orb_sl_buffer:            float = 0.001  # SL = OR_low × (1 - orb_sl_buffer)
    orb_position_pct:         float = 0.10   # 기본 포지션 10%
    orb_entry_end_hour:       int   = 11     # 11:00 ET 이후 신규 ORB 진입 금지
    orb_entry_end_minute:     int   = 0
    orb_morning_close_hour:   int   = 11     # 11:30 ET 시간 청산
    orb_morning_close_minute: int   = 30

    # ── V4 Multi-Day Hold ─────────────────────────────────────────────────
    # 진입 로직은 V4와 동일. 인트라데이 TP 제거, 일봉 기준 trailing + 최대 5일 보유.
    v4_multi_day:       bool  = False
    v4_md_trailing_pct: float = 0.030   # 고점 대비 -3.0% trailing stop (일봉 저점 기준)
    v4_md_max_days:     int   = 5       # 최대 보유 거래일 (진입 다음날부터 카운트)
    v4_md_tp1_pct:      float = 0.050   # +5% 도달 시 50% 청산 (1차 TP)
    v4_md_tp2_pct:      float = 0.100   # +10% 도달 시 추가 30% 청산 (2차 TP)

    # ── ITC 전략 (Intraday Trend Continuation) ───────────────────────────
    # 갭 불필요 — 10:30 ET 이후 VWAP 풀백→재돌파 진입. V4 보완 전략.
    use_itc:           bool  = False
    itc_min_gain_pct:  float = 0.015   # 10:30 ET 기준 시가 대비 최소 상승률 (1.5%)
    itc_vwap_band:     float = 0.003   # VWAP ±0.3% = 풀백 인식 범위
    itc_entry_start:   int   = 60      # 진입 허용 시작 (09:30+60분 = 10:30 ET)
    itc_entry_end:     int   = 120     # 진입 허용 종료 (09:30+120분 = 11:30 ET)
    itc_close_hour:    int   = 12      # 시간 청산 (12:00 ET)
    itc_close_minute:  int   = 0

    # ── Earnings Momentum (EM) 필터 ───────────────────────────────────────
    # True: 해당 종목의 실적 발표 후 갭 발생일에만 V4 진입 허용
    use_earnings_filter:   bool  = False
    earnings_cache_path:   str   = "earnings_cache.json"

    # ── 순수 PEAD 진입 (V4 풀백 없이 갭 유지 확인 후 진입) ────────────────
    # use_earnings_filter=True와 함께 사용. V4 pullback 로직을 우회하고
    # 10:00 ET 시점에 갭이 충분히 유지되면 즉시 진입 (홀드 지속성 기반).
    earnings_simple_entry: bool  = False   # True: 순수 PEAD 진입 활성화
    earnings_gap_hold_pct: float = 0.80    # 갭의 80% 이상 유지 → 진입
    earnings_gap_hold_min: int   = 30      # 09:30 + 30분 = 10:00 ET 에서 갭 확인

    # PEAD 진입건 인트라데이 SL 비활성화 (일봉 trailing stop만 사용)
    # True: 5분봉 SL 체크 스킵. 진입가 -10% 극단 하락만 즉시 청산.
    pead_no_intraday_sl:   bool  = False

    # PEAD 전용 일봉 trailing stop (기본 10% — V4 기본 3%보다 넓게 설정)
    # PEAD는 consolidation 후 상승 패턴이므로 일시적 하락에 청산되지 않도록 설정
    pead_trailing_pct:     float = 0.10

    # PEAD 제외 섹터 (GICS 섹터명 리스트 — 빈 리스트 = 제외 없음)
    pead_exclude_sectors:  list  = field(default_factory=list)
    # 섹터 캐시 파일 경로 (earnings_cache_path와 같은 디렉터리에 저장)
    sector_cache_path:     str   = "sector_cache.json"

    # ── Gap Fade Down 전략 (갭다운 반전 Long — Phase 2 주전략) ─────────────
    # 갭다운 -3%+ 발생 후 첫 30분 내 50%+ 회복 확인 → Long 진입
    # 주의: 아래의 gap_fade_enabled(갭업 Short, 폐기)와 별개 전략
    gap_fade_down:              bool  = False
    gap_fade_down_min_gap_pct:  float = 0.030   # 갭다운 최소 크기 -3%
    gap_fade_down_confirm_pct:  float = 0.50    # 진입 트리거: 갭의 50%+ 회복 시 진입
    gap_fade_down_tp1_pct:      float = 0.75    # TP1: 갭의 75% 채움 → 50% 청산
    gap_fade_down_confirm_min:  int   = 30      # 확인 창 30분 (09:30~10:00)
    gap_fade_down_sl_pct:       float = 0.02    # 고정 SL -2% (당일 저점과 비교해 넓은 쪽)
    gap_fade_down_trailing_pct: float = 0.03    # Trailing Stop 3% (TP1 이후 잔여)
    gap_fade_down_max_days:     int   = 5       # 최대 보유 거래일

    # ── 52주 신고가 브레이크아웃 전략 (Phase 2 주전략) ────────────────────
    # 전날 종가가 252거래일 최고가 돌파 + 거래량 확인 → 다음 날 시가 진입
    # 5분봉 불필요, 일봉 기반. 레짐 필터(SPY > SMA200) 적용 — 2022년 자동 차단
    nh52_breakout:          bool  = False
    nh52_lookback:          int   = 252    # 52주 = 252거래일
    nh52_volume_ratio:      float = 1.5    # 거래량 확인 배율 (1.5× 20일 평균)
    nh52_sl_pct:            float = 0.05   # 고정 SL -5%
    nh52_trailing_pct:      float = 0.05   # Trailing Stop 5%
    nh52_max_days:          int   = 10     # 최대 보유 10거래일

    # ── 갭 페이드 전략 (Short 시뮬레이션, 폐기) ──────────────────────────
    # 갭업 후 첫 5분봉 음봉 + VWAP 하향 시 Short 진입, 갭 되돌림 포착
    # V4와 음의 상관관계 — 베어마켓/반전장 헤지 역할
    gap_fade_enabled:          bool  = False
    gap_fade_threshold_pct:    float = 0.040   # 갭업 최소 4%
    gap_fade_tp1_ratio:        float = 0.30    # 갭의 30% 되돌림 = TP1
    gap_fade_tp2_ratio:        float = 0.60    # 갭의 60% 되돌림 = TP2
    gap_fade_tp1_qty_ratio:    float = 0.40    # TP1 시 40% 청산
    gap_fade_tp2_qty_ratio:    float = 0.30    # TP2 시 30% 청산
    gap_fade_morning_close_hour:   int   = 11  # 11:00 ET 시간 청산
    gap_fade_morning_close_minute: int   = 0
    gap_fade_sl_buffer:        float = 0.001   # 첫 바 고점 + 0.1% SL
    gap_fade_position_pct:     float = 0.10    # 기본 포지션 10%


@dataclass
class TradeRecord:
    symbol:      str
    entry_dt:    str
    exit_dt:     str
    entry_price: float
    exit_price:  float
    qty:         int
    pnl:         float
    pnl_pct:     float
    signal_type: str   # STOP_LOSS / TRAILING_STOP / PARTIAL_TP / TAKE_PROFIT / EOD


@dataclass
class UniverseBacktestResult:
    # 수익성
    total_return_pct:     float = 0.0
    annualized_return_pct: float = 0.0
    final_capital:        float = 0.0

    # 리스크
    sharpe_ratio:         float = 0.0
    sortino_ratio:        float = 0.0
    max_drawdown_pct:     float = 0.0
    calmar_ratio:         float = 0.0

    # 거래 통계
    total_trades:         int   = 0
    win_trades:           int   = 0
    loss_trades:          int   = 0
    win_rate_pct:         float = 0.0
    profit_factor:        float = 0.0
    avg_profit_pct:       float = 0.0
    avg_loss_pct:         float = 0.0
    avg_hold_bars:        float = 0.0

    # 스크리닝 통계
    total_days_scanned:   int   = 0
    total_entry_signals:  int   = 0
    entry_hit_rate_pct:   float = 0.0

    # 원시 데이터 (분석용)
    trade_records:        List[dict] = field(default_factory=list)
    equity_curve:         List[Tuple[date, float]] = field(default_factory=list)
    daily_returns:        List[float] = field(default_factory=list)

    # 통과 여부
    passed:               bool  = False

    def summary(self) -> str:
        lines = [
            "=" * 55,
            "  NAVIS 유니버스 백테스트 결과",
            "=" * 55,
            f"  총 수익률       : {self.total_return_pct:+.2f}%",
            f"  연환산 수익률   : {self.annualized_return_pct:+.2f}%",
            f"  최종 자본       : ${self.final_capital:,.0f}",
            f"  Sharpe Ratio    : {self.sharpe_ratio:.3f}",
            f"  Max Drawdown    : {self.max_drawdown_pct:.2f}%",
            f"  Profit Factor   : {self.profit_factor:.2f}",
            f"  승률            : {self.win_rate_pct:.1f}%  "
            f"({self.win_trades}W / {self.loss_trades}L)",
            f"  총 거래수       : {self.total_trades}회",
            f"  스크리닝 감지일 : {self.total_days_scanned}일",
            f"  진입 성공률     : {self.entry_hit_rate_pct:.1f}%",
            f"  {'PASS' if self.passed else 'FAIL'}",
            "=" * 55,
        ]
        return "\n".join(lines)


class UniverseBacktestEngine:
    """
    NAVIS 종목 선정 시스템을 과거 재현하여 전략 전체 성과를 측정한다.

    사용 예:
        from backtesting.universe_backtest import (
            UniverseBacktestEngine, UniverseBacktestConfig,
            DataCache, HistoricalScreener, PeriodAnalyzer
        )

        # 1. 데이터 캐시 빌드 (최초 1회)
        cache = DataCache(api_key, api_secret, cache_dir="cache")
        cache.build(symbols, start="2020-07-27")

        # 2. 백테스트 실행
        engine = UniverseBacktestEngine(config=UniverseBacktestConfig())
        result = engine.run(
            symbols=symbols,
            cache=cache,
            start="2021-01-01",
            end="2025-12-31",
        )
        print(result.summary())

        # 3. 기간별 분석
        analyzer = PeriodAnalyzer(result.trade_records, result.equity_curve)
        analyzer.print_report()
    """

    # 실전 투입 최소 기준
    MIN_SHARPE         = 1.0
    MIN_PROFIT_FACTOR  = 1.3
    MAX_DRAWDOWN_LIMIT = 25.0
    MIN_TRADES         = 30

    def __init__(self, config: Optional[UniverseBacktestConfig] = None):
        self.config = config or UniverseBacktestConfig()
        self.earnings_calendar: Dict[str, List[str]] = self._load_earnings_calendar()
        self.sector_map:        Dict[str, str]        = self._load_sector_cache()

    def _load_sector_cache(self) -> Dict[str, str]:
        """sector_cache.json 로드. 섹터 필터 비활성화 시 빈 딕셔너리 반환."""
        if not self.config.pead_exclude_sectors:
            return {}
        import json
        from pathlib import Path
        path = Path(self.config.sector_cache_path)
        if not path.exists():
            logger.warning(
                f"[UniverseBT] 섹터 캐시 파일 없음: {path} — "
                "--pead-exclude-sectors 사용 전 build_earnings_cache.py --with-sectors 실행하세요"
            )
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        excluded = self.config.pead_exclude_sectors
        filtered = sum(1 for s in data.values() if s in excluded)
        logger.info(
            f"[UniverseBT] 섹터 캐시 로드: {len(data)}종목 | "
            f"제외 대상({excluded}): {filtered}종목"
        )
        return data

    def _load_earnings_calendar(self) -> Dict[str, List[str]]:
        """earnings_cache.json 로드. use_earnings_filter=False 이면 빈 딕셔너리 반환."""
        if not self.config.use_earnings_filter:
            return {}
        import json
        from pathlib import Path
        path = Path(self.config.earnings_cache_path)
        if not path.exists():
            logger.warning(
                f"[UniverseBT] 어닝 캐시 파일 없음: {path} — "
                "backtesting/build_earnings_cache.py 먼저 실행하세요"
            )
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(
            f"[UniverseBT] 어닝 캘린더 로드: {len(data)}종목 "
            f"({path})"
        )
        return data

    def run(
        self,
        symbols:    List[str],
        cache:      "DataCache",
        start:      Optional[str] = None,
        end:        Optional[str] = None,
        spy_daily:  Optional[pd.DataFrame] = None,
    ) -> UniverseBacktestResult:
        """
        유니버스 기반 전체 백테스트 실행.

        Args:
            symbols:   테스트할 종목 리스트
            cache:     DataCache 인스턴스 (데이터 이미 빌드됨)
            start:     백테스트 시작일 (YYYY-MM-DD)
            end:       백테스트 종료일 (YYYY-MM-DD)
            spy_daily: SPY 일봉 DataFrame (index=date, columns=[open,high,low,close,volume])
                       V3 시장 국면 필터에 사용. None 이면 regime 필터 비활성화.
        """
        from .screener import HistoricalScreener

        logger.info(f"[UniverseBT] 시작 | {len(symbols)}종목 | {start} ~ {end}")

        # ── 1. 데이터 로드 ─────────────────────────────────────────────
        logger.info("[UniverseBT] 캐시에서 데이터 로드 중...")
        daily_data:   Dict[str, pd.DataFrame] = {}
        fmin_by_sym:  Dict[str, Dict[date, pd.DataFrame]] = {}

        for sym in symbols:
            df_d = cache.load_daily(sym)
            if df_d is not None and len(df_d) >= self.config.warmup_periods:
                daily_data[sym] = df_d
                df_5 = cache.load_5min_by_date(sym)
                if df_5:
                    fmin_by_sym[sym] = df_5

        logger.info(
            f"[UniverseBT] 일봉 로드: {len(daily_data)}종목 | "
            f"5분봉 로드: {len(fmin_by_sym)}종목"
        )

        if not daily_data:
            logger.error("[UniverseBT] 데이터 없음 — DataCache.build() 먼저 실행하세요")
            return UniverseBacktestResult()

        # ── 2. 과거 스크리닝 재현 ─────────────────────────────────────
        screener = HistoricalScreener(
            gap_threshold=self.config.gap_threshold_pct,
            volume_ratio_threshold=self.config.volume_ratio_threshold,
            gap_fade_down=self.config.gap_fade_down,
            gap_fade_down_min_gap=self.config.gap_fade_down_min_gap_pct * 100,
        )
        screened = screener.run(daily_data, start=start, end=end,
                                warmup_days=self.config.warmup_periods)

        if not screened:
            logger.warning("[UniverseBT] 스크리닝 결과 없음")
            return UniverseBacktestResult()

        # ── 3. SPY 국면 맵 사전 구축 (V3) ──────────────────────────────
        spy_regime_map: Dict[date, bool] = {}
        if self.config.regime_filter_enabled and spy_daily is not None:
            spy_regime_map = self._build_spy_regime(
                spy_daily, use_sma50=self.config.regime_sma50
            )
            bull_days  = sum(1 for v in spy_regime_map.values() if v)
            bear_days  = sum(1 for v in spy_regime_map.values() if not v)
            sma_label  = "SMA200+SMA50" if self.config.regime_sma50 else "SMA200"
            logger.info(
                f"[UniverseBT] SPY 국면 맵 구축 완료 [{sma_label}] | Bull={bull_days}일 Bear={bear_days}일"
            )
        elif self.config.regime_filter_enabled:
            logger.warning(
                "[UniverseBT] regime_filter_enabled=True 이지만 spy_daily 없음 — "
                "필터 비활성화. run(..., spy_daily=spy_df) 로 SPY 데이터를 전달하세요."
            )

        # ── 4. 백테스트 시뮬레이션 ────────────────────────────────────
        capital            = self.config.initial_capital
        positions: List[dict] = []
        trade_records:     List[dict] = []
        equity_curve:      List[Tuple[date, float]] = []
        daily_returns:     List[float] = []
        total_entry_signals = 0
        bear_days_skipped   = 0

        if self.config.orb_enabled or self.config.use_itc or self.config.v4_multi_day or self.config.nh52_breakout:
            # ORB/ITC/Multi-Day: 갭 여부 무관하게 5분봉 데이터가 있는 모든 거래일 포함
            all_fmin_dates: set = set()
            for sym_dates in fmin_by_sym.values():
                all_fmin_dates.update(sym_dates.keys())
            # start/end 필터링 (screener와 동일 기준)
            if start:
                start_date = date.fromisoformat(start) if isinstance(start, str) else start
                all_fmin_dates = {d for d in all_fmin_dates if d >= start_date}
            if end:
                end_date = date.fromisoformat(end) if isinstance(end, str) else end
                all_fmin_dates = {d for d in all_fmin_dates if d <= end_date}
            all_trading_days = sorted(set(screened.keys()) | all_fmin_dates)
        else:
            all_trading_days = sorted(screened.keys())

        for today in all_trading_days:
            day_start_capital = capital
            entries_today     = 0
            daily_pnl         = 0.0

            watchlist = screened.get(today, [])

            # ── 기존 포지션 청산 처리 ────────────────────────────────
            still_open = []
            for pos in positions:
                sym          = pos["symbol"]
                five_min_df  = fmin_by_sym.get(sym, {}).get(today)

                # Multi-Day 모드: 일봉 기준 TP/Trailing/MaxHold 먼저 체크
                # (진입 당일은 positions에 아직 없으므로 여기서는 항상 hold day 처리)
                # GAP_FADE_DOWN 포지션도 EOD 처리 (gap_fade_down 플래그 OR signal_source 확인)
                _use_eod = (
                    self.config.v4_multi_day
                    or pos.get("signal_source") == "GAP_FADE_DOWN"
                    or pos.get("signal_source") == "NH52_BREAKOUT"
                )
                if _use_eod:
                    df_d = daily_data.get(sym)
                    if df_d is not None:
                        capital, daily_pnl, closed = self._process_position_eod(
                            pos, today, df_d, capital, daily_pnl, trade_records
                        )
                        if closed:
                            continue

                if five_min_df is not None and len(five_min_df) > 0:
                    capital, daily_pnl, closed = self._process_position_5min(
                        pos, five_min_df, capital, daily_pnl, trade_records
                    )
                    if not closed:
                        still_open.append(pos)
                else:
                    # 5분봉 없는 날: 일봉으로 처리 (Multi-Day / GAP_FADE_DOWN 제외 — 이미 위에서 처리)
                    if not _use_eod:
                        df_d = daily_data.get(sym)
                        if df_d is not None and today in df_d.index:
                            capital, daily_pnl, closed = self._process_position_daily(
                                pos, df_d.loc[today], capital, daily_pnl, trade_records, str(today)
                            )
                            if not closed:
                                still_open.append(pos)
                        else:
                            still_open.append(pos)
                    else:
                        still_open.append(pos)

            positions = still_open

            # ── 일일 손실 한도 체크 ──────────────────────────────────
            max_daily_loss = (self.config.pms_max_daily_loss if self.config.pms_mode
                              else self.config.max_daily_loss_pct)
            daily_loss_pct = daily_pnl / day_start_capital if day_start_capital > 0 else 0
            if daily_loss_pct <= -max_daily_loss:
                equity_curve.append((today, capital))
                daily_returns.append(daily_pnl / day_start_capital)
                continue

            # ── V3: 시장 국면 필터 ────────────────────────────────────
            # Bear 구간에서는 신규 진입 차단 (기존 포지션 청산은 정상 처리)
            regime_ok = True
            if self.config.regime_filter_enabled and spy_regime_map:
                regime_ok = spy_regime_map.get(today, True)
                if not regime_ok:
                    bear_days_skipped += 1
            self._regime_ok = regime_ok  # _try_earnings_entry 방어 체크용

            # ── 신규 진입 시도 (Bull 국면에만, Gap Fade Down 제외) ──────
            # Gap Fade Down은 Bear 구간에서 오히려 갭다운이 많아 작동 → 필터 우회
            if not regime_ok and not self.config.gap_fade_down:
                # Bear 일: 신규 진입 건너뜀, 자본/equity는 아래에서 기록
                equity_curve.append((today, capital))
                daily_returns.append(
                    (capital - day_start_capital) / day_start_capital
                    if day_start_capital > 0 else 0
                )
                continue

            for candidate in watchlist:
                if len(positions) >= self.config.max_positions:
                    break
                if entries_today >= self.config.max_entries_per_day:
                    break

                sym         = candidate["symbol"]
                day_open    = candidate["day_open"]
                prev_close  = candidate.get("prev_close")
                five_min_df = fmin_by_sym.get(sym, {}).get(today)

                if five_min_df is None or len(five_min_df) == 0:
                    continue

                # 이미 포지션 보유 중인 종목 제외
                if any(p["symbol"] == sym for p in positions):
                    continue

                # Earnings Momentum 필터: 실적 발표 후 갭 발생일이 아니면 스킵
                if self.config.use_earnings_filter:
                    sym_earnings = self.earnings_calendar.get(sym, [])
                    if today.strftime("%Y-%m-%d") not in sym_earnings:
                        continue

                # PEAD 섹터 필터: 제외 섹터 종목 스킵
                if self.config.pead_exclude_sectors and self.sector_map:
                    sym_sector = self.sector_map.get(sym, "Unknown")
                    if sym_sector in self.config.pead_exclude_sectors:
                        continue

                total_entry_signals += 1

                # ATR SL 계산 (일봉 사용)
                df_d = daily_data.get(sym)
                atr  = self._calculate_atr(df_d, today) if df_d is not None else None

                # 상대 거래량 계산 (갭업일 / 20일 평균)
                rel_volume = (
                    self._calculate_rel_volume(df_d, today)
                    if df_d is not None and self.config.v4_min_rel_volume > 0
                    else None
                )

                result = self._try_entry(
                    symbol=sym,
                    day_open=day_open,
                    five_min_df=five_min_df,
                    capital=capital,
                    n_positions=len(positions),
                    atr=atr,
                    prev_close=prev_close,
                    rel_volume=rel_volume,
                )

                if result is not None:
                    pos, cost, remaining_bars = result
                    capital -= cost
                    entries_today += 1
                    daily_pnl -= cost  # 진입 비용 반영

                    # 진입 당일 잔여 5분봉으로 즉시 SL/TP 처리
                    if len(remaining_bars) > 0:
                        capital, daily_pnl, closed = self._process_position_5min(
                            pos, remaining_bars, capital, daily_pnl, trade_records
                        )
                        if not closed:
                            positions.append(pos)
                    else:
                        positions.append(pos)

            # ── ORB 진입 루프 (regime OK인 날만) ─────────────────────
            if self.config.orb_enabled and regime_ok:
                for sym in symbols:
                    if len(positions) >= self.config.max_positions:
                        break
                    if entries_today >= self.config.max_entries_per_day:
                        break

                    # 이미 포지션 보유 중인 종목 제외
                    if any(p["symbol"] == sym for p in positions):
                        continue

                    five_min_df = fmin_by_sym.get(sym, {}).get(today)
                    if five_min_df is None or len(five_min_df) == 0:
                        continue

                    orb_result = self._try_entry_orb(
                        symbol=sym,
                        five_min_df=five_min_df,
                        capital=capital,
                    )

                    if orb_result is not None:
                        pos, cost, remaining_bars = orb_result
                        capital   -= cost
                        entries_today += 1
                        daily_pnl -= cost

                        if len(remaining_bars) > 0:
                            capital, daily_pnl, closed = self._process_position_5min(
                                pos, remaining_bars, capital, daily_pnl, trade_records
                            )
                            if not closed:
                                positions.append(pos)
                        else:
                            positions.append(pos)

            # ── ITC 진입 루프 (regime OK인 날만) ─────────────────────
            if self.config.use_itc and regime_ok:
                for sym in symbols:
                    if len(positions) >= self.config.max_positions:
                        break
                    if entries_today >= self.config.max_entries_per_day:
                        break

                    # 이미 포지션 보유 중인 종목 제외
                    if any(p["symbol"] == sym for p in positions):
                        continue

                    five_min_df = fmin_by_sym.get(sym, {}).get(today)
                    if five_min_df is None or len(five_min_df) == 0:
                        continue

                    # 당일 시가 조회
                    df_d = daily_data.get(sym)
                    if df_d is None or today not in df_d.index:
                        continue
                    day_open_itc = float(df_d.loc[today]["open"])

                    itc_result = self._try_entry_itc(
                        symbol=sym,
                        day_open=day_open_itc,
                        five_min_df=five_min_df,
                        capital=capital,
                    )

                    if itc_result is not None:
                        pos, cost, remaining_bars = itc_result
                        capital       -= cost
                        entries_today += 1
                        daily_pnl     -= cost

                        if len(remaining_bars) > 0:
                            capital, daily_pnl, closed = self._process_position_5min(
                                pos, remaining_bars, capital, daily_pnl, trade_records
                            )
                            if not closed:
                                positions.append(pos)
                        else:
                            positions.append(pos)

            # ── 52주 신고가 브레이크아웃 진입 (전날 신호 → 당일 시가) ─────
            # 5분봉 불필요 — 일봉 데이터만 사용, 레짐 필터는 메인 루프에서 처리
            if self.config.nh52_breakout and regime_ok:
                today_idx = all_trading_days.index(today)
                if today_idx > 0:
                    prev_day = all_trading_days[today_idx - 1]
                    for sym in symbols:
                        if len(positions) >= self.config.max_positions:
                            break
                        if entries_today >= self.config.max_entries_per_day:
                            break
                        if any(p["symbol"] == sym for p in positions):
                            continue

                        df_d = daily_data.get(sym)
                        if df_d is None or prev_day not in df_d.index:
                            continue

                        # 전날 NH52 신호 체크
                        if not self._check_nh52_signal(prev_day, df_d, is_bull=regime_ok):
                            continue

                        # 당일 시가 진입
                        if today not in df_d.index:
                            continue
                        today_bar   = df_d.loc[today]
                        today_open  = float(today_bar.get("open", today_bar["close"]))
                        entry_price = today_open * (1 + self.config.slippage_rate)
                        sl_price    = entry_price * (1 - self.config.nh52_sl_pct)
                        sl_distance = (entry_price - sl_price) / entry_price
                        if sl_distance <= 0:
                            continue

                        qty = int(capital * self.config.pms_position_pct / entry_price)
                        if qty <= 0 or capital < entry_price * qty:
                            continue

                        commission  = entry_price * qty * self.config.commission_rate
                        total_cost  = entry_price * qty + commission
                        capital    -= total_cost
                        entries_today += 1
                        daily_pnl  -= total_cost
                        total_entry_signals += 1

                        pos = {
                            "symbol":          sym,
                            "entry_price":     entry_price,
                            "qty":             qty,
                            "qty_original":    qty,
                            "sl_price":        sl_price,
                            "highest_price":   entry_price,
                            "partial_tp_done": False,
                            "pms_tp1_done":    False,
                            "pms_tp2_done":    False,
                            "md_tp1_done":     False,
                            "md_tp2_done":     False,
                            "hold_days":       0,
                            "entry_dt":        str(today),
                            "signal_source":   "NH52_BREAKOUT",
                        }
                        positions.append(pos)

            # ── 장 마감 강제 청산 ─────────────────────────────────────
            # Multi-Day / GAP_FADE_DOWN / NH52 모드에서는 포지션을 다음 날로 이월
            if self.config.eod_force_close and not self.config.v4_multi_day:
                remaining_pos = []
                for pos in list(positions):
                    # GAP_FADE_DOWN / NH52_BREAKOUT 포지션은 이월 (멀티데이 전략)
                    if pos.get("signal_source") in ("GAP_FADE_DOWN", "NH52_BREAKOUT"):
                        remaining_pos.append(pos)
                        continue
                    sym         = pos["symbol"]
                    five_min_df = fmin_by_sym.get(sym, {}).get(today)
                    eod_price   = self._get_eod_price(five_min_df, daily_data.get(sym), today)
                    if eod_price:
                        capital, daily_pnl = self._close_position(
                            pos, eod_price, "EOD", str(today),
                            capital, daily_pnl, trade_records
                        )
                positions = remaining_pos

            equity_curve.append((today, capital))
            daily_returns.append((capital - day_start_capital) / day_start_capital
                                  if day_start_capital > 0 else 0)

        # ── 5. 성과 지표 계산 ────────────────────────────────────────
        if bear_days_skipped > 0:
            logger.info(
                f"[UniverseBT] Bear 국면 차단: {bear_days_skipped}일 / "
                f"{len(all_trading_days)}일 중 신규 진입 없음"
            )
        return self._calculate_metrics(
            trade_records=trade_records,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            total_days_scanned=len(screened),
            total_entry_signals=total_entry_signals,
            initial_capital=self.config.initial_capital,
        )

    # ── 진입 로직 ─────────────────────────────────────────────────────────

    def _try_entry(
        self,
        symbol:      str,
        day_open:    float,
        five_min_df: pd.DataFrame,
        capital:     float,
        n_positions: int,
        atr:         Optional[float],
        prev_close:  Optional[float] = None,
        rel_volume:  Optional[float] = None,
    ) -> Optional[Tuple[dict, float, pd.DataFrame]]:
        """
        5분봉에서 spike_trigger_pct 도달 여부를 순차 탐색, 진입 시도.

        Returns:
            (position_dict, total_cost, remaining_bars) 또는 None
            remaining_bars: 진입 바 이후의 잔여 5분봉 (당일 SL/TP 처리용)
        """
        # ── Gap Fade Down 진입 (갭다운 반전 Long — Phase 2 주전략) ─────────
        if self.config.gap_fade_down and prev_close is not None:
            return self._try_gap_fade_down_entry(
                symbol, day_open, prev_close, five_min_df, capital
            )

        # ── 순수 PEAD 진입 (earnings_simple_entry 우선) ──────────────────
        # use_earnings_filter=True + earnings_simple_entry=True 조합에서만 동작.
        # V4 풀백 로직을 완전히 우회하고 10:00 ET 갭 유지 확인 후 진입.
        if self.config.earnings_simple_entry and prev_close is not None:
            return self._try_earnings_entry(
                symbol, day_open, prev_close, five_min_df, capital
            )

        # ── V4 풀백 진입 (PMS + v4_pullback 플래그) ─────────────────────
        if self.config.pms_mode and self.config.v4_pullback:
            v4_result = self._try_entry_v4(symbol, day_open, five_min_df, capital, atr=atr, rel_volume=rel_volume)
            if v4_result is not None:
                return v4_result
            # V4 실패(음봉 등) → Gap Fade 시도
            if self.config.gap_fade_enabled and prev_close is not None:
                return self._try_entry_gap_fade(
                    symbol, prev_close, day_open, five_min_df, capital
                )
            return None

        # ── 표준 Spike 진입 ───────────────────────────────────────────────
        spike_trigger = day_open * (1 + self.config.spike_trigger_pct / 100)

        for idx, (ts, bar) in enumerate(five_min_df.iterrows()):
            # PMS 모드: 진입 시간 창 필터 및 첫 5분봉 방향 필터
            if self.config.pms_mode:
                # 첫 5분봉 방향 필터 (v4_first_bar_filter 또는 v4_pullback)
                if idx == 0 and (self.config.v4_first_bar_filter or self.config.v4_pullback):
                    if float(bar["close"]) < float(bar["open"]):
                        return None  # 갭 페이드 초기 신호 — 진입 포기
                try:
                    bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                    minutes_since_open = (bar_et.hour - 9) * 60 + bar_et.minute - 30
                    end_minutes = (self.config.entry_end_hour - 9) * 60 + self.config.entry_end_minute - 30
                    if minutes_since_open < self.config.entry_start_minute:
                        continue  # 09:35 이전 — 건너뜀
                    if minutes_since_open > end_minutes:
                        break     # 10:15 초과 — 진입 포기
                except Exception:
                    pass

            if float(bar["high"]) >= spike_trigger:
                entry_raw   = spike_trigger
                buy_price   = entry_raw * (1 + self.config.slippage_rate)

                # 포지션 사이징
                if self.config.pms_mode:
                    pos_pct = self.config.pms_position_pct
                else:
                    pos_pct = max(
                        self.config.min_position_pct,
                        self.config.max_position_pct - n_positions * self.config.position_step,
                    )
                invest_amt  = capital * pos_pct
                qty         = int(invest_amt / buy_price)

                if qty <= 0 or capital < buy_price * qty:
                    return None

                commission  = buy_price * qty * self.config.commission_rate
                total_cost  = buy_price * qty + commission

                # SL 계산
                if self.config.pms_mode:
                    sl_price = buy_price * (1 - self.config.pms_sl_pct)
                else:
                    fixed_sl = buy_price * (1 - self.config.stop_loss_pct)
                    if atr is not None and atr > 0:
                        atr_sl   = buy_price - (self.config.atr_sl_multiplier * atr)
                        sl_price = max(atr_sl, fixed_sl)
                    else:
                        sl_price = fixed_sl

                pos = {
                    "symbol":           symbol,
                    "entry_price":      buy_price,
                    "qty":              qty,
                    "sl_price":         sl_price,
                    "highest_price":    buy_price,
                    "partial_tp_done":  False,
                    "pms_tp1_done":     False,
                    "pms_tp2_done":     False,
                    "entry_dt":         str(ts),
                }
                remaining = five_min_df.iloc[idx + 1:]
                return pos, total_cost, remaining

        return None

    def _try_earnings_entry(
        self,
        symbol:     str,
        day_open:   float,
        prev_close: float,
        five_min_df: pd.DataFrame,
        capital:    float,
    ) -> Optional[Tuple[dict, float, pd.DataFrame]]:
        """
        순수 PEAD 진입: V4 풀백 없이 갭 유지 확인 후 진입.

        로직:
          - 09:30 + earnings_gap_hold_min(=30)분 = 10:00 ET 바의 close 가
            갭의 earnings_gap_hold_pct(=80%) 이상을 유지하면 진입.
          - SL = day_open × 0.98 (갭 오픈 -2%)
          - 포지션 사이징: pms_position_pct 기준 (V4와 동일)
          - 잔여 5분봉 반환: 진입 바 이후 (당일 SL/TP 처리용)
        """
        # Regime filter 방어 체크: Bear 구간 진입 차단 (메인 루프와 동일 조건)
        if self.config.regime_filter_enabled and not getattr(self, "_regime_ok", True):
            return None

        if prev_close <= 0 or day_open <= prev_close:
            return None

        gap_size = (day_open - prev_close) / prev_close  # 갭 크기 (소수 비율)
        if gap_size <= 0:
            return None

        target_minute = self.config.earnings_gap_hold_min  # 30

        for i, (ts, bar) in enumerate(five_min_df.iterrows()):
            try:
                bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                minutes_since_open = (bar_et.hour - 9) * 60 + bar_et.minute - 30
            except Exception:
                continue

            if minutes_since_open < target_minute:
                continue  # 30분 전 바는 건너뜀

            # 10:00 ET 이후 첫 바에서 단 1회 체크
            bar_close = float(bar["close"])
            current_gap = (bar_close - prev_close) / prev_close

            # 갭의 80% 이상 유지 여부 확인
            if current_gap < gap_size * self.config.earnings_gap_hold_pct:
                return None  # 갭 되돌림 → 진입 포기

            # 진입 가격 결정 (슬리피지 포함)
            buy_price  = bar_close * (1 + self.config.slippage_rate)
            sl_price   = day_open * 0.98   # 갭 오픈가 -2% SL
            sl_distance = (buy_price - sl_price) / buy_price
            if sl_distance <= 0:
                return None

            # 포지션 수량 결정
            if self.config.use_risk_sizing and sl_distance > 0:
                target_risk = capital * self.config.risk_per_trade_pct
                qty = int(target_risk / (buy_price * sl_distance))
                qty = min(qty, int(capital * 0.10 / buy_price))
            else:
                qty = int(capital * self.config.pms_position_pct / buy_price)

            if qty <= 0 or capital < buy_price * qty:
                return None

            commission  = buy_price * qty * self.config.commission_rate
            total_cost  = buy_price * qty + commission

            pos = {
                "symbol":          symbol,
                "entry_price":     buy_price,
                "qty":             qty,
                "qty_original":    qty,
                "sl_price":        sl_price,
                "highest_price":   buy_price,
                "partial_tp_done": False,
                "pms_tp1_done":    False,
                "pms_tp2_done":    False,
                "md_tp1_done":     False,
                "md_tp2_done":     False,
                "hold_days":       0,
                "entry_dt":        str(ts),
                "signal_source":   "PEAD_GAP_HOLD",
            }
            remaining = five_min_df.iloc[i + 1:]
            return pos, total_cost, remaining

        return None  # 30분 바 도달 전 데이터 종료

    def _check_nh52_signal(
        self,
        date:        date,
        daily_df:    pd.DataFrame,
        is_bull:     bool = True,
    ) -> bool:
        """
        당일 종가가 과거 252거래일 최고가를 상향 돌파했는지 확인.

        조건:
          1. 종가 > 직전 252거래일 high 최댓값 (당일 제외)
          2. 당일 거래량 ≥ 직전 20일 평균 거래량 × nh52_volume_ratio
          3. Bull Regime (SPY > SMA200)

        Returns:
            True = 다음 날 진입 신호 발생
        """
        if not is_bull:
            return False

        if date not in daily_df.index:
            return False

        idx = daily_df.index.get_loc(date)
        if idx < self.config.nh52_lookback:
            return False   # 252거래일 데이터 부족

        # 1. 52주 최고가 돌파 확인 (당일 제외 — 직전 252거래일 기준)
        window       = daily_df.iloc[idx - self.config.nh52_lookback: idx]
        prev_high_52 = float(window["high"].max())
        today_bar    = daily_df.iloc[idx]
        today_close  = float(today_bar["close"])

        if today_close <= prev_high_52:
            return False

        # 2. 거래량 확인 (직전 20일 평균 대비)
        vol_window = daily_df.iloc[max(0, idx - 20): idx]
        avg_vol    = float(vol_window["volume"].mean())
        today_vol  = float(today_bar["volume"])

        if avg_vol <= 0 or today_vol < avg_vol * self.config.nh52_volume_ratio:
            return False

        return True

    def _try_gap_fade_down_entry(
        self,
        symbol:      str,
        day_open:    float,
        prev_close:  float,
        five_min_df: pd.DataFrame,
        capital:     float,
    ) -> Optional[Tuple[dict, float, pd.DataFrame]]:
        """
        갭다운 반전 Long 진입 (Phase 2 주전략).

        로직:
          1. 갭다운 -3%+ 확인 (day_open < prev_close × 0.97)
          2. 첫 30분 내(09:30~10:00) 갭의 50%+ 회복(bar high 기준) 확인
          3. 확인 바 다음 바 시가 진입 (look-ahead 방지)
          4. SL = min(세션 저점 × 0.995, 진입가 × 0.98) — 더 낮은 값(넓은 SL)
          5. TP1 = 갭의 50% 채움 (open + gap_size × 0.5)
          6. TP2 = 전일 종가 (갭 100% 채움)
        """
        if prev_close <= 0:
            return None

        gap_pct = (day_open - prev_close) / prev_close   # 음수 = 갭다운
        if gap_pct > -self.config.gap_fade_down_min_gap_pct:
            return None   # 갭다운 크기 미달

        gap_size      = abs(day_open - prev_close)        # 갭 크기 (양수)
        confirm_level = day_open + gap_size * self.config.gap_fade_down_confirm_pct
        session_low   = float("inf")

        cutoff_min = self.config.gap_fade_down_confirm_min  # 30

        for i, (ts, bar) in enumerate(five_min_df.iterrows()):
            try:
                bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                minutes_since_open = (bar_et.hour - 9) * 60 + bar_et.minute - 30
            except Exception:
                continue

            if minutes_since_open >= cutoff_min:
                break   # 확인 창(30분) 초과 → 진입 포기

            bar_low  = float(bar["low"])
            bar_high = float(bar["high"])

            if bar_low < session_low:
                session_low = bar_low

            if bar_high >= confirm_level:
                # 다음 바가 있어야 진입 가능 (look-ahead 방지)
                if i + 1 >= len(five_min_df):
                    return None

                next_bar    = five_min_df.iloc[i + 1]
                entry_price = float(next_bar["open"]) * (1 + self.config.slippage_rate)

                # SL: 당일 저점 -0.5% vs 진입가 -2% 중 더 낮은 값(넓은 SL)
                sl_by_low   = session_low * 0.995
                sl_by_pct   = entry_price * (1 - self.config.gap_fade_down_sl_pct)
                sl_price    = min(sl_by_low, sl_by_pct)
                sl_distance = (entry_price - sl_price) / entry_price
                if sl_distance <= 0:
                    return None

                qty = int(capital * self.config.pms_position_pct / entry_price)
                if qty <= 0 or capital < entry_price * qty:
                    return None

                commission = entry_price * qty * self.config.commission_rate
                total_cost = entry_price * qty + commission

                tp_half = day_open + gap_size * self.config.gap_fade_down_tp1_pct  # 갭 75% 채움
                tp_full = prev_close                                               # 갭 100% 채움

                pos = {
                    "symbol":          symbol,
                    "entry_price":     entry_price,
                    "qty":             qty,
                    "qty_original":    qty,
                    "sl_price":        sl_price,
                    "highest_price":   entry_price,
                    "partial_tp_done": False,
                    "pms_tp1_done":    False,
                    "pms_tp2_done":    False,
                    "md_tp1_done":     False,
                    "md_tp2_done":     False,
                    "hold_days":       0,
                    "entry_dt":        str(ts),
                    "signal_source":   "GAP_FADE_DOWN",
                    "gfd_tp_half":     tp_half,
                    "gfd_tp_full":     tp_full,
                }
                remaining = five_min_df.iloc[i + 2:]
                return pos, total_cost, remaining

        return None   # 확인 조건 미달

    def _try_entry_v4(
        self,
        symbol:      str,
        day_open:    float,
        five_min_df: pd.DataFrame,
        capital:     float,
        atr:         Optional[float] = None,
        rel_volume:  Optional[float] = None,
    ) -> Optional[Tuple[dict, float, pd.DataFrame]]:
        """
        V4 풀백 진입 로직:
          ① 첫 5분봉 방향 필터 (close < open → 갭 페이드, 포기)
          ② spike_high 기록 (첫 바 고점)
          ③ spike_high × (1 - pullback_pct) 이하 하락 → 풀백 확인
          ④ pullback_low 기록
          ⑤ 재상승 spike_high × (1 + rebreak_pct) 돌파 + 가격 > VWAP → 진입
          ⑥ SL = pullback_low × 0.998 / SL 거리 > 2% → 패스
        """
        if len(five_min_df) < 2:
            return None

        # ATR 필터: 고변동성 국면 진입 차단
        if (self.config.v4_max_atr_pct > 0
                and atr is not None
                and day_open > 0
                and (atr / day_open) > self.config.v4_max_atr_pct):
            return None

        # 상대 거래량 필터: 소식성 갭 차단 (제도권 매수 없는 갭 제외)
        if (self.config.v4_min_rel_volume > 0
                and rel_volume is not None
                and rel_volume < self.config.v4_min_rel_volume):
            return None

        bars = list(five_min_df.iterrows())
        first_ts, first_bar = bars[0]

        # ① 첫 5분봉 방향 필터
        if float(first_bar["close"]) < float(first_bar["open"]):
            return None

        spike_high    = float(first_bar["high"])
        cum_vol       = float(first_bar.get("volume", 0))
        cum_tp_vol    = ((float(first_bar["high"]) + float(first_bar["low"]) +
                          float(first_bar["close"])) / 3) * cum_vol

        pullback_confirmed = False
        pullback_low       = None

        end_minutes   = (self.config.entry_end_hour - 9) * 60 + self.config.entry_end_minute - 30
        start_minutes = self.config.entry_start_minute  # 09:35 = 5분

        for i, (ts, bar) in enumerate(bars[1:], start=1):
            # 진입 시간 창 체크 (09:35~10:15 ET)
            try:
                bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                minutes_since_open = (bar_et.hour - 9) * 60 + bar_et.minute - 30
                if minutes_since_open < start_minutes:
                    # VWAP·풀백 추적은 하되 진입은 불가
                    bar_high = float(bar["high"])
                    bar_low  = float(bar["low"])
                    bar_close = float(bar["close"])
                    vol = float(bar.get("volume", 0))
                    tp  = (bar_high + bar_low + bar_close) / 3
                    cum_vol    += vol
                    cum_tp_vol += tp * vol
                    if not pullback_confirmed:
                        if bar_low <= spike_high * (1 - self.config.v4_pullback_pct):
                            pullback_confirmed = True
                            pullback_low = bar_low
                        elif bar_high > spike_high:
                            spike_high = bar_high
                    elif bar_low < pullback_low:
                        pullback_low = bar_low
                    continue
                if minutes_since_open > end_minutes:
                    break
            except Exception:
                pass

            bar_high = float(bar["high"])
            bar_low  = float(bar["low"])
            bar_close = float(bar["close"])
            vol      = float(bar.get("volume", 0))

            # VWAP 갱신
            tp = (bar_high + bar_low + bar_close) / 3
            cum_vol    += vol
            cum_tp_vol += tp * vol
            vwap = cum_tp_vol / cum_vol if cum_vol > 0 else bar_close

            if not pullback_confirmed:
                # ③ 풀백 감지
                if bar_low <= spike_high * (1 - self.config.v4_pullback_pct):
                    pullback_confirmed = True
                    pullback_low = bar_low
                else:
                    # 아직 풀백 없음 — spike_high 갱신 가능
                    if bar_high > spike_high:
                        spike_high = bar_high
                continue  # 풀백 확인 전까지는 진입 불가

            # ④ 풀백 저점 갱신
            if bar_low < pullback_low:
                pullback_low = bar_low

            # ⑤ 재돌파 + VWAP 위 → 진입
            rebreak_level = spike_high * (1 + self.config.v4_rebreak_pct)
            bar_open = float(bar.get("open", bar_close))
            if bar_high >= rebreak_level and bar_open >= vwap:
                entry_raw  = rebreak_level
                buy_price  = entry_raw * (1 + self.config.slippage_rate)

                # ⑥ 구조적 SL
                sl_price    = pullback_low * 0.998
                sl_distance = (buy_price - sl_price) / buy_price
                if sl_distance > self.config.v4_max_sl_distance:
                    return None  # R:R 불량 — 패스

                if self.config.use_risk_sizing and sl_distance > 0:
                    target_risk = capital * self.config.risk_per_trade_pct
                    sl_dollar   = buy_price * sl_distance
                    qty_risk    = int(target_risk / sl_dollar)
                    cap_pct     = 0.10  # 리스크 사이징 모드: 상한 10% 고정
                    qty_cap     = int(capital * cap_pct / buy_price)
                    qty         = min(qty_risk, qty_cap)
                else:
                    qty = int(capital * self.config.pms_position_pct / buy_price)

                if qty <= 0 or capital < buy_price * qty:
                    return None

                commission = buy_price * qty * self.config.commission_rate
                total_cost = buy_price * qty + commission

                pos = {
                    "symbol":          symbol,
                    "entry_price":     buy_price,
                    "qty":             qty,
                    "qty_original":    qty,   # Multi-Day TP2 비율 계산용
                    "sl_price":        sl_price,
                    "highest_price":   buy_price,
                    "partial_tp_done": False,
                    "pms_tp1_done":    False,
                    "pms_tp2_done":    False,
                    "md_tp1_done":     False,
                    "md_tp2_done":     False,
                    "hold_days":       0,     # Multi-Day 보유 일수 (진입 다음날부터 +1)
                    "entry_dt":        str(ts),
                }
                remaining = five_min_df.iloc[i + 1:]
                return pos, total_cost, remaining

        return None

    def _try_entry_gap_fade(
        self,
        symbol:      str,
        prev_close:  float,
        day_open:    float,
        five_min_df: pd.DataFrame,
        capital:     float,
    ) -> Optional[Tuple[dict, float, pd.DataFrame]]:
        """
        갭 페이드 Short 진입:
          ① 갭업 4% 이상 확인
          ② 첫 5분봉 음봉 확인 (close < open)
          ③ 첫 5분봉 close < VWAP(첫 바 typ price) 확인
          ④ Short 진입: 첫 바 close (슬리피지 반영)
          ⑤ SL = 첫 바 high × (1 + gap_fade_sl_buffer)
          ⑥ TP1 = prev_close + gap_size × (1 - tp1_ratio)  — 30% 되돌림
          ⑦ TP2 = prev_close + gap_size × (1 - tp2_ratio)  — 60% 되돌림
        """
        if len(five_min_df) < 1:
            return None

        # ① 갭업 확인
        if prev_close <= 0 or day_open <= 0:
            return None
        gap_pct = (day_open - prev_close) / prev_close
        if gap_pct < self.config.gap_fade_threshold_pct:
            return None

        first_ts, first_bar = list(five_min_df.iterrows())[0]
        first_close = float(first_bar["close"])
        first_open  = float(first_bar["open"])
        first_high  = float(first_bar["high"])
        first_low   = float(first_bar["low"])

        # ② 첫 5분봉 음봉 확인
        if first_close >= first_open:
            return None  # 양봉 = V4 영역

        # ③ 첫 바 close < VWAP(typ price) 확인
        vwap = (first_high + first_low + first_close) / 3
        if first_close >= vwap:
            return None

        # ④ Short 진입: 매도 슬리피지는 낮게 팔림
        entry_price = first_close * (1 - self.config.slippage_rate)
        sl_price    = first_high * (1 + self.config.gap_fade_sl_buffer)

        sl_distance = (sl_price - entry_price) / entry_price
        if sl_distance <= 0 or sl_distance > self.config.v4_max_sl_distance:
            return None

        # ⑤ 목표가 계산
        gap_size  = day_open - prev_close
        tp1_price = prev_close + gap_size * (1 - self.config.gap_fade_tp1_ratio)  # 30% 되돌림
        tp2_price = prev_close + gap_size * (1 - self.config.gap_fade_tp2_ratio)  # 60% 되돌림

        # R:R 검증: TP1이 진입가보다 낮아야 Short에서 수익
        tp1_distance = (entry_price - tp1_price) / entry_price
        if tp1_distance <= 0:
            return None  # 이미 TP1 수준 아래에서 진입 — 패스

        # ⑥ 포지션 사이징
        if self.config.use_risk_sizing and sl_distance > 0:
            target_risk = capital * self.config.risk_per_trade_pct
            sl_dollar   = entry_price * sl_distance
            qty_risk    = int(target_risk / sl_dollar)
            qty_cap     = int(capital * 0.10 / entry_price)
            qty         = min(qty_risk, qty_cap)
        else:
            qty = int(capital * self.config.gap_fade_position_pct / entry_price)

        if qty <= 0 or capital < entry_price * qty:
            return None

        commission = entry_price * qty * self.config.commission_rate
        total_cost = entry_price * qty + commission  # 증거금 + 수수료

        pos = {
            "symbol":                   symbol,
            "direction":                "SHORT",
            "strategy":                 "GAP_FADE",
            "entry_price":              entry_price,
            "qty":                      qty,
            "sl_price":                 sl_price,      # 이 위로 돌파 시 손절
            "tp1_price":                tp1_price,
            "tp2_price":                tp2_price,
            "lowest_price":             entry_price,   # Short trailing 기준 (highest_price 대신)
            "gap_fade_tp1_done":        False,
            "gap_fade_tp2_done":        False,
            "partial_tp_done":          False,
            "pms_tp1_done":             False,
            "pms_tp2_done":             False,
            "entry_dt":                 str(first_ts),
        }
        remaining = five_min_df.iloc[1:]
        return pos, total_cost, remaining

    def _try_entry_orb(
        self,
        symbol:      str,
        five_min_df: pd.DataFrame,
        capital:     float,
    ) -> Optional[Tuple[dict, float, pd.DataFrame]]:
        """
        ORB (Opening Range Breakout) Long 진입:
          ① 09:30~09:45 ET 첫 3개 5분봉으로 OR_high / OR_low / OR_avg_volume 산출
          ② 09:45~11:00 ET 구간에서:
             - bar_open < OR_high (OR 아래에서 출발)
             - bar_high >= OR_high (돌파)
             - bar_volume > OR_avg_volume × orb_volume_ratio
          ③ 진입가: OR_high × (1 + slippage)
          ④ SL: OR_low × (1 - orb_sl_buffer)
          ⑤ TP: OR_high + OR_range × orb_tp_ratio
        """
        if len(five_min_df) < 4:
            return None

        # ── OR 구성: 09:30, 09:35, 09:40 ET (3개 바) ────────────────────
        or_bars = []
        or_bar_indices = []  # iloc 인덱스 보관
        bars_list = list(five_min_df.iterrows())

        for i, (ts, bar) in enumerate(bars_list):
            try:
                bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                bar_minutes = (bar_et.hour - 9) * 60 + bar_et.minute - 30
                if 0 <= bar_minutes < 15:   # 09:30 ~ 09:44 = OR 구성 구간
                    or_bars.append(bar)
                    or_bar_indices.append(i)
                elif bar_minutes >= 15:
                    break
            except Exception:
                pass

        if len(or_bars) < 3:
            return None  # OR 구성 불충분

        OR_high       = max(float(b["high"]) for b in or_bars)
        OR_low        = min(float(b["low"])  for b in or_bars)
        OR_avg_volume = sum(float(b.get("volume", 0)) for b in or_bars) / len(or_bars)

        if OR_high <= OR_low:
            return None

        OR_range = OR_high - OR_low

        # 진입 탐색 시작 인덱스: OR 마지막 바 다음
        scan_start = or_bar_indices[-1] + 1
        if scan_start >= len(bars_list):
            return None

        end_minutes = (self.config.orb_entry_end_hour - 9) * 60 \
                      + self.config.orb_entry_end_minute - 30

        for i, (ts, bar) in enumerate(bars_list[scan_start:], start=scan_start):
            try:
                bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                bar_minutes = (bar_et.hour - 9) * 60 + bar_et.minute - 30
                if bar_minutes > end_minutes:
                    break
            except Exception:
                pass

            bar_open   = float(bar.get("open", bar["close"]))
            bar_high   = float(bar["high"])
            bar_volume = float(bar.get("volume", 0))

            # ① bar_open < OR_high (OR 아래에서 출발, 갭 체이싱 금지)
            if bar_open >= OR_high:
                continue

            # ② bar_high >= OR_high (상향 돌파)
            if bar_high < OR_high:
                continue

            # ③ 거래량 확인
            if OR_avg_volume > 0 and bar_volume < OR_avg_volume * self.config.orb_volume_ratio:
                continue

            # ── 진입 ────────────────────────────────────────────────────
            entry_raw  = OR_high
            buy_price  = entry_raw * (1 + self.config.slippage_rate)
            sl_price   = OR_low * (1 - self.config.orb_sl_buffer)
            tp_price   = OR_high + OR_range * self.config.orb_tp_ratio

            sl_distance = (buy_price - sl_price) / buy_price
            if sl_distance <= 0 or sl_distance > self.config.v4_max_sl_distance:
                continue  # SL 거리 불량 — 다음 바 탐색

            if self.config.use_risk_sizing and sl_distance > 0:
                target_risk = capital * self.config.risk_per_trade_pct
                sl_dollar   = buy_price * sl_distance
                qty_risk    = int(target_risk / sl_dollar)
                qty_cap     = int(capital * 0.10 / buy_price)
                qty         = min(qty_risk, qty_cap)
            else:
                qty = int(capital * self.config.orb_position_pct / buy_price)

            if qty <= 0 or capital < buy_price * qty:
                continue

            commission = buy_price * qty * self.config.commission_rate
            total_cost = buy_price * qty + commission

            pos = {
                "symbol":          symbol,
                "direction":       "LONG",
                "strategy":        "ORB",
                "entry_price":     buy_price,
                "qty":             qty,
                "sl_price":        sl_price,
                "orb_tp_price":    tp_price,   # ORB 전용 고정 TP
                "highest_price":   buy_price,
                "partial_tp_done": False,
                "pms_tp1_done":    False,
                "pms_tp2_done":    False,
                "entry_dt":        str(ts),
            }
            remaining = five_min_df.iloc[i + 1:]
            return pos, total_cost, remaining

        return None

    def _try_entry_itc(
        self,
        symbol:      str,
        day_open:    float,
        five_min_df: pd.DataFrame,
        capital:     float,
    ) -> Optional[Tuple[dict, float, pd.DataFrame]]:
        """
        ITC (Intraday Trend Continuation) 진입 로직:
          ① 10:30 ET 이후 봉부터 스캔
          ② 조건 1: 시가 대비 +1.5% 이상 상승
          ③ 조건 2: 현재가 > VWAP
          ④ 조건 3: 직전 봉 저점이 VWAP ±0.3% 이내 (풀백 터치)
          ⑤ 조건 4: 양봉 + 거래량 > 최근 5봉 평균 × 1.2
          ⑥ 진입가: close × (1 + slippage)
          ⑦ SL: pullback_low × 0.998
          ⑧ TP1 +1.5% / TP2 +2.5% / 잔여 Trailing -1.2% / 12:00 ET 청산
        """
        if not self.config.use_itc:
            return None
        if len(five_min_df) < 3 or day_open <= 0:
            return None

        bars = list(five_min_df.iterrows())
        cum_vol    = 0.0
        cum_tp_vol = 0.0
        gain_ok    = False   # 조건 1 충족 여부 (once true, stays true)

        for i, (ts, bar) in enumerate(bars):
            bar_high  = float(bar["high"])
            bar_low   = float(bar["low"])
            bar_close = float(bar["close"])
            bar_open  = float(bar.get("open", bar_close))
            vol       = float(bar.get("volume", 0))

            # VWAP 누적 계산
            tp = (bar_high + bar_low + bar_close) / 3
            cum_vol    += vol
            cum_tp_vol += tp * vol
            vwap = cum_tp_vol / cum_vol if cum_vol > 0 else bar_close

            # 진입 시간 창 체크
            try:
                bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                minutes_since_open = (bar_et.hour - 9) * 60 + bar_et.minute - 30
            except Exception:
                continue

            if minutes_since_open < self.config.itc_entry_start:
                continue   # 10:30 이전 — VWAP 추적만, 진입 불가
            if minutes_since_open > self.config.itc_entry_end:
                break      # 11:30 초과 — 포기

            # 조건 1: 시가 대비 +1.5% 이상 상승 (한 번 충족하면 유지)
            if not gain_ok:
                if (bar_close / day_open - 1) < self.config.itc_min_gain_pct:
                    continue
                gain_ok = True

            # 조건 2: VWAP 위에서 거래
            if bar_close <= vwap:
                continue

            # 조건 3: 직전 봉 저점이 VWAP ±0.3% 이내 (풀백 터치)
            if i == 0:
                continue
            prev_low = float(bars[i - 1][1]["low"])
            if abs(prev_low / vwap - 1) > self.config.itc_vwap_band:
                continue

            # 조건 4: 현재 봉 양봉 + 거래량 > 최근 5봉 평균 × 1.2
            if bar_close <= bar_open:
                continue
            recent_start = max(0, i - 5)
            recent_vols  = [float(bars[j][1].get("volume", 0)) for j in range(recent_start, i)]
            recent_vol_avg = sum(recent_vols) / len(recent_vols) if recent_vols else 0
            if recent_vol_avg > 0 and vol < recent_vol_avg * 1.2:
                continue

            # 진입가 / 손절가 계산
            buy_price   = bar_close * (1 + self.config.slippage_rate)
            sl_price    = prev_low * 0.998
            sl_distance = (buy_price - sl_price) / buy_price

            if sl_distance <= 0 or sl_distance > self.config.v4_max_sl_distance:
                continue

            # 포지션 사이징 (V4와 동일 구조)
            if self.config.use_risk_sizing and sl_distance > 0:
                target_risk = capital * self.config.risk_per_trade_pct
                sl_dollar   = buy_price * sl_distance
                qty_risk    = int(target_risk / sl_dollar)
                cap_pct     = 0.10
                qty_cap     = int(capital * cap_pct / buy_price)
                qty         = min(qty_risk, qty_cap)
            else:
                qty = int(capital * self.config.pms_position_pct / buy_price)

            if qty <= 0 or capital < buy_price * qty:
                continue

            commission = buy_price * qty * self.config.commission_rate
            total_cost = buy_price * qty + commission

            pos = {
                "symbol":          symbol,
                "strategy":        "ITC",
                "direction":       "LONG",
                "entry_price":     buy_price,
                "qty":             qty,
                "sl_price":        sl_price,
                "highest_price":   buy_price,
                "partial_tp_done": False,
                "pms_tp1_done":    False,
                "pms_tp2_done":    False,
                "itc_tp1_price":   buy_price * (1 + self.config.pms_partial_tp1_pct),
                "itc_tp2_price":   buy_price * (1 + self.config.pms_partial_tp2_pct),
                "entry_dt":        str(ts),
            }
            remaining = five_min_df.iloc[i + 1:]
            return pos, total_cost, remaining

        return None

    # ── 5분봉 청산 처리 ────────────────────────────────────────────────────

    def _process_position_5min(
        self,
        pos:           dict,
        five_min_df:   pd.DataFrame,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
    ) -> Tuple[float, float, bool]:
        """
        5분봉 바 순차 처리로 SL / Partial TP / Trailing Stop / Full TP 체크.

        Returns:
            (updated_capital, updated_daily_pnl, is_closed)
        """
        # 갭 페이드 Short 포지션은 별도 함수로 처리
        if pos.get("direction") == "SHORT":
            return self._process_short_position_5min(
                pos, five_min_df, capital, daily_pnl, trade_records
            )

        # ORB 포지션은 별도 함수로 처리 (고정 TP, Morning Close 11:30 ET)
        if pos.get("strategy") == "ORB":
            return self._process_orb_position_5min(
                pos, five_min_df, capital, daily_pnl, trade_records
            )

        # ITC 포지션은 별도 함수로 처리 (PMS TP 구조 + 12:00 ET 시간 청산)
        if pos.get("strategy") == "ITC":
            return self._process_itc_position_5min(
                pos, five_min_df, capital, daily_pnl, trade_records
            )

        # NH52_BREAKOUT 포지션: 인트라데이는 SL만 체크 (Trailing/MAX_HOLD는 EOD에서 처리)
        if pos.get("signal_source") == "NH52_BREAKOUT":
            for ts, bar in five_min_df.iterrows():
                bar_low  = float(bar["low"])
                bar_high = float(bar["high"])
                if bar_high > pos["highest_price"]:
                    pos["highest_price"] = bar_high
                if bar_low <= pos["sl_price"]:
                    exit_px = min(pos["sl_price"], float(bar.get("open", bar["close"])))
                    capital, daily_pnl = self._close_position(
                        pos, exit_px, "STOP_LOSS", str(ts),
                        capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True
            return capital, daily_pnl, False

        # GAP_FADE_DOWN 포지션: 인트라데이는 SL만 체크 (TP1/TP2는 EOD에서 처리)
        if pos.get("signal_source") == "GAP_FADE_DOWN":
            for ts, bar in five_min_df.iterrows():
                bar_low  = float(bar["low"])
                bar_high = float(bar["high"])
                if bar_high > pos["highest_price"]:
                    pos["highest_price"] = bar_high
                if bar_low <= pos["sl_price"]:
                    exit_px = min(pos["sl_price"], float(bar.get("open", bar["close"])))
                    capital, daily_pnl = self._close_position(
                        pos, exit_px, "STOP_LOSS", str(ts),
                        capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True
            return capital, daily_pnl, False

        # Multi-Day 모드: 인트라데이 TP/시간청산 비활성화, 당일 SL만 체크
        if self.config.v4_multi_day:
            _pead_no_sl = (
                pos.get("signal_source") == "PEAD_GAP_HOLD"
                and self.config.pead_no_intraday_sl
            )
            for ts, bar in five_min_df.iterrows():
                bar_high = float(bar["high"])
                bar_low  = float(bar["low"])
                bar_open = float(bar.get("open", bar["close"]))
                if bar_high > pos["highest_price"]:
                    pos["highest_price"] = bar_high

                if _pead_no_sl:
                    # PEAD 인트라데이 SL 비활성화: 극단 하락(-10%) 차단만 유지
                    if bar_low < pos["entry_price"] * 0.90:
                        exit_px = pos["entry_price"] * 0.90
                        capital, daily_pnl = self._close_position(
                            pos, exit_px, "STOP_LOSS", str(ts),
                            capital, daily_pnl, trade_records
                        )
                        return capital, daily_pnl, True
                    continue  # 일반 SL 체크 스킵

                if bar_low <= pos["sl_price"]:
                    label   = "TRAILING_STOP" if pos.get("partial_tp_done") else "STOP_LOSS"
                    exit_px = min(pos["sl_price"], bar_open)
                    capital, daily_pnl = self._close_position(
                        pos, exit_px, label, str(ts), capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True
            return capital, daily_pnl, False

        entry_price = pos["entry_price"]

        if self.config.pms_mode:
            tp1_px   = entry_price * (1 + self.config.pms_partial_tp1_pct)
            tp2_px   = entry_price * (1 + self.config.pms_partial_tp2_pct)
            full_tp_px = entry_price * (1 + self.config.pms_full_tp_pct)
        else:
            partial_tp_px = entry_price * (1 + self.config.partial_tp_pct)
            full_tp_px    = entry_price * (1 + self.config.take_profit_pct)

        # 진입 시각 (Time Stop 계산용)
        entry_ts: Optional[pd.Timestamp] = None
        if pos.get("entry_dt"):
            try:
                entry_ts = pd.to_datetime(pos["entry_dt"], utc=True)
            except Exception:
                entry_ts = None

        for ts, bar in five_min_df.iterrows():
            bar_high = float(bar["high"])
            bar_low  = float(bar["low"])
            bar_open = float(bar.get("open", bar["close"]))

            # 고점 갱신
            if bar_high > pos["highest_price"]:
                pos["highest_price"] = bar_high

            # Trailing Stop 갱신 (TP 1단계 이후)
            if pos["partial_tp_done"]:
                trail_pct = self.config.pms_trailing_stop_pct if self.config.pms_mode else self.config.trailing_stop_pct
                trail_sl  = pos["highest_price"] * (1 - trail_pct)
                if trail_sl > pos["sl_price"]:
                    pos["sl_price"] = trail_sl

            # ── PMS 전용 청산 로직 ────────────────────────────────────
            if self.config.pms_mode:
                # PMS Time Stop: 2시간 경과 + 실손실 -1.5% 이상 시 청산
                if entry_ts is not None and not pos.get("pms_tp2_done"):
                    try:
                        bar_ts = pd.to_datetime(ts, utc=True)
                        minutes_held = (bar_ts - entry_ts).total_seconds() / 60
                        unrealized_pct = (bar_open - entry_price) / entry_price
                        if (minutes_held >= self.config.pms_time_stop_minutes and
                                unrealized_pct <= -self.config.pms_time_stop_loss_pct):
                            capital, daily_pnl = self._close_position(
                                pos, bar_open, "TIME_STOP", str(ts),
                                capital, daily_pnl, trade_records
                            )
                            return capital, daily_pnl, True
                    except Exception:
                        pass

                # PMS Morning Close: 11:30 ET 이후 미실현 손익 < 0 → 청산
                if self.config.morning_close_enabled and not pos["partial_tp_done"]:
                    try:
                        bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                        mc_threshold = (self.config.morning_close_hour * 60 +
                                        self.config.morning_close_minute)
                        bar_minutes  = bar_et.hour * 60 + bar_et.minute
                        if bar_minutes >= mc_threshold and bar_open < entry_price:
                            capital, daily_pnl = self._close_position(
                                pos, bar_open, "NOON_EXIT", str(ts),
                                capital, daily_pnl, trade_records
                            )
                            return capital, daily_pnl, True
                    except Exception:
                        pass

            else:
                # ── V3 Time Stop: 45분 경과 후 수익 +0.5% 미달 시 청산 ──
                if self.config.time_stop_enabled and entry_ts is not None and not pos["partial_tp_done"]:
                    try:
                        bar_ts = pd.to_datetime(ts, utc=True)
                        minutes_held = (bar_ts - entry_ts).total_seconds() / 60
                        unrealized_pct = (bar_open - entry_price) / entry_price
                        if (minutes_held >= self.config.time_stop_minutes and
                                unrealized_pct < self.config.time_stop_min_profit_pct):
                            capital, daily_pnl = self._close_position(
                                pos, bar_open, "TIME_STOP", str(ts),
                                capital, daily_pnl, trade_records
                            )
                            return capital, daily_pnl, True
                    except Exception:
                        pass

                # ── V3 Noon Rule: 12:00 ET 이후 미실현 손익 < 0 → 청산 ──
                if self.config.noon_rule_enabled and not pos["partial_tp_done"]:
                    try:
                        bar_et = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                        if bar_et.hour >= 12 and bar_open < entry_price:
                            capital, daily_pnl = self._close_position(
                                pos, bar_open, "NOON_EXIT", str(ts),
                                capital, daily_pnl, trade_records
                            )
                            return capital, daily_pnl, True
                    except Exception:
                        pass

            # 1. SL 체크
            if bar_low <= pos["sl_price"]:
                label   = "TRAILING_STOP" if pos["partial_tp_done"] else "STOP_LOSS"
                exit_px = min(pos["sl_price"], bar_open)
                capital, daily_pnl = self._close_position(
                    pos, exit_px, label, str(ts), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            if self.config.pms_mode:
                # 2-a. PMS 1차 Partial TP (+1.5%, 40%)
                if not pos["pms_tp1_done"] and bar_high >= tp1_px:
                    tp1_qty = max(1, int(pos["qty"] * self.config.pms_partial_tp1_ratio))
                    capital, daily_pnl = self._close_partial(
                        pos, tp1_qty, tp1_px, "PARTIAL_TP",
                        str(ts), capital, daily_pnl, trade_records
                    )
                    pos["pms_tp1_done"]    = True
                    pos["partial_tp_done"] = True
                    # BreakEven SL 으로 이동
                    if entry_price > pos["sl_price"]:
                        pos["sl_price"] = entry_price
                    if pos["qty"] <= 0:
                        return capital, daily_pnl, True

                # 2-b. PMS 2차 Partial TP (+2.5%, 30%)
                if pos["pms_tp1_done"] and not pos["pms_tp2_done"] and bar_high >= tp2_px:
                    remaining_for_tp2 = pos["qty"]
                    tp2_qty = max(1, int(remaining_for_tp2 * (
                        self.config.pms_partial_tp2_ratio /
                        (1 - self.config.pms_partial_tp1_ratio)
                    )))
                    tp2_qty = min(tp2_qty, remaining_for_tp2)
                    capital, daily_pnl = self._close_partial(
                        pos, tp2_qty, tp2_px, "PARTIAL_TP2",
                        str(ts), capital, daily_pnl, trade_records
                    )
                    pos["pms_tp2_done"] = True
                    if pos["qty"] <= 0:
                        return capital, daily_pnl, True

                # 2-c. PMS Full TP (+5.0%)
                if bar_high >= full_tp_px:
                    capital, daily_pnl = self._close_position(
                        pos, full_tp_px, "TAKE_PROFIT", str(ts), capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True

            else:
                # 2. V3 Partial TP (기존 1단계)
                if not pos["partial_tp_done"] and bar_high >= partial_tp_px:
                    partial_qty = max(1, pos["qty"] // 2)
                    capital, daily_pnl = self._close_partial(
                        pos, partial_qty, partial_tp_px, "PARTIAL_TP",
                        str(ts), capital, daily_pnl, trade_records
                    )
                    pos["partial_tp_done"] = True
                    pos["sl_price"] = pos["highest_price"] * (1 - self.config.trailing_stop_pct)
                    if pos["qty"] <= 0:
                        return capital, daily_pnl, True
                    if bar_high >= full_tp_px:
                        capital, daily_pnl = self._close_position(
                            pos, full_tp_px, "TAKE_PROFIT", str(ts), capital, daily_pnl, trade_records
                        )
                        return capital, daily_pnl, True
                    continue

                # 3. V3 Full TP
                if bar_high >= full_tp_px:
                    capital, daily_pnl = self._close_position(
                        pos, full_tp_px, "TAKE_PROFIT", str(ts), capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True

        return capital, daily_pnl, False

    def _process_short_position_5min(
        self,
        pos:           dict,
        five_min_df:   pd.DataFrame,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
    ) -> Tuple[float, float, bool]:
        """
        갭 페이드 Short 포지션 5분봉 청산 처리.

        Short 로직 (Long과 방향 반전):
          - SL:       bar_high >= sl_price → 손절 (위로 돌파 = 실패)
          - TP1:      bar_low  <= tp1_price → 1차 부분 청산 (40%)
          - TP2:      bar_low  <= tp2_price → 2차 부분 청산 (30%)
          - 잔여:     Morning Close 강제 청산 (11:00 ET)
          - Trailing: TP1 이후 lowest_price 갱신, 잔여에 Trailing Stop 적용
        """
        entry_price = pos["entry_price"]

        mc_threshold = (self.config.gap_fade_morning_close_hour * 60 +
                        self.config.gap_fade_morning_close_minute)

        for ts, bar in five_min_df.iterrows():
            bar_high  = float(bar["high"])
            bar_low   = float(bar["low"])
            bar_open  = float(bar.get("open", bar["close"]))

            # 저점 갱신 (Short Trailing 기준)
            if bar_low < pos["lowest_price"]:
                pos["lowest_price"] = bar_low

            # Trailing Stop 갱신 (TP1 이후 잔여 포지션)
            if pos["gap_fade_tp1_done"]:
                trail_pct = self.config.pms_trailing_stop_pct
                trail_sl  = pos["lowest_price"] * (1 + trail_pct)
                if trail_sl < pos["sl_price"]:
                    pos["sl_price"] = trail_sl

            # 1. SL 체크: 고점이 sl_price 돌파 시 손절
            if bar_high >= pos["sl_price"]:
                exit_px = max(pos["sl_price"], bar_open)
                label   = "TRAILING_STOP" if pos["gap_fade_tp1_done"] else "STOP_LOSS"
                capital, daily_pnl = self._close_position(
                    pos, exit_px, label, str(ts), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 2. Morning Close: 11:00 ET 이후 전량 강제 청산
            try:
                bar_et       = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                bar_minutes  = bar_et.hour * 60 + bar_et.minute
                if bar_minutes >= mc_threshold:
                    capital, daily_pnl = self._close_position(
                        pos, bar_open, "NOON_EXIT", str(ts), capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True
            except Exception:
                pass

            # 3. TP1: 가격이 tp1_price 이하 하락
            if not pos["gap_fade_tp1_done"] and bar_low <= pos["tp1_price"]:
                tp1_qty = max(1, int(pos["qty"] * self.config.gap_fade_tp1_qty_ratio))
                capital, daily_pnl = self._close_partial(
                    pos, tp1_qty, pos["tp1_price"], "PARTIAL_TP",
                    str(ts), capital, daily_pnl, trade_records
                )
                pos["gap_fade_tp1_done"] = True
                pos["partial_tp_done"]   = True
                # Break-Even SL: SL을 entry_price 수준으로 하향
                be_sl = entry_price * (1 + self.config.gap_fade_sl_buffer)
                if be_sl < pos["sl_price"]:
                    pos["sl_price"] = be_sl
                if pos["qty"] <= 0:
                    return capital, daily_pnl, True

            # 4. TP2: 가격이 tp2_price 이하 하락
            if pos["gap_fade_tp1_done"] and not pos["gap_fade_tp2_done"] \
                    and bar_low <= pos["tp2_price"]:
                tp2_qty = max(1, int(pos["qty"] * self.config.gap_fade_tp2_qty_ratio))
                capital, daily_pnl = self._close_partial(
                    pos, tp2_qty, pos["tp2_price"], "PARTIAL_TP",
                    str(ts), capital, daily_pnl, trade_records
                )
                pos["gap_fade_tp2_done"] = True
                if pos["qty"] <= 0:
                    return capital, daily_pnl, True

        return capital, daily_pnl, False

    def _process_orb_position_5min(
        self,
        pos:           dict,
        five_min_df:   pd.DataFrame,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
    ) -> Tuple[float, float, bool]:
        """
        ORB Long 포지션 5분봉 청산 처리.

          - SL:           OR_low × (1 - orb_sl_buffer) 하향 돌파 시 손절
          - TP:           orb_tp_price 도달 시 전량 청산 (고정 TP, Partial 없음)
          - Morning Close: 11:30 ET 이후 전량 강제 청산
          - Trailing Stop: 없음 (단순 구조)
        """
        entry_price = pos["entry_price"]
        tp_price    = pos.get("orb_tp_price", entry_price * 1.03)

        mc_threshold = (self.config.orb_morning_close_hour * 60 +
                        self.config.orb_morning_close_minute)

        for ts, bar in five_min_df.iterrows():
            bar_high = float(bar["high"])
            bar_low  = float(bar["low"])
            bar_open = float(bar.get("open", bar["close"]))

            # 고점 갱신 (Trailing Stop 미사용이나 기록은 유지)
            if bar_high > pos["highest_price"]:
                pos["highest_price"] = bar_high

            # 1. SL 체크
            if bar_low <= pos["sl_price"]:
                exit_px = min(pos["sl_price"], bar_open)
                capital, daily_pnl = self._close_position(
                    pos, exit_px, "STOP_LOSS", str(ts), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 2. Morning Close: 11:30 ET
            try:
                bar_et      = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                bar_minutes = bar_et.hour * 60 + bar_et.minute
                if bar_minutes >= mc_threshold:
                    capital, daily_pnl = self._close_position(
                        pos, bar_open, "NOON_EXIT", str(ts), capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True
            except Exception:
                pass

            # 3. TP: OR_high + OR_range × 1.5 고정 TP
            if bar_high >= tp_price:
                capital, daily_pnl = self._close_position(
                    pos, tp_price, "TAKE_PROFIT", str(ts), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

        return capital, daily_pnl, False

    def _process_itc_position_5min(
        self,
        pos:           dict,
        five_min_df:   pd.DataFrame,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
    ) -> Tuple[float, float, bool]:
        """
        ITC Long 포지션 5분봉 청산 처리.

          - SL:           pullback_low × 0.998 하향 돌파 시 손절
          - TP1:          진입가 × 1.015 → 40% 청산, SL = 진입가(BreakEven)
          - TP2:          진입가 × 1.025 → 30% 청산
          - Trailing:     TP1 이후 고점 대비 -1.2%
          - Time Close:   12:00 ET 잔여 포지션 전량 청산
        """
        entry_price = pos["entry_price"]
        tp1_px      = pos.get("itc_tp1_price", entry_price * (1 + self.config.pms_partial_tp1_pct))
        tp2_px      = pos.get("itc_tp2_price", entry_price * (1 + self.config.pms_partial_tp2_pct))

        close_threshold = self.config.itc_close_hour * 60 + self.config.itc_close_minute

        for ts, bar in five_min_df.iterrows():
            bar_high = float(bar["high"])
            bar_low  = float(bar["low"])
            bar_open = float(bar.get("open", bar["close"]))

            # 고점 갱신
            if bar_high > pos["highest_price"]:
                pos["highest_price"] = bar_high

            # Trailing Stop 갱신 (TP1 이후)
            if pos["partial_tp_done"]:
                trail_sl = pos["highest_price"] * (1 - self.config.pms_trailing_stop_pct)
                if trail_sl > pos["sl_price"]:
                    pos["sl_price"] = trail_sl

            # 1. SL 체크
            if bar_low <= pos["sl_price"]:
                label   = "TRAILING_STOP" if pos["partial_tp_done"] else "STOP_LOSS"
                exit_px = min(pos["sl_price"], bar_open)
                capital, daily_pnl = self._close_position(
                    pos, exit_px, label, str(ts), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 2. Time Close: 12:00 ET 전량 청산
            try:
                bar_et      = pd.to_datetime(ts, utc=True).tz_convert("America/New_York")
                bar_minutes = bar_et.hour * 60 + bar_et.minute
                if bar_minutes >= close_threshold:
                    capital, daily_pnl = self._close_position(
                        pos, bar_open, "NOON_EXIT", str(ts), capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True
            except Exception:
                pass

            # 3. TP1: +1.5%, 40% 청산
            if not pos["pms_tp1_done"] and bar_high >= tp1_px:
                tp1_qty = max(1, int(pos["qty"] * self.config.pms_partial_tp1_ratio))
                capital, daily_pnl = self._close_partial(
                    pos, tp1_qty, tp1_px, "PARTIAL_TP",
                    str(ts), capital, daily_pnl, trade_records
                )
                pos["pms_tp1_done"]    = True
                pos["partial_tp_done"] = True
                if entry_price > pos["sl_price"]:
                    pos["sl_price"] = entry_price  # BreakEven
                if pos["qty"] <= 0:
                    return capital, daily_pnl, True

            # 4. TP2: +2.5%, 30% 청산
            if pos["pms_tp1_done"] and not pos["pms_tp2_done"] and bar_high >= tp2_px:
                remaining_for_tp2 = pos["qty"]
                tp2_qty = max(1, int(remaining_for_tp2 * (
                    self.config.pms_partial_tp2_ratio /
                    (1 - self.config.pms_partial_tp1_ratio)
                )))
                tp2_qty = min(tp2_qty, remaining_for_tp2)
                capital, daily_pnl = self._close_partial(
                    pos, tp2_qty, tp2_px, "PARTIAL_TP2",
                    str(ts), capital, daily_pnl, trade_records
                )
                pos["pms_tp2_done"] = True
                if pos["qty"] <= 0:
                    return capital, daily_pnl, True

        return capital, daily_pnl, False

    def _process_position_daily(
        self,
        pos:           dict,
        daily_bar:     pd.Series,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
        date_str:      str,
    ) -> Tuple[float, float, bool]:
        """5분봉 없는 날 일봉 바로 SL/TP 처리."""
        bar_high = float(daily_bar.get("high", daily_bar["close"]))
        bar_low  = float(daily_bar.get("low",  daily_bar["close"]))
        bar_open = float(daily_bar.get("open", daily_bar["close"]))

        entry_price   = pos["entry_price"]
        partial_tp_px = entry_price * (1 + self.config.partial_tp_pct)
        full_tp_px    = entry_price * (1 + self.config.take_profit_pct)

        if bar_high > pos["highest_price"]:
            pos["highest_price"] = bar_high
        if pos["partial_tp_done"]:
            trail_sl = pos["highest_price"] * (1 - self.config.trailing_stop_pct)
            if trail_sl > pos["sl_price"]:
                pos["sl_price"] = trail_sl

        if bar_low <= pos["sl_price"]:
            label = "TRAILING_STOP" if pos["partial_tp_done"] else "STOP_LOSS"
            exit_px = min(pos["sl_price"], bar_open)
            capital, daily_pnl = self._close_position(
                pos, exit_px, label, date_str, capital, daily_pnl, trade_records
            )
            return capital, daily_pnl, True

        if not pos["partial_tp_done"] and bar_high >= partial_tp_px:
            partial_qty = max(1, pos["qty"] // 2)
            capital, daily_pnl = self._close_partial(
                pos, partial_qty, partial_tp_px, "PARTIAL_TP",
                date_str, capital, daily_pnl, trade_records
            )
            pos["partial_tp_done"] = True
            if pos["qty"] <= 0:
                return capital, daily_pnl, True

        if bar_high >= full_tp_px:
            capital, daily_pnl = self._close_position(
                pos, full_tp_px, "TAKE_PROFIT", date_str, capital, daily_pnl, trade_records
            )
            return capital, daily_pnl, True

        return capital, daily_pnl, False

    def _process_position_eod(
        self,
        pos:           dict,
        today:         date,
        daily_df:      pd.DataFrame,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
    ) -> Tuple[float, float, bool]:
        """
        V4 Multi-Day Hold 전용 일별 청산 체크.
        매 거래일 시작 시 호출 (전날 보유 포지션 대상).

          - 최대 보유 일수(hold_days >= max_days) → 당일 시가 청산
          - Trailing Stop: 일봉 저점이 고점 × (1 - trailing_pct) 이하 → 청산
          - TP1: +5% → 50% 청산, SL BreakEven 이동
          - TP2: +10% → 원래 수량의 30% 추가 청산
          - 미청산 시 hold_days += 1 후 계속 보유
        """
        if today not in daily_df.index:
            return capital, daily_pnl, False

        daily_bar = daily_df.loc[today]
        day_open  = float(daily_bar.get("open", daily_bar["close"]))
        day_high  = float(daily_bar.get("high", daily_bar["close"]))
        day_low   = float(daily_bar.get("low",  daily_bar["close"]))
        entry_price = pos["entry_price"]

        # ── GAP_FADE_DOWN 전용 청산 로직 ────────────────────────────────
        if pos.get("signal_source") == "GAP_FADE_DOWN":
            # 1. 최대 보유일 초과 → 당일 시가 강제 청산
            if pos.get("hold_days", 0) >= self.config.gap_fade_down_max_days:
                capital, daily_pnl = self._close_position(
                    pos, day_open, "MAX_HOLD", str(today), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 고점 갱신
            if day_high > pos.get("highest_price", entry_price):
                pos["highest_price"] = day_high

            # 2. TP1: 갭 50% 채움 → 50% 청산 + BreakEven SL 이동
            tp_half = pos.get("gfd_tp_half", float("inf"))
            if not pos.get("md_tp1_done") and day_high >= tp_half:
                tp1_qty = max(1, int(pos["qty"] * 0.50))
                capital, daily_pnl = self._close_partial(
                    pos, tp1_qty, tp_half, "PARTIAL_TP",
                    str(today), capital, daily_pnl, trade_records
                )
                pos["md_tp1_done"]     = True
                pos["partial_tp_done"] = True
                if entry_price > pos["sl_price"]:
                    pos["sl_price"] = entry_price   # BreakEven 이동
                if pos["qty"] <= 0:
                    return capital, daily_pnl, True

            # 3. TP2: 갭 100% 채움(전일 종가) → 전량 청산
            tp_full = pos.get("gfd_tp_full", float("inf"))
            if pos.get("md_tp1_done") and not pos.get("md_tp2_done") and day_high >= tp_full:
                capital, daily_pnl = self._close_position(
                    pos, tp_full, "PARTIAL_TP2", str(today), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 4. Trailing Stop (TP1 이후 잔여 포지션)
            if pos.get("md_tp1_done"):
                trail_sl = pos["highest_price"] * (1 - self.config.gap_fade_down_trailing_pct)
                if day_low <= trail_sl:
                    exit_px = min(trail_sl, day_open)
                    capital, daily_pnl = self._close_position(
                        pos, exit_px, "TRAILING_STOP", str(today), capital, daily_pnl, trade_records
                    )
                    return capital, daily_pnl, True

            # 5. SL 체크 (TP1 미달성)
            if day_low <= pos["sl_price"]:
                exit_px = min(pos["sl_price"], day_open)
                capital, daily_pnl = self._close_position(
                    pos, exit_px, "STOP_LOSS", str(today), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 계속 보유
            pos["hold_days"] = pos.get("hold_days", 0) + 1
            return capital, daily_pnl, False

        # ── NH52_BREAKOUT 전용 청산 로직 ──────────────────────────────────
        if pos.get("signal_source") == "NH52_BREAKOUT":
            # 1. 최대 보유일 초과 → 당일 시가 강제 청산
            if pos.get("hold_days", 0) >= self.config.nh52_max_days:
                capital, daily_pnl = self._close_position(
                    pos, day_open, "MAX_HOLD", str(today), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 고점 갱신 (일봉 고점 기준)
            if day_high > pos.get("highest_price", entry_price):
                pos["highest_price"] = day_high

            # 2. SL 체크
            if day_low <= pos["sl_price"]:
                exit_px = min(pos["sl_price"], day_open)
                capital, daily_pnl = self._close_position(
                    pos, exit_px, "STOP_LOSS", str(today), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 3. Trailing Stop
            trailing_sl = pos["highest_price"] * (1 - self.config.nh52_trailing_pct)
            if day_low <= trailing_sl:
                exit_px = min(trailing_sl, day_open)
                capital, daily_pnl = self._close_position(
                    pos, exit_px, "TRAILING_STOP", str(today), capital, daily_pnl, trade_records
                )
                return capital, daily_pnl, True

            # 계속 보유
            pos["hold_days"] = pos.get("hold_days", 0) + 1
            return capital, daily_pnl, False

        # ── V4 / PEAD Multi-Day 청산 로직 ────────────────────────────────
        # 최대 보유 일수 초과 → 당일 시가에 강제 청산
        if pos.get("hold_days", 0) >= self.config.v4_md_max_days:
            capital, daily_pnl = self._close_position(
                pos, day_open, "MAX_HOLD", str(today), capital, daily_pnl, trade_records
            )
            return capital, daily_pnl, True

        # 고점 갱신 (일봉 고점 기준)
        if day_high > pos.get("highest_price", entry_price):
            pos["highest_price"] = day_high

        # Trailing Stop: 일봉 저점 기준
        # PEAD 포지션은 pead_trailing_pct (기본 10%) 사용 — consolidation 허용
        trail_pct = (
            self.config.pead_trailing_pct
            if pos.get("signal_source") == "PEAD_GAP_HOLD"
            else self.config.v4_md_trailing_pct
        )
        trailing_sl = pos["highest_price"] * (1 - trail_pct)
        if day_low <= trailing_sl:
            label   = "TRAILING_STOP" if pos.get("md_tp1_done") else "STOP_LOSS"
            # 갭다운 시 day_open이 trailing_sl보다 낮을 수 있음 → 실제 체결 가능 가격 사용
            exit_px = min(trailing_sl, day_open)
            capital, daily_pnl = self._close_position(
                pos, exit_px, label, str(today), capital, daily_pnl, trade_records
            )
            return capital, daily_pnl, True

        # TP1: +5% → 50% 청산
        tp1_px = entry_price * (1 + self.config.v4_md_tp1_pct)
        if not pos.get("md_tp1_done") and day_high >= tp1_px:
            tp1_qty = max(1, int(pos["qty"] * 0.50))
            capital, daily_pnl = self._close_partial(
                pos, tp1_qty, tp1_px, "PARTIAL_TP",
                str(today), capital, daily_pnl, trade_records
            )
            pos["md_tp1_done"]     = True
            pos["partial_tp_done"] = True
            if entry_price > pos["sl_price"]:
                pos["sl_price"] = entry_price   # BreakEven 이동
            if pos["qty"] <= 0:
                return capital, daily_pnl, True

        # TP2: +10% → 원래 수량의 30% 추가 청산
        tp2_px = entry_price * (1 + self.config.v4_md_tp2_pct)
        if pos.get("md_tp1_done") and not pos.get("md_tp2_done") and day_high >= tp2_px:
            qty_original = pos.get("qty_original", pos["qty"])
            tp2_qty = max(1, int(qty_original * 0.30))
            tp2_qty = min(tp2_qty, pos["qty"])
            capital, daily_pnl = self._close_partial(
                pos, tp2_qty, tp2_px, "PARTIAL_TP2",
                str(today), capital, daily_pnl, trade_records
            )
            pos["md_tp2_done"] = True
            if pos["qty"] <= 0:
                return capital, daily_pnl, True

        # 보유 일수 증가 후 계속 보유
        pos["hold_days"] = pos.get("hold_days", 0) + 1
        return capital, daily_pnl, False

    # ── 청산 헬퍼 ─────────────────────────────────────────────────────────

    def _close_position(
        self,
        pos:           dict,
        exit_raw:      float,
        signal_type:   str,
        exit_dt:       str,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
    ) -> Tuple[float, float]:
        is_short = pos.get("direction") == "SHORT"

        if is_short:
            # Short 청산 = 매수(커버): 슬리피지로 더 높은 가격에 매수
            exit_price = exit_raw * (1 + self.config.slippage_rate)
            commission = exit_price * pos["qty"] * self.config.commission_rate
            pnl        = (pos["entry_price"] - exit_price) * pos["qty"] - commission
            # 자본 반환: 증거금 복원 + 손익
            capital   += pos["entry_price"] * pos["qty"] + pnl
        else:
            # Long 청산 = 매도: 슬리피지로 더 낮은 가격에 매도
            exit_price = exit_raw * (1 - self.config.slippage_rate)
            commission = exit_price * pos["qty"] * self.config.commission_rate
            proceeds   = exit_price * pos["qty"] - commission
            cost_basis = pos["entry_price"] * pos["qty"]
            pnl        = proceeds - cost_basis
            capital   += proceeds

        cost_basis = pos["entry_price"] * pos["qty"]
        pnl_pct    = pnl / cost_basis if cost_basis > 0 else 0
        daily_pnl += pnl

        trade_records.append({
            "symbol":      pos["symbol"],
            "entry_dt":    pos["entry_dt"],
            "exit_dt":     exit_dt,
            "entry_price": pos["entry_price"],
            "exit_price":  exit_price,
            "qty":         pos["qty"],
            "pnl":         round(pnl, 4),
            "pnl_pct":     round(pnl_pct, 6),
            "signal_type": signal_type,
            "strategy":    pos.get("strategy", "V4"),
            "direction":   pos.get("direction", "LONG"),
        })
        pos["qty"] = 0
        return capital, daily_pnl

    def _close_partial(
        self,
        pos:           dict,
        qty:           int,
        exit_raw:      float,
        signal_type:   str,
        exit_dt:       str,
        capital:       float,
        daily_pnl:     float,
        trade_records: List[dict],
    ) -> Tuple[float, float]:
        is_short = pos.get("direction") == "SHORT"

        if is_short:
            exit_price = exit_raw * (1 + self.config.slippage_rate)
            commission = exit_price * qty * self.config.commission_rate
            pnl        = (pos["entry_price"] - exit_price) * qty - commission
            capital   += pos["entry_price"] * qty + pnl
        else:
            exit_price = exit_raw * (1 - self.config.slippage_rate)
            commission = exit_price * qty * self.config.commission_rate
            proceeds   = exit_price * qty - commission
            cost_basis = pos["entry_price"] * qty
            pnl        = proceeds - cost_basis
            capital   += proceeds

        cost_basis = pos["entry_price"] * qty
        daily_pnl += pnl
        pos["qty"] -= qty

        trade_records.append({
            "symbol":      pos["symbol"],
            "entry_dt":    pos["entry_dt"],
            "exit_dt":     exit_dt,
            "entry_price": pos["entry_price"],
            "exit_price":  exit_price,
            "qty":         qty,
            "pnl":         round(pnl, 4),
            "pnl_pct":     round(pnl / cost_basis, 6) if cost_basis > 0 else 0,
            "signal_type": signal_type,
            "strategy":    pos.get("strategy", "V4"),
            "direction":   pos.get("direction", "LONG"),
        })
        return capital, daily_pnl

    def _get_eod_price(
        self,
        five_min_df: Optional[pd.DataFrame],
        daily_df:    Optional[pd.DataFrame],
        today:       date,
    ) -> Optional[float]:
        """EOD 청산 가격 (5분봉 마지막 close 또는 일봉 close)."""
        if five_min_df is not None and len(five_min_df) > 0:
            return float(five_min_df.iloc[-1]["close"])
        if daily_df is not None and today in daily_df.index:
            return float(daily_df.loc[today]["close"])
        return None

    # ── V3: SPY 국면 맵 빌드 ─────────────────────────────────────────────

    @staticmethod
    def _build_spy_regime(
        spy_daily: pd.DataFrame,
        use_sma50: bool = False,
    ) -> Dict[date, bool]:
        """
        SPY 일봉 데이터로 Bull/Bear 국면 일별 맵을 생성한다.

        Args:
            spy_daily: index=DatetimeIndex(또는 date), columns=[close, ...]
            use_sma50: True이면 SMA200 AND SMA50 이중 조건 (더 빠른 반응)
        Returns:
            {date: True(Bull) / False(Bear)}
        """
        spy = spy_daily.copy()
        spy["sma200"] = spy["close"].rolling(200, min_periods=200).mean()
        if use_sma50:
            spy["sma50"] = spy["close"].rolling(50, min_periods=50).mean()
        regime_map: Dict[date, bool] = {}
        for idx, row in spy.iterrows():
            d = idx.date() if hasattr(idx, "date") else idx
            if pd.isna(row["sma200"]):
                continue
            close   = float(row["close"])
            sma200  = float(row["sma200"])
            is_bull = close > sma200
            if use_sma50 and not pd.isna(row.get("sma50", float("nan"))):
                is_bull = is_bull and (close > float(row["sma50"]))
            regime_map[d] = is_bull
        return regime_map

    # ── ATR 계산 ──────────────────────────────────────────────────────────

    @staticmethod
    def _calculate_atr(
        daily_df: pd.DataFrame,
        today:    date,
        period:   int = 14,
    ) -> Optional[float]:
        if today not in daily_df.index:
            return None
        idx = daily_df.index.get_loc(today)
        if idx < period + 1:
            return None
        window = daily_df.iloc[idx - period: idx]
        tr_list = []
        for i in range(1, len(window)):
            h = float(window.iloc[i]["high"])
            l = float(window.iloc[i]["low"])
            pc = float(window.iloc[i - 1]["close"])
            tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
        if not tr_list:
            return None
        atr = float(np.mean(tr_list))
        return atr if atr > 0 else None

    @staticmethod
    def _calculate_rel_volume(
        daily_df: pd.DataFrame,
        today:    date,
        period:   int = 20,
    ) -> Optional[float]:
        """당일 거래량 / 직전 20일 평균 거래량 반환. 데이터 부족 시 None."""
        if today not in daily_df.index:
            return None
        idx = daily_df.index.get_loc(today)
        if idx < period:
            return None
        hist = daily_df.iloc[idx - period: idx]
        avg_vol = float(hist["volume"].mean())
        if avg_vol <= 0:
            return None
        today_vol = float(daily_df.iloc[idx]["volume"])
        return today_vol / avg_vol

    # ── 성과 지표 계산 ────────────────────────────────────────────────────

    def _calculate_metrics(
        self,
        trade_records:        List[dict],
        equity_curve:         List[Tuple[date, float]],
        daily_returns:        List[float],
        total_days_scanned:   int,
        total_entry_signals:  int,
        initial_capital:      float,
    ) -> UniverseBacktestResult:

        if not trade_records:
            return UniverseBacktestResult(
                trade_records=trade_records,
                equity_curve=equity_curve,
            )

        final_capital = equity_curve[-1][1] if equity_curve else initial_capital
        total_ret     = (final_capital - initial_capital) / initial_capital * 100

        # 연환산
        if len(equity_curve) >= 2:
            days  = (equity_curve[-1][0] - equity_curve[0][0]).days
            years = days / 365.0
            ann   = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
        else:
            ann = 0.0

        # Sharpe / Sortino
        dr = np.array(daily_returns)
        if len(dr) > 1 and dr.std() > 0:
            sharpe  = dr.mean() / dr.std() * np.sqrt(252)
            neg_dr  = dr[dr < 0]
            sortino = dr.mean() / neg_dr.std() * np.sqrt(252) if len(neg_dr) > 1 else 0.0
        else:
            sharpe = sortino = 0.0

        # MDD
        capitals = [c for _, c in equity_curve]
        if capitals:
            peak  = np.maximum.accumulate(capitals)
            dd    = (np.array(capitals) - peak) / peak * 100
            mdd   = abs(dd.min())
        else:
            mdd = 0.0

        calmar = ann / mdd if mdd > 0 else 0.0

        # 거래 통계
        pnls    = [t["pnl"] for t in trade_records]
        wins    = [p for p in pnls if p > 0]
        losses  = [p for p in pnls if p <= 0]
        win_rt  = len(wins) / len(pnls) * 100 if pnls else 0
        pf      = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 999.0

        ep      = [t["pnl_pct"] for t in trade_records if t["pnl"] > 0]
        lp      = [t["pnl_pct"] for t in trade_records if t["pnl"] <= 0]

        passed = (
            sharpe  >= self.MIN_SHARPE and
            mdd     <= self.MAX_DRAWDOWN_LIMIT and
            pf      >= self.MIN_PROFIT_FACTOR and
            len(pnls) >= self.MIN_TRADES
        )

        entry_hit_rate = (
            len([t for t in trade_records if t["signal_type"] != "EOD"]) /
            total_entry_signals * 100
        ) if total_entry_signals > 0 else 0.0

        return UniverseBacktestResult(
            total_return_pct=round(total_ret, 2),
            annualized_return_pct=round(ann, 2),
            final_capital=round(final_capital, 2),
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            max_drawdown_pct=round(mdd, 2),
            calmar_ratio=round(calmar, 3),
            total_trades=len(pnls),
            win_trades=len(wins),
            loss_trades=len(losses),
            win_rate_pct=round(win_rt, 1),
            profit_factor=round(pf, 2),
            avg_profit_pct=round(np.mean(ep) * 100, 3) if ep else 0.0,
            avg_loss_pct=round(np.mean(lp) * 100, 3)   if lp else 0.0,
            total_days_scanned=total_days_scanned,
            total_entry_signals=total_entry_signals,
            entry_hit_rate_pct=round(entry_hit_rate, 1),
            trade_records=trade_records,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            passed=passed,
        )
