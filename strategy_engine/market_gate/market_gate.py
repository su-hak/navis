"""
Market Gate - VIX/SPY 하드 게이트 (IMP-01)

아래 조건 중 하나라도 충족 시 신규 진입 전면 금지:
  - VIX > 25
  - SPY < 200일 이동평균
  - SPY 당일 -2% 이하 하락
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

MARKET_GATE_CONDITIONS = {
    "vix_threshold": 25.0,      # VIX > 25: 전략 OFF
    "spy_below_ma200": True,    # SPY < 200일 이동평균: 전략 OFF
    "spy_daily_drop": -0.02,    # SPY 당일 -2% 이하: 전략 OFF
}


@dataclass
class MarketGateResult:
    """게이트 체크 결과"""
    allowed: bool
    reason: str
    vix: Optional[float] = None
    spy_price: Optional[float] = None
    spy_ma200: Optional[float] = None
    spy_daily_change_pct: Optional[float] = None


class MarketGate:
    """
    VIX/SPY 하드 게이트

    신규 진입 전에 반드시 check() 를 통과해야 합니다.
    False 반환 시 신규 진입 전면 금지.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        vix_threshold: float = MARKET_GATE_CONDITIONS["vix_threshold"],
        spy_daily_drop: float = MARKET_GATE_CONDITIONS["spy_daily_drop"],
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.vix_threshold = vix_threshold
        self.spy_daily_drop = spy_daily_drop

    def _fetch_spy_data(self):
        """Alpaca로 SPY 최근 210일 일봉 조회 (200일 MA 계산용, 최대 3회 재시도)"""
        import time
        from alpaca.data import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from datetime import datetime, timedelta

        client = StockHistoricalDataClient(self.api_key, self.api_secret)
        end = datetime.utcnow()
        start = end - timedelta(days=300)

        req = StockBarsRequest(
            symbol_or_symbols=["SPY"],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed="iex",
        )

        for attempt in range(3):
            try:
                bars = client.get_stock_bars(req)
                spy_bars = bars["SPY"]
                closes = [float(b.close) for b in spy_bars]
                return closes
            except Exception as e:
                wait = 2 ** attempt
                if attempt < 2:
                    logger.warning(f"SPY 데이터 조회 실패 (재시도 {attempt+1}/3, {wait}s 후): {e}")
                    time.sleep(wait)
                else:
                    logger.error(f"SPY 데이터 조회 최종 실패 (3회 시도): {e}")
        return None

    def _fetch_vix(self) -> Optional[float]:
        """
        VIX 지수 조회 - yfinance 또는 ^VIX 심볼 사용.
        Alpaca는 VIX를 직접 지원하지 않으므로 yfinance 사용.
        yfinance 없으면 None 반환(게이트 통과).
        """
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="2d")
            if hist.empty:
                return None
            return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"VIX 조회 실패 (yfinance 없거나 오류): {e}")
            return None

    def check(self) -> MarketGateResult:
        """
        시장 게이트 체크

        Returns:
            MarketGateResult.allowed=False 이면 신규 진입 금지
        """
        spy_closes = self._fetch_spy_data()
        vix = self._fetch_vix()

        if spy_closes is None or len(spy_closes) < 201:
            # SUB-01: 데이터 부족 시 안전하게 진입 차단 (잘못된 MA200으로 판단하는 것보다 안전)
            logger.warning("SPY 데이터 부족 (200봉 미만) — MA200 계산 불가, 안전 모드로 진입 차단")
            return MarketGateResult(allowed=False, reason="SPY 데이터 부족 — MA200 계산 불가, 진입 차단")

        spy_price = spy_closes[-1]
        spy_prev = spy_closes[-2]
        spy_ma200 = sum(spy_closes[-200:]) / 200
        spy_daily_chg = (spy_price - spy_prev) / spy_prev

        # SUB-01: MA200 이상값 방어
        import math
        if spy_ma200 <= 0 or math.isnan(spy_ma200):
            logger.warning(f"SPY MA200 이상값({spy_ma200}) — 진입 차단")
            return MarketGateResult(allowed=False, reason=f"SPY MA200 이상값 — 진입 차단")

        # ── VIX 체크 ──────────────────────────────────
        if vix is not None and vix > self.vix_threshold:
            msg = f"VIX={vix:.1f} > {self.vix_threshold} → 신규 진입 금지"
            logger.warning(f"[MarketGate] {msg}")
            return MarketGateResult(
                allowed=False, reason=msg,
                vix=vix, spy_price=spy_price, spy_ma200=spy_ma200,
                spy_daily_change_pct=spy_daily_chg * 100,
            )

        # ── SPY < MA200 체크 ──────────────────────────
        if spy_price < spy_ma200:
            msg = f"SPY({spy_price:.2f}) < MA200({spy_ma200:.2f}) → 신규 진입 금지"
            logger.warning(f"[MarketGate] {msg}")
            return MarketGateResult(
                allowed=False, reason=msg,
                vix=vix, spy_price=spy_price, spy_ma200=spy_ma200,
                spy_daily_change_pct=spy_daily_chg * 100,
            )

        # ── SPY 당일 낙폭 체크 ────────────────────────
        if spy_daily_chg <= self.spy_daily_drop:
            msg = (
                f"SPY 당일 {spy_daily_chg*100:.2f}% ≤ {self.spy_daily_drop*100:.0f}% "
                f"→ 신규 진입 금지"
            )
            logger.warning(f"[MarketGate] {msg}")
            return MarketGateResult(
                allowed=False, reason=msg,
                vix=vix, spy_price=spy_price, spy_ma200=spy_ma200,
                spy_daily_change_pct=spy_daily_chg * 100,
            )

        logger.info(
            f"[MarketGate] 통과 | VIX={vix if vix else 'N/A'} | "
            f"SPY={spy_price:.2f} MA200={spy_ma200:.2f} ({(spy_price/spy_ma200-1)*100:+.2f}%) | "
            f"당일변동={spy_daily_chg*100:+.2f}%"
        )
        return MarketGateResult(
            allowed=True,
            reason="시장 게이트 통과",
            vix=vix, spy_price=spy_price, spy_ma200=spy_ma200,
            spy_daily_change_pct=spy_daily_chg * 100,
        )
