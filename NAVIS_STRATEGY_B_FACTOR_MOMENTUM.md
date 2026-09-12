# ~~NAVIS 전략 B — 팩터 모멘텀 (Cross-Sectional Momentum)~~
# ❌ 폐기 확정 (2026-05-02)

> **폐기 사유**: 추세장(2021~2024) 구조적 약점. CAGR 최고 3.86% — 전략 목표 미달.  
> 상세 분석: `NAVIS_PHASE2_ARCHIVE.md` P15 항목 참조.  
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
매월 말: S&P 500 전 종목의 직전 12개월 수익률 계산 (가장 최근 1개월 제외)
         → 수익률 상위 20% (약 100종목) 선별
         → 동일 비중으로 매수 / 1개월 보유 / 다음 달 말 리밸런싱

엣지: 과거 12개월 강세 종목은 향후 1~3개월에도 계속 강세
     (Jegadeesh & Titman 1993 — 30년간 전 세계 시장에서 복제됨)
```

### V4와의 차이

| 항목 | V4 Multi-Day | 팩터 모멘텀 |
|------|-------------|------------|
| 신호 기반 | 당일 갭 이벤트 (인트라데이) | 월말 수익률 랭킹 (일봉) |
| 보유 기간 | 1~10거래일 | 1개월 (고정) |
| 동시 포지션 | 1~2개 | 100개 (분산) |
| 레짐 필터 | SPY SMA200 필요 | 불필요 (상대 강도 기반) |
| 데이터 | 5분봉 필수 | 일봉 종가만 사용 |
| 노이즈 | 단일 종목 노출 | 100종목 평균화 |

### 예상 성과 (학술 실증 기반, Long-only)

| 지표 | 예상 범위 | 비고 |
|------|----------|------|
| 연간 수익률 | 15~22% | S&P 500 벤치마크 대비 초과 |
| Sharpe Ratio | 0.8~1.2 | |
| MDD | 30~45% | 모멘텀 크래시 구간 주의 |
| 거래 빈도 | 월 12회 리밸런싱 | 연 100~200건 회전 |

### ⚠️ 모멘텀 크래시 경고

모멘텀 팩터는 시장 급반등 시 역전 위험이 있습니다.
- 2009년 3월 (금융위기 저점 반등): 단기 -50%+ 가능
- 2020년 4월 (COVID 반등): 단기 -30%
- **대응**: 시장 변동성 필터 또는 Long/Short 구조로 헤지

---

## 아키텍처 결정

현재 엔진은 **단일 종목, 인트라데이 이벤트** 기반입니다.
팩터 모멘텀은 **포트폴리오 전체, 월말 리밸런싱** 기반으로 구조가 근본적으로 다릅니다.

**결론: 신규 백테스트 모듈 분리 구현**

```
backtesting/
├── universe_backtest/      ← 기존 (V4, NH52 등 인트라데이 전략)
│   ├── engine.py
│   └── data_cache.py
└── factor_backtest/        ← 신규 (팩터 모멘텀 전용)
    ├── engine.py           ← 월별 포트폴리오 리밸런싱 엔진
    ├── factor_calculator.py ← 팩터 계산 (모멘텀, 볼륨 필터 등)
    └── portfolio.py        ← 포지션 관리, 리밸런싱 로직
```

---

## 구현 지시

### Step 1: 팩터 계산 모듈

**신규 파일**: `backtesting/factor_backtest/factor_calculator.py`

```python
import pandas as pd
import numpy as np

def calc_momentum_12_1(daily_df: pd.DataFrame, as_of_date) -> float:
    """
    12-1 모멘텀: (t-252일 ~ t-21일) 수익률
    가장 최근 1개월(t-21 ~ t) 제외 — 단기 반전 회피.

    daily_df: 해당 종목 일봉 DataFrame (index=date, columns=[open,high,low,close,volume])
    as_of_date: 계산 기준일 (월말)
    반환: float (수익률), 데이터 부족 시 None
    """
    idx = daily_df.index.get_loc(as_of_date, method="ffill")
    if idx < 252:
        return None

    price_t    = daily_df.iloc[idx]["close"]
    price_t252 = daily_df.iloc[idx - 252]["close"]
    price_t21  = daily_df.iloc[idx - 21]["close"]

    if price_t252 <= 0 or price_t21 <= 0:
        return None

    # 12-1 모멘텀 = (t-21 종가 / t-252 종가) - 1
    return (price_t21 / price_t252) - 1.0


def calc_avg_dollar_volume(daily_df: pd.DataFrame, as_of_date, window: int = 21) -> float:
    """
    최근 21거래일 평균 달러 거래량 (유동성 필터용).
    """
    idx = daily_df.index.get_loc(as_of_date, method="ffill")
    if idx < window:
        return 0.0
    window_df = daily_df.iloc[idx - window: idx]
    return (window_df["close"] * window_df["volume"]).mean()
