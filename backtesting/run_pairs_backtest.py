"""
NAVIS 페어 트레이딩 백테스트 실행기 (P16)

사용 예:
  # Step 0: 페어 선정 캐시 빌드 (최초 1회, 30분~1시간)
  python backtesting/run_pairs_backtest.py --build-pairs --sp500

  # P16-1: 기본 파라미터
  python backtesting/run_pairs_backtest.py \\
    --pairs-file pairs_cache.json \\
    --entry-z 2.0 --exit-z 0.5 --stop-z 3.5 \\
    --max-pairs 20 --capital-per-pair 5 \\
    --start 2021-01-01

  # P16-2: 진입 완화
  python backtesting/run_pairs_backtest.py \\
    --pairs-file pairs_cache.json \\
    --entry-z 1.5 --exit-z 0.5 --stop-z 3.0 \\
    --max-pairs 20 --capital-per-pair 5 \\
    --start 2021-01-01
"""
from __future__ import annotations

import argparse
import json
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
logger = logging.getLogger("run_pairs_backtest")


def main():
    parser = argparse.ArgumentParser(description="NAVIS 페어 트레이딩 백테스트 (P16)")

    # 모드
    parser.add_argument("--build-pairs", action="store_true",
                        help="페어 선정 후 pairs_cache.json 저장 (최초 1회, ~30분)")

    # 유니버스
    parser.add_argument("--sp500", action="store_true", help="S&P 500 유니버스 (~500종목)")
    parser.add_argument("--itc",   action="store_true", help="ITC 16종목 유니버스")

    # 페어 선정 옵션 (--build-pairs 시 사용)
    parser.add_argument("--min-corr",    type=float, default=0.70,
                        help="최소 상관계수 (기본 0.70)")
    parser.add_argument("--coint-pval",  type=float, default=0.05,
                        help="공적분 p-value 상한 (기본 0.05)")
    parser.add_argument("--min-dv",      type=float, default=20.0,
                        help="최소 일평균 달러 거래량 $M (기본 $20M)")
    parser.add_argument("--cross-sector", action="store_true",
                        help="섹터 제한 없이 전체 조합 검정 (기본: 동일 섹터만)")
    parser.add_argument("--pairs-file",  default="pairs_cache.json",
                        help="페어 캐시 파일 경로 (기본 pairs_cache.json)")

    # 백테스트 파라미터 (백테스트 모드 시)
    parser.add_argument("--entry-z",     type=float, default=2.0,
                        help="진입 Z-score 임계값 (기본 2.0)")
    parser.add_argument("--exit-z",      type=float, default=0.5,
                        help="청산 Z-score 임계값 (기본 0.5)")
    parser.add_argument("--stop-z",      type=float, default=3.5,
                        help="손절 Z-score 임계값 (기본 3.5)")
    parser.add_argument("--zscore-win",  type=int,   default=60,
                        help="Z-score 롤링 창 거래일 (기본 60)")
    parser.add_argument("--max-pairs",   type=int,   default=20,
                        help="동시 최대 활성 페어 수 (기본 20)")
    parser.add_argument("--capital-per-pair", type=float, default=5.0,
                        help="페어당 자본 비율 %% (기본 5%%)")
    parser.add_argument("--max-hold",    type=int,   default=30,
                        help="최대 보유 거래일 (기본 30)")
    parser.add_argument("--max-sector-pairs", type=int, default=5,
                        help="섹터당 최대 동시 활성 페어 수 (기본 5)")

    # 공통
    parser.add_argument("--start",       default="2021-01-01")
    parser.add_argument("--end",         default="2026-04-21")
    parser.add_argument("--cache-dir",   default="cache")
    parser.add_argument("--sector-cache", default="sector_cache.json")
    parser.add_argument("--capital",     type=float, default=1_000_000)

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
        cache_dir = Path(args.cache_dir)
        daily_dir = cache_dir / "daily"
        if not daily_dir.exists():
            logger.error(f"캐시 없음: {daily_dir}")
            sys.exit(1)
        symbols = [f.stem for f in sorted(daily_dir.glob("*.parquet")) if f.stem != "SPY"]
        universe_label = f"캐시 전체 ({len(symbols)}종목)"

    logger.info(f"[PairsBT] 유니버스: {universe_label}")

    # ── 일봉 데이터 로드 ──────────────────────────────────────────────────
    from backtesting.universe_backtest.data_cache import DataCache
    cache_obj = DataCache(
        api_key    = os.getenv("ALPACA_API_KEY", ""),
        api_secret = os.getenv("ALPACA_SECRET_KEY", ""),
        cache_dir  = args.cache_dir,
    )

    logger.info(f"[PairsBT] 일봉 로드 중... ({len(symbols)}종목)")
    daily_data = {}
    for sym in symbols:
        df = cache_obj.load_daily(sym)
        if df is not None and len(df) > 0:
            daily_data[sym] = df
    logger.info(f"[PairsBT] 로드 완료: {len(daily_data)}/{len(symbols)}종목")

    spy_daily = cache_obj.load_daily("SPY")

    # ── 모드 분기 ─────────────────────────────────────────────────────────
    if args.build_pairs:
        _build_pairs(args, daily_data, universe_label)
    else:
        _run_backtest(args, daily_data, spy_daily, universe_label)


