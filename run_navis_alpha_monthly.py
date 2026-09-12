"""
NAVIS ALPHA v1.0 — 월말 리밸런싱 진입점

Railway Cron 또는 로컬에서 매월 마지막 거래일에 실행합니다.

사용:
    python run_navis_alpha_monthly.py            # 실제 주문 제출
    python run_navis_alpha_monthly.py --dry-run  # 시뮬레이션만 (주문 없음)

환경변수:
    ALPACA_API_KEY     (필수)
    ALPACA_SECRET_KEY  (필수)
    ALPACA_BASE_URL    (선택 — 기본: https://paper-api.alpaca.markets)
"""
import argparse
import logging
import sys
from datetime import date

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("navis_alpha.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("navis_alpha_runner")


def main():
    parser = argparse.ArgumentParser(description="NAVIS ALPHA v1.0 월간 리밸런싱")
    parser.add_argument("--dry-run", action="store_true", help="주문 없이 시뮬레이션만")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"NAVIS ALPHA v1.0 월간 리밸런싱 — {date.today()}")
    logger.info(f"모드: {'DRY RUN' if args.dry_run else '페이퍼 트레이딩'}")
    logger.info("=" * 60)

    try:
        from navis_alpha.paper_trader import NavisAlphaPaperTrader
        trader  = NavisAlphaPaperTrader.from_env(dry_run=args.dry_run)
        summary = trader.rebalance()

        logger.info("─" * 60)
        logger.info("리밸런싱 요약:")
        logger.info(f"  날짜:       {summary['date']}")
        logger.info(f"  계좌 자산:  ${summary['equity']:,.0f}")
        logger.info(f"  보유 종목:  {summary['n_target']}개")
        logger.info(f"  매도:       {summary['n_sells']}종목")
        logger.info(f"  매수:       {summary['n_buys']}종목")
        logger.info(f"  상위 종목:  {', '.join(summary['top_symbols'])}")
        logger.info(f"  상태:       {summary['status']}")
        logger.info("─" * 60)

    except KeyError as e:
        logger.error(f"환경변수 누락: {e}")
        logger.error("ALPACA_API_KEY, ALPACA_SECRET_KEY 설정을 확인하세요.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"리밸런싱 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
