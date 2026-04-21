"""
NAVIS 팩터 모멘텀 백테스트 실행기 (P15)

사용 예:
  # P15-1: ITC 유니버스, 상위 50%
  python backtesting/run_factor_backtest.py --itc --top-pct 50 --min-dv 10 --start 2021-01-01

  # P15-2: S&P 500, 상위 20%
  python backtesting/run_factor_backtest.py --sp500 --top-pct 20 --min-dv 50 --start 2021-01-01

  # P15-3: S&P 500, 상위 10% (집중 포트폴리오)
  python backtesting/run_factor_backtest.py --sp500 --top-pct 10 --min-dv 50 --start 2021-01-01
"""
from __future__ import annotations

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
logger = logging.getLogger("run_factor_backtest")


def main():
    parser = argparse.ArgumentParser(description="NAVIS 팩터 모멘텀 백테스트 (P15)")

    # 유니버스
    parser.add_argument("--sp500", action="store_true", help="S&P 500 유니버스 (~500종목)")
    parser.add_argument("--itc",   action="store_true", help="ITC 16종목 유니버스")

    # 팩터 파라미터
    parser.add_argument("--top-pct",     type=float, default=20.0,
                        help="상위 선택 비율 %% (기본 20)")
    parser.add_argument("--min-dv",      type=float, default=50.0,
                        help="최소 일평균 달러 거래량 $M (기본 $50M)")
    parser.add_argument("--max-pos-pct", type=float, default=5.0,
                        help="단일 종목 최대 비중 %% (기본 5)")
    parser.add_argument("--min-price",   type=float, default=5.0,
                        help="최소 주가 $$ (기본 5)")

    # 백테스트 기간
    parser.add_argument("--start",   default="2021-01-01", help="시작일 (기본 2021-01-01)")
    parser.add_argument("--end",     default="2026-04-21", help="종료일 (기본 2026-04-21)")

    # 캐시
    parser.add_argument("--cache-dir", default="cache", help="캐시 디렉토리 (기본 cache)")

    # 자본
    parser.add_argument("--capital", type=float, default=1_000_000,
                        help="초기 자본 (기본 1,000,000)")

    args = parser.parse_args()

    # ── 유니버스 선택 ─────────────────────────────────────────────────────
    if args.itc:
        from config.trading_constants import ITC_UNIVERSE
        symbols = list(ITC_UNIVERSE)
        universe_label = f"ITC ({len(symbols)}종목)"
    elif args.sp500:
        from backtesting.build_earnings_cache import SP500_SYMBOLS
        symbols = list(SP500_SYMBOLS)
        universe_label = f"S&P 500 ({len(symbols)}종목)"
    else:
        # 기본: 캐시에 있는 모든 종목
        cache_dir = Path(args.cache_dir)
        daily_dir = cache_dir / "daily"
        if not daily_dir.exists():
            logger.error(f"[FactorBT] 캐시 없음: {daily_dir}. --build-cache 먼저 실행하세요.")
            sys.exit(1)
        symbols = [f.stem for f in sorted(daily_dir.glob("*.parquet")) if f.stem != "SPY"]
        universe_label = f"캐시 전체 ({len(symbols)}종목)"

    logger.info(f"[FactorBT] 유니버스: {universe_label}")
    logger.info(
        f"[FactorBT] 파라미터: 상위 {args.top_pct:.0f}% | 최소 달러 거래량 ${args.min_dv:.0f}M "
        f"| 최대 포지션 {args.max_pos_pct:.0f}% | 기간 {args.start} ~ {args.end}"
    )

    # ── 일봉 데이터 로드 ──────────────────────────────────────────────────
    from backtesting.universe_backtest.data_cache import DataCache
    cache = DataCache(
        api_key    = os.getenv("ALPACA_API_KEY", ""),
        api_secret = os.getenv("ALPACA_SECRET_KEY", ""),
        cache_dir  = args.cache_dir,
    )

    logger.info(f"[FactorBT] 일봉 데이터 로드 중... ({len(symbols)}종목)")
    daily_data = {}
    loaded = 0
    for sym in symbols:
        df = cache.load_daily(sym)
        if df is not None and len(df) > 0:
            daily_data[sym] = df
            loaded += 1
    logger.info(f"[FactorBT] 로드 완료: {loaded}/{len(symbols)}종목")

    # SPY 일봉 (벤치마크)
    spy_daily = cache.load_daily("SPY")

    # ── 백테스트 실행 ────────────────────────────────────────────────────
    from backtesting.factor_backtest.engine import FactorBacktestConfig, FactorBacktestEngine

    config = FactorBacktestConfig(
        symbols           = [s for s in symbols if s in daily_data],
        top_pct           = args.top_pct / 100,
        min_dollar_volume = args.min_dv * 1e6,
        max_position_pct  = args.max_pos_pct / 100,
        min_price         = args.min_price,
        initial_capital   = args.capital,
        start_date        = args.start,
        end_date          = args.end,
    )

    engine = FactorBacktestEngine(config, daily_data, spy_daily=spy_daily)
    result = engine.run()

    if not result:
        logger.error("[FactorBT] 결과 없음. 데이터 또는 기간 확인 필요.")
        sys.exit(1)

    # ── 결과 출력 ────────────────────────────────────────────────────────
    _print_report(result, universe_label, args)


