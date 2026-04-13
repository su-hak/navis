"""
Native Tool Calling Trading Agent

LangChain 프레임워크 대신 Anthropic의 native tool calling 직접 사용
더 안정적이고 버전 호환성 문제 없음
"""

import logging
from typing import Dict, List, Optional, Any
import json

from anthropic import Anthropic

from ai_team.news.analyzer import NewsAnalyzer
from ai_team.prompts.templates import TRADING_AGENT_SYSTEM_PROMPT
from ai_team.config import config

logger = logging.getLogger(__name__)

# 성과 추적기 (in-context 학습용)
try:
    from ai_team.performance.tracker import performance_tracker
    PERFORMANCE_TRACKING = True
except Exception as _e:
    performance_tracker = None
    PERFORMANCE_TRACKING = False
    logger.warning(f"성과 추적기 비활성화: {_e}")

# RAG는 optional (LangChain 버전 문제로 실패할 수 있음)
try:
    from ai_team.rag.retriever import RAGRetriever
    RAG_AVAILABLE = True
except Exception as e:
    RAG_AVAILABLE = False
    logger.warning(f"RAG not available: {e}")


class NativeTradingAgent:
    """Anthropic native tool calling을 사용하는 Agent"""

    def __init__(self):
        """에이전트 초기화"""
        # 뉴스 분석기
        self.news_analyzer = NewsAnalyzer()

        # RAG 검색기 (optional)
        if RAG_AVAILABLE:
            try:
                self.rag_retriever = RAGRetriever()
                logger.info("✓ RAG retriever initialized")
            except Exception as e:
                self.rag_retriever = None
                logger.warning(f"RAG retriever initialization failed: {e}")
        else:
            self.rag_retriever = None
            logger.info("RAG not available, skipping")

        # Anthropic 클라이언트
        self.client = Anthropic(api_key=config.anthropic_api_key)

        # 도구 정의 (Anthropic 형식)
        self.tools = self._define_tools()

    def _define_tools(self) -> List[Dict]:
        """Anthropic tool calling 형식으로 도구 정의"""
        tools = [
            {
                "name": "analyze_news_sentiment",
                "description": "특정 종목의 뉴스 감성을 분석합니다. 감성 점수, 주요 이벤트, 리스크 요인을 반환합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "종목 심볼 (예: AAPL, TSLA)"
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "get_news_count",
                "description": "특정 종목의 최근 뉴스 개수를 조회합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "종목 심볼 (예: AAPL, TSLA)"
                        }
                    },
                    "required": ["symbol"]
                }
            },
            {
                "name": "assess_market_risk",
                "description": "전체 시장의 리스크 레벨을 평가합니다. 주요 지수(SPY, QQQ, DIA)를 분석하여 시장 리스크를 판단합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]

        # RAG가 사용 가능한 경우에만 추가
        if self.rag_retriever is not None:
            tools.append({
                "name": "search_knowledge_base",
                "description": "RAG 지식 베이스에서 관련 정보를 검색합니다. 과거 뉴스나 분석 자료를 찾을 때 사용합니다.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색 쿼리 (예: Apple earnings report)"
                        }
                    },
                    "required": ["query"]
                }
            })

        return tools

    def _execute_tool(self, tool_name: str, tool_input: Dict) -> str:
        """도구 실행"""
        try:
            if tool_name == "analyze_news_sentiment":
                symbol = tool_input.get("symbol", "")
                result = self.news_analyzer.analyze_news_sentiment(symbol)
                return json.dumps({
                    "symbol": symbol,
                    "sentiment_score": result['sentiment_score'],
                    "sentiment_label": result['sentiment_label'],
                    "news_count": result['news_count'],
                    "key_events": result['key_events'],
                    "risk_factors": result['risk_factors'],
                    "summary": result['summary']
                }, ensure_ascii=False)

            elif tool_name == "get_news_count":
                symbol = tool_input.get("symbol", "")
                count = self.news_analyzer.get_news_count(symbol)
                return json.dumps({
                    "symbol": symbol,
                    "count": count
                }, ensure_ascii=False)

            elif tool_name == "assess_market_risk":
                result = self.news_analyzer.assess_market_risk()
                return json.dumps({
                    "risk_level": result['risk_level'],
                    "risk_score": result['risk_score'],
                    "factors": result['factors']
                }, ensure_ascii=False)

            elif tool_name == "search_knowledge_base":
                if self.rag_retriever is None:
                    return json.dumps({
                        "error": "RAG not available"
                    })
                query = tool_input.get("query", "")
                context = self.rag_retriever.retrieve_context(query, k=3)
                return json.dumps({
                    "query": query,
                    "context": context
                }, ensure_ascii=False)

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return json.dumps({"error": str(e)})

    def analyze_stock(self, symbol: str, context: Optional[Dict] = None) -> Dict:
        """
        종목 분석 - Agent가 자율적으로 도구를 선택하여 분석

        Args:
            symbol: 종목 심볼
            context: 추가 컨텍스트

        Returns:
            분석 결과
        """
        logger.info(f"Analyzing stock with native agent: {symbol}")

        # 컨텍스트 준비
        context_str = ""
        if context:
            context_str = "\n\n추가 정보:\n"
            for key, value in context.items():
                context_str += f"- {key}: {value}\n"

        # 성과 컨텍스트 (in-context 학습)
        performance_context = ""
        symbol_history = ""
        if PERFORMANCE_TRACKING and performance_tracker is not None:
            performance_context = performance_tracker.get_performance_context(lookback_days=7)
            symbol_history = performance_tracker.get_symbol_history(symbol)

        # 초기 메시지
        user_message = f"""
{symbol} 종목을 분석하고 투자 추천을 제공하세요.
{context_str}
{symbol_history}

다음 단계를 수행하세요:
1. analyze_news_sentiment 도구로 뉴스 감성 분석
2. assess_market_risk 도구로 시장 리스크 평가
3. 필요시 search_knowledge_base 도구로 추가 정보 검색
4. 종합 분석 및 투자 추천 (BUY/SELL/HOLD/AVOID)

각 단계의 근거를 명확히 제시하세요.
"""

        # 시스템 프롬프트에 성과 컨텍스트 동적 주입
        dynamic_system_prompt = TRADING_AGENT_SYSTEM_PROMPT + performance_context

        messages = [{"role": "user", "content": user_message}]

        tools_used = []
        steps = 0
        max_iterations = config.agent_max_iterations

        try:
            # Agent loop
            while steps < max_iterations:
                steps += 1

                # Claude 호출 (tool calling) — 성과 컨텍스트가 반영된 동적 시스템 프롬프트
                response = self.client.messages.create(
                    model=config.anthropic_model,
                    max_tokens=4096,
                    temperature=config.anthropic_temperature,
                    system=dynamic_system_prompt,
                    tools=self.tools,
                    messages=messages
                )

                logger.info(f"Step {steps}: stop_reason = {response.stop_reason}")

                # 도구 사용이 필요한 경우
                if response.stop_reason == "tool_use":
                    # 응답을 메시지에 추가
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # 도구 실행
                    tool_results = []
                    for content_block in response.content:
                        if content_block.type == "tool_use":
                            tool_name = content_block.name
                            tool_input = content_block.input
                            tool_id = content_block.id

                            logger.info(f"Executing tool: {tool_name}")
                            tools_used.append(tool_name)

                            # 도구 실행
                            result = self._execute_tool(tool_name, tool_input)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": result
                            })

                    # 도구 결과를 메시지에 추가
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                # 최종 응답
                elif response.stop_reason == "end_turn":
                    # 응답 텍스트 추출
                    final_text = ""
                    for content_block in response.content:
                        if hasattr(content_block, 'text'):
                            final_text += content_block.text

                    # 점수 보정값 계산
                    score_adjustment = self.news_analyzer.calculate_score_adjustment(symbol)

                    # 추천 추출
                    recommendation = self._extract_recommendation(final_text)

                    # 성과 추적기에 추천 기록 (in-context 학습 피드백 루프)
                    if PERFORMANCE_TRACKING and performance_tracker is not None:
                        try:
                            performance_tracker.record_recommendation(
                                symbol=symbol,
                                recommendation=recommendation,
                                sentiment_score=score_adjustment,
                                analysis_summary=final_text[:200],
                            )
                        except Exception:
                            pass

                    return {
                        'analysis': final_text,
                        'score_adjustment': score_adjustment,
                        'recommendation': recommendation,
                        'steps_taken': steps,
                        'tools_used': tools_used
                    }

                else:
                    # 예상치 못한 종료
                    logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
                    break

            # 최대 반복 도달
            logger.warning(f"Max iterations ({max_iterations}) reached")
            return {
                'analysis': "분석 중 최대 반복 횟수에 도달했습니다.",
                'score_adjustment': 0.0,
                'recommendation': 'HOLD',
                'steps_taken': steps,
                'tools_used': tools_used
            }

        except Exception as e:
            logger.error(f"Error in agent analysis: {e}")
            return {
                'analysis': f"Error: {str(e)}",
                'score_adjustment': 0.0,
                'recommendation': 'HOLD',
                'steps_taken': steps,
                'tools_used': tools_used
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
            Agent 응답
        """
        try:
            messages = [{"role": "user", "content": message}]

            response = self.client.messages.create(
                model=config.anthropic_model,
                max_tokens=4096,
                temperature=config.anthropic_temperature,
                system=TRADING_AGENT_SYSTEM_PROMPT,
                tools=self.tools,
                messages=messages
            )

            # 텍스트 응답 추출
            for content_block in response.content:
                if hasattr(content_block, 'text'):
                    return content_block.text

            return "응답을 생성할 수 없습니다."

        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return f"Error: {str(e)}"

    def get_tool_names(self) -> List[str]:
        """사용 가능한 도구 목록"""
        return [tool["name"] for tool in self.tools]


# 별칭
TradingAgent = NativeTradingAgent
