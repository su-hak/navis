"""
매매 시그널 생성 로직

점수와 조건을 기반으로 매수/매도/청산 시그널을 생성합니다.
"""

import pandas as pd
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from ..scoring.score_calculator import ScoreCalculator, ScoreResult


class SignalType(Enum):
    """시그널 타입"""
    BUY = "BUY"  # 매수
    SELL = "SELL"  # 매도
    HOLD = "HOLD"  # 보유
    STOP_LOSS = "STOP_LOSS"  # 손절
    TAKE_PROFIT = "TAKE_PROFIT"  # 익절


@dataclass
class TradingConditions:
    """매매 조건 설정"""
    # 매수 조건
    buy_score_threshold: float = 75.0  # 최소 매수 점수
    buy_volume_ratio_min: float = 1.5  # 최소 거래량 비율
    buy_trend_strength_min: float = 60.0  # 최소 추세 강도

    # 매도 조건
    sell_score_threshold: float = 30.0  # 매도 점수 (이하 시 매도)
    score_drop_threshold: float = 20.0  # 점수 급락 기준 (N점 이상 하락)

    # 손익 조건
    take_profit_pct: float = 0.10  # 목표 수익률 (10%)
    stop_loss_pct: float = -0.02  # 손절 기준 (-2%)

    # 추가 조건
    require_uptrend: bool = True  # 상승 추세 필수
    min_holding_minutes: int = 60  # 최소 보유 시간 (분)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'buy_score_threshold': self.buy_score_threshold,
            'buy_volume_ratio_min': self.buy_volume_ratio_min,
            'buy_trend_strength_min': self.buy_trend_strength_min,
            'sell_score_threshold': self.sell_score_threshold,
            'score_drop_threshold': self.score_drop_threshold,
            'take_profit_pct': self.take_profit_pct,
            'stop_loss_pct': self.stop_loss_pct,
            'require_uptrend': self.require_uptrend,
            'min_holding_minutes': self.min_holding_minutes,
        }


@dataclass
class Signal:
    """매매 시그널"""
    symbol: str
    signal_type: SignalType
    score: float
    confidence: float  # 신뢰도 (0~1)
    entry_price: float  # 진입 가격
    target_price: Optional[float] = None  # 목표 가격
    stop_loss_price: Optional[float] = None  # 손절 가격
    reasons: List[str] = field(default_factory=list)  # 시그널 근거
    metadata: Dict[str, Any] = field(default_factory=dict)  # 추가 정보
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'score': self.score,
            'confidence': self.confidence,
            'entry_price': self.entry_price,
            'target_price': self.target_price,
            'stop_loss_price': self.stop_loss_price,
            'reasons': self.reasons,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
        }


