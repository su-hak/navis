"""
전략 엔진 API

전략 엔진의 기능을 REST API로 제공합니다.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime

from ..indicators.technical_indicators import TechnicalIndicators
from ..filters.stock_filter import StockFilter, FilterCriteria
from ..scoring.score_calculator import ScoreCalculator, ScoreWeights
from ..signals.signal_generator import SignalGenerator, TradingConditions, SignalType


# ==================== Request Models ====================

class OHLCVData(BaseModel):
    """OHLCV 데이터 모델"""
    timestamp: List[str] = Field(..., description="타임스탬프 리스트")
    open: List[float] = Field(..., description="시가 리스트")
    high: List[float] = Field(..., description="고가 리스트")
    low: List[float] = Field(..., description="저가 리스트")
    close: List[float] = Field(..., description="종가 리스트")
    volume: List[int] = Field(..., description="거래량 리스트")

    def to_dataframe(self) -> pd.DataFrame:
        """데이터프레임으로 변환"""
        return pd.DataFrame({
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
        })


class CalculateIndicatorsRequest(BaseModel):
    """기술적 지표 계산 요청"""
    symbol: str = Field(..., description="종목 심볼")
    data: OHLCVData = Field(..., description="OHLCV 데이터")


class FilterStocksRequest(BaseModel):
    """종목 필터링 요청"""
    stock_data: Dict[str, OHLCVData] = Field(..., description="종목별 OHLCV 데이터")
    criteria: Optional[Dict[str, Any]] = Field(None, description="필터링 기준")
    news_data: Optional[Dict[str, int]] = Field(None, description="종목별 뉴스 개수")


class CalculateScoreRequest(BaseModel):
    """점수 계산 요청"""
    symbol: str = Field(..., description="종목 심볼")
    data: OHLCVData = Field(..., description="OHLCV 데이터")
    news_sentiment: Optional[float] = Field(None, ge=-1.0, le=1.0, description="뉴스 감성 (-1.0 ~ 1.0)")
    news_count: int = Field(0, ge=0, description="뉴스 개수")
    revenue_growth: Optional[float] = Field(None, description="매출 성장률 (%)")
    eps_growth: Optional[float] = Field(None, description="EPS 성장률 (%)")
    institutional_ownership_change: Optional[float] = Field(None, description="기관 보유 변화율 (%)")
    weights: Optional[Dict[str, float]] = Field(None, description="점수 가중치")


class GenerateBuySignalRequest(BaseModel):
    """매수 시그널 생성 요청"""
    symbol: str = Field(..., description="종목 심볼")
    data: OHLCVData = Field(..., description="OHLCV 데이터")
    news_sentiment: Optional[float] = Field(None, ge=-1.0, le=1.0, description="뉴스 감성")
    news_count: int = Field(0, ge=0, description="뉴스 개수")
    revenue_growth: Optional[float] = Field(None, description="매출 성장률")
    eps_growth: Optional[float] = Field(None, description="EPS 성장률")
    institutional_ownership_change: Optional[float] = Field(None, description="기관 보유 변화율")
    conditions: Optional[Dict[str, Any]] = Field(None, description="매매 조건")


class GenerateSellSignalRequest(BaseModel):
    """매도 시그널 생성 요청"""
    symbol: str = Field(..., description="종목 심볼")
    data: OHLCVData = Field(..., description="OHLCV 데이터")
    entry_price: float = Field(..., gt=0, description="진입 가격")
    previous_score: Optional[float] = Field(None, ge=0, le=100, description="이전 점수")
    news_sentiment: Optional[float] = Field(None, ge=-1.0, le=1.0, description="뉴스 감성")
    news_count: int = Field(0, ge=0, description="뉴스 개수")
    conditions: Optional[Dict[str, Any]] = Field(None, description="매매 조건")


# ==================== Response Models ====================

class IndicatorsResponse(BaseModel):
    """기술적 지표 응답"""
    symbol: str
    indicators: Dict[str, float]


class FilterResultResponse(BaseModel):
    """필터링 결과 응답"""
    symbol: str
    passed: bool
    reasons: List[str]
    metrics: Dict[str, Any]


class ScoreResponse(BaseModel):
    """점수 계산 응답"""
    symbol: str
    total_score: float
    technical_score: float
    volume_score: float
    trend_score: float
    news_score: float
    financial_score: float
    recommendation: str
    breakdown: Dict[str, Any]


class SignalResponse(BaseModel):
    """시그널 응답"""
    symbol: str
    signal_type: str
    score: float
    confidence: float
    entry_price: float
    target_price: Optional[float]
    stop_loss_price: Optional[float]
    reasons: List[str]
    metadata: Dict[str, Any]
    timestamp: str


# ==================== API Class ====================

class StrategyEngineAPI:
    """전략 엔진 API 클래스"""

    def __init__(self):
        self.technical_indicators = TechnicalIndicators()
        self.stock_filter = StockFilter()
        self.score_calculator = ScoreCalculator()
        self.signal_generator = SignalGenerator()

    def calculate_indicators(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
        """기술적 지표 계산"""
        indicators = self.technical_indicators.calculate_all_indicators(df)
        return {
            'symbol': symbol,
            'indicators': indicators.to_dict()
        }

    def filter_stocks(self,
                      stock_data: Dict[str, pd.DataFrame],
                      criteria: Optional[FilterCriteria] = None,
                      news_data: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
        """종목 필터링"""
        if criteria:
            self.stock_filter.criteria = criteria

        results = self.stock_filter.filter_stocks(stock_data, news_data)
        return [r.to_dict() for r in results]

    def calculate_score(self,
                        symbol: str,
                        df: pd.DataFrame,
                        weights: Optional[ScoreWeights] = None,
                        **kwargs) -> Dict[str, Any]:
        """점수 계산"""
        if weights:
            self.score_calculator.weights = weights

        score_result = self.score_calculator.score_stock(symbol, df, **kwargs)
        return score_result.to_dict()

    def generate_buy_signal(self,
                            symbol: str,
                            df: pd.DataFrame,
                            conditions: Optional[TradingConditions] = None,
                            **kwargs) -> Optional[Dict[str, Any]]:
        """매수 시그널 생성"""
        if conditions:
            self.signal_generator.conditions = conditions

        signal = self.signal_generator.generate_buy_signal(symbol, df, **kwargs)
        return signal.to_dict() if signal else None

    def generate_sell_signal(self,
                             symbol: str,
                             df: pd.DataFrame,
                             entry_price: float,
                             conditions: Optional[TradingConditions] = None,
                             **kwargs) -> Optional[Dict[str, Any]]:
        """매도 시그널 생성"""
        if conditions:
            self.signal_generator.conditions = conditions

        signal = self.signal_generator.generate_sell_signal(symbol, df, entry_price, **kwargs)
        return signal.to_dict() if signal else None


# ==================== FastAPI App ====================

def create_strategy_api() -> FastAPI:
    """전략 엔진 FastAPI 앱 생성"""

    app = FastAPI(
        title="Strategy Engine API",
        description="AI 자동매매 시스템 전략 엔진 API",
        version="1.0.0"
    )

    api = StrategyEngineAPI()

    @app.get("/", tags=["Health"])
    async def root():
        """API 상태 확인"""
        return {
            "service": "Strategy Engine API",
            "version": "1.0.0",
            "status": "running",
            "timestamp": datetime.now().isoformat()
        }

    @app.post("/indicators/calculate", response_model=IndicatorsResponse, tags=["Indicators"])
    async def calculate_indicators(request: CalculateIndicatorsRequest):
        """
        기술적 지표 계산

        RSI, MACD, Bollinger Bands 등 다양한 기술적 지표를 계산합니다.
        """
        try:
            df = request.data.to_dataframe()
            result = api.calculate_indicators(request.symbol, df)
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/filter/stocks", response_model=List[FilterResultResponse], tags=["Filter"])
    async def filter_stocks(request: FilterStocksRequest):
        """
        종목 필터링

        거래량, 변동성, 추세 등을 기준으로 매매 후보 종목을 필터링합니다.
        """
        try:
            # 데이터 변환
            stock_data = {
                symbol: data.to_dataframe()
                for symbol, data in request.stock_data.items()
            }

            # 필터링 기준 설정
            criteria = None
            if request.criteria:
                criteria = FilterCriteria(**request.criteria)

            results = api.filter_stocks(stock_data, criteria, request.news_data)
            return results
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/score/calculate", response_model=ScoreResponse, tags=["Score"])
    async def calculate_score(request: CalculateScoreRequest):
        """
        종합 점수 계산

        기술적 지표, 뉴스 감성, 재무 성장성 등을 종합하여 매매 적합도를 평가합니다.
        """
        try:
            df = request.data.to_dataframe()

            # 가중치 설정
            weights = None
            if request.weights:
                weights = ScoreWeights(**request.weights)

            result = api.calculate_score(
                symbol=request.symbol,
                df=df,
                weights=weights,
                news_sentiment=request.news_sentiment,
                news_count=request.news_count,
                revenue_growth=request.revenue_growth,
                eps_growth=request.eps_growth,
                institutional_ownership_change=request.institutional_ownership_change,
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/signal/buy", response_model=SignalResponse, tags=["Signal"])
    async def generate_buy_signal(request: GenerateBuySignalRequest):
        """
        매수 시그널 생성

        점수와 조건을 기반으로 매수 시그널을 생성합니다.
        """
        try:
            df = request.data.to_dataframe()

            # 매매 조건 설정
            conditions = None
            if request.conditions:
                conditions = TradingConditions(**request.conditions)

            result = api.generate_buy_signal(
                symbol=request.symbol,
                df=df,
                conditions=conditions,
                news_sentiment=request.news_sentiment,
                news_count=request.news_count,
                revenue_growth=request.revenue_growth,
                eps_growth=request.eps_growth,
                institutional_ownership_change=request.institutional_ownership_change,
            )

            if not result:
                raise HTTPException(status_code=404, detail="매수 시그널이 생성되지 않았습니다 (조건 미충족)")

            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/signal/sell", response_model=SignalResponse, tags=["Signal"])
    async def generate_sell_signal(request: GenerateSellSignalRequest):
        """
        매도 시그널 생성

        점수와 조건을 기반으로 매도/손절/익절 시그널을 생성합니다.
        """
        try:
            df = request.data.to_dataframe()

            # 매매 조건 설정
            conditions = None
            if request.conditions:
                conditions = TradingConditions(**request.conditions)

            result = api.generate_sell_signal(
                symbol=request.symbol,
                df=df,
                entry_price=request.entry_price,
                conditions=conditions,
                previous_score=request.previous_score,
                news_sentiment=request.news_sentiment,
                news_count=request.news_count,
            )

            if not result:
                raise HTTPException(status_code=404, detail="매도 시그널이 생성되지 않았습니다 (보유 유지)")

            return result
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/health", tags=["Health"])
    async def health_check():
        """헬스 체크"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

    return app


# ==================== Main ====================

# FastAPI 앱 인스턴스 생성 (Railway 등 배포 플랫폼을 위해)
app = create_strategy_api()

if __name__ == "__main__":
    import uvicorn
    import os

    # Railway 등 클라우드 플랫폼의 PORT 환경변수 사용
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
