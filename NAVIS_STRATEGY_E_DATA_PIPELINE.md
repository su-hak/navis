# NAVIS 전략 E — 데이터 파이프라인 구현 지시서
**작성일**: 2026-05-02  
**작성자**: 퀀트 트레이더 (Claude)  
**대상**: 개발 1팀  
**선행 문서**: NAVIS_STRATEGY_E_QUALITY_VALUE_CEO.md  
**착수 조건**: 이 문서의 데이터 파이프라인 구축 완료 후 P17 백테스트 착수 가능

---

## 왜 이 문서가 별도로 필요한가

기존 NAVIS 백테스트는 **주가 일봉(OHLCV)** 데이터만 사용했습니다.  
전략 E는 NAVIS 최초로 **재무제표 데이터**를 사용하며, 이 데이터에는 주가 데이터에 없는
고유한 문제인 **Point-in-time(시점 정합성)** 이슈가 있습니다.

이를 잘못 처리하면 백테스트가 실전보다 비현실적으로 좋게 나옵니다.  
이 문서는 그 문제를 올바르게 해결하는 방법을 명시합니다.

---

## 1. 데이터 요구사항 전체 목록

| 데이터 종류 | 용도 | 기존 보유 | 신규 필요 |
|-----------|------|---------|---------|
| 주가 일봉 (OHLCV) | 진입·청산 가격 | ✅ | — |
| 분기별 재무제표 | F-Score 계산 | ❌ | ✅ |
| 재무제표 **공시일** | Point-in-time 처리 | ❌ | ✅ 필수 |
| 일별 시가총액 | 유니버스 필터 ($500M~$5B) | ❓ | ✅ |
| 일별 P/E·P/B·EV/EBITDA | Value 스크리닝 | ❌ | ✅ |
| 섹터 분류 (GICS) | 상대 저평가 비교 | ❌ | ✅ |
| 상장폐지 종목 이력 | 생존 편향 방지 | ❌ | ✅ 필수 |
| 주식 수 변동 이력 | F7(희석 여부) 계산 | ❌ | ✅ |
| SEC Form 4 | CEO 내부자 매수 신호 | ❌ | Phase 4-B |

---

## 2. Point-in-time 문제 — 가장 중요한 개념

### 문제 정의

```
Q1 2024 (1월~3월) 실적
    │
    └─▶ 기업 내부 결산: 3월 31일
    └─▶ SEC 10-Q 제출: 5월 9일  ← 시장이 이 데이터를 "알게 되는 날"
    └─▶ 일반 투자자 접근: 5월 9일~

잘못된 코드:  스크리닝 날짜 = 2024-04-01
              데이터 = Q1 2024 재무제표 (아직 공시 안 됨)
              → 룩어헤드 바이어스 발생

올바른 코드:  스크리닝 날짜 = 2024-04-01
              데이터 = Q4 2023 재무제표 (2024-02-15 공시 완료)
              → 해당 날짜에 실제로 알 수 있었던 데이터만 사용
```

### 구현 원칙

> **스크리닝 날짜에 사용할 수 있는 가장 최근 분기 데이터 =  
> filing_date ≤ 스크리닝 날짜인 것 중 period_end_date가 가장 최근인 것**

```python
def get_latest_available_fundamentals(symbol: str,
                                       as_of_date: str) -> FundamentalRecord:
    """
    as_of_date 기준으로 실제로 공시된 가장 최근 분기 재무제표를 반환.
    filing_date > as_of_date인 데이터는 절대 사용하지 않음.
    """
    records = load_fundamentals(symbol)  # 전체 분기 이력

    available = [
        r for r in records
        if r.filing_date <= as_of_date  # 공시 완료된 것만
    ]

    if not available:
        return None

    # 가장 최근 공시 분기
    return max(available, key=lambda r: r.period_end_date)
```

### 실제 공시 지연 현황

| 기업 규모 | 10-Q (분기) 제출 기한 | 10-K (연간) 제출 기한 |
|---------|------------------|------------------|
| 대형주 (Large Accelerated Filer) | 분기말 후 40일 | 연말 후 60일 |
| 중형주 (Accelerated Filer) | 분기말 후 40일 | 연말 후 75일 |
| 소형주 (Non-Accelerated Filer) | 분기말 후 45일 | 연말 후 90일 |

→ 전략 E 대상(스몰~미드캡) 기준: **분기말 후 평균 45~75일** 후에 데이터 사용 가능

---

## 3. 데이터 소스 선택 및 단계별 업그레이드 계획

### 현재 NAVIS 데이터 인프라

