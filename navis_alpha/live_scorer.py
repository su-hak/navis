"""
NAVIS ALPHA v1.0 — 라이브 스코어러

yfinance 재무 데이터 + Alpaca 일봉 데이터로 실시간 팩터 점수를 계산합니다.
MultiFactorScorer를 상속하되, parquet 파일 대신 yfinance를 데이터 소스로 사용합니다.

사용:
    scorer = NavisAlphaLiveScorer(
        api_key="...", api_secret="...",
        sector_cache_path="sector_cache.json",
    )
    scores = scorer.score_universe(symbols, date.today(), lookback_days=400)
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from backtesting.factor_backtest.multi_factor_scorer import MultiFactorScorer
from backtesting.factor_backtest.factor_calculator import (
    calc_atr_ratio,
    passes_value_trap_filter,
    passes_growth_filter,
    calc_momentum_12_1,
    calc_quality_score,
    calc_value_score,
    calc_composite_score,
    _percentile_rank,
    MAX_ATR_RATIO,
)

logger = logging.getLogger(__name__)


class NavisAlphaLiveScorer(MultiFactorScorer):
    """
    라이브 운용용 MultiFactorScorer.

    parquet 재무 파일 대신 yfinance를 실시간으로 조회합니다.
    Alpaca API로 일봉 데이터를 수집합니다.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        sector_cache_path: str = "sector_cache.json",
        lookback_days: int = 400,
    ):
        # MultiFactorScorer 초기화 (fund_dir은 사용하지 않음)
        super().__init__(
            fund_dir="",
            sector_map_path="",
            form4_cache_dir="",
        )
        self._api_key     = api_key
        self._api_secret  = api_secret
        self._lookback    = lookback_days
        self._yf_cache:  dict[str, Optional[pd.DataFrame]] = {}

        # 섹터 맵 로드 (JSON 형식 — sector_cache.json)
        try:
            with open(sector_cache_path, encoding="utf-8") as f:
                self._sector_map = json.load(f)
            logger.info(f"[LiveScorer] 섹터 맵 로드: {len(self._sector_map)}종목")
        except Exception as e:
            logger.warning(f"[LiveScorer] 섹터 맵 로드 실패: {e}")
            self._sector_map = {}

    # ── 메인 API ─────────────────────────────────────────────────────────────

    def score_universe(
        self,
        symbols: List[str],
        as_of_date: date,
        daily_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> dict[str, float]:
        """
        유니버스 전체 Composite Score 계산 (라이브 버전).

        daily_data가 None이면 Alpaca API에서 자동 수집합니다.

        Returns:
            {symbol: composite_score}
        """
        if daily_data is None:
            logger.info(f"[LiveScorer] Alpaca에서 일봉 데이터 수집 중 ({len(symbols)}종목)...")
            daily_data = self._fetch_daily_data(symbols, as_of_date)

        return super().score_universe(symbols, as_of_date, daily_data)

    # ── 재무 데이터 — yfinance ────────────────────────────────────────────────

    def _load_quarterly(self, symbol: str) -> Optional[pd.DataFrame]:
        """yfinance에서 분기 재무 데이터를 조회하고 parquet 스키마와 동일한 형태로 반환."""
        if symbol in self._fund_cache:
            return self._fund_cache[symbol]

        df = self._fetch_yfinance_quarterly(symbol)
        self._fund_cache[symbol] = df
        return df

    def _fetch_yfinance_quarterly(self, symbol: str) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance 미설치: pip install yfinance")
            return None

        try:
            ticker = yf.Ticker(symbol)
            info   = ticker.info or {}

            # 분기 손익계산서
            q_income = ticker.quarterly_income_stmt
            # 분기 현금흐름표
            q_cf     = ticker.quarterly_cashflow
            # 분기 대차대조표
            q_bal    = ticker.quarterly_balance_sheet

            if q_income is None or q_income.empty:
                return None

            rows = []
            for col in q_income.columns:
                period_end = col.date() if hasattr(col, "date") else col
                # yfinance의 filing_date는 period_end + ~45일로 추정
                filing_date = period_end + timedelta(days=45)

                def get_val(df, *keys):
                    if df is None or df.empty:
                        return None
                    for k in keys:
                        if k in df.index:
                            v = df.loc[k, col]
                            return float(v) if pd.notna(v) else None
                    return None

                row = {
                    "period_end_date": str(period_end),
                    "filing_date":     str(filing_date),
                    "revenue":         get_val(q_income, "Total Revenue"),
                    "gross_profit":    get_val(q_income, "Gross Profit"),
                    "operating_income": get_val(q_income, "Operating Income", "EBIT"),
                    "net_income":      get_val(q_income, "Net Income"),
                    "da":              get_val(q_cf, "Depreciation And Amortization",
                                              "Depreciation"),
                    "cfo":             get_val(q_cf, "Operating Cash Flow",
                                              "Cash From Operations"),
                    "total_assets":    get_val(q_bal, "Total Assets"),
                    "total_liabilities": get_val(q_bal, "Total Liabilities Net Minority Interest",
                                                 "Total Liabilities"),
                    "lt_debt":         get_val(q_bal, "Long Term Debt",
                                              "Long-Term Debt"),
                    "current_assets":  get_val(q_bal, "Current Assets"),
                    "current_liabilities": get_val(q_bal, "Current Liabilities"),
                    "cash":            get_val(q_bal, "Cash And Cash Equivalents"),
                    "shares_outstanding": info.get("sharesOutstanding"),
                }
                rows.append(row)

            if not rows:
                return None

            result = pd.DataFrame(rows).sort_values(
                "period_end_date", ascending=False
            ).reset_index(drop=True)
            return result

        except Exception as e:
            logger.debug(f"[LiveScorer] {symbol} yfinance 조회 실패: {e}")
            return None

    # ── 가격 데이터 — Alpaca ──────────────────────────────────────────────────

    def _fetch_daily_data(
        self,
        symbols: List[str],
        as_of_date: date,
    ) -> Dict[str, pd.DataFrame]:
        """Alpaca API로 일봉 데이터 수집 (lookback_days 기준)."""
        try:
            from alpaca.data import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
        except ImportError:
            logger.error("alpaca-py 미설치: pip install alpaca-py")
            return {}

        start = as_of_date - timedelta(days=self._lookback)
        end   = as_of_date + timedelta(days=1)

        client = StockHistoricalDataClient(self._api_key, self._api_secret)

        # Alpaca 무료 요금제: 500종목씩 분할 요청
        result: Dict[str, pd.DataFrame] = {}
        batch_size = 500
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i: i + batch_size]
            try:
                req = StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=datetime.combine(start, datetime.min.time()),
                    end=datetime.combine(end, datetime.min.time()),
                )
                raw = client.get_stock_bars(req)
                for sym in batch:
                    if sym not in raw:
                        continue
                    bars = []
                    for b in raw[sym]:
                        dt = b.timestamp.date() if hasattr(b.timestamp, "date") else b.timestamp
                        bars.append({
                            "date":   dt,
                            "open":   float(b.open),
                            "high":   float(b.high),
                            "low":    float(b.low),
                            "close":  float(b.close),
                            "volume": int(b.volume),
                        })
                    if bars:
                        df = pd.DataFrame(bars).sort_values("date")
                        df.set_index("date", inplace=True)
                        result[sym] = df
            except Exception as e:
                logger.warning(f"[LiveScorer] Alpaca 배치 {i}~{i+batch_size} 수집 실패: {e}")

        logger.info(f"[LiveScorer] 일봉 수집 완료: {len(result)}/{len(symbols)}종목")
        return result
