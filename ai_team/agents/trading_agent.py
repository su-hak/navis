"""
Trading Agent

Native/Simple Agent를 자동으로 선택
"""

import logging
import os

logger = logging.getLogger(__name__)

# 환경 변수로 Agent 타입 선택
_agent_type = os.getenv("AI_AGENT_TYPE", "auto")


def _get_agent_class():
    """Agent 클래스를 반환"""
    if _agent_type == "simple":
        logger.info("Using Simple Trading Agent")
        from ai_team.agents.trading_agent_simple import TradingAgent
        return TradingAgent

    elif _agent_type == "native":
        logger.info("Using Native Tool Calling Agent")
        from ai_team.agents.trading_agent_native import NativeTradingAgent
        return NativeTradingAgent

    else:  # auto
        # Native Agent 시도 (가장 안정적)
        try:
            logger.info("Using Native Tool Calling Agent (default)")
            from ai_team.agents.trading_agent_native import NativeTradingAgent
            return NativeTradingAgent
        except Exception as e:
            logger.warning(f"Native Agent not available, using Simple Agent: {e}")
            from ai_team.agents.trading_agent_simple import TradingAgent
            return TradingAgent


# Agent 클래스 export
TradingAgent = _get_agent_class()

__all__ = ["TradingAgent"]