```

---

### Step 2: 리밸런싱 엔진

**신규 파일**: `backtesting/factor_backtest/engine.py`

```python
from dataclasses import dataclass, field
from typing import List, Dict
import pandas as pd
import numpy as np
from .factor_calculator import calc_momentum_12_1, calc_avg_dollar_volume

@dataclass
class FactorBacktestConfig:
    # 유니버스
    symbols: List[str] = field(default_factory=list)   # S&P 500 티커 리스트

    # 팩터 파라미터
    momentum_lookback: int   = 252    # 12개월 = 252거래일
    momentum_skip:     int   = 21     # 최근 1개월 제외 (단기 반전 회피)
    top_pct:           float = 0.20   # 상위 20% 매수

    # 유동성 필터
    min_dollar_volume: float = 5e7    # 일평균 $5,000만 이상 (유동성 확보)
    min_price:         float = 5.0    # $5 이상 (페니스톡 제외)

    # 포지션 관리
    max_position_pct:  float = 0.05   # 단일 종목 최대 5% (최소 분산 20종목)
    rebalance_day:     str   = "last" # "last": 월 마지막 거래일

    # 비용
    commission_rate:   float = 0.001  # 0.1%
    slippage_rate:     float = 0.005  # 0.5% (시가 슬리피지)

    # 백테스트 설정
    initial_capital:   float = 1_000_000.0
    start_date:        str   = "2021-01-01"
    end_date:          str   = "2026-04-21"


class FactorBacktestEngine:
    def __init__(self, config: FactorBacktestConfig, daily_data: Dict[str, pd.DataFrame]):
        self.config = config
        self.daily_data = daily_data   # {symbol: daily_df}
        self.capital = config.initial_capital
        self.portfolio = {}            # {symbol: {"qty": int, "entry_price": float}}
        self.equity_curve = []
        self.trade_log = []

    def run(self):
        # 월말 리밸런싱 날짜 목록 생성
        all_dates = pd.bdate_range(self.config.start_date, self.config.end_date)
        month_ends = [d for d in all_dates
                      if d.month != (d + pd.offsets.BDay(1)).month]

        for rebalance_date in month_ends:
            self._rebalance(rebalance_date)
            self._record_equity(rebalance_date)

        return self._generate_report()

    def _rebalance(self, date):
        """
        월말 리밸런싱:
        1. 전 종목 12-1 모멘텀 계산
        2. 상위 20% 선별
        3. 기존 포트폴리오 대비 차이 매매
        """
        scores = {}
        for symbol in self.config.symbols:
            df = self.daily_data.get(symbol)
            if df is None or date not in df.index:
                continue

            # 유동성 필터
            dv = calc_avg_dollar_volume(df, date)
            if dv < self.config.min_dollar_volume:
                continue
            price = df.loc[date, "close"]
            if price < self.config.min_price:
                continue

            # 모멘텀 계산
            mom = calc_momentum_12_1(df, date)
            if mom is None:
                continue

            scores[symbol] = mom

        if not scores:
            return

        # 상위 20% 선별
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        n_top = max(1, int(len(ranked) * self.config.top_pct))
        target_symbols = set(s for s, _ in ranked[:n_top])

        # 현재 포트폴리오 가치 계산
        portfolio_value = self._calc_portfolio_value(date)
        total_value = self.capital + portfolio_value

        # 청산: 목표 유니버스에서 제외된 종목
        for symbol in list(self.portfolio.keys()):
            if symbol not in target_symbols:
                self._close_position(symbol, date)

        # 신규 매수 / 리밸런싱
        n_target = len(target_symbols)
        if n_target == 0:
            return

        per_position = min(
            total_value / n_target,
            total_value * self.config.max_position_pct
        )

        next_open = self._get_next_open(date)  # 다음 거래일 시가
        for symbol in target_symbols:
            df = self.daily_data.get(symbol)
            if df is None or next_open not in df.index:
                continue
            entry_price = df.loc[next_open, "open"] * (1 + self.config.slippage_rate)
            qty = int(per_position / entry_price)
            if qty <= 0:
                continue
            cost = entry_price * qty * (1 + self.config.commission_rate)
            if cost > self.capital:
                continue

            if symbol in self.portfolio:
                # 기존 보유 — 수량 조정
                self._adjust_position(symbol, qty, entry_price)
            else:
                # 신규 진입
                self.capital -= cost
                self.portfolio[symbol] = {
                    "qty": qty,
                    "entry_price": entry_price,
                    "entry_date": str(next_open.date()),
                }
                self.trade_log.append({
                    "date": str(next_open.date()),
                    "symbol": symbol,
                    "action": "BUY",
                    "price": entry_price,
                    "qty": qty,
                })

    def _close_position(self, symbol, date):
        pos = self.portfolio.pop(symbol, None)
        if pos is None:
            return
        next_open = self._get_next_open(date)
        df = self.daily_data.get(symbol)
        if df is None or next_open not in df.index:
            return
        exit_price = df.loc[next_open, "open"] * (1 - self.config.slippage_rate)
        proceeds = exit_price * pos["qty"] * (1 - self.config.commission_rate)
        pnl = (exit_price - pos["entry_price"]) * pos["qty"]
        self.capital += proceeds
        self.trade_log.append({
            "date": str(next_open.date()),
            "symbol": symbol,
            "action": "SELL",
            "price": exit_price,
            "qty": pos["qty"],
            "pnl": pnl,
        })
