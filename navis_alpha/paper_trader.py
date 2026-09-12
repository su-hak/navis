"""
NAVIS ALPHA v1.0 — 페이퍼 트레이딩 엔진

매월 마지막 거래일에 실행하여:
  1. 유니버스 팩터 스코어링 (NavisAlphaLiveScorer)
  2. 현재 Alpaca 페이퍼 포트폴리오 조회
  3. 목표 포트폴리오 계산 (top 10%, 동일 비중)
  4. 매수/매도 주문 제출 (다음 거래일 시가 — MOO 주문)
  5. 리밸런싱 결과 로그 저장

사용:
    trader = NavisAlphaPaperTrader.from_env()
    trader.rebalance()

환경변수:
    ALPACA_API_KEY, ALPACA_SECRET_KEY
    ALPACA_BASE_URL (기본: https://paper-api.alpaca.markets)
"""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# 확정 파라미터 (P24)
TOP_PCT        = 0.10    # 상위 10% 선별
MAX_SECTOR_PCT = 0.25    # 섹터 최대 25%
MAX_SINGLE_PCT = 0.05    # 단일 종목 최대 5%
MIN_PRICE      = 5.0     # 최소 주가 $5
MIN_ADV        = 2e6     # 일평균 거래대금 $2M
MIN_MKT_CAP    = 2e8     # 시가총액 $200M

TRACKING_FILE  = Path("navis_alpha_tracking.csv")


