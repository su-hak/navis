"""
Full LangChain Trading Agent

도구를 자율적으로 선택하고 멀티스텝 추론을 수행하는 완전한 Agent
"""

import logging
from typing import Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser

from ai_team.news.analyzer import NewsAnalyzer
from ai_team.rag.retriever import RAGRetriever
from ai_team.prompts.templates import TRADING_AGENT_SYSTEM_PROMPT
from ai_team.config import config


logger = logging.getLogger(__name__)


class FullTradingAgent:
    """완전한 LangChain Agent - 도구를 자율적으로 선택"""

    def __init__(self):
        """에이전트 초기화"""
        # 뉴스 분석기
        self.news_analyzer = NewsAnalyzer()

        # RAG 검색기
        self.rag_retriever = RAGRetriever()

        # Anthropic Claude LLM 초기화 (tool calling 지원)
        self.llm = ChatAnthropic(
            model=config.anthropic_model,
            temperature=config.anthropic_temperature,
            api_key=config.anthropic_api_key
        )

        # Agent 도구 정의
        self.tools = self._create_tools()

        # LLM with tools binding
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # 프롬프트 템플릿
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", TRADING_AGENT_SYSTEM_PROMPT + """

당신은 다음 도구들을 사용할 수 있습니다:
1. analyze_news_sentiment - 종목의 뉴스 감성 분석
2. get_news_count - 최근 뉴스 개수 조회
3. assess_market_risk - 전체 시장 리스크 평가
4. search_knowledge_base - RAG 지식 베이스 검색

**중요**: 종목 분석 시 반드시 다음 단계를 따르세요:
1. 먼저 뉴스 감성 분석 (analyze_news_sentiment)
2. 시장 리스크 평가 (assess_market_risk)
3. 필요시 추가 정보 검색 (search_knowledge_base)
4. 종합 분석 및 추천

