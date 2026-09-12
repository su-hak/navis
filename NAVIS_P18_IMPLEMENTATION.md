# NAVIS P18 구현 지시서 — Quality + CEO Catalyst / Momentum
**작성일**: 2026-05-03  
**작성자**: 퀀트 트레이더 (Claude)  
**승인**: 대표님  
**대상**: 개발 1팀  
**전제 조건**: P17 부분합격 확정 (CAGR 8.98%, PF 1.37, F≥6 기준)  
**연관 문서**: NAVIS_STRATEGY_E_QUALITY_VALUE_CEO.md, NAVIS_STRATEGY_E_DATA_PIPELINE.md

---

## 0. P18 개요

### 목적

P17 최우수 결과(P17-3A, F≥6)는 부분합격입니다.

| 지표 | P17-3A | P18 목표 | 갭 |
|------|--------|---------|-----|
| CAGR | 8.98% | ≥ 12% | +3%p 이상 필요 |
| MDD | 28.81% | ≤ 20% | -8.8%p 개선 필요 |
| PF | 1.37 | ≥ 1.20 | ✅ (이미 달성) |

**병목 진단**: STOP_LOSS 비율 37~43% → 약세장(코로나·금리충격)에서 무방어 탈출.  
**해법**: 재무 건전성(F-Score) 위에 **승자 선별 신호**를 추가해 진입 정확도를 높인다.

### P18 두 갈래

| 테스트 | 추가 신호 | 가설 | 우선순위 |
|--------|---------|------|---------|
| **P18-A** | SEC Form 4 CEO 내부자 매수 | 경영진이 직접 돈을 넣었다 = 외부인이 모르는 긍정 정보 | 🥇 |
| **P18-B** | 6개월 가격 모멘텀 상위 30% | 이미 오르기 시작한 종목이 계속 오른다 (추세 추종) | 🥈 |

두 테스트는 **독립적으로 병행** 진행합니다. 결과를 비교해 더 나은 쪽을 채택합니다.

---

## 1. P18-A — SEC Form 4 내부자 매수 필터

### 1-1. 신호 정의

**합격 조건**: 최근 **90일 이내** SEC Form 4 신고에서  
- 신고자 직함: CEO, President, Chief Executive Officer, CFO, Chief Financial Officer  
- 거래 유형: P (Purchase — 매수)  
- 금액: ≥ $100,000 (USD)

> **왜 90일인가**: 내부자는 어닝 전후 30일 블랙아웃 기간이 있어 실제 매수 가능 기간이 제한적입니다.  
> 30일로 좁히면 매수 직후만 포착해 신호가 너무 희소해집니다. 90일이 적정 균형입니다.

> **왜 $10만인가**: 소액($1만~$5만) 내부자 매수는 스톡옵션 행사·복리 계획 등 잡음이 많습니다.  
> $10만 이상은 경영진이 개인 판단으로 자사주를 적극 취득했다는 신호입니다.

### 1-2. SEC EDGAR Form 4 API 구조

**무료, API 키 없음** (User-Agent 헤더만 필요)

```
# 기업 CIK 조회
GET https://data.sec.gov/files/company_tickers.json

# 특정 CIK의 최신 제출 내역
GET https://data.sec.gov/submissions/{CIK_PADDED}.json
  → CIK_PADDED: 10자리 0 패딩 (예: CIK 12345 → 0000012345)

# Form 4 개별 파일 접근
GET https://www.sec.gov/Archives/edgar/data/{CIK}/{ACCESSION_NO_STRIPPED}/{FILENAME}
```

**Rate Limit**: 10 req/sec (User-Agent 헤더 필수)

```python
HEADERS = {
    'User-Agent': 'NAVIS Quant Fund uiouij@naver.com',
    'Accept-Encoding': 'gzip, deflate',
}
```

### 1-3. Form 4 파서 구현

**파일**: `data/form4/form4_collector.py`

