"""
MultiFactorScorer — NAVIS ALPHA v1.0 P24 확정

월말 리밸런싱 시 유니버스 전체를 4팩터 복합 점수(0~100)로 정량화.

  Quality Score  (0~35): F-Score + ROE + FCF/Assets + Accruals
  Value Score    (0~40): EV/EBITDA(48%) + P/FCF(32%) + P/B(20%) — 섹터 상대
  Momentum Score (0~25): 12-1 가격 모멘텀 크로스섹셔널 정규화
  Catalyst Score (0~0):  Form4 확보 전 비활성

  Composite      (0~100): 위 합산

Layer 3 하드 필터 (passes_value_trap_filter + passes_growth_filter):
  Value Trap: ROE_2yr, FCF_2yr, D/E 기준 구조적 쇠퇴 기업 제거
  성장 필터: rev_cagr_3yr ≥ -0.05 (CPB 유형 제거)

진입 거부 필터:
  ATR/종가 > 0.05 종목 진입 거부 (MAX_ATR_RATIO)
  인트라-피리어드 스탑 없음 — P24 영구 제거.

두 패스 알고리즘:
  Pass 1 — 모든 종목의 원시 지표 계산 + 하드 필터 적용
  Pass 2 — 섹터별 피어 리스트 구성 → 각 종목 점수 산출
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .factor_calculator import (
    _percentile_rank,
    calc_quality_score,
    calc_value_score,
    calc_composite_score,
    calc_momentum_12_1,
    calc_atr_ratio,
    passes_value_trap_filter,
    passes_growth_filter,
    MAX_ATR_RATIO,
)

logger = logging.getLogger(__name__)

FORM4_CACHE_DIR   = Path("data/form4/cache")
CATALYST_LOOKBACK = 90   # days

# Catalyst 점수 임계값 (스펙 §5-4)
CATALYST_TIERS = [
    (100_000, 10),
    ( 50_000,  6),
    ( 10_000,  3),
]


class MultiFactorScorer:
    """
    유니버스 전체 4팩터 복합 점수 계산기.

    사용:
        scorer = MultiFactorScorer()
        scores = scorer.score_universe(symbols, rebalance_date, daily_data)
        # → {symbol: composite_score 0~100}
    """

    def __init__(
        self,
        fund_dir: str        = "data/fundamentals",
        sector_map_path: str = "data/universe/sector_map.parquet",
        form4_cache_dir: str = "data/form4/cache",
    ):
        self._fund_dir        = Path(fund_dir)
        self._form4_dir       = Path(form4_cache_dir)
        self._fund_cache:  dict[str, Optional[pd.DataFrame]] = {}
        self._form4_cache: dict[str, pd.DataFrame] = {}

        try:
            sm = pd.read_parquet(sector_map_path)
            self._sector_map: dict[str, str] = dict(zip(sm["symbol"], sm["sector"]))
        except Exception:
            logger.warning("섹터 맵 로드 실패 — 전체 단일 섹터로 처리")
            self._sector_map = {}

    # ── 메인 API ──────────────────────────────────────────────────────────────

    def score_universe(
        self,
        symbols: list[str],
        as_of_date: date,
        daily_data: dict[str, pd.DataFrame],
    ) -> dict[str, float]:
        """
        유니버스 전체 Composite Score 계산.

        Args:
            symbols:    종목 리스트
            as_of_date: 기준일 (월말)
            daily_data: {symbol: 일봉 DataFrame}

        Returns:
            {symbol: composite_score}  점수 산출 불가 종목은 제외
        """
        as_of_str = str(as_of_date)

        # ── Pass 1: 원시 지표 수집 ──────────────────────────────────────────
        raw: dict[str, dict]   = {}
        mom_raw: dict[str, float] = {}

        for sym in symbols:
            df = daily_data.get(sym)
            if df is None or len(df) == 0:
                continue

            price = self._get_price(df, as_of_date)
            if price is None or price <= 0:
                continue

            # ATR 진입 거부 필터 (MAX_ATR_RATIO = 0.05)
            atr_ratio = calc_atr_ratio(df, as_of_date)
            if atr_ratio is not None and atr_ratio > MAX_ATR_RATIO:
                continue

            fund = self._load_quarterly(sym)
            if fund is None or fund.empty:
                continue

            # Point-in-time 필터
            avail = fund[fund["filing_date"] <= as_of_str].sort_values(
                "period_end_date", ascending=False
            ).reset_index(drop=True)
            if avail.empty:
                continue

            latest  = avail.iloc[0]
            n_ttm   = min(4, len(avail))
            ttm_rows = avail.head(n_ttm)

            def ttm(col: str) -> Optional[float]:
                if col not in ttm_rows.columns:
                    return None
                vals = ttm_rows[col].dropna()
                return float(vals.sum()) if len(vals) > 0 else None

            def lat(col: str) -> Optional[float]:
                v = latest.get(col)
                return float(v) if pd.notna(v) else None

            total_assets = lat("total_assets")
            total_liab   = lat("total_liabilities")
            lt_debt      = lat("lt_debt")
            shares       = lat("shares_outstanding")
            cash         = lat("cash")
            net_income   = ttm("net_income")
            cfo          = ttm("cfo")
            op_income    = ttm("operating_income")
            da           = ttm("da")

            if total_assets is None or shares is None or shares <= 0:
                continue

            equity = (total_assets - total_liab) if total_liab is not None else None

            # F-Score
            f_score = self._calc_fscore(sym, avail)

            # ROE (TTM)
            roe = None
            if net_income is not None and equity and equity != 0:
                roe = net_income / equity

            # FCF/Assets (CFO 기준, TTM)
            fcf_yield = None
            if cfo is not None and total_assets != 0:
                fcf_yield = cfo / total_assets

            # ── P21: 2년 평균 ROE/FCF (Value Trap 필터용) ──────────────────
            roe_2yr      = self._calc_2yr_avg_roe(avail)
            fcf_yield_2yr = self._calc_2yr_avg_fcf_yield(avail)

            # D/E (Value Trap 필터용)
            debt_equity = None
            if lt_debt is not None and equity is not None and equity != 0:
                debt_equity = lt_debt / equity

            # ── P22-A: 매출 3년 CAGR (성장 필터용) ────────────────────────
            revenue_cagr_3yr = self._calc_rev_cagr_3yr(avail)

            # ── Layer 3 하드 필터 ────────────────────────────────────────────
            sector = self._sector_map.get(sym, "Unknown")
            fundamentals_for_filter = {
                "debt_equity":      debt_equity,
                "roe_2yr":          roe_2yr,
                "fcf_yield_2yr":    fcf_yield_2yr,
                "revenue_cagr_3yr": revenue_cagr_3yr,
            }
            if not passes_value_trap_filter(fundamentals_for_filter, sector):
                continue
            if not passes_growth_filter(fundamentals_for_filter):
                continue

            # P/B
            p_b = None
            if equity is not None and equity > 0:
                bvps = equity / shares
                if bvps > 0:
                    p_b = price / bvps

            # P/FCF
            p_fcf = None
            if cfo is not None:
                cfo_ps = cfo / shares
                if cfo_ps > 0:
                    p_fcf = price / cfo_ps

            # EV/EBITDA
            ev_ebitda = None
            if op_income is not None and da is not None:
                ebitda = op_income + da
                if ebitda > 0:
                    ev = price * shares + (lt_debt or 0.0) - (cash or 0.0)
                    if ev > 0:
                        ev_ebitda = ev / ebitda

            raw[sym] = {
                "f_score":    f_score,
                "roe":        roe,
                "fcf_yield":  fcf_yield,
                "net_income": net_income,
                "cfo":        cfo,
                "total_assets": total_assets,
                "ev_ebitda":  ev_ebitda,
                "p_fcf":      p_fcf,
                "p_b":        p_b,
                "sector":     sector,
            }

            mom = calc_momentum_12_1(df, as_of_date)
            if mom is not None:
                mom_raw[sym] = mom

        if not raw:
            return {}

        # ── Pass 2: 섹터 피어 구성 → 점수 계산 ────────────────────────────
        sector_peers = self._build_sector_peers(raw)
        mom_values   = list(mom_raw.values())

        scores: dict[str, float] = {}
        for sym, m in raw.items():
            peers    = sector_peers.get(m["sector"], {})
            quality  = calc_quality_score(m, peers)
            value    = calc_value_score(m, peers)
            momentum = self._normalize_momentum(mom_raw.get(sym), mom_values)
            catalyst = self._calc_catalyst_score(sym, as_of_date)
            scores[sym] = calc_composite_score(quality, value, momentum, catalyst)

        return scores

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _get_price(self, df: pd.DataFrame, target: date) -> Optional[float]:
        if target in df.index:
            return float(df.loc[target, "close"])
        loc = df.index.searchsorted(target, side="right") - 1
        return float(df.iloc[loc]["close"]) if loc >= 0 else None

    def _load_quarterly(self, symbol: str) -> Optional[pd.DataFrame]:
        if symbol in self._fund_cache:
            return self._fund_cache[symbol]
        path = self._fund_dir / "quarterly" / symbol / f"{symbol}_quarterly.parquet"
        if not path.exists():
            self._fund_cache[symbol] = None
            return None
        try:
            df = pd.read_parquet(path)
            df = df.dropna(subset=["filing_date", "period_end_date"])
            df["filing_date"]    = df["filing_date"].astype(str)
            df["period_end_date"] = df["period_end_date"].astype(str)
            self._fund_cache[symbol] = df
            return df
        except Exception as e:
            logger.debug(f"{symbol} 재무 데이터 로드 실패: {e}")
            self._fund_cache[symbol] = None
            return None

    def _calc_fscore(self, symbol: str, avail: pd.DataFrame) -> int:
        """
        Piotroski F-Score (0~9) 간이 계산 (Point-in-time 보장).

        fundamental_screener.FundamentalScreener 와 동일한 로직을 인라인으로 구현.
        MultiFactorScorer가 fundamental_screener에 의존하지 않도록 독립적으로 계산.
        """
        def fval(row, col: str) -> Optional[float]:
            v = row.get(col) if row is not None else None
            return float(v) if v is not None and pd.notna(v) else None

        if avail.empty:
            return 0
        cur  = avail.iloc[0]
        prior = avail.iloc[3] if len(avail) >= 4 else None

        def _ta(row) -> Optional[float]:
            return fval(row, "total_assets")

        def _roa(row) -> Optional[float]:
            ni = fval(row, "net_income")
            ta = _ta(row)
            return (ni / ta) if ni is not None and ta and ta != 0 else None

        def _cfo_roa(row) -> Optional[float]:
            c = fval(row, "cfo")
            ta = _ta(row)
            return (c / ta) if c is not None and ta and ta != 0 else None

        def _lev(row) -> Optional[float]:
            d = fval(row, "lt_debt")
            ta = _ta(row)
            return (d / ta) if d is not None and ta and ta != 0 else None

        def _cr(row) -> Optional[float]:
            ca = fval(row, "current_assets")
            cl = fval(row, "current_liabilities")
            return (ca / cl) if ca is not None and cl and cl != 0 else None

        def _gm(row) -> Optional[float]:
            gp = fval(row, "gross_profit")
            rv = fval(row, "revenue")
            return (gp / rv) if gp is not None and rv and rv != 0 else None

        def _at(row) -> Optional[float]:
            rv = fval(row, "revenue")
            ta = _ta(row)
            return (rv / ta) if rv is not None and ta and ta != 0 else None

        roa_c = _roa(cur)
        cfo_c = fval(cur, "cfo")
        cfo_roa_c = _cfo_roa(cur)
        roa_p = _roa(prior) if prior is not None else None

        f1 = 1 if roa_c is not None and roa_c > 0 else 0
        f2 = 1 if cfo_c is not None and cfo_c > 0 else 0
        f3 = 1 if (roa_c is not None and roa_p is not None and roa_c > roa_p) else 0
        f4 = 1 if (cfo_roa_c is not None and roa_c is not None and cfo_roa_c > roa_c) else 0

        lev_c = _lev(cur)
        lev_p = _lev(prior) if prior is not None else None
        f5 = 1 if (lev_c is not None and lev_p is not None and lev_c < lev_p) else 0

        cr_c = _cr(cur)
        cr_p = _cr(prior) if prior is not None else None
        f6 = 1 if (cr_c is not None and cr_p is not None and cr_c > cr_p) else 0

        sh_c = fval(cur, "shares_outstanding")
        sh_p = fval(prior, "shares_outstanding") if prior is not None else None
        if sh_c and sh_p and sh_p > 0:
            dilution = (sh_c - sh_p) / sh_p
            f7 = 1 if dilution <= 0.02 else 0
        else:
            f7 = 1

        gm_c = _gm(cur)
        gm_p = _gm(prior) if prior is not None else None
        f8 = 1 if (gm_c is not None and gm_p is not None and gm_c > gm_p) else 0

        at_c = _at(cur)
        at_p = _at(prior) if prior is not None else None
        f9 = 1 if (at_c is not None and at_p is not None and at_c > at_p) else 0

        return f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8 + f9

    def _build_sector_peers(self, raw: dict[str, dict]) -> dict[str, dict]:
        """섹터별 피어 지표 리스트 구성."""
        peer_map: dict[str, dict] = defaultdict(lambda: {
            "roe": [], "fcf_yield": [], "accruals": [],
            "ev_ebitda": [], "p_fcf": [], "p_b": [],
        })
        for m in raw.values():
            sec = m["sector"]
            if m.get("roe") is not None:
                peer_map[sec]["roe"].append(m["roe"])
            if m.get("fcf_yield") is not None:
                peer_map[sec]["fcf_yield"].append(m["fcf_yield"])
            ni = m.get("net_income")
            cfo = m.get("cfo")
            ta  = m.get("total_assets")
            if ni is not None and cfo is not None and ta and ta != 0:
                peer_map[sec]["accruals"].append((ni - cfo) / ta)
            if m.get("ev_ebitda") is not None:
                peer_map[sec]["ev_ebitda"].append(m["ev_ebitda"])
            if m.get("p_fcf") is not None:
                peer_map[sec]["p_fcf"].append(m["p_fcf"])
            if m.get("p_b") is not None:
                peer_map[sec]["p_b"].append(m["p_b"])
        return dict(peer_map)

    def _normalize_momentum(
        self,
        raw_mom: Optional[float],
        all_moms: list[float],
    ) -> float:
        """12-1 모멘텀을 크로스섹셔널 백분위로 0~25점 정규화 (P24 확정)."""
        if raw_mom is None:
            return 0.0
        return _percentile_rank(raw_mom, all_moms) * 25.0

    def _calc_2yr_avg_roe(self, avail: pd.DataFrame) -> Optional[float]:
        """최근 8분기(2년) 평균 ROE. TTM 기준 2개 연도 평균."""
        if avail.empty:
            return None
        rows = avail.head(min(8, len(avail)))
        roes = []
        for i, row in rows.iterrows():
            ni = row.get("net_income")
            ta = row.get("total_assets")
            tl = row.get("total_liabilities")
            if pd.isna(ni) or pd.isna(ta) or ta == 0:
                continue
            eq = ta - (tl if pd.notna(tl) else 0)
            if eq != 0:
                roes.append(ni / eq)
        if not roes:
            return None
        return float(np.mean(roes))

    def _calc_2yr_avg_fcf_yield(self, avail: pd.DataFrame) -> Optional[float]:
        """최근 8분기(2년) 평균 FCF/Assets."""
        if avail.empty:
            return None
        rows = avail.head(min(8, len(avail)))
        yields = []
        for i, row in rows.iterrows():
            cfo = row.get("cfo")
            ta  = row.get("total_assets")
            if pd.isna(cfo) or pd.isna(ta) or ta == 0:
                continue
            yields.append(cfo / ta)
        if not yields:
            return None
        return float(np.mean(yields))

    def _calc_rev_cagr_3yr(self, avail: pd.DataFrame) -> Optional[float]:
        """3개년 매출 CAGR (12분기 또는 연간 데이터 기준)."""
        if "revenue" not in avail.columns:
            return None
        rows = avail.head(min(12, len(avail)))
        rev_vals = rows["revenue"].dropna().values
        if len(rev_vals) < 8:
            return None
        rev_recent = rev_vals[:4].sum()
        rev_3yago  = rev_vals[8:12].sum() if len(rev_vals) >= 12 else rev_vals[-4:].sum()
        if rev_3yago <= 0:
            return None
        return float((rev_recent / rev_3yago) ** (1 / 3) - 1)

    def _calc_catalyst_score(self, symbol: str, as_of_date: date) -> float:
        """
        내부자 순매수 금액 → 0~10점.
        자사주 매입(0~5점)은 P20에서 추가.
        """
        df = self._load_form4(symbol)
        if df.empty:
            return 0.0
        cutoff = pd.Timestamp(as_of_date) - pd.Timedelta(days=CATALYST_LOOKBACK)
        recent = df[
            (df["filing_date"] >= cutoff)
            & (df["filing_date"] <= pd.Timestamp(as_of_date))
        ]
        if recent.empty:
            return 0.0
        net_buy = float(recent["total_value"].sum())
        for threshold, pts in CATALYST_TIERS:
            if net_buy >= threshold:
                return float(pts)
        return 0.0

    def _load_form4(self, symbol: str) -> pd.DataFrame:
        if symbol in self._form4_cache:
            return self._form4_cache[symbol]
        path = self._form4_dir / f"{symbol}_form4.parquet"
        if not path.exists():
            self._form4_cache[symbol] = pd.DataFrame()
            return pd.DataFrame()
        try:
            df = pd.read_parquet(path)
            df["filing_date"] = pd.to_datetime(df["filing_date"])
            self._form4_cache[symbol] = df
            return df
        except Exception:
            self._form4_cache[symbol] = pd.DataFrame()
            return pd.DataFrame()
