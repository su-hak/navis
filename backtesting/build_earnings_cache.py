"""
NAVIS Earnings Calendar Cache Builder
======================================
yfinance.earnings_dates 를 사용하여 종목별 실적 발표 후 갭 발생일(T+1)을 수집한다.

발표 시각 분류:
  - BMO (Before Market Open): 당일 갭 발생 → 발표일(T) 저장
  - AMC (After Market Close): 다음 거래일 갭 발생 → T+1 저장

저장 형식 (earnings_cache.json):
{
    "NVDA": ["2021-02-25", "2021-05-27", ...],  # 갭 발생 거래일
    ...
}

사용법:
    # ITC 유니버스 (기본)
    python backtesting/build_earnings_cache.py

    # ITC Extended 유니버스
    python backtesting/build_earnings_cache.py --itc-universe-ext

    # S&P 500 전체
    python backtesting/build_earnings_cache.py --sp500

    # 특정 종목
    python backtesting/build_earnings_cache.py --symbols NVDA CRM ORCL
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.trading_constants import ITC_UNIVERSE, ITC_UNIVERSE_EXTENDED

logger = logging.getLogger(__name__)

# ─── 상수 ────────────────────────────────────────────────────────────────────

# pandas_market_calendars 로 NYSE 거래일 조회
try:
    import pandas_market_calendars as mcal
    _NYSE = mcal.get_calendar("NYSE")
    _HAS_MCal = True
except ImportError:
    _HAS_MCal = False
    logger.warning("pandas_market_calendars 없음 — 간이 거래일 추정 사용")

# BMO 판정 기준 시각 (시 단위, 현지 시간 기준)
# 어닝 시각이 12:00 이전이면 BMO, 이후면 AMC
_BMO_HOUR_THRESHOLD = 12


def _get_next_trading_day(dt: date) -> date:
    """dt 이후 첫 번째 NYSE 거래일 반환 (dt 자신 제외)."""
    if _HAS_MCal:
        schedule = _NYSE.schedule(
            start_date=dt + timedelta(days=1),
            end_date=dt + timedelta(days=10),
        )
        if not schedule.empty:
            return schedule.index[0].date()
    # fallback: 주말만 건너뜀 (공휴일 미반영)
    next_day = dt + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day


def _is_trading_day(dt: date) -> bool:
    """NYSE 거래일 여부."""
    if _HAS_MCal:
        schedule = _NYSE.schedule(start_date=dt, end_date=dt)
        return not schedule.empty
    return dt.weekday() < 5  # fallback


def fetch_earnings_dates(
    symbol: str,
    start: str = "2021-01-01",
    end: Optional[str] = None,
) -> List[str]:
    """
    yfinance로 symbol의 실적 발표 후 갭 발생일(거래일) 리스트를 반환.

    Returns:
        ["2021-02-25", "2021-05-27", ...] — 갭 발생 거래일(YYYY-MM-DD) 오름차순
    """
    import yfinance as yf

    start_date = date.fromisoformat(start)
    end_date   = date.fromisoformat(end) if end else date.today()

    ticker = yf.Ticker(symbol)
    try:
        ed = ticker.earnings_dates  # DataFrame, index=DatetimeTZ
    except Exception as e:
        logger.warning(f"[{symbol}] earnings_dates 조회 실패: {e}")
        return []

    if ed is None or ed.empty:
        logger.warning(f"[{symbol}] earnings_dates 없음")
        return []

    gap_dates: List[str] = []
    for ts, row in ed.iterrows():
        # ts: Timestamp with tz (e.g. 2025-11-19 16:00:00-05:00)
        try:
            local_dt: datetime = ts.to_pydatetime()
            ann_date: date     = local_dt.date()
            ann_hour: int      = local_dt.hour
        except Exception:
            continue

        # 범위 필터 (발표일 기준)
        if ann_date < start_date or ann_date > end_date:
            continue

        # EPS Estimate가 NaN이면 미래 예정일 → 제외
        eps_est = row.get("EPS Estimate", float("nan"))
        if pd.isna(eps_est):
            continue

        # BMO / AMC 판별 → 갭 발생 거래일 결정
        if ann_hour < _BMO_HOUR_THRESHOLD:
            # BMO: 발표 당일 장전에 갭 발생
            gap_day = ann_date
        else:
            # AMC: 발표 다음 거래일에 갭 발생
            gap_day = _get_next_trading_day(ann_date)

        # 거래일 검증
        if not _is_trading_day(gap_day):
            gap_day = _get_next_trading_day(gap_day)

        gap_dates.append(gap_day.strftime("%Y-%m-%d"))

    gap_dates = sorted(set(gap_dates))
    logger.info(f"[{symbol}] 갭 발생일 {len(gap_dates)}건 ({start} ~ {end or '오늘'})")
    return gap_dates


def fetch_sector(symbol: str) -> str:
    """yfinance로 GICS 섹터 조회. 실패 시 'Unknown' 반환."""
    import yfinance as yf
    try:
        info = yf.Ticker(symbol).info
        return info.get("sector", "Unknown") or "Unknown"
    except Exception:
        return "Unknown"


def build_cache(
    symbols: List[str],
    output_path: str = "earnings_cache.json",
    start: str = "2021-01-01",
    end: Optional[str] = None,
    delay: float = 0.5,
    with_sectors: bool = False,
) -> Dict[str, List[str]]:
    """
    symbols 전체 어닝 캐시를 수집하여 JSON에 저장.

    Args:
        symbols:      수집할 종목 리스트
        output_path:  출력 파일 경로
        start:        수집 시작일 (YYYY-MM-DD)
        end:          수집 종료일 (None=오늘)
        delay:        종목 간 API 호출 딜레이(초)
        with_sectors: True 시 섹터 정보도 sector_cache.json에 함께 저장

    Returns:
        {symbol: [gap_date, ...]} 딕셔너리
    """
    cache: Dict[str, List[str]] = {}
    sector_cache: Dict[str, str] = {}

    output_file  = Path(output_path)
    sector_file  = output_file.parent / "sector_cache.json"

    # 기존 캐시 로드 (증분 업데이트)
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
        logger.info(f"기존 어닝 캐시 로드: {len(cache)}종목")

    if with_sectors and sector_file.exists():
        with open(sector_file, "r", encoding="utf-8") as f:
            sector_cache = json.load(f)
        logger.info(f"기존 섹터 캐시 로드: {len(sector_cache)}종목")

    total   = len(symbols)
    updated = 0

    for i, sym in enumerate(symbols, 1):
        logger.info(f"[{i}/{total}] {sym} 수집 중...")
        dates = fetch_earnings_dates(sym, start=start, end=end)

        if dates:
            cache[sym] = dates
            updated += 1
        else:
            cache.setdefault(sym, [])

        # 섹터 수집 (기존 캐시에 없는 종목만)
        if with_sectors and sym not in sector_cache:
            sector_cache[sym] = fetch_sector(sym)
            logger.info(f"  [{sym}] 섹터: {sector_cache[sym]}")

        # 중간 저장 (10종목마다)
        if i % 10 == 0:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            if with_sectors:
                with open(sector_file, "w", encoding="utf-8") as f:
                    json.dump(sector_cache, f, indent=2, ensure_ascii=False)
            logger.info(f"  중간 저장 완료 ({i}/{total})")

        if i < total:
            time.sleep(delay)

    # 최종 저장
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    if with_sectors:
        with open(sector_file, "w", encoding="utf-8") as f:
            json.dump(sector_cache, f, indent=2, ensure_ascii=False)
        logger.info(f"섹터 캐시 저장: {sector_file} ({len(sector_cache)}종목)")

    logger.info(
        f"\n어닝 캐시 저장 완료: {output_file}\n"
        f"  총 종목: {len(cache)} | 데이터 있는 종목: {updated}"
    )
    return cache


def validate_cache(cache: Dict[str, List[str]], symbols: List[str]) -> None:
    """캐시 검증 — 주요 종목의 샘플 날짜를 출력."""
    print("\n" + "=" * 60)
    print("  어닝 캐시 검증")
    print("=" * 60)

    # 알려진 실적일 검증 (NVDA 2026-02-25, CRM 2026-02-26)
    checks = {
        "NVDA": "2026-02-26",   # 2026-02-25 AMC → T+1
        "CRM":  "2026-02-26",   # 2026-02-25 AMC → T+1
        "ORCL": None,
    }

    for sym in symbols[:8]:  # 최대 8개 샘플
        dates = cache.get(sym, [])
        recent = dates[-5:] if len(dates) >= 5 else dates
        expected = checks.get(sym)
        status = ""
        if expected:
            status = " OK" if expected in dates else f" NG (expected {expected})"
        print(f"  {sym:8s}: {len(dates):3d}건  최근={recent}{status}")

    print("=" * 60)


# ─── S&P 500 종목 리스트 ──────────────────────────────────────────────────────

SP500_SYMBOLS = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB","AKAM",
    "ALB","ARE","ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN","AMCR","AMP",
    "AME","AMGN","APH","ADI","ANSS","AON","APA","AAPL","AMAT","APTV","ACGL","ADM",
    "ANET","AJG","AIZ","T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL",
    "BAC","BK","BBWI","BAX","BDX","BRK.B","BBY","BIO","TECH","BIIB","BLK","BX","BA",
    "BCH","BSX","BMY","AVGO","BR","BRO","BF.B","BLDR","BG","CDNS","CZR","CPT","CPB",
    "COF","CAH","KMX","CCL","CARR","CTLT","CAT","CBOE","CBRE","CDW","CE","COR","CNC",
    "CNX","CDAY","CF","CRL","SCHW","CHTR","CVX","CMG","CB","CHD","CI","CINF","CTAS",
    "CSCO","C","CFG","CLX","CME","CMS","KO","CTSH","CL","CMCSA","CAG","COP","ED",
    "STZ","CEG","COO","CPRT","GLW","CPAY","CTVA","CSGP","COST","CTRA","CRWD","CCI",
    "CSX","CMI","CVS","DHR","DRI","DVA","DAY","DECK","DE","DELL","DAL","DVN","DXCM",
    "FANG","DLR","DFS","DG","DLTR","D","DPZ","DOV","DOW","DHI","DTE","DUK","DD",
    "EMN","ETN","EBAY","ECL","EIX","EW","EA","ELV","EMR","ENPH","ETR","EOG","EPAM",
    "EQT","EFX","EQIX","EQR","ESS","EL","ETSY","EG","EVRST","ES","EXC","EXPE","EXPD",
    "EXR","XOM","FFIV","FDS","FICO","FAST","FRT","FDX","FIS","FITB","FSLR","FE",
    "FI","FMC","F","FTNT","FTV","FOXA","FOX","BEN","FCX","GRMN","IT","GE","GEHC",
    "GEV","GEN","GNRC","GD","GIS","GM","GPC","GILD","GS","HAL","HIG","HAS","HCA",
    "DOC","HSIC","HSY","HES","HPE","HLT","HOLX","HD","HON","HRL","HST","HWM","HPQ",
    "HUBB","HUM","HBAN","HII","IBM","IEX","IDXX","ITW","INCY","IR","PODD","INTC",
    "ICE","IFF","IP","IPG","INTU","ISRG","IVZ","INVH","IQV","IRM","JBAL","JKHY",
    "J","JBL","JNPR","JPM","K","KVUE","KDP","KEY","KEYS","KMB","KIM","KMI","KKR",
    "KLAC","KHC","KR","LHX","LH","LRCX","LW","LVS","LDOS","LEN","LLY","LIN",
    "LYV","LKQ","LMT","L","LOW","LULU","LYB","MTB","MRO","MPC","MKTX","MAR","MMC",
    "MLM","MAS","MA","MTCH","MKC","MCD","MCK","MDT","MRK","META","MET","MTD","MGM",
    "MCHP","MU","MSFT","MAA","MRNA","MHK","MOH","TAP","MDLZ","MPWR","MNST","MCO",
    "MS","MOS","MSI","MSCI","NDAQ","NTAP","NOW","NEM","NFLX","NI","NDSN","NSC",
    "NTRS","NOC","NCLH","NRG","NUE","NVDA","NVR","NXPI","ORLY","OXY","ODFL","OMC",
    "ON","OKE","ORCL","OTIS","OC","OGN","PCAR","PKG","PLTR","PH","PAYX","PAYC",
    "PYPL","PNR","PEP","PFE","PCG","PM","PSX","PNW","PNC","POOL","PPG","PPL","PFG",
    "PG","PGR","PLD","PRU","PEG","PTC","PSA","PHM","QRVO","PWR","QCOM","DGX","RL",
    "RJF","RTX","O","REG","REGN","RF","RSG","RMD","RVTY","ROK","ROL","ROP","ROST",
    "RCL","SPGI","CRM","SBAC","SLB","STX","SRE","NOW","SHW","SPG","SWKS","SJM",
    "SW","SNA","SOLV","SO","LUV","SWK","SBUX","STT","STLD","STE","SYK","SMCI","SYF",
    "SNPS","SYY","TMUS","TROW","TTWO","TPR","TRGP","TGT","TEL","TDY","TFX","TER",
    "TSLA","TXN","TXT","TMO","TJX","TSCO","TT","TDG","TRV","TRMB","TFC","TYL",
    "TSN","USB","UBER","UDR","ULTA","UNP","UAL","UPS","URI","UNH","UHS","VLO","VTR",
    "VLTO","VRSN","VRSK","VZ","VRTX","VTRS","VICI","V","VST","VMC","WRB","GWW",
    "WAB","WBA","WMT","DIS","WBD","WM","WAT","WEC","WFC","WELL","WST","WDC","WY",
    "WMB","WTW","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS",
]


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="NAVIS Earnings Calendar Cache Builder")
    parser.add_argument("--symbols",        nargs="+", metavar="SYM",
                        help="수집할 특정 종목 리스트")
    parser.add_argument("--itc-universe",   action="store_true",
                        help="ITC 유니버스 16종목 (기본)")
    parser.add_argument("--itc-universe-ext", action="store_true",
                        help="ITC Extended 유니버스 24종목")
    parser.add_argument("--sp500",          action="store_true",
                        help="S&P 500 전체 종목 (~500개)")
    parser.add_argument("--start",          default="2021-01-01",
                        help="수집 시작일 (기본: 2021-01-01)")
    parser.add_argument("--end",            default=None,
                        help="수집 종료일 (기본: 오늘)")
    parser.add_argument("--output",         default="earnings_cache.json",
                        help="출력 파일 경로 (기본: earnings_cache.json)")
    parser.add_argument("--delay",          type=float, default=0.5,
                        help="종목 간 딜레이(초, 기본: 0.5)")
    parser.add_argument("--with-sectors",   action="store_true",
                        help="섹터 정보도 함께 수집하여 sector_cache.json 저장")
    args = parser.parse_args()

    # 종목 리스트 결정
    if args.symbols:
        symbols = args.symbols
    elif args.sp500:
        symbols = SP500_SYMBOLS
    elif args.itc_universe_ext:
        symbols = ITC_UNIVERSE_EXTENDED
    else:
        # 기본: ITC 유니버스
        symbols = ITC_UNIVERSE

    logger.info(f"수집 대상: {len(symbols)}종목 | 기간: {args.start} ~ {args.end or '오늘'}")
    logger.info(f"출력: {args.output}")

    cache = build_cache(
        symbols=symbols,
        output_path=args.output,
        start=args.start,
        end=args.end,
        delay=args.delay,
        with_sectors=getattr(args, "with_sectors", False),
    )

    validate_cache(cache, symbols)


if __name__ == "__main__":
    main()