```python
import requests
import xml.etree.ElementTree as ET
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import json
import os

HEADERS = {'User-Agent': 'NAVIS Quant Fund uiouij@naver.com'}
SUBMISSIONS_URL = "https://data.sec.gov/submissions/{cik}.json"
EDGAR_BASE_URL  = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"


@dataclass
class InsiderTransaction:
    symbol:           str
    cik:              str
    filer_name:       str
    filer_title:      str       # CEO, CFO 등
    transaction_date: str       # YYYY-MM-DD
    transaction_type: str       # P = Purchase
    shares:           float
    price_per_share:  float
    total_value:      float     # shares × price


class Form4Collector:
    """
    SEC EDGAR Form 4 (내부자 거래 신고) 수집기.
    CEO/CFO의 자사주 매수 이력을 조회합니다.
    """

    ELIGIBLE_TITLES = {
        'CEO', 'Chief Executive Officer', 'President and CEO',
        'CFO', 'Chief Financial Officer', 'President',
        'Executive Chairman',
    }
    MIN_PURCHASE_USD = 100_000
    LOOKBACK_DAYS    = 90

    def __init__(self, ticker_cik_map: dict):
        """
        ticker_cik_map: {'AAPL': '0000320193', 'MSFT': '0000789019', ...}
        SEC EDGAR의 company_tickers.json에서 로드.
        """
        self.ticker_cik_map = ticker_cik_map

    def has_significant_insider_buy(self, symbol: str,
                                     as_of_date: str) -> bool:
        """
        as_of_date 기준 90일 이내 유효한 내부자 매수가 있으면 True.
        백테스트용 — point-in-time 준수 (미래 Form 4 참조 안 함).
        """
        transactions = self.get_insider_buys(symbol, as_of_date)
        return len(transactions) > 0

    def get_insider_buys(self, symbol: str,
                          as_of_date: str) -> list[InsiderTransaction]:
        """
        as_of_date 기준 90일 이내 CEO/CFO의 $10만+ 매수 신고 반환.
        """
        cik = self.ticker_cik_map.get(symbol.upper())
        if not cik:
            return []

        cutoff_date = (datetime.strptime(as_of_date, '%Y-%m-%d')
                       - timedelta(days=self.LOOKBACK_DAYS)).strftime('%Y-%m-%d')

        form4_filings = self._get_form4_filings(cik, cutoff_date, as_of_date)
        transactions = []

        for filing in form4_filings:
            txns = self._parse_form4(cik, filing['accessionNumber'], symbol)
            for t in txns:
                if (t.transaction_type == 'P'
                        and t.total_value >= self.MIN_PURCHASE_USD
                        and self._is_eligible_title(t.filer_title)):
                    transactions.append(t)

        return transactions

    def _get_form4_filings(self, cik: str, start_date: str,
                            end_date: str) -> list[dict]:
        """CIK의 submissions.json에서 Form 4 목록 조회."""
        url = SUBMISSIONS_URL.format(cik=cik)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            time.sleep(0.15)  # 10 req/sec 준수
        except Exception:
            return []

        filings = data.get('filings', {}).get('recent', {})
        if not filings:
            return []

        result = []
        forms      = filings.get('form', [])
        dates      = filings.get('filingDate', [])
        accessions = filings.get('accessionNumber', [])

        for form, date, acc in zip(forms, dates, accessions):
            if form == '4' and start_date <= date <= end_date:
                result.append({'filingDate': date,
                                'accessionNumber': acc.replace('-', '')})

        return result

    def _parse_form4(self, cik: str, accession_no: str,
                      symbol: str) -> list[InsiderTransaction]:
        """Form 4 XML 파싱 — 거래 내역 추출."""
        url = (EDGAR_BASE_URL.format(cik=cik.lstrip('0'),
                                      accession=accession_no)
               + 'primary_doc.xml')
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            time.sleep(0.15)
        except Exception:
            return []

        # 신고자 직함 추출
        filer_title = ''
        for elem in root.iter('officerTitle'):
            filer_title = elem.text or ''
            break

        filer_name = ''
        for elem in root.iter('rptOwnerName'):
            filer_name = elem.text or ''
            break

        transactions = []
        for txn in root.iter('nonDerivativeTransaction'):
            try:
                txn_type = txn.findtext('.//transactionCode') or ''
                date_str  = txn.findtext('.//transactionDate/value') or ''
                shares    = float(txn.findtext('.//transactionShares/value') or 0)
                price     = float(txn.findtext(
                                './/transactionPricePerShare/value') or 0)
                transactions.append(InsiderTransaction(
                    symbol=symbol,
                    cik=cik,
                    filer_name=filer_name,
                    filer_title=filer_title,
                    transaction_date=date_str,
                    transaction_type=txn_type,
                    shares=shares,
                    price_per_share=price,
                    total_value=shares * price,
                ))
            except (ValueError, TypeError):
                continue

        return transactions

    def _is_eligible_title(self, title: str) -> bool:
        title_upper = title.upper()
        return any(t.upper() in title_upper for t in self.ELIGIBLE_TITLES)
```

