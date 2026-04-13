"""
NAVIS 성과 추적기 - AI 에이전트의 in-context 학습을 위한 피드백 루프

작동 원리:
- 매수 추천 시 recommendation을 기록
- 매도(손절/익절) 시 outcome을 기록
- NativeTradingAgent가 분석 시 최근 성과를 시스템 프롬프트에 주입
- 이를 통해 Claude가 과거 패턴을 참고하여 더 나은 판단 가능
"""
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# 성과 데이터 저장 경로
PERFORMANCE_FILE = Path(os.getenv("PERFORMANCE_DATA_PATH", "/tmp/navis_performance.json"))


class PerformanceTracker:
    """거래 성과 추적 및 AI 피드백 컨텍스트 생성"""

    def __init__(self, data_path: Path = PERFORMANCE_FILE):
        self.data_path = data_path
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """파일에서 성과 데이터 로드"""
        try:
            if self.data_path.exists():
                with open(self.data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"성과 데이터 로드 실패: {e}")
        return {
            "recommendations": [],   # AI 추천 기록
            "outcomes": [],           # 실제 거래 결과
            "daily_stats": {},        # 날짜별 통계
            "symbol_stats": {},       # 종목별 통계
            "last_updated": None,
        }

    def _save(self):
        """성과 데이터 파일 저장"""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"성과 데이터 저장 실패: {e}")

    def record_recommendation(
        self,
        symbol: str,
        recommendation: str,   # BUY / SELL / HOLD / AVOID
        sentiment_score: float,
        analysis_summary: str,
        market_regime: str = "BULL",
    ):
        """AI 추천 기록 (매수 신호 발생 시 호출)"""
        record = {
            "ts": datetime.now().isoformat(),
            "symbol": symbol,
            "recommendation": recommendation,
            "sentiment_score": sentiment_score,
            "analysis_summary": analysis_summary[:200],
            "market_regime": market_regime,
            "outcome": None,   # 나중에 record_outcome()으로 채워짐
        }
        self._data["recommendations"].append(record)
        # 최근 500개만 유지
        self._data["recommendations"] = self._data["recommendations"][-500:]
        self._data["last_updated"] = datetime.now().isoformat()
        self._save()

    def record_outcome(
        self,
        symbol: str,
        action: str,        # STOP_LOSS / TAKE_PROFIT / SELL
        pnl: float,
        pnl_pct: float,
        hold_minutes: Optional[float] = None,
    ):
        """거래 결과 기록 (매도 완료 시 호출)"""
        outcome = {
            "ts": datetime.now().isoformat(),
            "symbol": symbol,
            "action": action,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "hold_minutes": hold_minutes,
            "is_win": pnl > 0,
        }
        self._data["outcomes"].append(outcome)
        self._data["outcomes"] = self._data["outcomes"][-500:]

        # 종목별 통계 업데이트
        stats = self._data["symbol_stats"].setdefault(symbol, {
            "trades": 0, "wins": 0, "total_pnl": 0.0,
        })
        stats["trades"] += 1
        stats["total_pnl"] += pnl
        if pnl > 0:
            stats["wins"] += 1

        # 날짜별 통계 업데이트
        today = datetime.now().strftime("%Y-%m-%d")
        daily = self._data["daily_stats"].setdefault(today, {
            "trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0,
        })
        daily["trades"] += 1
        daily["total_pnl"] += pnl
        if pnl > 0:
            daily["wins"] += 1
        else:
            daily["losses"] += 1

        # 최근 추천 중 동일 종목의 outcome 연결
        for rec in reversed(self._data["recommendations"]):
            if rec["symbol"] == symbol and rec["outcome"] is None:
                rec["outcome"] = action
                break

        self._data["last_updated"] = datetime.now().isoformat()
        self._save()

    def get_performance_context(self, lookback_days: int = 7) -> str:
        """
        AI 에이전트 시스템 프롬프트에 주입할 성과 컨텍스트 생성

        Returns:
            최근 성과를 요약한 텍스트 (시스템 프롬프트에 추가됨)
        """
        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent_outcomes = [
            o for o in self._data["outcomes"]
            if datetime.fromisoformat(o["ts"]) > cutoff
        ]

        if not recent_outcomes:
            return ""

        total = len(recent_outcomes)
        wins = sum(1 for o in recent_outcomes if o["is_win"])
        total_pnl = sum(o["pnl"] for o in recent_outcomes)
        win_rate = (wins / total * 100) if total > 0 else 0

        # 수익/손실 상위 종목
        by_symbol: Dict[str, Dict] = {}
        for o in recent_outcomes:
            s = o["symbol"]
            b = by_symbol.setdefault(s, {"pnl": 0.0, "count": 0})
            b["pnl"] += o["pnl"]
            b["count"] += 1

        best = sorted(by_symbol.items(), key=lambda x: x[1]["pnl"], reverse=True)
        top_winners = [f"{s}(${v['pnl']:+.0f})" for s, v in best[:3] if v["pnl"] > 0]
        top_losers = [f"{s}(${v['pnl']:+.0f})" for s, v in best[-3:] if v["pnl"] < 0]

        # STOP_LOSS vs TAKE_PROFIT 비율
        stop_losses = sum(1 for o in recent_outcomes if o["action"] == "STOP_LOSS")
        take_profits = sum(1 for o in recent_outcomes if o["action"] == "TAKE_PROFIT")

        lines = [
            f"\n## NAVIS 최근 {lookback_days}일 실전 성과 (자기 학습 컨텍스트)",
            f"- 총 거래: {total}회 | 승: {wins} / 패: {total - wins} | 승률: {win_rate:.0f}%",
            f"- 실현 손익: ${total_pnl:+,.2f}",
            f"- 손절: {stop_losses}회 | 익절: {take_profits}회",
        ]
        if top_winners:
            lines.append(f"- 수익 상위: {', '.join(top_winners)}")
        if top_losers:
            lines.append(f"- 손실 종목: {', '.join(top_losers)}")

        # 패턴 인사이트
        if stop_losses > take_profits * 2:
            lines.append("⚠️ 손절이 익절보다 2배 이상 많음 → 매수 진입 기준을 더 엄격히 적용할 것")
        if win_rate < 40:
            lines.append("⚠️ 승률 40% 미만 → 뉴스 부정 신호에 더 민감하게 반응할 것")
        if win_rate > 65:
            lines.append("✅ 승률 65% 이상 → 현재 전략 유효, 포지션 크기 최적화 고려")

        lines.append("위 성과 데이터를 참고하여 이번 분석의 판단 기준을 조정하세요.")
        return "\n".join(lines)

    def get_symbol_history(self, symbol: str) -> str:
        """특정 종목의 과거 거래 이력 요약"""
        stats = self._data["symbol_stats"].get(symbol)
        if not stats or stats["trades"] == 0:
            return ""
        win_rate = (stats["wins"] / stats["trades"] * 100) if stats["trades"] > 0 else 0
        return (
            f"\n## {symbol} 과거 이력\n"
            f"- 총 {stats['trades']}회 거래 | 승률 {win_rate:.0f}% | "
            f"누적 손익 ${stats['total_pnl']:+,.2f}"
        )

    @property
    def today_pnl(self) -> float:
        today = datetime.now().strftime("%Y-%m-%d")
        return self._data["daily_stats"].get(today, {}).get("total_pnl", 0.0)

    @property
    def today_win_rate(self) -> float:
        today = datetime.now().strftime("%Y-%m-%d")
        d = self._data["daily_stats"].get(today, {})
        total = d.get("trades", 0)
        wins = d.get("wins", 0)
        return (wins / total * 100) if total > 0 else 0.0


# 전역 싱글턴
performance_tracker = PerformanceTracker()
