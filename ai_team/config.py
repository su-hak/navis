"""
AI Team Configuration
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class AITeamConfig(BaseSettings):
    """AI Team 설정"""

    # Anthropic Claude API 설정 (뉴스 분석, AI Agent에 사용)
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_temperature: float = 0.3

    # OpenAI API 설정 (RAG 임베딩에만 사용, 선택적)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = "gpt-4-turbo-preview"
    openai_temperature: float = 0.3

    # 뉴스 수집 설정
    news_api_key: Optional[str] = os.getenv("NEWS_API_KEY", "")
    news_sources: list = ["reuters", "bloomberg", "cnbc", "marketwatch"]
    max_news_per_symbol: int = 20
    news_lookback_hours: int = 24

    # RAG 설정
    vector_db_path: str = "./ai_team/data/vector_db"
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_results: int = 5

    # 감성 분석 설정
    sentiment_threshold_positive: float = 0.6
    sentiment_threshold_negative: float = -0.6

    # Agent 설정
    agent_max_iterations: int = 5
    agent_verbose: bool = True

    # 점수 보정 설정
    max_score_adjustment: float = 10.0  # 최대 ±10점 보정

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # .env 파일의 추가 필드 무시


# 전역 설정 인스턴스
config = AITeamConfig()