def _print_report(result: dict, universe_label: str, args) -> None:
    """결과 보고서 출력."""

    # 합격 판정
    cagr   = result["cagr"]
    sharpe = result["sharpe"]
    if cagr >= 15 and sharpe >= 0.8:
        verdict = "[합격] V4 + 팩터 모멘텀 통합 포트폴리오 설계"
    elif cagr >= 10 and sharpe >= 0.6:
        verdict = "[부분 합격] top-pct / 유동성 필터 조정 후 재시도"
    else:
        verdict = "[실패] 전략 D (페어 트레이딩) 착수"

    spy_vs = ""
    if result.get("spy_cagr") is not None:
        excess = cagr - result["spy_cagr"]
        spy_vs = f" (SPY {result['spy_cagr']:.1f}% 대비 {excess:+.1f}%p)"

    print()
    print("=" * 60)
    print("  NAVIS 팩터 모멘텀 백테스트 결과 (P15)")
    print("=" * 60)
    print(f"  유니버스         : {universe_label}")
    print(f"  상위 선택        : {args.top_pct:.0f}%")
    print(f"  최소 달러 거래량 : ${args.min_dv:.0f}M")
    print(f"  기간             : {args.start} ~ {args.end}")
    print()
    print(f"  CAGR             : {cagr:.2f}%{spy_vs}")
    print(f"  총 수익률        : {result['total_ret_pct']:.2f}%  (${result['final_capital']:,.0f})")
    print(f"  Sharpe Ratio     : {sharpe:.3f}")
    print(f"  Sortino Ratio    : {result['sortino']:.3f}")
    print(f"  Max Drawdown     : {result['max_drawdown']:.2f}%")
    print(f"  MDD 기간         : {result['mdd_start']} ~ {result['mdd_end']}")
    print(f"  Profit Factor    : {result['profit_factor']:.3f}")
    print(f"  승률             : {result['win_rate']:.1f}%")
    print(f"  총 SELL 거래     : {result['total_trades']}건")
    print()
    print(f"  월 수익률 최고   : {result['best_month']:.2f}%")
    print(f"  월 수익률 최저   : {result['worst_month']:.2f}%")
    print(f"  월 수익률 평균   : {result['avg_month']:.2f}%")
    print()
    print(f"  판정: {verdict}")
    print("=" * 60)

    # 연도별 수익률
    print()
    print("  [연도별 수익률]")
    for yr, ret in sorted(result["yearly_ret"].items()):
        bar = "▲" if ret >= 0 else "▼"
        print(f"    {yr}: {ret:+.2f}%  {bar}")

    # 벤치마크
    if result.get("spy_ret_pct") is not None:
        print()
        print(f"  [벤치마크] SPY 동기간: {result['spy_ret_pct']:.2f}%  "
              f"(CAGR {result['spy_cagr']:.2f}%)")

    # 상위/하위 종목
    print()
    print("  [상위 기여 종목 10]")
    for sym, pnl in result["top10_symbols"]:
        print(f"    {sym:8s}  ${pnl:>10,.0f}")

    print()
    print("  [하위 기여 종목 10]")
    for sym, pnl in result["bot10_symbols"]:
        print(f"    {sym:8s}  ${pnl:>10,.0f}")

    print()


if __name__ == "__main__":
    main()
