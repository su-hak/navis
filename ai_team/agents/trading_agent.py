"""
<<<<<<< HEAD
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
=======
Simple Trading Agent (without LangChain Agent framework)

복잡한 Agent 프레임워크 없이 직접 도구를 호출하는 단순 버전
"""

import logging
from typing import Dict, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from ai_team.news.analyzer import NewsAnalyzer
from ai_team.prompts.templates import TRADING_AGENT_SYSTEM_PROMPT
from ai_team.config import config


logger = logging.getLogger(__name__)


class TradingAgent:
    """간단한 트레이딩 분석 에이전트"""

    def __init__(self):
        """에이전트 초기화"""
        # 뉴스 분석기
        self.news_analyzer = NewsAnalyzer()

        # Anthropic Claude LLM 초기화
        self.llm = ChatAnthropic(
            model=config.anthropic_model,
            temperature=config.anthropic_temperature,
            api_key=config.anthropic_api_key
        )

    def analyze_stock(self, symbol: str, context: Optional[Dict] = None) -> Dict:
        """
        종목 분석

        Args:
            symbol: 종목 심볼
            context: 추가 컨텍스트 (기술적 지표, 점수 등)

        Returns:
            {
                'analysis': str,
                'score_adjustment': float,
                'recommendation': str
            }
        """
        logger.info(f"Analyzing stock: {symbol}")

        try:
            # 1. 뉴스 감성 분석
            news_analysis = self.news_analyzer.analyze_news_sentiment(symbol)

            # 2. 점수 보정값 계산
            score_adjustment = self.news_analyzer.calculate_score_adjustment(symbol)

            # 3. 시장 리스크 평가
            market_risk = self.news_analyzer.assess_market_risk()

            # 4. Claude에게 종합 분석 요청
            analysis_prompt = f"""
종목: {symbol}

뉴스 분석:
- 감성 점수: {news_analysis['sentiment_score']} ({news_analysis['sentiment_label']})
- 뉴스 개수: {news_analysis['news_count']}
- 주요 이벤트: {', '.join(news_analysis['key_events']) if news_analysis['key_events'] else '없음'}
- 리스크 요인: {', '.join(news_analysis['risk_factors']) if news_analysis['risk_factors'] else '없음'}
- 요약: {news_analysis['summary']}

시장 리스크:
- 레벨: {market_risk['risk_level']}
- 점수: {market_risk['risk_score']}

점수 보정: {score_adjustment:+.2f}
"""

            if context:
                analysis_prompt += f"\n추가 정보:\n"
                for key, value in context.items():
                    analysis_prompt += f"- {key}: {value}\n"

            analysis_prompt += """
위 정보를 바탕으로 다음을 제공하세요:
1. 종합 분석 (3-5문장)
2. 투자 추천 (BUY/SELL/HOLD/AVOID 중 하나)
3. 주요 근거 (2-3개)

간결하고 명확하게 작성하세요.
"""

            messages = [
                SystemMessage(content=TRADING_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=analysis_prompt)
            ]

            response = self.llm.invoke(messages)
            analysis_text = response.content

            # 추천 추출
            recommendation = self._extract_recommendation(analysis_text)

            return {
                'analysis': analysis_text,
                'score_adjustment': score_adjustment,
                'recommendation': recommendation,
                'news_analysis': news_analysis,
                'market_risk': market_risk
            }

        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {e}")
            return {
                'analysis': f"Error: {str(e)}",
                'score_adjustment': 0.0,
                'recommendation': 'HOLD'
            }

    def _extract_recommendation(self, analysis: str) -> str:
        """분석 텍스트에서 추천 추출"""
        analysis_lower = analysis.lower()

        if 'strong buy' in analysis_lower or '강력 매수' in analysis_lower:
            return 'STRONG_BUY'
        elif 'buy' in analysis_lower or '매수' in analysis_lower:
            return 'BUY'
        elif 'sell' in analysis_lower or '매도' in analysis_lower:
            return 'SELL'
        elif 'avoid' in analysis_lower or '회피' in analysis_lower:
            return 'AVOID'
        else:
            return 'HOLD'

    def chat(self, message: str) -> str:
        """
        대화형 인터페이스

        Args:
            message: 사용자 메시지

        Returns:
            에이전트 응답
        """
        try:
            messages = [
                SystemMessage(content=TRADING_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=message)
            ]
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"Error: {str(e)}"

    def get_news_analysis(self, symbol: str) -> Dict:
        """뉴스 분석만 반환"""
        return self.news_analyzer.analyze_news_sentiment(symbol)

    def get_score_adjustment(self, symbol: str) -> float:
        """점수 보정값만 반환"""
        return self.news_analyzer.calculate_score_adjustment(symbol)

    def get_market_risk(self) -> Dict:
        """시장 리스크만 반환"""
        return self.news_analyzer.assess_market_risk()
>>>>>>> 5d86c4230b98765d8b230668bae5a6132ebd7a55