| 용도 | 현재 사용 API | 재무제표 제공 여부 |
|------|------------|----------------|
| 주가 일봉 (백테스트) | **Alpaca** (메인) + yfinance (대안) | ❌ |
| 주문 실행 / 페이퍼 트레이딩 | **Alpaca** | ❌ |
| 재무제표 | **없음** | — |

Alpaca는 주문 실행과 가격 데이터 전용 API로, 재무제표 데이터를 제공하지 않습니다.  
전략 E를 위해 재무 데이터 소스를 신규로 선택해야 합니다.

> ⚠️ **yfinance 재무 데이터 사용 금지**  
> yfinance는 이미 주가 데이터 대안으로 사용 중이나, 재무제표 용도로는 부적합합니다.  
> `filing_date`(공시일)를 제공하지 않아 Point-in-time 처리가 불가능하고,  
> 상장폐지 종목 데이터가 불완전하여 생존 편향이 발생합니다.

### 단계별 업그레이드 계획

수익이 발생하기 전과 후로 단계를 나눕니다.

---

#### Phase 4-A — 무료 조합 (현재: 백테스트·페이퍼 트레이딩 단계)

**재무제표**: SEC EDGAR Bulk ZIP (완전 무료, API 키 불필요)  
**섹터·시총·상장폐지**: Polygon.io 무료 (API 키 무료 발급)

| 항목 | SEC EDGAR | Polygon.io 무료 |
|------|-----------|----------------|
| 비용 | **$0** | **$0** |
| 재무제표 + `filing_date` | ✅ 원본 | — |
| 초기 수집 방식 | **Bulk ZIP 1회 다운로드** | API 호출 (소량) |
| rate limit | 10 req/초 (또는 ZIP) | 5 req/분 |
| 초기 구축 소요 시간 | **~30분** (ZIP 다운로드) | ~3시간 (섹터 1회) |
| 섹터·시총·상장폐지 | ❌ | ✅ |

```
역할 분담:
  SEC EDGAR  → 재무제표 전체 (Bulk ZIP 1회 다운로드, 이후 분기 증분)
  Polygon.io → 섹터 분류, 시가총액 이력, 상장폐지 이력
               (소량 호출이므로 느린 rate limit 문제 없음)
월 비용: $0
```

**SEC EDGAR Bulk ZIP 핵심 정보:**
```
다운로드 URL: https://data.sec.gov/api/xbrl/companyfacts.zip
크기: 약 1~2GB (압축)
내용: 미국 전체 상장·상장폐지 기업 재무제표 + filing_date 전부 포함
갱신: SEC가 매일 밤 재컴파일
사용법: 1회 다운로드 → 로컬 파싱 → 분기마다 재다운로드
```

---

#### Phase 4-B / Phase 5 — 유료 업그레이드 (실전 투입 후 수익 발생 시)

실전 운용 시작 후 **월 순수익 > $100 달성 시** 업그레이드를 검토합니다.

| 업그레이드 항목 | 비용 | 효과 |
|-------------|------|------|
| Polygon.io Starter | $29/월 | 재무제표·섹터·시총 단일 API 통합, 관리 단순화 |
| Financial Modeling Prep | $29/월 | 정형화 JSON, 구현 편의성 향상 (Polygon.io 대안) |

> **유료 전환 시 코드 변경 범위**:  
> `FundamentalsCollector`의 `BASE_URL`과 파싱 로직만 교체.  
> 엔진·스크리너·포트폴리오 매니저 코드는 변경 불필요.

---

### 전체 데이터 소스 로드맵

| 데이터 | Phase 4-A (무료, 현재) | Phase 5 (수익 후 선택) |
|------|----------------------|----------------------|
| 재무제표 + `filing_date` | **SEC EDGAR Bulk ZIP** | Polygon.io 유료로 통합 |
| 섹터·시총·상장폐지 | **Polygon.io 무료** | Polygon.io 유료로 통합 |
| 주가 일봉 | Alpaca (기존 유지) | Alpaca 유지 |
| 주문 실행 | Alpaca (기존 유지) | Alpaca 유지 |
| CEO Form 4 (내부자) | SEC EDGAR 무료 API | SEC EDGAR 유지 |
| **월 합계** | **$0** | **$29~** |

---

## 4. 데이터 저장 구조

