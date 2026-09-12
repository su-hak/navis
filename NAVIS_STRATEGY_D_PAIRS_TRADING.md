# ~~NAVIS 전략 D — 페어 트레이딩 (Statistical Arbitrage)~~
# ❌ 폐기 확정 (2026-05-02)

> **폐기 사유**: 추세장(2021~2024)에서 공적분 스프레드 90일 이상 지속 괴리. CAGR 최고 1.08% — 전략 목표 미달.  
> 상세 분석: `NAVIS_PHASE2_ARCHIVE.md` P16 항목 참조.  
> 이 문서는 구현 참고용으로만 보존합니다. 재시도 금지.

---

**작성일**: 2026-04-21  
**폐기일**: 2026-05-02  
**작성자**: 퀀트 트레이더  
**대상**: 개발 1팀 (참고 보존용)  
**연관 문서**: NAVIS_QUANT_ROADMAP.md, NAVIS_PHASE2_ARCHIVE.md

---

## 전략 개요

### 핵심 아이디어

```
동일 섹터 내 역사적으로 함께 움직이던 두 종목(페어)의 가격 괴리를 포착.

정상 상태: NVDA와 AMD는 같은 반도체 섹터 → 비슷한 방향으로 움직임
비정상:    어느 날 NVDA만 급등 (종목 특유 이슈 또는 노이즈)
            → 스프레드가 2σ 이탈
            → NVDA Short + AMD Long
            → 스프레드 평균 회귀 시 청산 → 수익

엣지: 단기 과잉 반응의 평균 회귀 (Mean Reversion)
      방향성 없음 — Bull/Bear 관계없이 작동
```

### 기존 전략들과의 근본 차이

| 항목 | V4 / NH52 / PEAD | 페어 트레이딩 |
|------|-----------------|-------------|
| 방향성 | Long-only (방향 베팅) | Market Neutral (방향 없음) |
| 시장 의존 | Bull 필요 | 불필요 |
| 레짐 필터 | 필수 | 불필요 |
| 2022년 하락장 | 0건 (차단) | 정상 작동 |
| 리스크 | 시장 급락 시 손실 | 페어 괴리 확대 시 손실 |
| Sharpe | 0.8~1.5 | 1.5~2.5 |

### 예상 성과

| 지표 | 예상 범위 | 비고 |
|------|----------|------|
| 연간 수익률 | 15~25% | 레버리지 1.5× 기준 |
| Sharpe Ratio | 1.5~2.5 | 목표(>1.5) 달성 가능 |
| MDD | 10~20% | 시장 중립으로 낮음 |
| 거래 빈도 | 연 100~300건 |  |
| 자본 활용 | Long + Short 동시 → 레버리지 |  |

---

## 아키텍처

팩터 모멘텀과 마찬가지로 신규 모듈로 분리합니다.

```
backtesting/
├── universe_backtest/       ← 기존 (V4 등)
├── factor_backtest/         ← 전략 B
└── pairs_backtest/          ← 전략 D (신규)
    ├── pair_selector.py     ← 페어 선정 (공적분 검정)
    ├── spread_calculator.py ← 스프레드 Z-score 계산
    └── engine.py            ← 페어 트레이딩 백테스트 엔진
```

---

## 구현 지시

### Step 1: 페어 선정 모듈

**신규 파일**: `backtesting/pairs_backtest/pair_selector.py`

#### 선정 기준
1. **동일 GICS 섹터** — 섹터 공통 팩터로 인한 동조화
2. **상관계수 > 0.7** — 과거 252거래일 일봉 수익률 기준
3. **공적분 검정 통과** — Engle-Granger p < 0.05 (장기적으로 함께 움직임)
4. **유동성** — 양 종목 모두 일평균 달러 거래량 $2,000만+