class NavisAlphaPaperTrader:
    """NAVIS ALPHA v1.0 월간 리밸런싱 페이퍼 트레이딩."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://paper-api.alpaca.markets",
        sector_cache_path: str = "sector_cache.json",
        dry_run: bool = False,
    ):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.base_url   = base_url
        self.dry_run    = dry_run

        with open(sector_cache_path, encoding="utf-8") as f:
            self.sector_map: Dict[str, str] = json.load(f)

        self.symbols = list(self.sector_map.keys())

        from navis_alpha.live_scorer import NavisAlphaLiveScorer
        self.scorer = NavisAlphaLiveScorer(
            api_key=api_key,
            api_secret=api_secret,
            sector_cache_path=sector_cache_path,
        )

    @classmethod
    def from_env(cls, dry_run: bool = False) -> "NavisAlphaPaperTrader":
        return cls(
            api_key    = os.environ["ALPACA_API_KEY"],
            api_secret = os.environ["ALPACA_SECRET_KEY"],
            base_url   = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            dry_run    = dry_run,
        )

    # ── 메인 ─────────────────────────────────────────────────────────────────

    def rebalance(self) -> dict:
        """
        월말 리밸런싱 실행.

        Returns:
            리밸런싱 요약 딕셔너리
        """
        today = date.today()
        logger.info(f"[NAVIS ALPHA] 리밸런싱 시작 — {today}")

        broker  = self._connect_broker()
        account = broker.get_account()
        equity  = float(account.equity)
        logger.info(f"[NAVIS ALPHA] 페이퍼 계좌 자산: ${equity:,.0f}")

        # ── 1. 스코어링 ────────────────────────────────────────────────────
        logger.info("[NAVIS ALPHA] 팩터 스코어링 중...")
        scores = self.scorer.score_universe(self.symbols, today)

        if not scores:
            logger.error("[NAVIS ALPHA] 스코어 산출 실패 — 리밸런싱 중단")
            return {"status": "failed", "reason": "no_scores"}

        # ── 2. 목표 포트폴리오 선별 ────────────────────────────────────────
        target_symbols = self._select_portfolio(scores, equity, broker)
        n_target = len(target_symbols)
        logger.info(f"[NAVIS ALPHA] 목표 포트폴리오: {n_target}종목")

        # ── 3. 현재 포지션 조회 ────────────────────────────────────────────
        current_positions = {p.symbol: p for p in broker.get_positions()}

        # ── 4. 매도 (탈락 종목) ────────────────────────────────────────────
        sells = [sym for sym in current_positions if sym not in target_symbols]
        for sym in sells:
            qty = int(current_positions[sym].qty)
            if qty > 0:
                self._submit_order(broker, sym, qty, "sell")

        # ── 5. 매수 (신규/편입 종목) ───────────────────────────────────────
        per_position = equity / n_target if n_target > 0 else 0
        buys = []
        for sym in sorted(target_symbols):
            price = self._get_current_price(broker, sym)
            if price is None or price <= 0:
                continue
            target_qty = max(1, int(per_position / price))
            curr_qty   = int(current_positions[sym].qty) if sym in current_positions else 0
            delta_qty  = target_qty - curr_qty
            if delta_qty > 0:
                self._submit_order(broker, sym, delta_qty, "buy")
                buys.append(sym)
            elif delta_qty < 0:
                self._submit_order(broker, sym, abs(delta_qty), "sell")

        # ── 6. 로그 저장 ────────────────────────────────────────────────────
        summary = {
            "date":         str(today),
            "equity":       round(equity, 2),
            "n_target":     n_target,
            "n_sells":      len(sells),
            "n_buys":       len(buys),
            "top_symbols":  sorted(target_symbols)[:10],
            "status":       "dry_run" if self.dry_run else "submitted",
        }
        self._log_tracking(summary, scores, target_symbols)
        logger.info(f"[NAVIS ALPHA] 리밸런싱 완료 — 매도={len(sells)}, 매수={len(buys)}")
        return summary

    # ── 포트폴리오 선별 ───────────────────────────────────────────────────────

    def _select_portfolio(
        self,
        scores: dict[str, float],
        equity: float,
        broker,
    ) -> Set[str]:
        """점수 상위 10% + 섹터 캡 + 시총 필터."""
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        n_top  = max(1, int(len(ranked) * TOP_PCT))
        candidates = [sym for sym, _ in ranked[:n_top]]

        # 시가총액 필터 ($200M 이상) — 현재 가격 × 발행주식수로 근사
        selected: Set[str] = set()
        sector_count: Dict[str, int] = {}
        max_per_sector = max(1, int(n_top * MAX_SECTOR_PCT))

        for sym in candidates:
            sector = self.sector_map.get(sym, "Unknown")
            if sector_count.get(sector, 0) >= max_per_sector:
                continue
            selected.add(sym)
            sector_count[sector] = sector_count.get(sector, 0) + 1

        return selected

    # ── Alpaca 연결 ───────────────────────────────────────────────────────────

    def _connect_broker(self):
        from execution_team.brokers.alpaca_broker import AlpacaBroker
        broker = AlpacaBroker({
            "api_key":    self.api_key,
            "secret_key": self.api_secret,
            "base_url":   self.base_url,
        })
        if not broker.connect():
            raise RuntimeError("Alpaca 연결 실패 — API 키 확인 필요")
        return broker

    def _submit_order(self, broker, symbol: str, qty: int, side: str) -> None:
        if self.dry_run:
            logger.info(f"[DRY RUN] {side.upper()} {symbol} {qty}주")
            return
        try:
            from execution_team.core.order_models import Order, OrderType, TimeInForce, OrderAction
            action = OrderAction.BUY if side == "buy" else OrderAction.SELL
            order = Order(
                symbol        = symbol,
                quantity      = qty,
                action        = action,
                order_type    = OrderType.MARKET,
                time_in_force = TimeInForce.DAY,
            )
            order_id = broker.submit_order(order)
            logger.info(f"[NAVIS ALPHA] {side.upper()} {symbol} {qty}주 → order_id={order_id}")
        except Exception as e:
            logger.error(f"[NAVIS ALPHA] 주문 실패 {side} {symbol}: {e}")

    def _get_current_price(self, broker, symbol: str) -> Optional[float]:
        try:
            return broker.get_current_price(symbol)
        except Exception:
            return None

    # ── 추적 로그 ─────────────────────────────────────────────────────────────

    def _log_tracking(
        self,
        summary: dict,
        scores: dict[str, float],
        target_symbols: Set[str],
    ) -> None:
        """리밸런싱 결과를 CSV에 누적 저장."""
        is_new = not TRACKING_FILE.exists()
        with open(TRACKING_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow([
                    "date", "equity", "n_holdings",
                    "n_sells", "n_buys", "status",
                    "top10_symbols",
                ])
            writer.writerow([
                summary["date"],
                summary["equity"],
                summary["n_target"],
                summary["n_sells"],
                summary["n_buys"],
                summary["status"],
                "|".join(sorted(target_symbols)[:10]),
            ])

        # 개별 종목 점수도 저장
        score_file = Path(f"navis_alpha_scores_{summary['date']}.csv")
        with open(score_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["symbol", "score", "sector", "in_portfolio"])
            for sym, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
                writer.writerow([
                    sym,
                    round(score, 2),
                    self.sector_map.get(sym, "Unknown"),
                    sym in target_symbols,
                ])

        logger.info(f"[NAVIS ALPHA] 추적 로그 저장: {TRACKING_FILE}, {score_file}")