### 1-4. 캐시 전략 (백테스트 속도 최적화)

Form 4는 한번 신고되면 변경되지 않습니다. 전 기간 사전 다운로드 후 로컬 캐시를 사용합니다.

```python
class Form4Cache:
    """
    백테스트 전 전 종목 Form 4 사전 다운로드.
    파일 구조: data/form4/cache/{symbol}.parquet
    컬럼: filer_title, transaction_date, transaction_type, total_value
    """

    CACHE_DIR = 'data/form4/cache'

    def preload_universe(self, symbols: list[str],
                          start_date: str = '2015-01-01') -> None:
        """
        백테스트 시작 전 1회 실행.
        예상 소요 시간: 5,000종목 × 평균 0.3초 = 약 25분.
        """
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        collector = Form4Collector(self._load_ticker_cik_map())

        for i, symbol in enumerate(symbols):
            cache_path = f"{self.CACHE_DIR}/{symbol}.parquet"
            if os.path.exists(cache_path):
                continue   # 이미 캐시 있음 — 건너뜀

            filings = collector._get_form4_filings(
                collector.ticker_cik_map.get(symbol, ''),
                start_date, '2026-12-31'
            )
            # ... parquet 저장

            if i % 100 == 0:
                print(f"  [{i}/{len(symbols)}] {symbol} 완료")

    def query(self, symbol: str, as_of_date: str,
               lookback_days: int = 90) -> bool:
        """캐시에서 조회 — O(1), API 호출 없음."""
        cache_path = f"{self.CACHE_DIR}/{symbol}.parquet"
        if not os.path.exists(cache_path):
            return False

        df = pd.read_parquet(cache_path)
        cutoff = (datetime.strptime(as_of_date, '%Y-%m-%d')
                  - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        mask = (
            (df['transaction_type'] == 'P') &
            (df['total_value'] >= 100_000) &
            (df['transaction_date'] >= cutoff) &
            (df['transaction_date'] <= as_of_date)   # point-in-time 준수
        )
        return mask.any()
```

### 1-5. P18-A 엔진 통합

**기존 QualityValueEngine의 `_screen_universe` 메서드에 다음 코드 추가:**

```python
def _screen_universe(self, date: str) -> list[str]:
    candidates = []

    for symbol in self.universe_builder.build(date)['symbol']:
        # 기존: F-Score 필터
        fd = self._get_fundamentals(symbol, date)
        if self.fs.score(fd) < self.config.min_fscore:
            continue

        # P18-A 추가: CEO Catalyst 필터 (use_catalyst_filter=True 시 활성)
        if self.config.use_catalyst_filter:
            has_buy = self.form4_cache.query(symbol, date,
                                              lookback_days=90)
            # Catalyst 없어도 제외하지 않음 — 우선순위만 조정
            candidates.append((symbol, has_buy))
        else:
            candidates.append((symbol, False))

    # Tier 1 (Catalyst 있음) → Tier 2 (없음) 순서로 정렬
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in candidates]
```

### 1-6. P18-A 실행 명령어

```bash
# P18-A 백테스트 실행
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 \
  --catalyst \
  --stop-loss 15.0 \
  --max-hold 126 \
  --start 2016-01-01

# 사전 준비 (최초 1회만):
python data/form4/preload_cache.py \
  --start 2015-01-01 \
  --universe data/universe/us_stocks_5183.parquet
```

**예상 사전 준비 시간**: 5,183종목 × ~0.3초 = 약 26분 (금요일 야간 실행 권장)

---

## 2. P18-B — 6개월 모멘텀 필터

### 2-1. 신호 정의

**합격 조건**: 직전 **126거래일(약 6개월)** 가격 수익률이  
동일 스크리닝 유니버스 내 **상위 30%** 이내