```python
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint
from itertools import combinations

def find_cointegrated_pairs(
    price_df: pd.DataFrame,   # columns = symbols, index = date
    min_corr: float = 0.70,
    coint_pvalue: float = 0.05,
    min_dollar_volume: float = 2e7,
    vol_df: pd.DataFrame = None,
) -> list[dict]:
    """
    공적분 페어 탐색.
    반환: [{"symbol_a": str, "symbol_b": str, "pvalue": float,
             "corr": float, "hedge_ratio": float}, ...]
    """
    symbols = list(price_df.columns)
    log_prices = np.log(price_df)
    results = []

    for sym_a, sym_b in combinations(symbols, 2):
        series_a = log_prices[sym_a].dropna()
        series_b = log_prices[sym_b].dropna()
        common_idx = series_a.index.intersection(series_b.index)
        if len(common_idx) < 252:
            continue

        s_a = series_a[common_idx]
        s_b = series_b[common_idx]

        # 상관관계 필터
        corr = s_a.corr(s_b)
        if corr < min_corr:
            continue

        # 공적분 검정 (Engle-Granger)
        _, pvalue, _ = coint(s_a, s_b)
        if pvalue > coint_pvalue:
            continue

        # 헤지 비율 (OLS: log_A = beta * log_B + alpha)
        from numpy.linalg import lstsq
        X = np.column_stack([s_b.values, np.ones(len(s_b))])
        beta, _ = lstsq(X, s_a.values, rcond=None)[0][:2], None
        beta = float(np.linalg.lstsq(X, s_a.values, rcond=None)[0][0])

        results.append({
            "symbol_a":    sym_a,
            "symbol_b":    sym_b,
            "pvalue":      pvalue,
            "corr":        corr,
            "hedge_ratio": beta,
        })

    # p-value 오름차순 정렬 (공적분 강도 순)
    return sorted(results, key=lambda x: x["pvalue"])
```

---

### Step 2: 스프레드 및 Z-score 계산

**신규 파일**: `backtesting/pairs_backtest/spread_calculator.py`

```python
import pandas as pd
import numpy as np

def calc_spread_zscore(
    price_a: pd.Series,
    price_b: pd.Series,
    hedge_ratio: float,
    window: int = 60,
) -> pd.Series:
    """
    스프레드 Z-score 계산.
    spread = log(price_A) - hedge_ratio * log(price_B)
    z_score = (spread - rolling_mean) / rolling_std

    window: 평균/표준편차 롤링 창 (기본 60거래일 = 3개월)
    """
    spread = np.log(price_a) - hedge_ratio * np.log(price_b)
    rolling_mean = spread.rolling(window).mean()
    rolling_std  = spread.rolling(window).std()
    z_score = (spread - rolling_mean) / rolling_std
    return z_score
```

---

### Step 3: 트레이딩 로직

**진입/청산 규칙**

```
진입 조건:
  Z-score > +2.0  → symbol_A 과대평가 → A Short + B Long
  Z-score < -2.0  → symbol_A 과소평가 → A Long  + B Short

청산 조건:
  |Z-score| < 0.5  → 스프레드 평균 회귀 → 전량 청산 (수익)

손절 조건:
  |Z-score| > 3.5  → 스프레드 확대 (괴리 영구화 가능성) → 전량 청산 (손실)

최대 보유 기간:
  30거래일 초과 → 강제 청산 (기회비용 방지)
```

---

### Step 4: 백테스트 엔진

**신규 파일**: `backtesting/pairs_backtest/engine.py`