# ── 페어 선정 ─────────────────────────────────────────────────────────────

def _build_pairs(args, daily_data: dict, universe_label: str) -> None:
    """공적분 페어 선정 후 pairs_cache.json 저장."""
    from backtesting.pairs_backtest.pair_selector import (
        find_cointegrated_pairs, load_sector_map
    )

    sector_map = load_sector_map(args.sector_cache)
    logger.info(f"[PairsBT] 섹터 맵: {len(sector_map)}종목 로드")

    logger.info(
        f"[PairsBT] 페어 선정 시작 | "
        f"corr>={args.min_corr} | coint_p<={args.coint_pval} | "
        f"min_dv=${args.min_dv}M | cross_sector={args.cross_sector}"
    )

    pairs = find_cointegrated_pairs(
        daily_data         = daily_data,
        sector_map         = sector_map,
        min_corr           = args.min_corr,
        coint_pvalue       = args.coint_pval,
        min_dollar_volume  = args.min_dv * 1e6,
        cross_sector       = args.cross_sector,
    )

    if not pairs:
        logger.error("[PairsBT] 공적분 페어를 찾지 못했습니다. 파라미터 완화 필요")
        sys.exit(1)

    # 저장
    with open(args.pairs_file, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2, ensure_ascii=False)
    logger.info(f"[PairsBT] {len(pairs)}개 페어 저장: {args.pairs_file}")

    # 선정 결과 출력
    _print_pairs_summary(pairs)


def _print_pairs_summary(pairs: list) -> None:
    """페어 선정 결과 요약 출력."""
    print()
    print("=" * 65)
    print("  페어 선정 결과 (Step 0)")
    print("=" * 65)
    print(f"  총 선정 페어: {len(pairs)}개")
    print()

    # 섹터별 분포
    from collections import Counter
    sector_counts = Counter(p.get("sector", "Unknown") for p in pairs)
    print("  [섹터별 분포]")
    for sec, cnt in sector_counts.most_common():
        bar = "#" * min(cnt, 40)
        print(f"    {sec:<35s} {cnt:3d}개  {bar}")

    print()
    print("  [상위 10개 페어 (공적분 강도 순)]")
    print(f"  {'#':3s}  {'Pair':<25s}  {'섹터':<20s}  {'p-value':>8s}  {'corr':>6s}  {'hedge':>6s}")
    print("  " + "-" * 75)
    for i, p in enumerate(pairs[:10], 1):
        pair_str = f"{p['symbol_a']}/{p['symbol_b']}"
        print(
            f"  {i:2d}.  {pair_str:<25s}  {p.get('sector','?'):<20s}  "
            f"{p['pvalue']:8.4f}  {p['corr']:6.3f}  {p['hedge_ratio']:6.3f}"
        )
    print()


# ── 백테스트 실행 ─────────────────────────────────────────────────────────