```
data/
├── fundamentals/
│   ├── quarterly/
│   │   └── {SYMBOL}/
│   │       └── {SYMBOL}_quarterly.parquet
│   │           # 컬럼: period_end_date, filing_date, fiscal_quarter,
│   │           #        net_income, total_assets, cfo, lt_debt,
│   │           #        current_assets, current_liabilities, shares_outstanding,
│   │           #        revenue, gross_profit
│   │
│   └── valuation/
│       └── daily/
│           └── {YYYY}/
│               └── valuation_{YYYY-MM-DD}.parquet
│                   # 컬럼: symbol, date, pe, pb, ev_ebitda,
│                   #        market_cap, sector
│
├── universe/
│   ├── sector_map.parquet       # symbol → GICS sector (정적)
│   ├── delisted_stocks.parquet  # 상장폐지 종목 이력 (생존 편향 방지)
│   └── market_cap_daily/
│       └── market_cap_{YYYY-MM}.parquet  # 월별 시가총액 이력
│
└── insider/
    └── form4/
        └── {SYMBOL}/
            └── {SYMBOL}_form4.parquet    # Phase 4-B
```

### 핵심 스키마: `quarterly.parquet`

```python
# 분기별 재무제표 — symbol당 1개 파일, 전체 분기 누적
QUARTERLY_SCHEMA = {
    'symbol':               str,
    'period_end_date':      str,   # 'YYYY-MM-DD' — 분기 종료일
    'filing_date':          str,   # 'YYYY-MM-DD' — SEC 공시일 ← Point-in-time 핵심
    'fiscal_quarter':       str,   # 'Q1', 'Q2', 'Q3', 'Q4'
    'fiscal_year':          int,
    # Income Statement
    'revenue':              float,
    'gross_profit':         float,
    'net_income':           float,
    # Balance Sheet
    'total_assets':         float,
    'total_liabilities':    float,
    'lt_debt':              float,  # 장기부채
    'current_assets':       float,
    'current_liabilities':  float,
    'shares_outstanding':   float,
    # Cash Flow
    'cfo':                  float,  # 영업활동 현금흐름
}
```

---

## 5. 데이터 수집 모듈 구현

