"""
NAVIS Universe Backtest — Phase 2: 과거 스크리닝 재현

WatchlistGenerator 의 갭+거래량 로직을 캐시된 일봉 데이터에 그대로 재현.
실제 NAVIS 가 매일 선택했을 종목 리스트를 날짜별로 생성한다.

출력:
    {trading_date: [
        {'symbol': str, 'gap_pct': float, 'volume_ratio': float,
         'score': float, 'prev_close': float, 'day_open': float},
        ...  (최대 max_watchlist_size개, score 내림차순)
    ]}
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class HistoricalScreener:
    """
    캐시된 일봉 데이터를 순회하며 NAVIS 갭+거래량 스크리닝을 재현한다.

    Args:
        gap_threshold:        갭 임계값 (%)
        volume_ratio_threshold: 거래량 배수 임계값
        volume_ma_period:     거래량 이동평균 기간 (일)
        max_watchlist_size:   최대 선정 종목 수
        min_price:            최소 주가 필터 ($)
        min_avg_volume:       최소 평균 거래량 필터
    """

    def __init__(
        self,
        gap_threshold:          float = 2.0,
        volume_ratio_threshold: float = 2.0,
        volume_ma_period:       int   = 20,
        max_watchlist_size:     int   = 20,
        min_price:              float = 5.0,
        min_avg_volume:         int   = 300_000,
        gap_fade_down:          bool  = False,   # True: 갭다운 후보 통과 (Gap Fade Down 전략)
        gap_fade_down_min_gap:  float = 3.0,     # 갭다운 최소 크기 %
    ):
        self.gap_threshold           = gap_threshold
        self.volume_ratio_threshold  = volume_ratio_threshold
        self.volume_ma_period        = volume_ma_period
        self.max_watchlist_size      = max_watchlist_size
        self.gap_fade_down           = gap_fade_down
        self.gap_fade_down_min_gap   = gap_fade_down_min_gap
        self.min_price               = min_price
        self.min_avg_volume          = min_avg_volume

    def run(
        self,
        daily_data: Dict[str, pd.DataFrame],
        start: Optional[str] = None,
        end:   Optional[str] = None,
        warmup_days: int = 25,
    ) -> Dict[date, List[dict]]:
        """
        전체 유니버스 일봉을 순회하며 날짜별 워치리스트를 생성한다.

        Args:
            daily_data:  {symbol: daily_df}  ← DataCache.load_daily() 결과 묶음
            start:       스크리닝 시작일 (None → 최초 가용일 + warmup)
            end:         스크리닝 종료일 (None → 최신)
            warmup_days: 거래량 MA 계산에 필요한 워밍업 기간

        Returns:
            {trading_date: [candidate_dict, ...]}
        """
        if not daily_data:
            return {}

        # ── 전체 거래일 목록 수집 ─────────────────────────────────────
        all_dates: set[date] = set()
        for df in daily_data.values():
            all_dates.update(df.index.tolist())
        trading_dates = sorted(all_dates)

        # ── 기간 필터 ─────────────────────────────────────────────────
        if start:
            from datetime import datetime
            start_d = datetime.strptime(start, "%Y-%m-%d").date()
            trading_dates = [d for d in trading_dates if d >= start_d]
        if end:
            from datetime import datetime
            end_d = datetime.strptime(end, "%Y-%m-%d").date()
            trading_dates = [d for d in trading_dates if d <= end_d]

        # warmup 이후부터 스크리닝
        trading_dates = trading_dates[warmup_days:]

        logger.info(
            f"[Screener] 스크리닝 기간: {trading_dates[0]} ~ {trading_dates[-1]} "
            f"({len(trading_dates)} 거래일)"
        )

        # ── 날짜별 스크리닝 ───────────────────────────────────────────
        result: Dict[date, List[dict]] = {}
        total_candidates = 0

        for today in trading_dates:
            candidates = []

            for symbol, df in daily_data.items():
                idx = df.index.get_loc(today) if today in df.index else None
                if idx is None or idx < warmup_days:
                    continue

                row      = df.iloc[idx]
                prev_row = df.iloc[idx - 1]

                prev_close   = float(prev_row["close"])
                day_open     = float(row.get("open", row["close"]))
                current_price = float(row["close"])
                current_volume = int(row["volume"])

                # ── 기본 필터 ─────────────────────────────────────
                if current_price < self.min_price:
                    continue

                # ── 갭 계산 ───────────────────────────────────────
                if prev_close <= 0:
                    continue
                gap_pct = (day_open - prev_close) / prev_close * 100.0

                # ── 거래량 비율 계산 ──────────────────────────────
                vol_window = df.iloc[idx - self.volume_ma_period: idx]["volume"]
                if len(vol_window) < self.volume_ma_period // 2:
                    continue
                avg_volume = float(vol_window.mean())
                if avg_volume < self.min_avg_volume:
                    continue
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0.0

                # ── 스크리닝 조건 ─────────────────────────────────
                if self.gap_fade_down:
                    # Gap Fade Down 모드: 갭다운 크기만으로 필터 (거래량 조건 무관)
                    if gap_pct > -self.gap_fade_down_min_gap:
                        continue
                else:
                    meets_gap    = gap_pct    >= self.gap_threshold
                    meets_volume = volume_ratio >= self.volume_ratio_threshold
                    if not (meets_gap or meets_volume):
                        continue

                # ── 스코어 계산 (gap 가중 + volume 가중) ──────────
                gap_score    = min(abs(gap_pct) / 10.0, 1.0)     # 10% 갭 = 1.0 (절댓값)
                vol_score    = min(volume_ratio / 10.0, 1.0)     # 10x = 1.0
                score        = gap_score * 0.4 + vol_score * 0.6  # volume 비중 높게

                candidates.append({
                    "symbol":       symbol,
                    "gap_pct":      round(gap_pct, 3),
                    "volume_ratio": round(volume_ratio, 3),
                    "score":        round(score, 4),
                    "prev_close":   prev_close,
                    "day_open":     day_open,
                    "avg_volume":   int(avg_volume),
                })

            # 스코어 내림차순, 상위 N개 선정
            candidates.sort(key=lambda x: x["score"], reverse=True)
            watchlist = candidates[: self.max_watchlist_size]

            if watchlist:
                result[today] = watchlist
                total_candidates += len(watchlist)

        logger.info(
            f"[Screener] 완료 | 갭/거래량 감지일: {len(result)}일 | "
            f"총 후보 진입 기회: {total_candidates}건"
        )
        return result

    def summary_stats(self, screened: Dict[date, List[dict]]) -> dict:
        """스크리닝 결과 요약 통계."""
        if not screened:
            return {}
        daily_counts    = [len(v) for v in screened.values()]
        all_gaps        = [c["gap_pct"]      for v in screened.values() for c in v]
        all_vol_ratios  = [c["volume_ratio"] for v in screened.values() for c in v]
        symbol_freq: Dict[str, int] = {}
        for candidates in screened.values():
            for c in candidates:
                symbol_freq[c["symbol"]] = symbol_freq.get(c["symbol"], 0) + 1
        top_symbols = sorted(symbol_freq.items(), key=lambda x: -x[1])[:10]
        return {
            "total_days_with_signals": len(screened),
            "avg_candidates_per_day":  round(np.mean(daily_counts), 1),
            "max_candidates_per_day":  max(daily_counts),
            "avg_gap_pct":             round(np.mean(all_gaps), 2),
            "avg_volume_ratio":        round(np.mean(all_vol_ratios), 2),
            "top_10_symbols":          top_symbols,
        }