> **왜 6개월 모멘텀인가**:  
> 학계 연구(Jegadeesh & Titman, 1993)에서 3~12개월 모멘텀이 1개월보다 강력함을 확인.  
> 1개월은 단기 되돌림(mean-reversion)으로 오히려 역모멘텀 구간.  
> 6개월은 PEAD(어닝 후 주가 표류) + 기관 누적 매수 패턴과 정렬됩니다.

> **왜 상위 30%인가**:  
> 상위 10%로 좁히면 종목 수가 너무 적어 거래 빈도 목표(20건/년)를 충족하기 어렵습니다.  
> 상위 50%는 신호가 너무 약합니다. 30%가 선별력과 빈도의 균형점입니다.

### 2-2. 모멘텀 계산 구현

**파일**: `backtesting/quality_value_backtest/momentum_screener.py`

```python
import pandas as pd
import numpy as np


class MomentumScreener:
    """
    6개월(126거래일) 가격 모멘텀 상위 30% 필터.

    주의사항:
    - 직전 1개월(21거래일) 제외: 단기 되돌림 회피 (표준 관행)
    - 계산식: return = price[t-21] / price[t-126] - 1
    """

    LOOKBACK_DAYS = 126   # 6개월
    SKIP_DAYS     = 21    # 최근 1개월 제외
    TOP_PERCENTILE = 0.30  # 상위 30%

    def calculate_momentum(self, symbol: str, as_of_date: str,
                            price_data: pd.DataFrame) -> float:
        """
        price_data: 일봉 종가 DataFrame (index=date, columns=symbol)
        반환: 6개월 모멘텀 수익률 (float, NaN 가능)
        """
        if symbol not in price_data.columns:
            return float('nan')

        prices = price_data[symbol].dropna()
        prices = prices[prices.index <= as_of_date]

        if len(prices) < self.LOOKBACK_DAYS:
            return float('nan')

        # t-126일 ~ t-21일 수익률
        price_end   = prices.iloc[-(self.SKIP_DAYS + 1)]
        price_start = prices.iloc[-(self.LOOKBACK_DAYS + 1)]

        if price_start <= 0:
            return float('nan')

        return price_end / price_start - 1

    def get_momentum_rank(self, symbols: list[str], as_of_date: str,
                           price_data: pd.DataFrame) -> pd.Series:
        """
        유니버스 전체 모멘텀 계산 후 상위 30% 마스크 반환.
        반환: {symbol: True/False} — True = 모멘텀 상위 30%
        """
        mom_series = pd.Series({
            sym: self.calculate_momentum(sym, as_of_date, price_data)
            for sym in symbols
        }).dropna()

        if len(mom_series) == 0:
            return pd.Series(False, index=symbols)

        threshold = mom_series.quantile(1 - self.TOP_PERCENTILE)
        return mom_series >= threshold
```

### 2-3. P18-B 엔진 통합

**기존 `_screen_universe`에 모멘텀 필터 분기 추가:**

```python
# P18-B 추가: 모멘텀 필터 (use_momentum_filter=True 시 활성)
if self.config.use_momentum_filter:
    universe_syms = [sym for sym, _ in candidates]
    momentum_mask = self.momentum_screener.get_momentum_rank(
        universe_syms, date, self.price_data
    )
    candidates = [
        (sym, cat) for sym, cat in candidates
        if momentum_mask.get(sym, False)
    ]
```

### 2-4. P18-B 실행 명령어

```bash
# P18-B 백테스트 실행
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 \
  --momentum \
  --stop-loss 15.0 \
  --max-hold 126 \
  --start 2016-01-01
```

---

## 3. 공통 보고 요구사항

각 테스트 완료 후 아래 형식으로 보고:

