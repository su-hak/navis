"""
Agent Selector

환경에 따라 적절한 Agent를 선택
"""

import logging
import os

logger = logging.getLogger(__name__)


def get_trading_agent():
    """
    사용 가능한 Agent 선택

    Returns:
        TradingAgent 인스턴스
    """
    # 환경 변수로 Agent 타입 선택
    agent_type = os.getenv("AI_AGENT_TYPE", "auto")

    if agent_type == "simple":
        # 단순 버전 (안정적)
        logger.info("Using Simple Trading Agent")
        from ai_team.agents.trading_agent_simple import TradingAgent
        return TradingAgent()

    elif agent_type == "full":
        # 완전한 LangChain Agent (고급)
        logger.info("Using Full LangChain Agent")
        from ai_team.agents.trading_agent_full import FullTradingAgent
        return FullTradingAgent()

    else:  # auto
        # 자동 선택 - Full Agent 시도, 실패시 Simple로 fallback
        try:
            logger.info("Attempting to use Full LangChain Agent")
            from ai_team.agents.trading_agent_full import FullTradingAgent
            agent = FullTradingAgent()
            logger.info("✓ Full LangChain Agent loaded successfully")
            return agent
        except Exception as e:
            logger.warning(f"Full Agent failed, falling back to Simple Agent: {e}")
            from ai_team.agents.trading_agent_simple import TradingAgent
            logger.info("✓ Using Simple Trading Agent as fallback")
            return TradingAgent()


# 편의를 위한 별칭
TradingAgent = get_trading_agent
