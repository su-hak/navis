"""
알림 / 리포트 팀 - TelegramNotifier (독립형)
백엔드 패키지에 의존하지 않고 독립 실행 가능
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

# 한국 표준시 (KST = UTC+9)
_KST = timezone(timedelta(hours=9))


def _now_kst() -> datetime:
    """현재 한국 시간(KST) 반환"""
    return datetime.now(_KST)

import httpx

from .config import config

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """텔레그램 봇 알림 발송 (notification_team 독립형)"""

    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.warning("텔레그램 미설정 - Mock 모드로 동작")

    async def send(self, message: str) -> bool:
        """메시지 발송"""
        if not self.enabled:
            logger.info(f"[Telegram Mock] {message}")
            return True

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"텔레그램 발송 실패: {e}")
            return False

    # ── 거래 알림 ───────────────────────────────────────────

    async def notify_buy(
        self,
        symbol: str,
        filled_price: float,
        quantity: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reason: Optional[str] = None,
    ):
        """매수 체결 알림"""
        amount = filled_price * quantity
        lines = [
            "🚀 *매수 체결*",
            f"종목: `{symbol}`",
            f"체결가: ${filled_price:,.2f}",
            f"수량: {quantity}주",
            f"투자금: ${amount:,.2f}",
        ]
        if stop_loss:
            lines.append(f"손절가: ${stop_loss:,.2f}")
        if take_profit:
            lines.append(f"익절가: ${take_profit:,.2f}")
        if reason:
            lines.append(f"사유: {reason}")
        lines.append(f"시각: {_now_kst().strftime('%H:%M:%S')}")
        await self.send("\n".join(lines))

    async def notify_sell(
        self,
        symbol: str,
        filled_price: float,
        quantity: int,
        pnl: float,
        pnl_pct: float,
        sell_type: str = "SELL",
    ):
        """매도 체결 알림 (일반/손절/익절 구분)"""
        emoji = {"STOP_LOSS": "🛑", "TAKE_PROFIT": "✅", "SELL": "📤"}.get(sell_type, "📤")
        label = {"STOP_LOSS": "손절", "TAKE_PROFIT": "익절", "SELL": "매도"}.get(sell_type, "매도")
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        msg = (
            f"{emoji} *{label} 체결*\n"
            f"종목: `{symbol}`\n"
            f"체결가: ${filled_price:,.2f}\n"
            f"수량: {quantity}주\n"
            f"손익: {pnl_emoji} ${pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
            f"시각: {_now_kst().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_risk_halt(self, reason: str, daily_pnl: float):
        """리스크 한계 도달 → 거래 중단 알림"""
        msg = (
            "⚠️ *거래 중단 - 리스크 한계*\n"
            f"사유: {reason}\n"
            f"일일 손익: ${daily_pnl:+,.2f}\n"
            f"시각: {_now_kst().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    # ── 리포트 알림 ─────────────────────────────────────────

    async def notify_daily_report(self, report: Dict[str, Any]):
        """일일 리포트 전송"""
        trade_date = report.get("trade_date", _now_kst().strftime("%Y-%m-%d"))
        # sell_trades: 매도 횟수 (winning+losing의 합계가 없을 때 표시용)
        sell_trades = report.get("sell_trades", report.get("total_trades", 0))
        winning = report.get("winning_trades", 0)
        losing = report.get("losing_trades", 0)
        realized_pnl = report.get("realized_pnl", 0.0)
        ending_equity = report.get("ending_equity", 0.0)
        source = report.get("source", "")

        closed = winning + losing  # pnl이 기록된 완결 거래
        win_rate = (winning / closed * 100) if closed > 0 else 0
        pnl_emoji = "📈" if realized_pnl >= 0 else "📉"

        source_label = {"alpaca": " (Alpaca)", "db": " (DB)", "none": " (데이터 없음)"}.get(source, "")

        msg = (
            f"📊 *일일 리포트 - {trade_date}*{source_label}\n"
            f"총 매도: {sell_trades}회\n"
            f"승: {winning} / 패: {losing} (승률 {win_rate:.0f}%)\n"
            f"실현 손익: {pnl_emoji} ${realized_pnl:+,.2f}\n"
            f"잔고: ${ending_equity:,.2f}"
        )
        await self.send(msg)

    async def notify_weekly_report(self, weekly_data: List[Dict[str, Any]]):
        """주간 리포트"""
        if not weekly_data:
            await self.send("📅 *주간 리포트*\n데이터 없음")
            return

        total_pnl = sum(float(d.get("realized_pnl") or 0) for d in weekly_data)
        total_trades = sum(int(d.get("total_trades") or 0) for d in weekly_data)
        total_wins = sum(int(d.get("winning_trades") or 0) for d in weekly_data)
        total_losses = sum(int(d.get("losing_trades") or 0) for d in weekly_data)
        win_rate = (
            (total_wins / (total_wins + total_losses) * 100)
            if (total_wins + total_losses) > 0 else 0
        )
        pnl_emoji = "📈" if total_pnl >= 0 else "📉"

        lines = [
            "📅 *주간 리포트*",
            f"기간: {len(weekly_data)}거래일",
            f"총 거래: {total_trades}회",
            f"승/패: {total_wins}/{total_losses} (승률 {win_rate:.0f}%)",
            f"실현 손익: {pnl_emoji} ${total_pnl:+,.2f}",
            "",
            "*일별 손익*",
        ]
        for d in reversed(weekly_data):
            date_str = str(d.get("trade_date", ""))[:10]
            pnl = float(d.get("realized_pnl") or 0)
            emoji = "📈" if pnl >= 0 else "📉"
            lines.append(f"  {date_str}: {emoji} ${pnl:+,.2f}")

        await self.send("\n".join(lines))

    async def notify_portfolio_status(
        self,
        equity: float,
        cash: float,
        positions: List[Dict],
        daily_pnl: float,
    ):
        """장중 포지션 현황 알림"""
        pos_count = len(positions)
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"

        # 총 투자금(포지션 시장가 합산) 대비 손익 %
        total_market_value = sum(float(p.get("market_value", 0)) for p in positions)
        invested = total_market_value - daily_pnl  # 원가 추정
        daily_pnl_pct = (daily_pnl / invested * 100) if invested != 0 else 0.0

        lines = [
            "📋 *포지션 현황*",
            f"총 자산: ${equity:,.2f}",
            f"현금: ${cash:,.2f}",
            f"보유 종목: {pos_count}개",
            f"일중 손익: {pnl_emoji} ${daily_pnl:+,.2f} ({daily_pnl_pct:+.2f}%)",
        ]

        if positions:
            lines.append("")
            for pos in positions[:5]:
                symbol = pos.get("symbol", "?")
                unreal = float(pos.get("unrealized_pl", 0))
                unreal_pct = float(pos.get("unrealized_plpc", 0)) * 100.0
                unreal_emoji = "📈" if unreal >= 0 else "📉"
                lines.append(f"  `{symbol}` {unreal_emoji} ${unreal:+,.2f} ({unreal_pct:+.2f}%)")
            if pos_count > 5:
                lines.append(f"  ... 외 {pos_count - 5}개")

        lines.append(f"시각: {_now_kst().strftime('%H:%M:%S')}")
        await self.send("\n".join(lines))

    # ── 시스템 알림 ─────────────────────────────────────────

    async def notify_system_start(
        self,
        mode: str = "시뮬레이션",
        watchlist_size: int = 0,
        portfolio_count: int = -1,
    ):
        """시스템 시작 알림"""
        lines = [
            f"🤖 *자동매매 시스템 시작*",
            f"모드: {mode}",
        ]
        if portfolio_count >= 0:
            lines.append(f"보유 포지션: {portfolio_count}개")
        if watchlist_size > 0:
            lines.append(f"백엔드 워치리스트: {watchlist_size}개")
        lines.append(f"시각: {_now_kst().strftime('%Y-%m-%d %H:%M:%S')}")
        await self.send("\n".join(lines))

    async def notify_error(self, context: str, error: str):
        """오류 알림"""
        msg = (
            f"❌ *시스템 오류*\n"
            f"위치: {context}\n"
            f"오류: {error}\n"
            f"시각: {_now_kst().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_test(self) -> bool:
        """테스트 메시지 발송"""
        msg = (
            f"✅ *텔레그램 알림 테스트*\n"
            f"Navis 자동매매 시스템 알림이 정상 작동합니다.\n"
            f"시각: {_now_kst().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return await self.send(msg)


# 전역 인스턴스
notifier = TelegramNotifier()
