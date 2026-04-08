"""
AI/RAG Team Module

비정형 데이터 해석 및 전략 보정을 담당하는 AI 팀 모듈

주요 기능:
- 뉴스 분석 (감성/이벤트)
- RAG 구축 및 검색
- LangChain Agent 구성
- 프롬프트 설계
"""

from ai_team.news.analyzer import NewsAnalyzer
from ai_team.agents.trading_agent import TradingAgent

__version__ = "1.0.0"

__all__ = [
    "NewsAnalyzer",
    "TradingAgent",
]
