"""
NAVIS 유니버스 백테스트 실행 스크립트

사용법:
    # 최초 실행 (데이터 수집 포함, 약 20~40분 소요)
    python backtesting/run_universe_backtest.py --build-cache

    # 캐시 있을 때 백테스트만 실행
    python backtesting/run_universe_backtest.py

    # 기간 지정
    python backtesting/run_universe_backtest.py --start 2022-01-01 --end 2024-12-31

    # 파라미터 조정
    python backtesting/run_universe_backtest.py --gap 2.0 --spike 1.0 --cache-dir my_cache
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_universe_backtest")


def main():
    parser = argparse.ArgumentParser(description="NAVIS 유니버스 백테스트")
    parser.add_argument("--build-cache", action="store_true",
                        help="최초 데이터 수집 후 캐시 저장 (약 20~40분)")
    parser.add_argument("--update-cache", action="store_true",
                        help="기존 캐시를 오늘 날짜까지 업데이트")
    parser.add_argument("--cache-dir", default="cache",
                        help="캐시 디렉토리 경로 (기본: cache)")
    parser.add_argument("--start", default="2021-01-01",
                        help="백테스트 시작일 (기본: 2021-01-01)")
    parser.add_argument("--end", default=None,
                        help="백테스트 종료일 (기본: 오늘)")
    parser.add_argument("--gap", type=float, default=None,
                        help="갭 임계값 %% (기본: PMS=3.0, 일반=2.0)")
    parser.add_argument("--spike", type=float, default=1.0,
                        help="스파이크 트리거 %% (기본: 1.0, 백테스트 결과 최적값)")
    parser.add_argument("--capital", type=float, default=1_000_000,
                        help="초기 자본 (기본: 1,000,000)")
    parser.add_argument("--no-eod-close", action="store_true",
                        help="장 마감 강제 청산 비활성화 (기본: 활성화)")
    parser.add_argument("--no-regime-filter", action="store_true",
                        help="SPY SMA200 시장 국면 필터 비활성화 (기본: 활성화)")
    parser.add_argument("--regime-sma50", action="store_true",
                        help="Regime 필터 이중 기준: SPY > SMA200 AND SMA50 (베어마켓 초입 조기 감지)")
    parser.add_argument("--no-time-stop", action="store_true",
                        help="Time Stop 비활성화 (기본: 활성화)")
    parser.add_argument("--no-noon-rule", action="store_true",
                        help="Noon Rule 비활성화 (기본: 활성화)")
    # ── PMS 모드 플래그 ──────────────────────────────────────────────────
    parser.add_argument("--pms", action="store_true",
                        help="PMS (Precision Momentum Scalper) 전략 전체 활성화")
    parser.add_argument("--tier1", action="store_true",
                        help="Tier 1 20종목 유니버스만 사용")
    parser.add_argument("--tier1-5", action="store_true",
                        help="Tier 1.5 유니버스 (Tier 1 + S&P500 대형주 10종목 추가)")
    # ── V4 풀백 진입 플래그 ───────────────────────────────────────────
    parser.add_argument("--v4-first-bar", action="store_true",
                        help="V4 격리 A: 첫 5분봉 방향 필터만 추가 (close<open → 포기)")
    parser.add_argument("--v4-pullback", action="store_true",
                        help="V4 격리 B: 풀백 감지 후 재돌파+VWAP 진입 전체 활성화")
    # ── 종목 제외 플래그 ─────────────────────────────────────────────
    parser.add_argument("--exclude", nargs="+", default=[], metavar="SYM",
                        help="백테스트에서 제외할 종목 (예: --exclude TSLA NVDA)")
    parser.add_argument("--no-morning-close", action="store_true",
                        help="PMS Morning Close 비활성화 (11:30 ET 손실 청산 제거)")
    parser.add_argument("--max-atr-pct", type=float, default=0.030,
                        help="V4 진입 ATR 상한 (ATR/가격 비율, 기본: 0.030 = 3%%)")
    parser.add_argument("--min-rel-volume", type=float, default=0.0,
                        help="갭업일 상대 거래량 최소값 (20일 평균 대비 배수, 기본 0.0=비활성, 권장 1.5)")
    parser.add_argument("--max-sl-distance", type=float, default=0.020,
                        help="V4 구조적 SL 거리 상한 (기본: 0.020 = 2.0%%)")
    # ── 리스크 기반 포지션 사이징 ─────────────────────────────────────────
    parser.add_argument("--risk-sizing", action="store_true",
                        help="구조적 SL 거리 기반 포지션 사이징 활성화 (고정 비율 대체)")
    parser.add_argument("--risk-per-trade", type=float, default=0.005,
                        help="거래당 목표 리스크 (자본 대비 비율, 기본: 0.005 = 0.5%%)")
    # ── 갭 페이드 전략 ───────────────────────────────────────────────────
    parser.add_argument("--gap-fade", action="store_true",
                        help="갭 페이드 전략 활성화 (V4 음봉 신호에서 Short 시뮬레이션)")
    # ── ORB 전략 ─────────────────────────────────────────────────────────
    parser.add_argument("--orb", action="store_true",
                        help="ORB 전략 활성화 (Opening Range Breakout, Tier 1 매일 스캔)")
    # ── 진입 창 (시작/종료) ───────────────────────────────────────────────
    parser.add_argument("--entry-start", type=int, default=None, metavar="MIN",
                        help="진입 허용 시작 시간 (장 시작 후 분, 기본=5 → 09:35 ET). "
                             "예: --entry-start 10 → 09:40, --entry-start 30 → 10:00")
    parser.add_argument("--entry-end", type=int, default=None, metavar="MIN",
                        help="진입 허용 종료 시간 (장 시작 후 분, 기본=60 → 10:30 ET). "
                             "예: --entry-end 25 → 09:55, --entry-end 30 → 10:00")
    # ── 최대 동시 포지션 ──────────────────────────────────────────────────
    parser.add_argument("--max-positions", type=int, default=None,
                        help="최대 동시 포지션 수 (기본: PMS=2, 일반=5)")
    # ── V4 Multi-Day Hold ────────────────────────────────────────────────
    parser.add_argument("--multi-day", action="store_true",
                        help="V4 Multi-Day Hold 모드 (인트라데이 TP 제거, 최대 5거래일 보유)")
    parser.add_argument("--md-trailing", type=float, default=0.030,
                        help="Multi-Day trailing stop (기본: 0.030 = 3%%)")
    parser.add_argument("--md-max-days", type=int, default=5,
                        help="최대 보유 거래일 (기본: 5)")
    # ── ITC 전략 ─────────────────────────────────────────────────────────
    parser.add_argument("--itc", action="store_true",
                        help="ITC(Intraday Trend Continuation) 전략 활성화")
    parser.add_argument("--itc-universe", action="store_true",
                        help="ITC 검증 유니버스 사용 (소비자 플랫폼 제외 16종목)")
    parser.add_argument("--itc-universe-ext", action="store_true",
                        help="ITC 확장 유니버스 사용 (16종목 + B2B 기업 SW/반도체 8종목 = 24종목)")
    parser.add_argument("--sp500", action="store_true",
                        help="S&P 500 전체 유니버스 사용 (~500종목, build_earnings_cache.SP500_SYMBOLS)")
    # ── Earnings Momentum 전략 ────────────────────────────────────────────
    parser.add_argument("--earnings-only", action="store_true",
                        help="실적 발표 후 갭 발생일에만 V4 진입 허용 (Earnings Momentum 전략)")
    parser.add_argument("--earnings-cache", default="earnings_cache.json",
                        help="어닝 캘린더 캐시 파일 경로 (기본: earnings_cache.json)")
    parser.add_argument("--build-earnings-cache", action="store_true",
                        help="어닝 캘린더 캐시 수집 후 종료 (build_earnings_cache.py 호출)")
    parser.add_argument("--pead", action="store_true",
                        help="순수 PEAD 진입: V4 풀백 없이 갭 유지 30분 후 진입 (--earnings-only와 함께 사용)")
    parser.add_argument("--pead-no-intraday-sl", action="store_true",
                        help="PEAD: 5분봉 SL 비활성화, 일봉 trailing stop만 사용 (극단 -10%% 차단 유지)")
    parser.add_argument("--pead-exclude-sectors", nargs="+", default=[],
                        metavar="SECTOR",
                        help="PEAD 제외 섹터 (GICS명, 예: 'Information Technology' 'Communication Services')")
    parser.add_argument("--pead-trailing", type=float, default=0.10,
                        help="PEAD 전용 일봉 trailing stop (기본: 0.10 = 10%%%%)")
    parser.add_argument("--sector-cache", default="sector_cache.json",
                        help="섹터 캐시 파일 경로 (기본: sector_cache.json)")
    # ── Gap Fade Down (갭다운 반전 Long — Phase 2 주전략) ─────────────────
    # 주의: 기존 --gap-fade(갭업 Short, 폐기)와 다른 전략
    parser.add_argument("--gap-fade-down", action="store_true",
                        help="갭다운 반전 Long 전략 활성화 (Phase 2 주전략)")
    parser.add_argument("--gfd-min-gap", type=float, default=3.0,
                        help="갭다운 최소 크기 %% (기본 3.0)")
    parser.add_argument("--gfd-confirm", type=float, default=0.50,
                        help="갭 회복 확인 비율 (기본 0.50 = 50%%%%)")
    parser.add_argument("--gfd-trailing", type=float, default=0.03,
                        help="Trailing Stop 비율 (기본 0.03 = 3%%%%)")
    parser.add_argument("--gfd-max-days", type=int, default=5,
                        help="최대 보유 일수 (기본 5)")
    # ── 52주 신고가 브레이크아웃 전략 (Phase 2 주전략) ─────────────────────
    parser.add_argument("--nh52", action="store_true",
                        help="52주 신고가 브레이크아웃 전략 활성화 (Phase 2 주전략)")
    parser.add_argument("--nh52-volume-ratio", type=float, default=1.5,
                        help="거래량 확인 배율 (기본 1.5×)")
    parser.add_argument("--nh52-sl", type=float, default=5.0,
                        help="고정 SL %% (기본 5.0)")
    parser.add_argument("--nh52-trailing", type=float, default=5.0,
                        help="Trailing Stop %% (기본 5.0)")
    parser.add_argument("--nh52-max-days", type=int, default=10,
                        help="최대 보유 일수 (기본 10)")
    # ── 종목별 심층 분석 ──────────────────────────────────────────────────
    parser.add_argument("--deep-analysis", nargs="+", default=[], metavar="SYM",
                        help="지정 종목의 연/월별 손익 상세 출력 (예: --deep-analysis NVDA TSLA)")
    args = parser.parse_args()

    # Windows cmd.exe 인용 부호 버그 수정: "Communication Services" → ['"Communication', 'Services"']
    if hasattr(args, "pead_exclude_sectors") and args.pead_exclude_sectors:
        fixed = []
        buf = []
        for tok in args.pead_exclude_sectors:
            if tok.startswith('"') and not tok.endswith('"'):
                buf.append(tok.lstrip('"'))
            elif buf and tok.endswith('"'):
                buf.append(tok.rstrip('"'))
                fixed.append(" ".join(buf))
                buf = []
            elif buf:
                buf.append(tok)
            else:
                fixed.append(tok.strip('"\''))
        if buf:
            fixed.append(" ".join(buf).strip('"\''))
        args.pead_exclude_sectors = fixed

    # ── --build-earnings-cache: 캐시 빌드 후 종료 ───────────────────────
    if getattr(args, "build_earnings_cache", False):
        import subprocess, sys as _sys
        _script = str(Path(__file__).parent / "build_earnings_cache.py")
        _cmd    = [_sys.executable, _script, "--output", args.earnings_cache]
        if getattr(args, "itc_universe_ext", False):
            _cmd.append("--itc-universe-ext")
        elif getattr(args, "itc_universe", False):
            _cmd.append("--itc-universe")
        elif getattr(args, "sp500", False):
            _cmd.append("--sp500")
        logger.info(f"어닝 캐시 빌드: {' '.join(_cmd)}")
        subprocess.run(_cmd, check=True)
        return

    # ── API 키 확인 ───────────────────────────────────────────────────────
    api_key    = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not api_secret:
        logger.error("ALPACA_API_KEY / ALPACA_SECRET_KEY 환경변수 설정 필요")
        sys.exit(1)

    # ── 종목 유니버스 로드 ────────────────────────────────────────────────
    if getattr(args, "sp500", False):
        from backtesting.build_earnings_cache import SP500_SYMBOLS
        symbols = list(SP500_SYMBOLS)
        logger.info(f"S&P 500 유니버스: {len(symbols)}종목")
    elif getattr(args, "itc_universe_ext", False):
        from config.trading_constants import ITC_UNIVERSE_EXTENDED
        symbols = list(ITC_UNIVERSE_EXTENDED)
        logger.info(f"ITC 확장 유니버스: {len(symbols)}종목")
    elif getattr(args, "itc_universe", False):
        from config.trading_constants import ITC_UNIVERSE
        symbols = list(ITC_UNIVERSE)
        logger.info(f"ITC 유니버스: {len(symbols)}종목")
    elif args.tier1:
        from config.trading_constants import PMS_TIER1_UNIVERSE
        symbols = list(PMS_TIER1_UNIVERSE)
        logger.info(f"Tier 1 유니버스: {len(symbols)}종목")
    elif getattr(args, "tier1_5", False):
        from config.trading_constants import PMS_TIER1_5_UNIVERSE
        symbols = list(PMS_TIER1_5_UNIVERSE)
        logger.info(f"Tier 1.5 유니버스: {len(symbols)}종목")
    else:
        from data_collection.monitoring.watchlist_generator import WatchlistGenerator
        wg      = WatchlistGenerator(api_key, api_secret)
        raw_uni = wg._get_default_universe()
        etfs    = {"SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "USO"}
        symbols = [s for s in raw_uni if s not in etfs]
        logger.info(f"유니버스: {len(symbols)}종목 (ETF {len(etfs)}개 제외)")

    # ── DataCache 초기화 ──────────────────────────────────────────────────
    from backtesting.universe_backtest.data_cache import DataCache
    cache = DataCache(api_key, api_secret, cache_dir=args.cache_dir)

    # V3: SPY를 시장 국면 필터용 기준 자산으로 캐시에 포함
    symbols_with_spy = symbols if "SPY" in symbols else ["SPY"] + symbols

    if args.build_cache:
        logger.info("캐시 빌드 시작 (최초 1회, 약 20~40분 소요) — SPY 포함")
        cache.build(symbols_with_spy, start="2020-07-27")
        cache.cache_stats()
        return

    elif args.update_cache:
        logger.info("캐시 업데이트 시작 — SPY 포함")
        cache.update(symbols_with_spy)
        cache.cache_stats()
        return

    # 캐시 현황 출력
    cached = cache.cached_symbols()
    all_cached = {s for s, ok in cached.items() if ok}
    # --tier1 / --tier1-5 / --itc-universe / --sp500: 목록 순서 유지 / 그 외: 전체 캐시 종목 (SPY 제외)
    if (args.tier1 or getattr(args, "tier1_5", False)
            or getattr(args, "itc_universe", False)
            or getattr(args, "itc_universe_ext", False)
            or getattr(args, "sp500", False)):
        ready = [s for s in symbols if s in all_cached]
    else:
        ready = [s for s in all_cached if s not in {"SPY"}]
    if args.exclude:
        before = len(ready)
        ready = [s for s in ready if s not in args.exclude]
        logger.info(f"제외 종목: {args.exclude} ({before - len(ready)}개 제거)")
    logger.info(f"캐시 완료 종목: {len(ready)} / {len(symbols)}")
    if len(ready) == 0:
        logger.error("캐시된 데이터 없음. --build-cache 먼저 실행하세요.")
        sys.exit(1)

    # ── 백테스트 실행 ─────────────────────────────────────────────────────
    from backtesting.universe_backtest.engine import (
        UniverseBacktestEngine, UniverseBacktestConfig
    )

    # PMS 모드: gap 기본값을 3.0%로 오버라이드
    # --gap 미지정 시: PMS=3.0%, 일반=2.0% / 명시적 지정 시 그대로 사용
    effective_gap = args.gap if args.gap is not None else (3.0 if args.pms else 2.0)

    config = UniverseBacktestConfig(
        initial_capital         = args.capital,
        gap_threshold_pct       = effective_gap,
        spike_trigger_pct       = args.spike,
        eod_force_close         = not args.no_eod_close,
        regime_filter_enabled   = not args.no_regime_filter,
        regime_sma50            = args.regime_sma50,
        time_stop_enabled       = not args.no_time_stop and not args.pms,
        noon_rule_enabled       = not args.no_noon_rule and not args.pms,
        morning_close_enabled   = not args.no_morning_close,
        pms_mode                = args.pms,
        max_positions           = args.max_positions if args.max_positions is not None else (2 if args.pms else 5),
        v4_first_bar_filter     = args.v4_first_bar or args.v4_pullback,
        v4_pullback             = args.v4_pullback,
        v4_max_sl_distance      = args.max_sl_distance,
        v4_max_atr_pct          = args.max_atr_pct,
        v4_min_rel_volume       = args.min_rel_volume,
        use_risk_sizing         = args.risk_sizing,
        risk_per_trade_pct      = args.risk_per_trade,
        gap_fade_enabled        = args.gap_fade,
        orb_enabled             = args.orb,
        use_itc                 = args.itc,
        v4_multi_day            = args.multi_day,
        v4_md_trailing_pct      = args.md_trailing,
        v4_md_max_days          = args.md_max_days,
        use_earnings_filter     = getattr(args, "earnings_only", False),
        earnings_cache_path     = getattr(args, "earnings_cache", "earnings_cache.json"),
        earnings_simple_entry   = getattr(args, "pead", False),
        pead_no_intraday_sl     = getattr(args, "pead_no_intraday_sl", False),
        pead_trailing_pct       = getattr(args, "pead_trailing", 0.10),
        pead_exclude_sectors    = getattr(args, "pead_exclude_sectors", []),
        sector_cache_path       = getattr(args, "sector_cache", "sector_cache.json"),
        gap_fade_down              = getattr(args, "gap_fade_down", False),
        gap_fade_down_min_gap_pct  = getattr(args, "gfd_min_gap", 3.0) / 100,
        gap_fade_down_confirm_pct  = getattr(args, "gfd_confirm", 0.50),
        gap_fade_down_trailing_pct = getattr(args, "gfd_trailing", 0.03),
        gap_fade_down_max_days     = getattr(args, "gfd_max_days", 5),
        nh52_breakout              = getattr(args, "nh52", False),
        nh52_volume_ratio          = getattr(args, "nh52_volume_ratio", 1.5),
        nh52_sl_pct                = getattr(args, "nh52_sl", 5.0) / 100,
        nh52_trailing_pct          = getattr(args, "nh52_trailing", 5.0) / 100,
        nh52_max_days              = getattr(args, "nh52_max_days", 10),
    )
    if args.entry_start is not None:
        config.entry_start_minute = args.entry_start
    if args.entry_end is not None:
        _ee_total = 9 * 60 + 30 + args.entry_end
        config.entry_end_hour   = _ee_total // 60
        config.entry_end_minute = _ee_total % 60

    # ── V3: SPY 일봉 로드 (시장 국면 필터용) ─────────────────────────────
    spy_daily = None
    if config.regime_filter_enabled:
        spy_daily = cache.load_daily("SPY")
        if spy_daily is None or len(spy_daily) < 200:
            logger.warning(
                "SPY 캐시 데이터 없음 — 시장 국면 필터 비활성화. "
                "--build-cache 시 SPY를 유니버스에 포함하거나 "
                "--no-regime-filter 플래그를 사용하세요."
            )
            spy_daily = None
        else:
            logger.info(f"SPY 일봉 로드 완료: {len(spy_daily)}일 ({spy_daily.index[0]} ~ {spy_daily.index[-1]})")

    if not config.regime_filter_enabled or spy_daily is None:
        regime_flag = "OFF"
    elif config.regime_sma50:
        regime_flag = "ON(SMA200+SMA50)"
    else:
        regime_flag = "ON(SMA200)"
    if config.v4_pullback:
        mode_flag = "V4-PULLBACK"
    elif config.v4_first_bar_filter:
        mode_flag = "V4-FIRSTBAR"
    elif config.pms_mode:
        mode_flag = "PMS"
    else:
        mode_flag = "V3"
    risk_flag      = f"ON (R={args.risk_per_trade*100:.2f}%)" if args.risk_sizing else "OFF"
    atr_flag       = f"ON (≤{int(args.max_atr_pct*100)}%)" if args.max_atr_pct > 0 else "OFF"
    gap_fade_flag  = "ON" if args.gap_fade else "OFF"
    orb_flag       = "ON" if args.orb else "OFF"
    itc_flag       = "ON" if args.itc else "OFF"
    md_flag        = f"ON (trail={args.md_trailing*100:.1f}%, max={args.md_max_days}d)" if args.multi_day else "OFF"
    _pead_on   = getattr(args, "pead", False)
    em_flag    = (f"PEAD ({args.earnings_cache})" if (_pead_on and getattr(args, "earnings_only", False))
                  else f"ON ({args.earnings_cache})" if getattr(args, "earnings_only", False)
                  else "OFF")
    rvol_flag      = f"ON (≥{args.min_rel_volume}x)" if args.min_rel_volume > 0 else "OFF"
    _es_total = 9 * 60 + 30 + config.entry_start_minute
    entry_start_et = f"{_es_total // 60:02d}:{_es_total % 60:02d}"
    entry_end_et   = f"{config.entry_end_hour:02d}:{config.entry_end_minute:02d}"
    logger.info(
        f"백테스트 시작 [{mode_flag}] | gap>={effective_gap}% | spike>={args.spike}% | "
        f"{args.start} ~ {args.end or '오늘'} | "
        f"Regime={regime_flag} | TimeStop={'ON' if config.time_stop_enabled else 'OFF'} | "
        f"NoonRule={'ON' if config.noon_rule_enabled else 'OFF'} | "
        f"RiskSizing={risk_flag} | ATR필터={atr_flag} | GapFade={gap_fade_flag} | ORB={orb_flag} | "
        f"ITC={itc_flag} | MultiDay={md_flag} | EarningsOnly={em_flag} | Entry={entry_start_et}~{entry_end_et} ET | RVol={rvol_flag}"
    )

    engine = UniverseBacktestEngine(config=config)
    result = engine.run(
        symbols   = ready,
        cache     = cache,
        start     = args.start,
        end       = args.end,
        spy_daily = spy_daily,
    )

    # ── 결과 출력 ─────────────────────────────────────────────────────────
    print(result.summary())

    # ── 기간별 성과 분석 ──────────────────────────────────────────────────
    from backtesting.universe_backtest.period_analyzer import PeriodAnalyzer
    analyzer = PeriodAnalyzer(result.trade_records, result.equity_curve)
    analyzer.print_report(initial_capital=args.capital)

    # ── 수익률 극대화 분석 ────────────────────────────────────────────────
    from backtesting.universe_backtest.return_maximizer import ReturnMaximizer
    maximizer = ReturnMaximizer(result.trade_records)
    maximizer.analyze_all(initial_capital=args.capital)

    # ── 전략별 분리 통계 (--gap-fade / --orb / --itc / --multi-day 활성화 시) ─
    if (args.gap_fade or args.orb or args.itc or args.multi_day) and result.trade_records:
        import pandas as pd
        df_all = pd.DataFrame(result.trade_records)
        strats = [("V4 (Long)", "V4")]
        if args.gap_fade:
            strats.append(("갭 페이드 (Short)", "GAP_FADE"))
        if args.orb:
            strats.append(("ORB (Long)", "ORB"))
        if args.itc:
            strats.append(("ITC (Long)", "ITC"))
        for strat_name, strat_key in strats:
            if "strategy" in df_all.columns:
                sub = df_all[df_all["strategy"] == strat_key]
            else:
                sub = df_all if strat_key == "V4" else df_all.iloc[0:0]
            if sub.empty:
                print(f"\n[{strat_name}] 거래 없음")
                continue
            wins = (sub["pnl"] > 0).sum()
            total = len(sub)
            gross_profit = sub[sub["pnl"] > 0]["pnl"].sum()
            gross_loss   = sub[sub["pnl"] <= 0]["pnl"].sum()
            pf = abs(gross_profit / gross_loss) if gross_loss != 0 else float("inf")
            print(f"\n[{strat_name}]  {total}건 | 승률 {wins/total*100:.1f}% | "
                  f"PF {pf:.2f} | 총 PnL ${sub['pnl'].sum():,.0f}")

    # ── 결과 CSV 저장 ─────────────────────────────────────────────────────
    if result.trade_records:
        import pandas as pd
        from pathlib import Path
        out_dir = Path("backtest_results")
        out_dir.mkdir(exist_ok=True)
        from datetime import datetime
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv = out_dir / f"universe_bt_{ts}.csv"
        pd.DataFrame(result.trade_records).to_csv(csv, index=False)
        logger.info(f"거래 내역 저장: {csv}")

        eq_csv = out_dir / f"equity_curve_{ts}.csv"
        pd.DataFrame(result.equity_curve, columns=["date", "capital"]).to_csv(eq_csv, index=False)
        logger.info(f"자본 곡선 저장: {eq_csv}")

    # ── 종목별 심층 분석 (--deep-analysis) ───────────────────────────────
    if args.deep_analysis and result.trade_records:
        import pandas as pd
        df = pd.DataFrame(result.trade_records)
        df["year"]  = pd.to_datetime(df["entry_dt"], utc=True).dt.year
        df["month"] = pd.to_datetime(df["entry_dt"], utc=True).dt.month

        for sym in args.deep_analysis:
            sub = df[df["symbol"] == sym]
            if sub.empty:
                print(f"\n[심층 분석] {sym}: 거래 없음")
                continue

            total_pnl  = sub["pnl"].sum()
            total_wins = (sub["pnl"] > 0).sum()
            print(f"\n{'='*60}")
            print(f"  {sym} 심층 분석  |  총 {len(sub)}건  |  승률 {total_wins/len(sub)*100:.1f}%  |  총 PnL ${total_pnl:,.0f}")
            print(f"{'='*60}")

            # 연/월별 집계
            monthly = (
                sub.groupby(["year", "month"])
                .agg(trades=("pnl", "count"), wins=("pnl", lambda x: (x > 0).sum()),
                     pnl=("pnl", "sum"), avg_pnl=("pnl", "mean"))
                .reset_index()
            )
            print(f"{'연도':>4}  {'월':>2}  {'거래':>4}  {'승률':>6}  {'월PnL':>10}  {'평균PnL':>9}")
            print("-" * 46)
            for _, row in monthly.iterrows():
                wr = row["wins"] / row["trades"] * 100 if row["trades"] else 0
                print(f"{int(row['year']):>4}  {int(row['month']):>2}  {int(row['trades']):>4}  "
                      f"{wr:>5.1f}%  ${row['pnl']:>9,.0f}  ${row['avg_pnl']:>8,.0f}")

            # 청산 유형별 집계
            print(f"\n  [{sym}] 청산 유형별")
            by_signal = sub.groupby("signal_type").agg(
                trades=("pnl","count"), pnl=("pnl","sum"), avg_pnl=("pnl","mean")
            ).sort_values("pnl")
            for sig, row in by_signal.iterrows():
                print(f"  {sig:<18} {int(row['trades']):>3}건  ${row['pnl']:>9,.0f}  (평균 ${row['avg_pnl']:>7,.0f})")


if __name__ == "__main__":
    main()
