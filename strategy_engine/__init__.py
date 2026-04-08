"""
전략 엔진 (Strategy Engine) 모듈

AI 자동매매 시스템의 핵심 전략 로직을 담당하는 모듈입니다.

주요 기능:
- 종목 필터링 (거래량, 변동성 기반)
- 기술적 지표 계산 (RSI, MACD, Bollinger Bands 등)
- 종합 점수 계산 시스템
- 매수/매도 시그널 생성

팀: Strategy Engine Team
역할: 매매 전략 및 점수 시스템 개발
"""

from .indicators.technical_indicators import TechnicalIndicators
from .filters.stock_filter import StockFilter
from .scoring.score_calculator import ScoreCalculator
from .signals.signal_generator import SignalGenerator

__all__ = [
    'TechnicalIndicators',
    'StockFilter',
    'ScoreCalculator',
    'SignalGenerator',
]

__version__ = '1.0.0'
__author__ = 'Strategy Engine Team'
