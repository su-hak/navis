"""
개별 전략 구현

기획서 전략:
- Strategy A: 모멘텀
- Strategy B: 돌파
- Strategy C: 리버전 (평균회귀)
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """전략 베이스 클래스"""

    def __init__(self, name: str):
        self.name = name
        logger.info(f"전략 초기화: {name}")

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        """
        매매 신호 생성

        Args:
            data: 시장 데이터 (OHLCV)

        Returns:
            {
                'action': 'BUY' or 'SELL' or 'HOLD',
                'symbol': str,
                'confidence': float,
                'reason': str
            }
        """
        pass

    @abstractmethod
    def validate_signal(self, signal: Dict, market_data: Dict) -> bool:
        """
        신호 유효성 검증

        Args:
            signal: 생성된 신호
            market_data: 시장 데이터

        Returns:
            유효 여부
        """
        pass


class MomentumStrategy(BaseStrategy):
    """
    모멘텀 전략 (Strategy A)

    특징:
    - 상승 추세 종목 추종
    - 거래량 급증 + 가격 상승
    - RSI, MACD 등 모멘텀 지표 활용

    기획서: 40% 포트폴리오 비중
    """

    def __init__(self):
        super().__init__("Momentum Strategy")
        self.rsi_threshold = 60  # RSI > 60 (강세)
        self.volume_threshold = 2.0  # 평균 대비 2배 이상

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        """
        모멘텀 신호 생성

        조건:
        1. RSI > 60 (강세)
        2. 거래량 > 평균의 2배
        3. 가격 > 20일 이동평균
        """
        try:
            if data.empty or len(data) < 20:
                return None

            # 최근 데이터
            latest = data.iloc[-1]
            symbol = latest.get('symbol', 'Unknown')

            # RSI 계산 (간단 예시)
            rsi = self._calculate_rsi(data['close'])

            # 거래량 비율
            avg_volume = data['volume'].rolling(20).mean().iloc[-1]
            volume_ratio = latest['volume'] / avg_volume if avg_volume > 0 else 0

            # 이동평균
            ma_20 = data['close'].rolling(20).mean().iloc[-1]

            # 신호 판단
            if rsi > self.rsi_threshold and volume_ratio > self.volume_threshold and latest['close'] > ma_20:
                return {
                    'action': 'BUY',
                    'symbol': symbol,
                    'confidence': min(0.9, rsi / 100.0),
                    'reason': f'모멘텀 강세 (RSI: {rsi:.1f}, 거래량: {volume_ratio:.1f}배)',
                    'strategy': 'momentum'
                }

            return {'action': 'HOLD'}

        except Exception as e:
            logger.error(f"모멘텀 신호 생성 오류: {e}")
            return None

    def validate_signal(self, signal: Dict, market_data: Dict) -> bool:
        """신호 검증"""
        # 시장 상태 확인 (예: 변동성 체크)
        return signal.get('action') in ['BUY', 'SELL']

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI 계산 (간단 버전)"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            return float(rsi.iloc[-1])
        except:
            return 50.0  # 중립


class BreakoutStrategy(BaseStrategy):
    """
    돌파 전략 (Strategy B)

    특징:
    - 저항선 돌파 감지
    - 신고가/신저가 돌파
    - 밴드 (볼린저) 돌파

    기획서: 30% 포트폴리오 비중
    """

    def __init__(self):
        super().__init__("Breakout Strategy")
        self.lookback_period = 20  # 20일 최고가/최저가
        self.breakout_threshold = 0.02  # 2% 이상 돌파

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        """
        돌파 신호 생성

        조건:
        1. 현재가 > 20일 최고가 (상향 돌파)
        2. 거래량 증가
        3. 강한 모멘텀
        """
        try:
            if data.empty or len(data) < self.lookback_period:
                return None

            latest = data.iloc[-1]
            symbol = latest.get('symbol', 'Unknown')

            # 20일 최고가/최저가
            high_20 = data['high'].rolling(self.lookback_period).max().iloc[-2]  # 직전까지
            current_price = latest['close']

            # 돌파 체크
            breakout_ratio = (current_price - high_20) / high_20

            if breakout_ratio > self.breakout_threshold:
                return {
                    'action': 'BUY',
                    'symbol': symbol,
                    'confidence': min(0.85, breakout_ratio * 10),
                    'reason': f'저항선 돌파 ({breakout_ratio * 100:.1f}% 상회)',
                    'strategy': 'breakout'
                }

            return {'action': 'HOLD'}

        except Exception as e:
            logger.error(f"돌파 신호 생성 오류: {e}")
            return None

    def validate_signal(self, signal: Dict, market_data: Dict) -> bool:
        """신호 검증"""
        return signal.get('action') in ['BUY', 'SELL']


class ReversionStrategy(BaseStrategy):
    """
    리버전 전략 (Strategy C) - 평균회귀

    특징:
    - 과매도/과매수 구간 역매매
    - 볼린저 밴드 이탈 후 복귀
    - RSI < 30 (과매도) 또는 > 70 (과매수)

    기획서: 30% 포트폴리오 비중
    """

    def __init__(self):
        super().__init__("Reversion Strategy")
        self.rsi_oversold = 30  # RSI < 30 (과매도)
        self.rsi_overbought = 70  # RSI > 70 (과매수)

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        """
        리버전 신호 생성

        조건:
        1. RSI < 30 (과매도) → 매수
        2. RSI > 70 (과매수) → 매도
        3. 볼린저 밴드 하단 돌파 → 매수
        """
        try:
            if data.empty or len(data) < 20:
                return None

            latest = data.iloc[-1]
            symbol = latest.get('symbol', 'Unknown')

            # RSI 계산
            rsi = self._calculate_rsi(data['close'])

            # 볼린저 밴드
            ma_20 = data['close'].rolling(20).mean().iloc[-1]
            std_20 = data['close'].rolling(20).std().iloc[-1]
            lower_band = ma_20 - (2 * std_20)
            upper_band = ma_20 + (2 * std_20)

            current_price = latest['close']

            # 과매도 구간 매수
            if rsi < self.rsi_oversold or current_price < lower_band:
                return {
                    'action': 'BUY',
                    'symbol': symbol,
                    'confidence': 0.75,
                    'reason': f'과매도 구간 (RSI: {rsi:.1f})',
                    'strategy': 'reversion'
                }

            # 과매수 구간 매도 (보유 중일 때)
            if rsi > self.rsi_overbought or current_price > upper_band:
                return {
                    'action': 'SELL',
                    'symbol': symbol,
                    'confidence': 0.75,
                    'reason': f'과매수 구간 (RSI: {rsi:.1f})',
                    'strategy': 'reversion'
                }

            return {'action': 'HOLD'}

        except Exception as e:
            logger.error(f"리버전 신호 생성 오류: {e}")
            return None

    def validate_signal(self, signal: Dict, market_data: Dict) -> bool:
        """신호 검증"""
        return signal.get('action') in ['BUY', 'SELL']

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI 계산"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            return float(rsi.iloc[-1])
        except:
            return 50.0


class InverseETFStrategy(BaseStrategy):
    """
    인버스 ETF 전략 (하락장 수익화)

    기획서 전략 B: 인버스 ETF 전략
    대상: SQQQ, SPXU
    조건: BEAR 국면 AND QQQ < SMA20
    익절: +5% / 손절: -1.5%
    최대 포지션: 20% / 하루 2회 제한
    """

    # 인버스 ETF 대상 종목
    INVERSE_SYMBOLS = ["SQQQ", "SPXU"]

    def __init__(self):
        super().__init__("Inverse ETF Strategy")
        self.take_profit_pct = 0.05   # +5% 익절
        self.stop_loss_pct = -0.015   # -1.5% 손절
        self.sma_period = 20          # SMA20 기준

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        """
        인버스 ETF 매수 신호 생성

        조건:
        1. regime == "BEAR" (외부에서 주입)
        2. 현재가 < SMA20 (하락 추세 확인)
        3. RSI < 50 (추가 하락 여력)
        """
        try:
            if data.empty or len(data) < self.sma_period:
                return None

            latest = data.iloc[-1]
            symbol = latest.get("symbol", "SQQQ")
            current_price = float(latest["close"])

            # SMA20
            sma20 = data["close"].rolling(self.sma_period).mean().iloc[-1]

            # RSI
            rsi = self._calculate_rsi(data["close"])

            # 매수 조건: 가격 < SMA20 (인버스 ETF는 시장 하락 = ETF 상승 대기)
            if current_price < sma20 and rsi < 50:
                distance_pct = ((sma20 - current_price) / sma20) * 100
                confidence = min(0.90, 0.60 + (distance_pct / 10.0))

                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "confidence": confidence,
                    "reason": (
                        f"하락장 인버스 ETF 매수 "
                        f"(가격 ${current_price:.2f} < SMA20 ${sma20:.2f}, RSI: {rsi:.1f})"
                    ),
                    "strategy": "inverse_etf",
                    "take_profit_pct": self.take_profit_pct,
                    "stop_loss_pct": self.stop_loss_pct,
                }

            return {"action": "HOLD"}

        except Exception as e:
            logger.error(f"인버스 ETF 신호 생성 오류: {e}")
            return None

    def validate_signal(self, signal: Dict, market_data: Dict) -> bool:
        """BEAR 국면에서만 유효"""
        if signal.get("action") != "BUY":
            return False
        regime = market_data.get("regime", "NEUTRAL")
        return regime == "BEAR"

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI 계산"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])
        except Exception:
            return 50.0


class DefensiveSectorStrategy(BaseStrategy):
    """
    수비형 섹터 로테이션 전략 (하락장 안정성 확보)

    기획서 전략 D: 섹터 로테이션
    대상: 헬스케어(JNJ), 필수소비재(PG), 유틸리티(XLU)
    조건: BEAR 또는 NEUTRAL 국면
    특징: 낮은 변동성, 배당 수익, 하락장 방어
    """

    # 방어형 종목
    DEFENSIVE_SYMBOLS = ["JNJ", "PG", "XLU"]

    def __init__(self):
        super().__init__("Defensive Sector Strategy")
        self.take_profit_pct = 0.05   # +5% 익절
        self.stop_loss_pct = -0.03    # -3% 손절 (방어주라 여유 있게)
        self.rsi_buy_threshold = 45   # RSI < 45일 때 저점 매수

    def generate_signal(self, data: pd.DataFrame) -> Optional[Dict]:
        """
        방어형 종목 매수 신호 생성

        조건:
        1. regime == "BEAR" or "NEUTRAL"
        2. RSI < 45 (과매도에 가까울 때 저가 매수)
        3. 볼린저 밴드 하단 근처
        """
        try:
            if data.empty or len(data) < 20:
                return None

            latest = data.iloc[-1]
            symbol = latest.get("symbol", "Unknown")
            current_price = float(latest["close"])

            # RSI 계산
            rsi = self._calculate_rsi(data["close"])

            # 볼린저 밴드
            ma20 = data["close"].rolling(20).mean().iloc[-1]
            std20 = data["close"].rolling(20).std().iloc[-1]
            lower_band = ma20 - (2 * std20)

            # 매수 조건: RSI 과매도 근처 OR 하단 밴드 근처
            near_lower_band = current_price <= (lower_band * 1.02)
            rsi_ok = rsi < self.rsi_buy_threshold

            if rsi_ok or near_lower_band:
                confidence = 0.70
                if rsi_ok and near_lower_band:
                    confidence = 0.85

                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "confidence": confidence,
                    "reason": (
                        f"방어형 섹터 매수 "
                        f"(RSI: {rsi:.1f}, 현재가 ${current_price:.2f})"
                    ),
                    "strategy": "defensive_sector",
                    "take_profit_pct": self.take_profit_pct,
                    "stop_loss_pct": self.stop_loss_pct,
                }

            return {"action": "HOLD"}

        except Exception as e:
            logger.error(f"방어형 섹터 신호 생성 오류: {e}")
            return None

    def validate_signal(self, signal: Dict, market_data: Dict) -> bool:
        """BEAR 또는 NEUTRAL 국면에서 유효"""
        if signal.get("action") != "BUY":
            return False
        regime = market_data.get("regime", "NEUTRAL")
        return regime in ("BEAR", "NEUTRAL")

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI 계산"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])
        except Exception:
            return 50.0


# 기획서 참고 (멀티 전략 구조)
"""
기획서 7. 멀티 전략 시스템:

구조:
[Market Regime Detection]
    → BULL  → Momentum(A) + Breakout(B) + Reversion(C)
    → BEAR  → InverseETF(D) + DefensiveSector(E)
    → NEUTRAL → DefensiveSector(E) + 현금 50% 유지

BULL 포트폴리오 분배:
- 전략 A (모멘텀): 40%
- 전략 B (돌파): 30%
- 전략 C (리버전): 30%

BEAR 포트폴리오 분배:
- 전략 D (인버스 ETF): 20% (SQQQ, SPXU)
- 전략 E (방어형 섹터): 30% (JNJ, PG, XLU)
- 현금: 50%
"""