각 도구를 적절히 선택하여 최선의 투자 판단을 내리세요.
"""),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Agent chain 생성
        self.agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
            }
            | self.prompt
            | self.llm_with_tools
            | OpenAIFunctionsAgentOutputParser()
        )

        # Agent Executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=config.agent_verbose,
            max_iterations=config.agent_max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )

    def _create_tools(self) -> List:
        """에이전트 도구 생성 - @tool 데코레이터 사용"""

        # 클로저로 self 접근
        news_analyzer = self.news_analyzer
        rag_retriever = self.rag_retriever

        @tool
        def analyze_news_sentiment(symbol: str) -> str:
            """
            특정 종목의 뉴스 감성을 분석합니다.

            Args:
                symbol: 종목 심볼 (예: 'AAPL', 'TSLA')

            Returns:
                감성 점수, 주요 이벤트, 리스크 요인을 포함한 분석 결과
            """
            try:
                result = news_analyzer.analyze_news_sentiment(symbol)
                return (
                    f"종목: {symbol}\n"
                    f"감성 점수: {result['sentiment_score']:.2f} ({result['sentiment_label']})\n"
                    f"뉴스 개수: {result['news_count']}\n"
                    f"주요 이벤트: {', '.join(result['key_events']) if result['key_events'] else '없음'}\n"
                    f"리스크 요인: {', '.join(result['risk_factors']) if result['risk_factors'] else '없음'}\n"
                    f"요약: {result['summary']}"
                )
            except Exception as e:
                logger.error(f"Error in analyze_news_sentiment: {e}")
                return f"Error: {str(e)}"

        @tool
        def get_news_count(symbol: str) -> str:
            """
            특정 종목의 최근 뉴스 개수를 조회합니다.

            Args:
                symbol: 종목 심볼 (예: 'AAPL', 'TSLA')

            Returns:
                뉴스 개수
            """
            try:
                count = news_analyzer.get_news_count(symbol)
                return f"{symbol} 종목의 최근 뉴스: {count}개"
            except Exception as e:
                logger.error(f"Error in get_news_count: {e}")
                return f"Error: {str(e)}"

        @tool
        def assess_market_risk() -> str:
            """
            전체 시장의 리스크 레벨을 평가합니다.
            주요 지수(SPY, QQQ, DIA)의 뉴스를 분석하여 시장 리스크를 판단합니다.

            Returns:
                시장 리스크 레벨과 주요 리스크 요인
            """
            try:
                result = news_analyzer.assess_market_risk()
                return (
                    f"시장 리스크 레벨: {result['risk_level'].upper()}\n"
                    f"리스크 점수: {result['risk_score']:.2f}\n"
                    f"주요 요인: {', '.join(result['factors']) if result['factors'] else '없음'}"
                )
            except Exception as e:
                logger.error(f"Error in assess_market_risk: {e}")
                return f"Error: {str(e)}"

        @tool
        def search_knowledge_base(query: str) -> str:
            """
            RAG 지식 베이스에서 관련 정보를 검색합니다.
            과거 뉴스, 분석 자료 등을 검색할 때 사용합니다.

            Args:
                query: 검색 쿼리 (예: "Apple earnings report")

            Returns:
                관련 정보와 컨텍스트
            """
            try:
                context = rag_retriever.retrieve_context(query, k=3)
                if not context or context == "No relevant context found.":
                    return "관련 정보를 찾을 수 없습니다."
                return f"검색 결과:\n{context}"
            except Exception as e:
                logger.error(f"Error in search_knowledge_base: {e}")
                return f"Error: {str(e)}"

        return [
            analyze_news_sentiment,
            get_news_count,
            assess_market_risk,
            search_knowledge_base
        ]

    def analyze_stock(self, symbol: str, context: Optional[Dict] = None) -> Dict:
        """
        종목 분석 - Agent가 자율적으로 도구를 선택하여 분석

        Args:
            symbol: 종목 심볼
            context: 추가 컨텍스트 (기술적 지표 등)

        Returns:
            분석 결과
        """
        logger.info(f"Analyzing stock with full agent: {symbol}")

        # 컨텍스트 준비
        context_str = ""
        if context:
            context_str = "\n\n추가 정보:\n"
            for key, value in context.items():
                context_str += f"- {key}: {value}\n"

        # Agent에게 분석 요청
        input_text = f"""
{symbol} 종목을 분석하고 투자 추천을 제공하세요.
{context_str}

다음 단계를 수행하세요:
1. 뉴스 감성 분석으로 최근 동향 파악
2. 시장 전체 리스크 평가
3. 필요시 추가 정보 검색
4. 종합 분석 및 투자 추천 (BUY/SELL/HOLD/AVOID)

각 단계의 근거를 명확히 제시하세요.
"""

        try:
            result = self.agent_executor.invoke({"input": input_text})

            # 점수 보정값 계산
            score_adjustment = self.news_analyzer.calculate_score_adjustment(symbol)

            # 추천 추출
            output_text = result.get("output", "")
            recommendation = self._extract_recommendation(output_text)

            # 중간 단계 로깅
            steps = result.get("intermediate_steps", [])
            logger.info(f"Agent executed {len(steps)} steps")

            return {
                'analysis': output_text,
                'score_adjustment': score_adjustment,
                'recommendation': recommendation,
                'steps_taken': len(steps),
                'tools_used': [step[0].tool for step in steps] if steps else []
            }

        except Exception as e:
            logger.error(f"Error in agent analysis: {e}")
            return {
                'analysis': f"Error: {str(e)}",
                'score_adjustment': 0.0,
                'recommendation': 'HOLD',
                'steps_taken': 0,
                'tools_used': []
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
        대화형 인터페이스 - Agent가 필요한 도구를 자동 선택

        Args:
            message: 사용자 메시지

        Returns:
            Agent 응답
        """
        try:
            result = self.agent_executor.invoke({"input": message})
            return result.get("output", "No response")
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"Error: {str(e)}"

    def get_tool_names(self) -> List[str]:
        """사용 가능한 도구 목록"""
        return [tool.name for tool in self.tools]