```python
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np
from .spread_calculator import calc_spread_zscore

@dataclass
class PairsBacktestConfig:
    # 페어 리스트 (pair_selector.py 출력 결과)
    pairs: List[Dict] = field(default_factory=list)

    # Z-score 임계값
    entry_z:     float = 2.0    # 진입: |Z| > 2.0
    exit_z:      float = 0.5    # 청산: |Z| < 0.5
    stop_z:      float = 3.5    # 손절: |Z| > 3.5

    # 스프레드 계산 창
    zscore_window: int = 60     # 60거래일 롤링 평균/표준편차

    # 포지션
    capital_per_pair:  float = 0.05   # 페어당 자본 5% (Long + Short 합산)
    max_pairs:         int   = 20     # 동시 최대 활성 페어 수
    max_hold_days:     int   = 30     # 최대 보유 30거래일

    # 비용
    commission_rate: float = 0.001    # 0.1%
    slippage_rate:   float = 0.005    # 0.5%
    borrow_rate:     float = 0.02     # Short 대주 연 2% (일할 계산)

    # 백테스트
    initial_capital: float = 1_000_000.0
    start_date:      str   = "2021-01-01"
    end_date:        str   = "2026-04-21"


class PairsBacktestEngine:
    def __init__(self, config: PairsBacktestConfig, daily_data: Dict[str, pd.DataFrame]):
        self.config = config
        self.daily_data = daily_data
        self.capital = config.initial_capital
        self.active_trades = {}    # {pair_id: trade_dict}
        self.trade_log = []
        self.equity_curve = []

    def run(self):
        # 전체 거래일 목록
        all_dates = pd.bdate_range(self.config.start_date, self.config.end_date)

        # 페어별 Z-score 사전 계산
        zscore_cache = self._precompute_zscores()

        for date in all_dates:
            self._process_day(date, zscore_cache)
            self._record_equity(date)

        return self._generate_report()

    def _precompute_zscores(self) -> Dict[str, pd.Series]:
        """모든 페어의 Z-score를 백테스트 시작 전에 일괄 계산."""
        cache = {}
        for pair in self.config.pairs:
            sym_a  = pair["symbol_a"]
            sym_b  = pair["symbol_b"]
            beta   = pair["hedge_ratio"]
            pair_id = f"{sym_a}_{sym_b}"

            df_a = self.daily_data.get(sym_a)
            df_b = self.daily_data.get(sym_b)
            if df_a is None or df_b is None:
                continue

            common_idx = df_a.index.intersection(df_b.index)
            z = calc_spread_zscore(
                df_a.loc[common_idx, "close"],
                df_b.loc[common_idx, "close"],
                beta,
                self.config.zscore_window,
            )
            cache[pair_id] = z
        return cache

    def _process_day(self, date, zscore_cache):
        # 1. 기존 포지션 청산 체크 (exit / stop / max_hold)
        for pair_id in list(self.active_trades.keys()):
            z_series = zscore_cache.get(pair_id)
            if z_series is None or date not in z_series.index:
                continue
            z = z_series[date]
            trade = self.active_trades[pair_id]
            self._check_exit(pair_id, trade, z, date)

        # 2. 신규 진입 체크
        if len(self.active_trades) >= self.config.max_pairs:
            return

        for pair in self.config.pairs:
            sym_a   = pair["symbol_a"]
            sym_b   = pair["symbol_b"]
            pair_id = f"{sym_a}_{sym_b}"

            if pair_id in self.active_trades:
                continue

            z_series = zscore_cache.get(pair_id)
            if z_series is None or date not in z_series.index:
                continue
            z = z_series[date]

            if abs(z) > self.config.entry_z:
                self._open_trade(pair, pair_id, z, date)

    def _open_trade(self, pair, pair_id, z, date):
        """Z > +2: A Short + B Long / Z < -2: A Long + B Short."""
        sym_a = pair["symbol_a"]
        sym_b = pair["symbol_b"]
        beta  = pair["hedge_ratio"]

        df_a = self.daily_data.get(sym_a)
        df_b = self.daily_data.get(sym_b)
        if df_a is None or df_b is None:
            return
        if date not in df_a.index or date not in df_b.index:
            return

        price_a = df_a.loc[date, "close"] * (1 + self.config.slippage_rate)
        price_b = df_b.loc[date, "close"] * (1 + self.config.slippage_rate)

        # 페어당 자본 계산
        alloc = self.capital * self.config.capital_per_pair
        qty_b = int(alloc / (price_b + beta * price_a))
        qty_a = max(1, int(qty_b * beta))

        if z > self.config.entry_z:
            direction = "SHORT_A"   # A 과대평가: A Short, B Long
            long_sym, short_sym     = sym_b, sym_a
            long_qty, short_qty     = qty_b, qty_a
            long_price, short_price = price_b, price_a
        else:
            direction = "LONG_A"    # A 과소평가: A Long, B Short
            long_sym, short_sym     = sym_a, sym_b
            long_qty, short_qty     = qty_a, qty_b
            long_price, short_price = price_a, price_b

        cost = (long_price * long_qty + short_price * short_qty) * self.config.commission_rate
        if cost > self.capital:
            return

        self.capital -= cost
        self.active_trades[pair_id] = {
            "pair_id":     pair_id,
            "direction":   direction,
            "long_sym":    long_sym,
            "short_sym":   short_sym,
            "long_qty":    long_qty,
            "short_qty":   short_qty,
            "long_price":  long_price,
            "short_price": short_price,
            "entry_date":  date,
            "entry_z":     z,
            "hold_days":   0,
        }

    def _check_exit(self, pair_id, trade, z, date):
        hold_days = (date - trade["entry_date"]).days
        direction = trade["direction"]

        should_exit = False
        exit_reason = ""

        # 청산 조건
        if abs(z) < self.config.exit_z:
            should_exit = True
            exit_reason = "MEAN_REVERT"
        elif abs(z) > self.config.stop_z:
            should_exit = True
            exit_reason = "STOP_LOSS"
        elif hold_days >= self.config.max_hold_days:
            should_exit = True
            exit_reason = "MAX_HOLD"

        if should_exit:
            self._close_trade(pair_id, trade, date, exit_reason)

    def _close_trade(self, pair_id, trade, date, reason):
        """포지션 청산 및 PnL 계산."""
        df_long  = self.daily_data.get(trade["long_sym"])
        df_short = self.daily_data.get(trade["short_sym"])
        if df_long is None or df_short is None:
            return
        if date not in df_long.index or date not in df_short.index:
            return

        exit_long  = df_long.loc[date, "close"]  * (1 - self.config.slippage_rate)
        exit_short = df_short.loc[date, "close"] * (1 + self.config.slippage_rate)

        pnl_long  = (exit_long  - trade["long_price"])  * trade["long_qty"]
        pnl_short = (trade["short_price"] - exit_short) * trade["short_qty"]

        # 대주 비용 (Short 보유 기간 × 연 2%)
        hold_days = max(0, (date - trade["entry_date"]).days)
        borrow_cost = (trade["short_price"] * trade["short_qty"]
                       * self.config.borrow_rate * hold_days / 252)

        commission = ((exit_long * trade["long_qty"]
                       + exit_short * trade["short_qty"])
                      * self.config.commission_rate)

        total_pnl = pnl_long + pnl_short - borrow_cost - commission
        self.capital += total_pnl

        self.trade_log.append({
            "date":       str(date.date()),
            "pair_id":    pair_id,
            "reason":     reason,
            "pnl":        total_pnl,
            "hold_days":  hold_days,
            "entry_z":    trade["entry_z"],
        })
        del self.active_trades[pair_id]
```

