"""
Trading Agent

LangChain 기반 트레이딩 분석 에이전트
"""

import logging
from typing import Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool

from ai_team.news.analyzer import NewsAnalyzer
from ai_team.rag.retriever import RAGRetriever
from ai_team.prompts.templates import TRADING_AGENT_SYSTEM_PROMPT
from ai_team.config import config


logger = logging.getLogger(__name__)


class TradingAgent:
    """트레이딩 분석 에이전트"""

    def __init__(self):
        """에이전트 초기화"""
        # 뉴스 분석기
        self.news_analyzer = NewsAnalyzer()

        # RAG 검색기
        self.rag_retriever = RAGRetriever()

        # Anthropic Claude LLM 초기화
        self.llm = ChatAnthropic(
            model=config.anthropic_model,
            temperature=config.anthropic_temperature,
            api_key=config.anthropic_api_key
        )

        # 메모리
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # 에이전트 도구 정의
        self.tools = self._create_tools()

        # 프롬프트 템플릿
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", TRADING_AGENT_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 에이전트 생성 (Claude tool calling 지원)
        self.agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        # 에이전트 실행기
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=config.agent_verbose,
            max_iterations=config.agent_max_iterations,
            handle_parsing_errors=True
        )

    def _create_tools(self) -> List[StructuredTool]:
        """에이전트 도구 생성"""
        tools = [
            StructuredTool.from_function(
                name="analyze_news_sentiment",
                func=self._analyze_news_sentiment,
                description=(
                    "Analyze news sentiment for a given stock symbol. "
                    "Input: stock symbol (e.g., 'AAPL'). "
                    "Returns: sentiment score, key events, risk factors."
                )
            ),
            StructuredTool.from_function(
                name="get_news_count",
                func=self._get_news_count,
                description=(
                    "Get the count of recent news articles for a stock symbol. "
                    "Input: stock symbol (e.g., 'TSLA'). "
                    "Returns: number of news articles."
                )
            ),
            StructuredTool.from_function(
                name="search_knowledge_base",
                func=self._search_knowledge_base,
                description=(
                    "Search the knowledge base (RAG) for relevant information. "
                    "Input: search query. "
                    "Returns: relevant context and information."
                )
            ),
            StructuredTool.from_function(
                name="assess_market_risk",
                func=self._assess_market_risk,
                description=(
                    "Assess overall market risk level. "
                    "No input required. "
                    "Returns: risk level and key risk factors."
                )
            ),
        ]
        return tools

    def _analyze_news_sentiment(self, symbol: str) -> str:
        """뉴스 감성 분석 도구"""
        try:
            result = self.news_analyzer.analyze_news_sentiment(symbol)
            return (
                f"Symbol: {symbol}\n"
                f"Sentiment Score: {result['sentiment_score']} ({result['sentiment_label']})\n"
                f"News Count: {result['news_count']}\n"
                f"Key Events: {', '.join(result['key_events']) if result['key_events'] else 'None'}\n"
                f"Risk Factors: {', '.join(result['risk_factors']) if result['risk_factors'] else 'None'}\n"
                f"Summary: {result['summary']}"
            )
        except Exception as e:
            logger.error(f"Error in analyze_news_sentiment: {e}")
            return f"Error: {str(e)}"

    def _get_news_count(self, symbol: str) -> str:
        """뉴스 개수 조회 도구"""
        try:
            count = self.news_analyzer.get_news_count(symbol)
            return f"Found {count} recent news articles for {symbol}"
        except Exception as e:
            logger.error(f"Error in get_news_count: {e}")
            return f"Error: {str(e)}"

    def _search_knowledge_base(self, query: str) -> str:
        """지식 베이스 검색 도구"""
        try:
            context = self.rag_retriever.retrieve_context(query)
            return f"Relevant information:\n{context}"
        except Exception as e:
            logger.error(f"Error in search_knowledge_base: {e}")
            return f"Error: {str(e)}"

    def _assess_market_risk(self, _: str = "") -> str:
        """시장 리스크 평가 도구"""
        try:
            result = self.news_analyzer.assess_market_risk()
            return (
                f"Market Risk Level: {result['risk_level']}\n"
                f"Risk Score: {result['risk_score']}\n"
                f"Key Factors: {', '.join(result['factors']) if result['factors'] else 'None'}"
            )
        except Exception as e:
            logger.error(f"Error in assess_market_risk: {e}")
            return f"Error: {str(e)}"

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

        # 컨텍스트 준비
        context_str = ""
        if context:
            context_str = f"\n\nAdditional Context:\n"
            for key, value in context.items():
                context_str += f"- {key}: {value}\n"

        # 에이전트에게 질문
        query = (
            f"Analyze {symbol} stock for trading decision. "
            f"Consider news sentiment, market risk, and provide a score adjustment recommendation (-10 to +10)."
            f"{context_str}"
        )

        try:
            response = self.agent_executor.invoke({"input": query})
            analysis_text = response.get('output', '')

            # 점수 보정값 계산
            score_adjustment = self.news_analyzer.calculate_score_adjustment(symbol)

            return {
                'analysis': analysis_text,
                'score_adjustment': score_adjustment,
                'recommendation': self._extract_recommendation(analysis_text)
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

        if 'strong buy' in analysis_lower or 'strongly recommend buying' in analysis_lower:
            return 'STRONG_BUY'
        elif 'buy' in analysis_lower or 'bullish' in analysis_lower:
            return 'BUY'
        elif 'sell' in analysis_lower or 'bearish' in analysis_lower:
            return 'SELL'
        elif 'avoid' in analysis_lower or 'do not buy' in analysis_lower:
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
            response = self.agent_executor.invoke({"input": message})
            return response.get('output', 'No response')
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"Error: {str(e)}"

    def reset_memory(self):
        """대화 기록 초기화"""
        self.memory.clear()
        logger.info("Agent memory cleared")

    def get_tool_names(self) -> List[str]:
        """사용 가능한 도구 목록 반환"""
        return [tool.name for tool in self.tools]