> **Phase 4-A 기준 (무료)**  
> - 재무제표: SEC EDGAR Bulk ZIP (API 키 불필요)  
> - 섹터·시총·상장폐지: Polygon.io 무료 (API 키 무료 발급: https://polygon.io)  
> - 설치: `pip install requests pandas pyarrow zipfile36`  
>  
> **Phase 5 유료 전환 시**: `FundamentalsCollector`의 `_download_and_parse()` 메서드만  
> Polygon.io/FMP API 호출로 교체. 나머지 코드 전부 그대로 유지.

### 5-1. `FundamentalsCollector` — SEC EDGAR Bulk ZIP 기반 재무제표 수집

**파일**: `data/collectors/fundamentals_collector.py`

```python
import requests, json, zipfile, io, time
import pandas as pd
from pathlib import Path

# SEC EDGAR XBRL 태그 → 내부 컬럼명 매핑
# 기업마다 다른 태그를 사용할 수 있으므로 우선순위 리스트로 정의
XBRL_TAG_MAP = {
    'revenue':           ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                          'SalesRevenueNet', 'SalesRevenueGoodsNet'],
    'gross_profit':      ['GrossProfit'],
    'net_income':        ['NetIncomeLoss', 'ProfitLoss', 'NetIncomeLossAvailableToCommonStockholdersDiluted'],
    'operating_income':  ['OperatingIncomeLoss'],
    'da':                ['DepreciationDepletionAndAmortization', 'DepreciationAndAmortization'],
    'total_assets':      ['Assets'],
    'total_liabilities': ['Liabilities'],
    'lt_debt':           ['LongTermDebt', 'LongTermDebtNoncurrent'],
    'current_assets':    ['AssetsCurrent'],
    'current_liabilities':['LiabilitiesCurrent'],
    'shares_outstanding':['CommonStockSharesOutstanding'],
    'cash':              ['CashAndCashEquivalentsAtCarryingValue', 'Cash'],
    'cfo':               ['NetCashProvidedByUsedInOperatingActivities'],
}


class FundamentalsCollector:
    """
    SEC EDGAR Bulk ZIP을 사용하여 전체 미국 상장기업 재무제표를 수집합니다.
    API 키 불필요, 완전 무료.

    동작 방식:
    1. companyfacts.zip (약 1~2GB) 1회 다운로드
    2. ZIP 내 각 기업의 JSON 파일을 파싱하여 분기별 재무 데이터 추출
    3. filing_date(= 'filed' 필드) 포함 → Point-in-time 처리 가능
    4. ticker → CIK 매핑은 company_tickers.json으로 해결

    유료 전환 시: 이 클래스만 Polygon.io/FMP API 호출로 교체,
                  나머지 엔진·스크리너 코드 변경 불필요.
    """

    ZIP_URL     = "https://data.sec.gov/api/xbrl/companyfacts.zip"
    TICKERS_URL = "https://data.sec.gov/files/company_tickers.json"
    HEADERS     = {"User-Agent": "NAVIS-Quant research@navis.com"}  # SEC 필수 헤더

    def __init__(self, data_dir: str = "data/fundamentals"):
        self.data_dir   = Path(data_dir)
        self.ticker_map = {}   # ticker → CIK (10자리 zero-padded)

    # ── 초기 구축 ──────────────────────────────────────────────

    def build_ticker_map(self) -> None:
        """ticker → CIK 매핑 테이블 로드. SEC에서 무료 제공."""
        resp = requests.get(self.TICKERS_URL, headers=self.HEADERS, timeout=30)
        data = resp.json()
        # {"0": {"cik_str": 320193, "ticker": "AAPL", ...}, ...}
        self.ticker_map = {
            v['ticker']: str(v['cik_str']).zfill(10)
            for v in data.values()
        }
        # 저장
        pd.DataFrame([
            {'ticker': t, 'cik': c} for t, c in self.ticker_map.items()
        ]).to_parquet(self.data_dir / 'ticker_cik_map.parquet', index=False)
        print(f"✅ ticker → CIK 매핑 완료: {len(self.ticker_map)}개")

    def download_bulk_zip(self) -> None:
        """
        companyfacts.zip 다운로드 (~1~2GB).
        주말 야간 1회 실행. 이후 분기 업데이트 시 재실행.
        """
        print("SEC EDGAR Bulk ZIP 다운로드 중... (약 1~2GB, 수 분 소요)")
        resp = requests.get(self.ZIP_URL, headers=self.HEADERS,
                            stream=True, timeout=300)
        zip_path = self.data_dir / 'companyfacts.zip'
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024*1024):
                f.write(chunk)
        print(f"✅ 다운로드 완료: {zip_path}")

    def parse_all(self, symbols: list[str]) -> None:
        """
        다운로드된 ZIP에서 대상 종목들의 재무 데이터를 추출·저장.
        API 호출 없음 — rate limit 없음.
        """
        zip_path = self.data_dir / 'companyfacts.zip'
        if not zip_path.exists():
            raise FileNotFoundError("companyfacts.zip 없음. download_bulk_zip() 먼저 실행")

        with zipfile.ZipFile(zip_path, 'r') as zf:
            for i, symbol in enumerate(symbols):
                cik = self.ticker_map.get(symbol)
                if not cik:
                    continue
                fname = f"CIK{cik}.json"
                if fname not in zf.namelist():
                    continue
                try:
                    data  = json.loads(zf.read(fname))
                    df    = self._parse_company_facts(symbol, data)
                    if df is not None and not df.empty:
                        self._save(symbol, df)
                    if i % 100 == 0:
                        print(f"  [{i}/{len(symbols)}] 파싱 중...")
                except Exception as e:
                    print(f"  ⚠️  {symbol} 파싱 실패: {e}")

    def _parse_company_facts(self, symbol: str, data: dict) -> pd.DataFrame:
        """
        companyfacts JSON → 분기별 재무 DataFrame 변환.
        filing_date = 'filed' 필드 (Point-in-time 핵심).
        """
        us_gaap = data.get('facts', {}).get('us-gaap', {})
        if not us_gaap:
            return None

        # 분기 보고서(10-Q) + 연간 보고서(10-K) 모두 수집
        # 기간별로 가장 최근 filed 값만 사용 (수정 공시 처리)
        records_by_period = {}

        for col_name, tags in XBRL_TAG_MAP.items():
            for tag in tags:
                if tag not in us_gaap:
                    continue
                units = us_gaap[tag].get('units', {}).get('USD', [])
                for u in units:
                    if u.get('form') not in ('10-Q', '10-K'):
                        continue
                    period = u.get('end')        # 분기 종료일
                    filed  = u.get('filed')      # ← filing_date (Point-in-time 핵심)
                    if not period or not filed:
                        continue

                    key = (period, filed)
                    if key not in records_by_period:
                        records_by_period[key] = {
                            'symbol': symbol,
                            'period_end_date': period,
                            'filing_date':     filed,
                            'form':            u.get('form'),
                        }
                    # 첫 번째로 매핑되는 태그 값 사용
                    if col_name not in records_by_period[key]:
                        records_by_period[key][col_name] = u.get('val')
                break  # 첫 번째 매칭 태그 사용

        if not records_by_period:
            return None

        df = pd.DataFrame(records_by_period.values())
        df = df.sort_values(['period_end_date', 'filing_date'], ascending=False)
        # 동일 period 내 가장 최근 filing만 유지 (수정 공시)
        df = df.drop_duplicates(subset='period_end_date', keep='first')
        return df

    def _save(self, symbol: str, df: pd.DataFrame) -> None:
        path = self.data_dir / 'quarterly' / symbol
        path.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path / f"{symbol}_quarterly.parquet", index=False)
```

### 5-2. `ValuationCollector` — 밸류에이션 지표 계산

**파일**: `data/collectors/valuation_collector.py`  
*(재무제표 소스 변경과 무관하게 동일 — SEC EDGAR·Polygon.io·FMP 모두 같은 코드 사용)*

```python
class ValuationCollector:
    """
    일별 P/E, P/B, EV/EBITDA를 계산합니다.
    주가(Alpaca 일봉) + 재무제표(SEC EDGAR 분기) 결합으로 산출합니다.
    외부 API 호출 없음 — 로컬 계산 전용.

    계산 방법:
    P/E       = 주가 / EPS_TTM        (최근 4분기 순이익 / 주식 수)
    P/B       = 주가 / BPS            (총자산 - 총부채) / 주식 수
    EV/EBITDA = (시가총액 + 순부채) / EBITDA_TTM
    EBITDA    = operating_income + D&A
    """

    def calculate(self, symbol: str, date: str,
                  price: float,
                  avail_fundamentals: pd.DataFrame) -> dict:
        """
        avail_fundamentals: filing_date <= date 인 분기 데이터만 포함된 DataFrame
                            (Point-in-time 필터 적용 후 전달할 것)
        """
        if avail_fundamentals.empty:
            return {'pe': None, 'pb': None, 'ev_ebitda': None}

        ttm = avail_fundamentals.nlargest(4, 'period_end_date')
        if len(ttm) < 2:
            return {'pe': None, 'pb': None, 'ev_ebitda': None}

        latest = ttm.iloc[0]
        shares = latest.get('shares_outstanding')
        if not shares or shares <= 0:
            return {'pe': None, 'pb': None, 'ev_ebitda': None}

        # P/E
        eps_ttm = ttm['net_income'].sum() / shares
        pe = round(price / eps_ttm, 2) if eps_ttm > 0 else None

        # P/B
        book_value = latest['total_assets'] - latest['total_liabilities']
        bps = book_value / shares
        pb = round(price / bps, 2) if bps > 0 else None

        # EV/EBITDA
        market_cap = price * shares
        net_debt   = latest.get('lt_debt', 0) - latest.get('cash', 0)
        da         = ttm['da'].fillna(0).sum()
        ebitda_ttm = ttm['operating_income'].sum() + da
        ev_ebitda  = round((market_cap + net_debt) / ebitda_ttm, 2) \
                     if ebitda_ttm > 0 else None

        return {'pe': pe, 'pb': pb, 'ev_ebitda': ev_ebitda}
```

### 5-3. `UniverseHistoryCollector` — 생존 편향 방지

**파일**: `data/collectors/universe_history_collector.py`

```python
class UniverseHistoryCollector:
    """
    생존 편향 방지를 위한 핵심 모듈.
    현재 상장된 종목만 수집하면 "망한 기업"을 제외한 편향이 생깁니다.

    Polygon.io 엔드포인트:
    - 현재 상장 종목: GET /v3/reference/tickers?active=true
    - 상장폐지 종목: GET /v3/reference/tickers?active=false
    """

    SLEEP_SEC = 12.0   # 무료 플랜 rate limit

    def collect_all_symbols(self) -> pd.DataFrame:
        """현재 상장 + 상장폐지 종목 전체 수집."""
        active   = self._fetch_tickers(active=True)
        delisted = self._fetch_tickers(active=False)

        active_df = pd.DataFrame([
            {'symbol': r['ticker'], 'name': r.get('name'),
             'exchange': r.get('primary_exchange'),
             'delisted_date': None, 'is_active': True}
            for r in active
        ])
        delisted_df = pd.DataFrame([
            {'symbol': r['ticker'], 'name': r.get('name'),
             'exchange': r.get('primary_exchange'),
             'delisted_date': r.get('delisted_utc', '')[:10],
             'is_active': False}
            for r in delisted
        ])
        return pd.concat([active_df, delisted_df], ignore_index=True)

    def _fetch_tickers(self, active: bool) -> list:
        results, url = [], "https://api.polygon.io/v3/reference/tickers"
        params = {'active': str(active).lower(), 'market': 'stocks',
                  'limit': 1000, 'apiKey': self.api_key}
        while url:
            resp = requests.get(url, params=params, timeout=15).json()
            results.extend(resp.get('results', []))
            url    = resp.get('next_url')
            params = {'apiKey': self.api_key}
            time.sleep(self.SLEEP_SEC)
        return results

    def get_universe_on_date(self, all_symbols: pd.DataFrame,
                              as_of_date: str) -> list[str]:
        active = all_symbols[all_symbols['is_active']]['symbol'].tolist()
        delisted_after = all_symbols[
            (~all_symbols['is_active']) &
            (all_symbols['delisted_date'] > as_of_date)
        ]['symbol'].tolist()
        return list(set(active) | set(delisted_after))
```

### 5-4. `SectorMapper` — GICS 섹터 분류

**파일**: `data/collectors/sector_mapper.py`

```python
class SectorMapper:
    """
    Polygon.io /v3/reference/tickers/{symbol} API에서
    SIC 코드 기반 섹터 정보를 수집하여 GICS로 매핑합니다.

    ⚠️ Polygon.io는 GICS 섹터명을 직접 제공하지 않고 SIC 코드를 제공합니다.
       SIC → GICS 매핑 테이블을 아래에 정의하여 변환합니다.
    """

    EXCLUDED_SECTORS = {'Financial Services', 'Real Estate'}
    SLEEP_SEC        = 12.0   # 무료 플랜

    # SIC 코드 범위 → GICS 섹터 매핑 (주요 범위)
    SIC_TO_GICS = {
        range(100,  1000):  'Materials',
        range(1000, 1500):  'Materials',
        range(1500, 1800):  'Industrials',
        range(2000, 2100):  'Consumer Staples',
        range(2100, 2200):  'Consumer Staples',
        range(2800, 2900):  'Materials',
        range(3300, 3400):  'Materials',
        range(3559, 3600):  'Industrials',
        range(3600, 3700):  'Information Technology',
        range(3670, 3680):  'Information Technology',
        range(3674, 3675):  'Information Technology',  # 반도체
        range(3700, 3800):  'Consumer Discretionary',
        range(4800, 4900):  'Communication Services',
        range(4900, 5000):  'Utilities',
        range(5000, 5200):  'Industrials',
        range(5200, 5400):  'Consumer Discretionary',
        range(5900, 6000):  'Consumer Discretionary',
        range(6000, 6300):  'Financial Services',
        range(6500, 6600):  'Real Estate',
        range(7000, 7400):  'Consumer Discretionary',
        range(7370, 7380):  'Information Technology',  # SW
        range(7372, 7373):  'Information Technology',
        range(8000, 8100):  'Health Care',
        range(8700, 8800):  'Industrials',
    }

    def build_sector_map(self, symbols: list[str]) -> pd.DataFrame:
        records = []
        for i, symbol in enumerate(symbols):
            detail = self._fetch_detail(symbol)
            sic    = int(detail.get('sic', 0) or 0)
            sector = self._sic_to_gics(sic) or detail.get('sic_description', 'Unknown')
            records.append({
                'symbol':   symbol,
                'sic':      sic,
                'sector':   sector,
                'excluded': sector in self.EXCLUDED_SECTORS or sector == 'Unknown',
            })
            time.sleep(self.SLEEP_SEC)
        return pd.DataFrame(records)

    def _sic_to_gics(self, sic: int) -> str | None:
        for r, name in self.SIC_TO_GICS.items():
            if sic in r:
                return name
        return None

    def _fetch_detail(self, symbol: str) -> dict:
        resp = requests.get(
            f"https://api.polygon.io/v3/reference/tickers/{symbol}",
            params={'apiKey': self.api_key}, timeout=10
        )
        return resp.json().get('results', {})
```

---

## 6. 데이터 수집 실행 순서

> **사전 준비**:  
> 1. Polygon.io API 키 무료 발급: https://polygon.io → `.env`에 `POLYGON_API_KEY=your_key`  
> 2. SEC EDGAR는 API 키 불필요. User-Agent 헤더만 설정 (코드에 이미 포함)

### Step A — 초기 구축 (1회, 주말 야간 실행 권장)

```bash
# 1. ticker → CIK 매핑 테이블 수집 (SEC EDGAR, ~1분)
python data/collectors/run_collection.py --step ticker-map

# 2. 유니버스 목록 수집 — 현재 상장 + 상장폐지 (Polygon.io 무료, ~30분)
python data/collectors/run_collection.py --step universe

# 3. 섹터 매핑 테이블 생성 (Polygon.io SIC → GICS, ~3시간, 야간 실행)
python data/collectors/run_collection.py --step sectors

# 4. SEC EDGAR Bulk ZIP 다운로드 (~1~2GB, ~5~10분)
python data/collectors/run_collection.py --step download-zip

# 5. Bulk ZIP에서 전 종목 재무제표 파싱 (API 호출 없음, ~30분)
python data/collectors/run_collection.py --step parse-fundamentals

# 6. 밸류에이션(P/E·P/B·EV/EBITDA) 계산 (로컬 계산, API 없음, ~1~2시간)
python data/collectors/run_collection.py --step valuation --start 2016-01-01
```

**예상 소요 시간 및 비용:**

| Step | 소요 시간 | API 비용 | 비고 |
|------|---------|--------|------|
| 1. ticker-map | ~1분 | $0 | SEC 무료 |
| 2. universe | ~30분 | $0 | Polygon.io 무료 |
| 3. sectors | ~3시간 | $0 | Polygon.io 무료, 야간 실행 |
| 4. download-zip | ~5~10분 | $0 | SEC 무료, 1~2GB |
| 5. parse-fundamentals | ~30분 | $0 | 로컬 파싱, API 없음 |
| 6. valuation | ~1~2시간 | $0 | 로컬 계산, API 없음 |
| **합계** | **~5~6시간** | **$0** | 주말 금요일 밤 시작 → 월요일 아침 완료 |

> 💡 Step 3은 오래 걸리지만 금요일 밤에 시작하면 주말 동안 완료됩니다.  
> 사람이 대기할 필요 없이 터미널을 열어두고 퇴근하면 됩니다.

### Step B — 분기 업데이트 (2월·5월·8월·11월 실적 발표 시기)

```bash
# Bulk ZIP 재다운로드 (최신 공시 반영, ~5~10분)
python data/collectors/run_collection.py --step download-zip

# 업데이트된 ZIP에서 변경된 종목만 재파싱 (~15분)
python data/collectors/run_collection.py --step parse-fundamentals --incremental

# 밸류에이션 최근 90일 재계산 (로컬, ~20분)
python data/collectors/run_collection.py --step valuation --start [90일전날짜]
```

**분기 업데이트 비용: $0, 소요 시간: ~30~45분**

---

## 7. 데이터 품질 검증 (`DataValidator`)

백테스트 실행 전 필수 검증 항목:

**파일**: `data/validators/data_validator.py`

```python
class DataValidator:

    def run_all_checks(self) -> ValidationReport:
        checks = [
            self._check_filing_date_coverage(),    # filing_date 누락 비율
            self._check_lookahead_bias(),           # filing_date > period_end + 90일 이상 이상치
            self._check_survivorship_bias(),        # 상장폐지 종목 포함 여부
            self._check_sector_coverage(),          # 섹터 미분류 종목 비율
            self._check_valuation_sanity(),         # P/E < 0 또는 > 1000 이상치
            self._check_fscore_data_completeness(), # F-Score 9개 항목 중 결측 비율
        ]
        return ValidationReport(checks)

    def _check_lookahead_bias(self) -> CheckResult:
        """
        filing_date가 period_end_date보다 120일 이상 늦은 경우 경고.
        실제 데이터 오류일 가능성 높음.
        """
        ...

    def _check_survivorship_bias(self) -> CheckResult:
        """
        2016~2026 백테스트 기간 중 상장폐지된 종목이 유니버스에 포함되는지 확인.
        포함되지 않으면 생존 편향 경고.
        """
        ...
```

**검증 실행**:
```bash
python data/validators/run_validation.py --report
```

**합격 기준**:

| 항목 | 합격 기준 |
|------|---------|
| filing_date 누락률 | < 5% |
| 룩어헤드 이상치 | < 1% |
| 섹터 미분류 | < 10% |
| P/E 이상치 (음수 또는 >500) | < 15% (음수 기업은 정상 제외) |
| 상장폐지 종목 포함 | ✅ 필수 |

---

## 8. 기존 백테스트 시스템과의 연결

전략 E 엔진은 기존 V4 코드와 독립적인 모듈로 구성하되,  
아래 공통 유틸리티는 기존 코드에서 재사용합니다.

| 재사용 항목 | 위치 | 재사용 방법 |
|-----------|------|-----------|
| `_is_bull_regime()` | `engine.py` | 임포트 또는 복사 — QV 엔진의 레짐 필터 |
| 거래일 계산 유틸리티 | `utils/trading_days.py` | 보유 기간 계산 |
| 백테스트 결과 리포터 | `utils/report.py` | PF, MDD, Sharpe 계산 통일 |
| Polygon.io 클라이언트 | `data/polygon_client.py` | API 키, rate limiter 재사용 |
| 슬리피지 계산 | `engine.py` | `entry_price * (1 + slippage_pct)` |

> **레짐 필터 적용 여부 결정**:  
> QV 전략은 3~6개월 보유로 V4(1~10일)보다 훨씬 길기 때문에, 레짐 필터의 효과가 다릅니다.  
> P17-2 기본 테스트는 **레짐 필터 없이** 실행하고,  
> P17-3 민감도 테스트에서 레짐 필터 ON/OFF를 비교하십시오.

---

## 9. 전체 모듈 구조 (최종)

```
navis/
├── data/
│   ├── collectors/
│   │   ├── fundamentals_collector.py    ← 신규
│   │   ├── valuation_collector.py       ← 신규
│   │   ├── universe_history_collector.py← 신규
│   │   ├── sector_mapper.py             ← 신규
│   │   └── run_collection.py            ← 신규 (통합 실행 스크립트)
│   ├── validators/
│   │   ├── data_validator.py            ← 신규
│   │   └── run_validation.py            ← 신규
│   ├── fundamentals/                    ← 신규 (데이터 저장 폴더)
│   ├── universe/                        ← 신규
│   └── insider/                         ← Phase 4-B
│
└── backtesting/
    └── quality_value_backtest/          ← 신규 (전략 E 문서 참조)
        ├── engine.py
        ├── fundamental_screener.py
        ├── valuation_screener.py
        ├── universe_builder.py
        └── portfolio_manager.py
```

---

## 10. 개발 착수 순서

데이터 파이프라인 없이는 백테스트를 실행할 수 없습니다.  
아래 순서를 반드시 지켜 진행하십시오.

```
[1주차] SEC EDGAR 파이프라인 구축
  Step 1. FundamentalsCollector 구현 및 소규모 테스트
           → AAPL, MSFT, NVDA 10개로 먼저 ZIP 파싱 검증
  Step 2. filing_date 정상 추출 확인 (Point-in-time 핵심)
           → AAPL 2024 Q1: period_end=2024-03-31, filing_date=2024-05-02 형태 확인
  Step 3. 전체 유니버스 ZIP 파싱 실행 (주말 야간)

[2주차] Polygon.io 보조 데이터 + 밸류에이션
  Step 4. UniverseHistoryCollector — 상장폐지 종목 수집 (Polygon.io 무료)
  Step 5. SectorMapper — 섹터 분류 완료 (Polygon.io 무료, 야간)
  Step 6. ValuationCollector — P/E·P/B·EV/EBITDA 로컬 계산

[3주차] 검증 및 백테스트 연결
  Step 7. DataValidator 실행 → 전 항목 합격 확인
  Step 8. 전략 E 엔진(NAVIS_STRATEGY_E 문서)과 데이터 파이프라인 연결
  Step 9. P17-1 테스트 실행 (Quality 단독 — 기준선 파악)
```

---

## 11. 보고 요구사항

**Step 3 완료 후 보고** (데이터 수집 검증):

```
데이터 수집 검증 보고

수집 완료 종목 수: X개 (전체 유니버스 대비 X%)
filing_date 보유 비율: X.X%
기간: 2014-01-01 ~ 2026-05-02

샘플 검증 (AAPL):
  2024 Q1: period_end=2024-03-31, filing_date=2024-05-02 ← 정상 (32일 지연)
  2023 Q4: period_end=2023-12-31, filing_date=2024-02-01 ← 정상 (32일 지연)
  ...

이상치 발견 사항: (있으면 기재)
DataValidator 결과: 합격 / 불합격 (불합격 항목 기재)
```

**Step 7 완료 후 보고** (전체 검증):

```
데이터 파이프라인 검증 최종 보고

전체 종목: X개 (상장폐지 포함 X개)
재무 데이터 커버리지: X%
섹터 분류 완료: X% (미분류 X%)
밸류에이션 데이터: 2016-01-01 ~ 2026-04-30

DataValidator 전 항목 결과:
  filing_date 누락률: X.X% (기준 < 5%)
  룩어헤드 이상치:    X.X% (기준 < 1%)
  섹터 미분류:        X.X% (기준 < 10%)
  상장폐지 포함:      ✅ / ❌

P17 백테스트 착수 가능 여부: 가능 / 불가 (사유 기재)
```

---

*데이터 파이프라인 구축 완료 보고 후 P17 백테스트 지시를 내리겠습니다.*  
*총 비용 $0으로 시작합니다. 실전 투입 후 월 수익 > $100 달성 시 유료 전환을 검토하겠습니다.*