---

### Step 5: 실행 스크립트

**신규 파일**: `backtesting/run_pairs_backtest.py`

```python
"""
페어 트레이딩 백테스트 실행기.
사용 예:
  # Step 0: 페어 선정 (최초 1회)
  python backtesting/run_pairs_backtest.py --build-pairs --sp500

  # Step 1: 백테스트
  python backtesting/run_pairs_backtest.py \
    --pairs-file pairs_cache.json \
    --entry-z 2.0 --exit-z 0.5 --stop-z 3.5 \
    --max-pairs 20 --start 2021-01-01
"""
import argparse, json
from pairs_backtest.pair_selector import find_cointegrated_pairs
from pairs_backtest.engine import PairsBacktestConfig, PairsBacktestEngine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-pairs",  action="store_true",
                        help="페어 선정 후 캐시 저장 (최초 1회)")
    parser.add_argument("--sp500",        action="store_true")
    parser.add_argument("--pairs-file",   default="pairs_cache.json")
    parser.add_argument("--entry-z",      type=float, default=2.0)
    parser.add_argument("--exit-z",       type=float, default=0.5)
    parser.add_argument("--stop-z",       type=float, default=3.5)
    parser.add_argument("--zscore-win",   type=int,   default=60)
    parser.add_argument("--max-pairs",    type=int,   default=20)
    parser.add_argument("--capital-per-pair", type=float, default=5.0,
                        help="페어당 자본 %% (기본 5)")
    parser.add_argument("--start",        default="2021-01-01")
    parser.add_argument("--end",          default="2026-04-21")
    args = parser.parse_args()

    if args.build_pairs:
        # 페어 선정 및 캐시 저장
        _build_and_save_pairs(args)
        return

    with open(args.pairs_file) as f:
        pairs = json.load(f)
    print(f"페어 수: {len(pairs)}개 로드")

    config = PairsBacktestConfig(
        pairs             = pairs,
        entry_z           = args.entry_z,
        exit_z            = args.exit_z,
        stop_z            = args.stop_z,
        zscore_window     = args.zscore_win,
        max_pairs         = args.max_pairs,
        capital_per_pair  = args.capital_per_pair / 100,
        start_date        = args.start,
        end_date          = args.end,
    )
    # daily_data 로드 후 엔진 실행
    ...

if __name__ == "__main__":
    main()
```

