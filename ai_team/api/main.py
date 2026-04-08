"""
AI Team FastAPI Server

AI/RAG 팀의 기능을 REST API로 제공
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_team.news.analyzer import NewsAnalyzer
from ai_team.agents.trading_agent import TradingAgent
from ai_team.rag.vector_store import VectorStoreManager
from ai_team.rag.retriever import RAGRetriever
from ai_team.config import config


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# FastAPI 앱 생성
app = FastAPI(
    title="AI Team API",
    description="AI/RAG 팀 - 뉴스 분석, RAG, LangChain Agent API",
    version="1.0.0"
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response 모델
class NewsSentimentRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")


class NewsSentimentResponse(BaseModel):
    symbol: str
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    sentiment_label: str
    key_events: List[str]
    risk_factors: List[str]
    summary: str
    news_count: int


class ScoreAdjustmentRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")


class ScoreAdjustmentResponse(BaseModel):
    symbol: str
    adjustment: float = Field(..., ge=-10.0, le=10.0)
    timestamp: str


class MarketRiskResponse(BaseModel):
    risk_level: str
    risk_score: float
    factors: List[str]
    timestamp: str


class StockAnalysisRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    context: Optional[Dict] = Field(None, description="Additional context (technical indicators, etc.)")


class StockAnalysisResponse(BaseModel):
    symbol: str
    analysis: str
    score_adjustment: float
    recommendation: str
    timestamp: str


class RAGSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    k: Optional[int] = Field(5, description="Number of results")


class RAGSearchResponse(BaseModel):
    query: str
    context: str
    sources: List[str]


class AddNewsRequest(BaseModel):
    news_list: List[Dict] = Field(..., description="List of news articles")


# 전역 인스턴스
news_analyzer: Optional[NewsAnalyzer] = None
trading_agent: Optional[TradingAgent] = None
vector_store: Optional[VectorStoreManager] = None
rag_retriever: Optional[RAGRetriever] = None


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 초기화"""
    global news_analyzer, trading_agent, vector_store, rag_retriever

    logger.info("Initializing AI Team components...")

    try:
        news_analyzer = NewsAnalyzer()
        logger.info("✓ NewsAnalyzer initialized")

        vector_store = VectorStoreManager()
        logger.info("✓ VectorStoreManager initialized")

        rag_retriever = RAGRetriever(vector_store)
        logger.info("✓ RAGRetriever initialized")

        trading_agent = TradingAgent()
        logger.info("✓ TradingAgent initialized")

        logger.info("AI Team API ready!")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise


@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "service": "AI Team API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
        "components": {
            "news_analyzer": news_analyzer is not None,
            "trading_agent": trading_agent is not None,
            "vector_store": vector_store is not None,
            "rag_retriever": rag_retriever is not None
        },
        "timestamp": datetime.now().isoformat()
    }


# ========== 뉴스 분석 API ==========

@app.post("/api/news/analyze", response_model=NewsSentimentResponse)
async def analyze_news_sentiment(request: NewsSentimentRequest):
    """
    뉴스 감성 분석

    종목의 최근 뉴스를 분석하여 감성 점수와 주요 이벤트, 리스크 요인을 반환합니다.
    """
    try:
        result = news_analyzer.analyze_news_sentiment(request.symbol)

        return NewsSentimentResponse(
            symbol=request.symbol,
            sentiment_score=result['sentiment_score'],
            sentiment_label=result['sentiment_label'],
            key_events=result['key_events'],
            risk_factors=result['risk_factors'],
            summary=result['summary'],
            news_count=result['news_count']
        )

    except Exception as e:
        logger.error(f"Error analyzing news for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/news/score-adjustment", response_model=ScoreAdjustmentResponse)
async def calculate_score_adjustment(request: ScoreAdjustmentRequest):
    """
    뉴스 기반 점수 보정값 계산

    뉴스 감성 분석 결과를 바탕으로 전략 엔진 점수 보정값을 계산합니다.
    범위: -10.0 ~ +10.0
    """
    try:
        adjustment = news_analyzer.calculate_score_adjustment(request.symbol)

        return ScoreAdjustmentResponse(
            symbol=request.symbol,
            adjustment=adjustment,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error calculating score adjustment for {request.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/count/{symbol}")
async def get_news_count(symbol: str):
    """뉴스 개수 조회"""
    try:
        count = news_analyzer.get_news_count(symbol)
        return {
            "symbol": symbol,
            "count": count,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting news count for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 시장 리스크 API ==========

@app.get("/api/market/risk", response_model=MarketRiskResponse)
async def assess_market_risk():
    """
    전체 시장 리스크 평가

    주요 지수(SPY, QQQ, DIA)의 뉴스를 분석하여 시장 전체 리스크를 평가합니다.
    """
    try:
        result = news_analyzer.assess_market_risk()

        return MarketRiskResponse(
            risk_level=result['risk_level'],
            risk_score=result['risk_score'],
            factors=result['factors'],
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error assessing market risk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== AI Agent API ==========

@app.post("/api/agent/analyze", response_model=StockAnalysisResponse)
async def analyze_stock_with_agent(request: StockAnalysisRequest):
    """
    AI Agent를 사용한 종목 분석

    LangChain Agent가 뉴스, RAG, 기술적 지표를 종합하여 종목을 분석합니다.
    """
    try:
        result = trading_agent.analyze_stock(request.symbol, request.context)

        return StockAnalysisResponse(
            symbol=request.symbol,
            analysis=result['analysis'],
            score_adjustment=result['score_adjustment'],
            recommendation=result['recommendation'],
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Error analyzing stock with agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/chat")
async def chat_with_agent(message: str = Query(..., description="Message to the agent")):
    """
    AI Agent와 대화

    자연어로 질문하고 답변을 받습니다.
    """
    try:
        response = trading_agent.chat(message)
        return {
            "message": message,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in agent chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/reset")
async def reset_agent_memory():
    """AI Agent 대화 기록 초기화"""
    try:
        trading_agent.reset_memory()
        return {
            "status": "success",
            "message": "Agent memory cleared",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error resetting agent memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== RAG API ==========

@app.post("/api/rag/search", response_model=RAGSearchResponse)
async def search_knowledge_base(request: RAGSearchRequest):
    """
    지식 베이스(RAG) 검색

    벡터 DB에서 관련 정보를 검색합니다.
    """
    try:
        context = rag_retriever.retrieve_context(request.query, request.k)

        # 소스 추출
        results = vector_store.search(request.query, request.k)
        sources = [doc.metadata.get('source', 'Unknown') for doc in results]
        sources = list(set(sources))

        return RAGSearchResponse(
            query=request.query,
            context=context,
            sources=sources
        )

    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rag/add-news")
async def add_news_to_vector_store(request: AddNewsRequest):
    """
    뉴스를 벡터 스토어에 추가

    수집한 뉴스를 RAG 지식 베이스에 추가합니다.
    """
    try:
        vector_store.add_news(request.news_list)

        return {
            "status": "success",
            "message": f"Added {len(request.news_list)} news articles to vector store",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error adding news to vector store: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rag/stats")
async def get_vector_store_stats():
    """벡터 스토어 통계"""
    try:
        stats = vector_store.get_stats()
        stats['timestamp'] = datetime.now().isoformat()
        return stats

    except Exception as e:
        logger.error(f"Error getting vector store stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 유틸리티 API ==========

@app.get("/api/tools")
async def get_available_tools():
    """사용 가능한 Agent 도구 목록"""
    try:
        tools = trading_agent.get_tool_names()
        return {
            "tools": tools,
            "count": len(tools),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