def _run_backtest(args, daily_data: dict, spy_daily, universe_label: str) -> None:
    """pairs_cache.json 로드 후 백테스트 실행."""
    pairs_file = args.pairs_file
    if not Path(pairs_file).exists():
        logger.error(
            f"[PairsBT] {pairs_file} 없음. "
            f"먼저 --build-pairs 로 페어를 선정하세요."
        )
        sys.exit(1)

    with open(pairs_file, encoding="utf-8") as f:
        pairs = json.load(f)
    logger.info(f"[PairsBT] {len(pairs)}개 페어 로드: {pairs_file}")

    from backtesting.pairs_backtest.engine import PairsBacktestConfig, PairsBacktestEngine

    config = PairsBacktestConfig(
        pairs             = pairs,
        entry_z           = args.entry_z,
        exit_z            = args.exit_z,
        stop_z            = args.stop_z,
        zscore_window     = args.zscore_win,
        max_pairs         = args.max_pairs,
        capital_per_pair  = args.capital_per_pair / 100,
        max_hold_days     = args.max_hold,
        max_sector_pairs  = args.max_sector_pairs,
        initial_capital   = args.capital,
        start_date        = args.start,
        end_date          = args.end,
    )

    logger.info(
        f"[PairsBT] 백테스트 | "
        f"entry_z={args.entry_z} exit_z={args.exit_z} stop_z={args.stop_z} | "
        f"max_pairs={args.max_pairs} capital/pair={args.capital_per_pair}% | "
        f"{args.start} ~ {args.end}"
    )

    engine = PairsBacktestEngine(config, daily_data, spy_daily=spy_daily)
    result = engine.run()

    if not result:
        logger.error("[PairsBT] 결과 없음")
        sys.exit(1)

    _print_report(result, universe_label, args)


def _print_report(result: dict, universe_label: str, args) -> None:
    """백테스트 결과 보고서 출력."""
    cagr   = result["cagr"]
    sharpe = result["sharpe"]

    if cagr >= 15 and sharpe >= 1.2:
        verdict = "[합격] V4 + 페어 트레이딩 통합 포트폴리오 설계"
    elif cagr >= 10 and sharpe >= 0.8:
        verdict = "[부분 합격] Z 임계값 / 페어 수 파라미터 조정"
    else:
        verdict = "[실패] 전략 구조 전면 재논의 (대표님 직접 결정)"

    spy_vs = ""
    if result.get("spy_cagr") is not None:
        excess = cagr - result["spy_cagr"]
        spy_vs = f" (SPY {result['spy_cagr']:.1f}% 대비 {excess:+.1f}%p)"

    print()
    print("=" * 65)
    print("  NAVIS 페어 트레이딩 백테스트 결과 (P16)")
    print("=" * 65)
    print(f"  유니버스        : {universe_label}")
    print(f"  Z (진입/청산/손절): {args.entry_z} / {args.exit_z} / {args.stop_z}")
    print(f"  최대 페어       : {args.max_pairs}개 | 페어당 {args.capital_per_pair}%")
    print(f"  기간            : {args.start} ~ {args.end}")
    print()
    print(f"  CAGR            : {cagr:.2f}%{spy_vs}")
    print(f"  총 수익률       : {result['total_ret_pct']:.2f}%  (${result['final_capital']:,.0f})")
    print(f"  Sharpe Ratio    : {sharpe:.3f}")
    print(f"  Sortino Ratio   : {result['sortino']:.3f}")
    print(f"  Max Drawdown    : {result['max_drawdown']:.2f}%")
    print(f"  MDD 기간        : {result['mdd_start']} ~ {result['mdd_end']}")
    print(f"  Profit Factor   : {result['profit_factor']:.3f}")
    print(f"  승률            : {result['win_rate']:.1f}%")
    print(f"  총 거래         : {result['total_trades']}건  (연평균 {result['total_trades']/result['n_years']:.0f}건)")
    print(f"  평균 보유       : {result['avg_hold_days']:.1f}거래일")
    print()

    # 청산 유형
    et = result["exit_types"]
    print("  [청산 유형]")
    for reason, cnt in sorted(et.items(), key=lambda x: -x[1]):
        print(f"    {reason:<15s}: {cnt:4d}건")
    print()

    # 연도별 수익률
    print("  [연도별 수익률]")
    for yr, ret in sorted(result["yearly_ret"].items()):
        bar = "+" if ret >= 0 else "-"
        print(f"    {yr}: {ret:+.2f}%  [{bar}]")

    if result.get("spy_cagr") is not None:
        print(f"\n  [벤치마크] SPY CAGR: {result['spy_cagr']:.2f}%")

    # 상위/하위 페어
    print()
    print("  [상위 기여 페어 10]")
    for pair_id, pnl in result["top10_pairs"]:
        print(f"    {pair_id:<25s}  ${pnl:>10,.0f}")

    print()
    print("  [하위 기여 페어 10]")
    for pair_id, pnl in result["bot10_pairs"]:
        print(f"    {pair_id:<25s}  ${pnl:>10,.0f}")

    print()
    print(f"  판정: {verdict}")
    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