---

## 테스트 순서

```bash
# Step 0: 페어 선정 캐시 빌드 (최초 1회, 30분~1시간 소요)
python backtesting/run_pairs_backtest.py \
  --build-pairs --sp500

# P16-1: 기본 파라미터 (Z=2.0/0.5/3.5, 페어당 5%, 최대 20페어)
python backtesting/run_pairs_backtest.py \
  --pairs-file pairs_cache.json \
  --entry-z 2.0 --exit-z 0.5 --stop-z 3.5 \
  --max-pairs 20 --capital-per-pair 5 \
  --start 2021-01-01

# P16-2: 진입 임계값 완화 (더 많은 신호)
python backtesting/run_pairs_backtest.py \
  --pairs-file pairs_cache.json \
  --entry-z 1.5 --exit-z 0.5 --stop-z 3.0 \
  --max-pairs 20 --capital-per-pair 5 \
  --start 2021-01-01

# P16-3: 집중 포트폴리오 (페어당 자본 확대)
python backtesting/run_pairs_backtest.py \
  --pairs-file pairs_cache.json \
  --entry-z 2.0 --exit-z 0.5 --stop-z 3.5 \
  --max-pairs 10 --capital-per-pair 10 \
  --start 2021-01-01
```

---

## 보고 양식

```
테스트명: P16-X [주요 파라미터]
실행 명령어: [전체 명령어]

결과:
- 연간 수익률 (CAGR) / 총 수익률
- Sharpe Ratio / Sortino Ratio
- MDD / MDD 발생 기간
- 거래 수: XX건 (연평균 XX건)
- 청산 유형: MEAN_REVERT(XX) STOP_LOSS(XX) MAX_HOLD(XX)
- 평균 보유 기간 (일)
- 연도별 수익률: 2021~2026 (2022 하락장 특히 주목)
- 활성 페어 수 분포 (평균/최대)
- 상위 기여 페어 10 / 하위 기여 페어 10
- 특이사항 (페어 괴리 확대 사례)
```

---

## 합격 기준

| 결과 | 조건 | 다음 행동 |
|------|------|---------|
| **합격** | CAGR ≥ 15% AND Sharpe ≥ 1.2 | V4 + 페어 트레이딩 통합 포트폴리오 |
| **부분 합격** | CAGR ≥ 10% AND Sharpe ≥ 0.8 | Z 임계값 / 페어 수 파라미터 조정 |
| **실패** | 위 조건 미달 | 전략 구조 전면 재논의 (대표님 직접 결정) |

---

## 핵심 리스크 — 페어 괴리 영구화

페어 트레이딩의 가장 큰 위험은 **공적분 관계 붕괴**입니다.

```
예시: NVDA↔AMD
  과거: AI 이전 — 반도체 섹터 동조화 → 공적분 성립
  현재: AI 이후 NVDA가 데이터센터 GPU 독점 → 탈동조화
  → NVDA Long + AMD Short 포지션이 영구 손실로 이어질 수 있음
```

**대응 방안 (구현 시 반드시 포함)**:
1. 공적분 관계를 **분기마다 재검정** → 괴리된 페어 교체
2. Stop-Z(3.5) 손절 규칙 엄수
3. 단일 페어 자본 배분 5% 상한 유지

---

## 인프라 사전 준비 사항

전략 B(팩터 모멘텀) 진행 중 병행 준비 권장:

1. **Alpaca Short Selling 활성화 확인**
   - 계좌 Margin 설정 필요
   - `api.submit_order(side="sell", type="market")` 테스트

2. **statsmodels 패키지 설치**
   ```bash
   pip install statsmodels
   ```

3. **페어 선정 소요 시간**: S&P 500 488종목 조합 약 119,000쌍 → 공적분 검정 30분~1시간

---

*전략 B(팩터 모멘텀) 결과 확인 후 착수 여부 결정.*
*인프라 준비(Short 설정, statsmodels)는 전략 B 진행 중 미리 완료 권장.*
*구현 예상 기간: 4~6주 (신규 모듈 + 페어 선정 전처리 포함)*