class SignalGenerator:
    """
    시그널 생성 클래스

    점수와 조건을 기반으로 매수/매도/청산 시그널을 생성합니다.
    """

    def __init__(self,
                 score_calculator: Optional[ScoreCalculator] = None,
                 conditions: Optional[TradingConditions] = None):
        """
        Args:
            score_calculator: 점수 계산기 (None이면 새로 생성)
            conditions: 매매 조건 (None이면 기본값 사용)
        """
        self.score_calculator = score_calculator or ScoreCalculator()
        self.conditions = conditions or TradingConditions()

    def check_buy_conditions(self, score_result: ScoreResult, current_price: float) -> tuple[bool, List[str], float]:
        """
        매수 조건 확인

        Args:
            score_result: 점수 계산 결과
            current_price: 현재 가격

        Returns:
            (매수 가능 여부, 사유 리스트, 신뢰도)
        """
        reasons = []
        confidence_factors = []

        # 1. 점수 체크
        if score_result.total_score >= self.conditions.buy_score_threshold:
            reasons.append(f"✅ 높은 점수 ({score_result.total_score:.1f} >= {self.conditions.buy_score_threshold})")
            confidence_factors.append(min(1.0, score_result.total_score / 100))
        else:
            reasons.append(f"❌ 점수 부족 ({score_result.total_score:.1f} < {self.conditions.buy_score_threshold})")
            return False, reasons, 0.0

        # 2. 거래량 체크
        volume_ratio = score_result.breakdown['volume']['volume_ratio']
        if volume_ratio >= self.conditions.buy_volume_ratio_min:
            reasons.append(f"✅ 거래량 증가 ({volume_ratio:.2f}x >= {self.conditions.buy_volume_ratio_min}x)")
            confidence_factors.append(min(1.0, volume_ratio / 3.0))
        else:
            reasons.append(f"❌ 거래량 부족 ({volume_ratio:.2f}x < {self.conditions.buy_volume_ratio_min}x)")
            return False, reasons, 0.0

        # 3. 추세 강도 체크
        trend_strength = score_result.breakdown['trend']['trend_strength']
        if trend_strength >= self.conditions.buy_trend_strength_min:
            reasons.append(f"✅ 강한 추세 ({trend_strength:.1f} >= {self.conditions.buy_trend_strength_min})")
            confidence_factors.append(trend_strength / 100)
        else:
            if self.conditions.require_uptrend:
                reasons.append(f"❌ 추세 강도 부족 ({trend_strength:.1f} < {self.conditions.buy_trend_strength_min})")
                return False, reasons, 0.0
            else:
                reasons.append(f"⚠️ 추세 강도 약함 ({trend_strength:.1f} < {self.conditions.buy_trend_strength_min})")
                confidence_factors.append(0.5)

        # 4. 기술적 지표 추가 체크
        indicators = score_result.breakdown['indicators']

        # RSI 체크 (과매수 아님)
        rsi = indicators['rsi']
        if rsi < 70:
            reasons.append(f"✅ RSI 적정 ({rsi:.1f} < 70)")
            confidence_factors.append(1.0 - (rsi / 100))
        else:
            reasons.append(f"⚠️ RSI 과매수 ({rsi:.1f} >= 70)")
            confidence_factors.append(0.3)

        # MACD 체크 (골든크로스)
        macd_histogram = indicators['macd_histogram']
        if macd_histogram > 0:
            reasons.append(f"✅ MACD 골든크로스 ({macd_histogram:.4f} > 0)")
            confidence_factors.append(1.0)
        else:
            reasons.append(f"⚠️ MACD 데드크로스 ({macd_histogram:.4f} <= 0)")
            confidence_factors.append(0.5)

        # 신뢰도 계산 (평균)
        confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.0

        return True, reasons, confidence

    def check_sell_conditions(self,
                               score_result: ScoreResult,
                               current_price: float,
                               entry_price: float,
                               previous_score: Optional[float] = None) -> tuple[bool, SignalType, List[str], float]:
        """
        매도 조건 확인

        Args:
            score_result: 현재 점수 계산 결과
            current_price: 현재 가격
            entry_price: 진입 가격
            previous_score: 이전 점수

        Returns:
            (매도 필요 여부, 시그널 타입, 사유 리스트, 신뢰도)
        """
        reasons = []
        confidence = 0.8

        # 수익률 계산
        profit_pct = (current_price - entry_price) / entry_price

        # 1. 목표 수익 달성
        if profit_pct >= self.conditions.take_profit_pct:
            reasons.append(f"🎯 목표 수익 도달 ({profit_pct:.2%} >= {self.conditions.take_profit_pct:.2%})")
            return True, SignalType.TAKE_PROFIT, reasons, 1.0

        # 2. 손절 조건
        if profit_pct <= self.conditions.stop_loss_pct:
            reasons.append(f"🛑 손절 기준 도달 ({profit_pct:.2%} <= {self.conditions.stop_loss_pct:.2%})")
            return True, SignalType.STOP_LOSS, reasons, 1.0

        # 3. 점수 급락
        if previous_score is not None:
            score_drop = previous_score - score_result.total_score
            if score_drop >= self.conditions.score_drop_threshold:
                reasons.append(f"⚠️ 점수 급락 ({score_drop:.1f}점 하락)")
                return True, SignalType.SELL, reasons, 0.9

        # 4. 낮은 점수
        if score_result.total_score < self.conditions.sell_score_threshold:
            reasons.append(f"📉 점수 하락 ({score_result.total_score:.1f} < {self.conditions.sell_score_threshold})")
            return True, SignalType.SELL, reasons, 0.8

        # 5. 기술적 지표 악화
        indicators = score_result.breakdown['indicators']

        # RSI 과매수 확인
        rsi = indicators['rsi']
        if rsi > 80:
            reasons.append(f"⚠️ RSI 극단 과매수 ({rsi:.1f} > 80)")
            return True, SignalType.SELL, reasons, 0.7

        # MACD 데드크로스 확인
        macd_histogram = indicators['macd_histogram']
        if macd_histogram < -0.5:
            reasons.append(f"⚠️ MACD 강한 데드크로스 ({macd_histogram:.4f} < -0.5)")
            return True, SignalType.SELL, reasons, 0.7

        # 매도 조건 없음
        return False, SignalType.HOLD, ["✅ 보유 유지"], 0.0

    def generate_buy_signal(self,
                            symbol: str,
                            df: pd.DataFrame,
                            news_sentiment: Optional[float] = None,
                            news_count: int = 0,
                            revenue_growth: Optional[float] = None,
                            eps_growth: Optional[float] = None,
                            institutional_ownership_change: Optional[float] = None) -> Optional[Signal]:
        """
        매수 시그널 생성

        Args:
            symbol: 종목 심볼
            df: OHLCV 데이터
            news_sentiment: 뉴스 감성
            news_count: 뉴스 개수
            revenue_growth: 매출 성장률
            eps_growth: EPS 성장률
            institutional_ownership_change: 기관 보유 변화율

        Returns:
            Signal 객체 (조건 미충족 시 None)
        """
        # 점수 계산
        score_result = self.score_calculator.score_stock(
            symbol=symbol,
            df=df,
            news_sentiment=news_sentiment,
            news_count=news_count,
            revenue_growth=revenue_growth,
            eps_growth=eps_growth,
            institutional_ownership_change=institutional_ownership_change,
        )

        current_price = float(df['close'].iloc[-1])

        # 매수 조건 확인
        can_buy, reasons, confidence = self.check_buy_conditions(score_result, current_price)

        if not can_buy:
            return None

        # 목표가 및 손절가 계산
        target_price = current_price * (1 + self.conditions.take_profit_pct)
        stop_loss_price = current_price * (1 + self.conditions.stop_loss_pct)

        return Signal(
            symbol=symbol,
            signal_type=SignalType.BUY,
            score=score_result.total_score,
            confidence=confidence,
            entry_price=current_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            reasons=reasons,
            metadata={
                'score_breakdown': score_result.to_dict(),
                'conditions': self.conditions.to_dict(),
            }
        )

    def generate_sell_signal(self,
                             symbol: str,
                             df: pd.DataFrame,
                             entry_price: float,
                             previous_score: Optional[float] = None,
                             news_sentiment: Optional[float] = None,
                             news_count: int = 0) -> Optional[Signal]:
        """
        매도 시그널 생성

        Args:
            symbol: 종목 심볼
            df: OHLCV 데이터
            entry_price: 진입 가격
            previous_score: 이전 점수
            news_sentiment: 뉴스 감성
            news_count: 뉴스 개수

        Returns:
            Signal 객체 (조건 미충족 시 None)
        """
        # 점수 계산
        score_result = self.score_calculator.score_stock(
            symbol=symbol,
            df=df,
            news_sentiment=news_sentiment,
            news_count=news_count,
        )

        current_price = float(df['close'].iloc[-1])

        # 매도 조건 확인
        should_sell, signal_type, reasons, confidence = self.check_sell_conditions(
            score_result, current_price, entry_price, previous_score
        )

        if not should_sell:
            return None

        profit_pct = (current_price - entry_price) / entry_price

        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            score=score_result.total_score,
            confidence=confidence,
            entry_price=entry_price,
            target_price=None,
            stop_loss_price=None,
            reasons=reasons,
            metadata={
                'current_price': current_price,
                'profit_pct': profit_pct,
                'score_breakdown': score_result.to_dict(),
                'previous_score': previous_score,
            }
        )

    def generate_signals_batch(self,
                               stock_data: Dict[str, pd.DataFrame],
                               **kwargs) -> List[Signal]:
        """
        여러 종목의 매수 시그널을 일괄 생성

        Args:
            stock_data: {심볼: OHLCV 데이터} 딕셔너리
            **kwargs: generate_buy_signal에 전달할 추가 인자

        Returns:
            Signal 리스트
        """
        signals = []

        for symbol, df in stock_data.items():
            signal = self.generate_buy_signal(symbol, df, **kwargs)
            if signal:
                signals.append(signal)

        # 점수 및 신뢰도 기준으로 정렬
        signals.sort(key=lambda s: (s.score, s.confidence), reverse=True)

        return signals