```

---

### Step 3: 실행 스크립트

**신규 파일**: `backtesting/run_factor_backtest.py`

```python
"""
팩터 모멘텀 백테스트 실행기.
사용 예:
  python backtesting/run_factor_backtest.py \
    --sp500 --top-pct 20 --min-dv 50 --start 2021-01-01
"""
import argparse
from factor_backtest.engine import FactorBacktestConfig, FactorBacktestEngine
from universe_backtest.data_cache import load_daily_data   # 기존 캐시 재사용
from config.trading_constants import SP500_SYMBOLS         # 필요 시 추가

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sp500",      action="store_true", help="S&P 500 유니버스")
    parser.add_argument("--itc",        action="store_true", help="ITC 16종목 유니버스")
    parser.add_argument("--top-pct",    type=float, default=20.0,
                        help="상위 선택 비율 %% (기본 20)")
    parser.add_argument("--min-dv",     type=float, default=50.0,
                        help="최소 일평균 달러 거래량 $M (기본 50)")
    parser.add_argument("--max-pos-pct",type=float, default=5.0,
                        help="단일 종목 최대 비중 %% (기본 5)")
    parser.add_argument("--start",      default="2021-01-01")
    parser.add_argument("--end",        default="2026-04-21")
    args = parser.parse_args()

    # 유니버스 선택
    if args.itc:
        from config.trading_constants import ITC_UNIVERSE
        symbols = ITC_UNIVERSE
    else:
        symbols = SP500_SYMBOLS  # 별도 리스트 필요

    config = FactorBacktestConfig(
        symbols          = symbols,
        top_pct          = args.top_pct / 100,
        min_dollar_volume= args.min_dv * 1e6,
        max_position_pct = args.max_pos_pct / 100,
        start_date       = args.start,
        end_date         = args.end,
    )

    daily_data = load_daily_data(symbols, args.start, args.end)
    engine = FactorBacktestEngine(config, daily_data)
    engine.run()

if __name__ == "__main__":
    main()
```

---

## 테스트 순서

```bash
# P15-1: 팩터 모멘텀 — ITC 유니버스 (16종목, 품질 먼저 확인)
# 상위 50% 선택 (16종목 중 8종목)
python backtesting/run_factor_backtest.py \
  --itc --top-pct 50 --min-dv 10 \
  --start 2021-01-01

# P15-2: 팩터 모멘텀 — S&P 500 전체 (빈도/분산 확인)
# 상위 20% 선택 (~100종목)
python backtesting/run_factor_backtest.py \
  --sp500 --top-pct 20 --min-dv 50 \
  --start 2021-01-01

# P15-3: 파라미터 변형 — 상위 10% (집중 포트폴리오)
python backtesting/run_factor_backtest.py \
  --sp500 --top-pct 10 --min-dv 50 \
  --start 2021-01-01
```

---

## 보고 양식

```
테스트명: P15-X [주요 파라미터]
실행 명령어: [전체 명령어]

결과:
- 연간 수익률 (CAGR) / 총 수익률
- Sharpe Ratio / Sortino Ratio
- MDD / MDD 발생 기간
- 거래 회전율 (연간 리밸런싱 시 교체 비율)
- 월별 수익률 분포 (최고/최저/평균)
- 연도별 수익률: 2021~2026
- 벤치마크 대비 초과 수익 (SPY 대비)
- 상위 기여 종목 10 / 하위 기여 종목 10
- 특이사항 (모멘텀 크래시 구간 발생 여부)
```

---

## 합격 기준

| 결과 | 조건 | 다음 행동 |
|------|------|---------|
| **합격** | CAGR ≥ 15% AND Sharpe ≥ 0.8 | V4 + 팩터 모멘텀 통합 포트폴리오 |
| **부분 합격** | CAGR ≥ 10% AND Sharpe ≥ 0.6 | top-pct / 유동성 필터 조정 후 재시도 |
| **실패** | 위 조건 미달 | 전략 D (페어 트레이딩) 착수 |

> **합격 기준을 V4보다 낮게 설정한 이유**: 팩터 모멘텀은 단일 종목이 아닌 포트폴리오 전략.
> PF 개념 대신 CAGR + Sharpe 조합으로 평가합니다.

---

## 향후 강화 방향 (합격 후)

1. **Long/Short 버전**: 하위 20% Short 추가 → Sharpe 1.3~1.8 기대
2. **멀티 팩터**: 모멘텀 + 퀄리티(ROE) + 저변동성 결합
3. **V4 병행**: V4 위성(25% 자본) + 팩터 모멘텀 주전략(75% 자본)

---

*P15-1 → P15-2 → P15-3 순서로 실행 후 보고 바랍니다.*
*구현 예상 기간: 2~3주 (신규 모듈 분리 구현)*
