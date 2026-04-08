"""
알림 / 리포트 팀 - TelegramNotifier (독립형)
백엔드 패키지에 의존하지 않고 독립 실행 가능
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

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
        lines.append(f"시각: {datetime.now().strftime('%H:%M:%S')}")
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
            f"시각: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_risk_halt(self, reason: str, daily_pnl: float):
        """리스크 한계 도달 → 거래 중단 알림"""
        msg = (
            "⚠️ *거래 중단 - 리스크 한계*\n"
            f"사유: {reason}\n"
            f"일일 손익: ${daily_pnl:+,.2f}\n"
            f"시각: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    # ── 리포트 알림 ─────────────────────────────────────────

    async def notify_daily_report(self, report: Dict[str, Any]):
        """일일 리포트 전송"""
        trade_date = report.get("trade_date", datetime.now().strftime("%Y-%m-%d"))
        total_trades = report.get("total_trades", 0)
        winning = report.get("winning_trades", 0)
        losing = report.get("losing_trades", 0)
        realized_pnl = report.get("realized_pnl", 0.0)
        ending_equity = report.get("ending_equity", 0.0)

        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
        pnl_emoji = "📈" if realized_pnl >= 0 else "📉"

        msg = (
            f"📊 *일일 리포트 - {trade_date}*\n"
            f"총 거래: {total_trades}회\n"
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

        lines = [
            "📋 *포지션 현황*",
            f"총 자산: ${equity:,.2f}",
            f"현금: ${cash:,.2f}",
            f"보유 종목: {pos_count}개",
            f"일중 손익: {pnl_emoji} ${daily_pnl:+,.2f}",
        ]

        if positions:
            lines.append("")
            for pos in positions[:5]:
                symbol = pos.get("symbol", "?")
                unreal = pos.get("unrealized_pl", 0)
                unreal_emoji = "📈" if float(unreal) >= 0 else "📉"
                lines.append(f"  `{symbol}` {unreal_emoji} ${float(unreal):+,.2f}")
            if pos_count > 5:
                lines.append(f"  ... 외 {pos_count - 5}개")

        lines.append(f"시각: {datetime.now().strftime('%H:%M:%S')}")
        await self.send("\n".join(lines))

    # ── 시스템 알림 ─────────────────────────────────────────

    async def notify_system_start(self, mode: str = "시뮬레이션", watchlist_size: int = 0):
        """시스템 시작 알림"""
        msg = (
            f"🤖 *자동매매 시스템 시작*\n"
            f"모드: {mode}\n"
            f"종목 수: {watchlist_size}개\n"
            f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_error(self, context: str, error: str):
        """오류 알림"""
        msg = (
            f"❌ *시스템 오류*\n"
            f"위치: {context}\n"
            f"오류: {error}\n"
            f"시각: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_test(self) -> bool:
        """테스트 메시지 발송"""
        msg = (
            f"✅ *텔레그램 알림 테스트*\n"
            f"Navis 자동매매 시스템 알림이 정상 작동합니다.\n"
            f"시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return await self.send(msg)


# 전역 인스턴스
notifier = TelegramNotifier()