```
P18-[A/B] 결과 보고

[전략 설정]
F-Score 기준:    F≥6
추가 필터:       [Form 4 Catalyst / 6개월 모멘텀 상위 30%]
최대 보유:       126거래일
손절:           -15%
테스트 기간:     2016-01-01 ~ 2026-04-30

[성과 지표]
CAGR:           X.X%   (P17-3A 대비: ±X.X%p)
MDD:            X.X%   (P17-3A 대비: ±X.X%p)
Sharpe Ratio:   X.XX
Profit Factor:  X.XX
총 거래 수:     X건  (연평균 X건)
승률:           X.X%
평균 보유 기간: X거래일

[연도별 수익률]
2016: X.X%
2017: X.X%
2018: X.X%    ← 금리 인상기 (핵심 스트레스 구간)
2019: X.X%
2020: X.X%    ← COVID (핵심 스트레스 구간)
2021: X.X%
2022: X.X%    ← 금리 인상기 2차
2023: X.X%
2024: X.X%
2025: X.X%

[청산 유형 분포]
STOP_LOSS:              X건 (X%)  ← P17 대비 개선 여부 핵심 지표
MAX_HOLD:               X건 (X%)
VALUE_REALIZED:         X건 (X%)
QUALITY_DETERIORATION:  X건 (X%)

[Catalyst 효과 분석 — P18-A만 해당]
Tier 1 (Catalyst 있음): X건, 평균 수익 X.X%, 승률 X%
Tier 2 (신호 없음):     X건, 평균 수익 X.X%, 승률 X%
→ Catalyst 프리미엄:    X.X%p

[판정]
합격 / 부분합격 / 실패
합격 기준: CAGR ≥ 12% AND MDD ≤ 20% AND PF ≥ 1.20 AND 연 20건+
```

---

## 4. 합격 기준 및 후속 처리

| 결과 | 조건 | 다음 단계 |
|------|------|---------|
| **합격** | CAGR ≥ 12% AND MDD ≤ 20% AND PF ≥ 1.20 | Phase 5 통합 포트폴리오 설계 착수 |
| **부분합격** | CAGR ≥ 8% AND PF ≥ 1.10 | P19 설계 (추가 조합 탐색) — 퀀트 트레이더에게 보고 |
| **실패** | 위 조건 미달 | 즉시 퀀트 트레이더에게 보고. 전략 방향 재설계 |

### P18-A vs P18-B 비교 기준

두 테스트가 모두 완료된 후:

| 비교 항목 | 우선 채택 조건 |
|---------|------------|
| CAGR 차이 ≥ 2%p | 높은 쪽 채택 |
| MDD 차이 ≥ 3%p | 낮은 쪽 채택 |
| 두 조건 상충 | Sharpe Ratio 높은 쪽 채택 |
| 두 결과 모두 합격 | P18-A + P18-B 결합 테스트 (P18-C) 추가 진행 |

---

## 5. 구현 우선순위 및 일정

```
Day 1 (금요일 야간):
  ■ Form 4 캐시 사전 다운로드 실행
    python data/form4/preload_cache.py
    → 약 26분 소요, 방치 가능

Day 2:
  ■ Form4Collector, Form4Cache 구현 및 단위 테스트
  ■ MomentumScreener 구현 및 단위 테스트

Day 3:
  ■ QualityValueEngine에 --catalyst, --momentum 플래그 통합
  ■ P18-A, P18-B 백테스트 병행 실행 (각 ~수 시간)

Day 4:
  ■ 결과 분석 및 보고서 작성 (위 형식)
  ■ 퀀트 트레이더에게 보고
```

---

## 6. ⚠️ 주의사항 — 절대 위반 금지

1. **Point-in-time 준수**: Form 4 조회 시 `transaction_date ≤ as_of_date` 조건 필수.  
   filing_date (SEC 접수일)가 transaction_date(실거래일)보다 늦을 수 있으므로  
   **반드시 `filing_date ≤ as_of_date`로 필터링**. 미래 신고 참조 = 심각한 look-ahead bias.

2. **모멘텀 계산 skip 기간**: 직전 21거래일 제외 필수.  
   `price[t-21] / price[t-126]` — `price[t] / price[t-126]` 사용 금지.

3. **생존 편향**: P18 유니버스도 P17과 동일하게 as_of_date 기준 생존 종목만 사용.  
   현재 상장 종목 리스트로 역산 금지.

4. **과최적화 금지**: 90일 창, $10만 기준, 30% 상위 등 파라미터를  
   P18 결과를 보고 후향적으로 조정하는 행위 금지.  
   조정이 필요하다면 P19로 별도 라운드를 열어 처음부터 다시 설계.

---

*P17 부분합격 확인 → P18 즉시 착수. 결과 나오면 위 형식으로 보고 바랍니다.*
