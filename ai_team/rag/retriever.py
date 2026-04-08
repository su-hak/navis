"""
RAG Retriever

벡터 스토어를 활용한 검색 및 컨텍스트 생성
"""

import logging
from typing import List, Dict, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from ai_team.rag.vector_store import VectorStoreManager
from ai_team.config import config


logger = logging.getLogger(__name__)


class RAGRetriever:
    """RAG 검색기"""

    def __init__(self, vector_store_manager: Optional[VectorStoreManager] = None):
        """
        Args:
            vector_store_manager: 벡터 스토어 매니저
        """
        self.vector_store = vector_store_manager or VectorStoreManager()

        # Anthropic Claude LLM 초기화
        self.llm = ChatAnthropic(
            model=config.anthropic_model,
            temperature=config.anthropic_temperature,
            api_key=config.anthropic_api_key
        )

    def retrieve_context(self, query: str, k: int = None) -> str:
        """
        쿼리에 대한 관련 컨텍스트 검색

        Args:
            query: 검색 쿼리
            k: 검색할 문서 개수

        Returns:
            컨텍스트 문자열
        """
        k = k or config.top_k_results

        # 벡터 스토어에서 검색
        results = self.vector_store.search(query, k=k)

        if not results:
            return "No relevant context found."

        # 컨텍스트 조합
        context_parts = []
        for i, doc in enumerate(results, 1):
            source = doc.metadata.get('source', 'Unknown')
            text = doc.page_content
            context_parts.append(f"[{i}] ({source})\n{text}")

        context = "\n\n".join(context_parts)
        return context

    def generate_answer(self, question: str, context: str = None) -> str:
        """
        RAG 기반 답변 생성

        Args:
            question: 질문
            context: 컨텍스트 (없으면 자동 검색)

        Returns:
            답변
        """
        # 컨텍스트가 없으면 검색
        if context is None:
            context = self.retrieve_context(question)

        # 프롬프트 템플릿
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 금융 시장 분석 전문가입니다.
주어진 컨텍스트를 바탕으로 질문에 정확하고 간결하게 답변하세요.

컨텍스트에 답변에 필요한 정보가 없으면 "정보가 충분하지 않습니다"라고 답변하세요.
추측하지 말고, 주어진 정보만을 바탕으로 답변하세요.
"""),
            ("user", "컨텍스트:\n{context}\n\n질문: {question}")
        ])

        # RAG 체인 구성
        chain = prompt | self.llm | StrOutputParser()

        try:
            answer = chain.invoke({
                "context": context,
                "question": question
            })
            return answer

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"Error: {str(e)}"

    def analyze_with_context(self, symbol: str, query: str) -> Dict:
        """
        특정 종목에 대한 컨텍스트 기반 분석

        Args:
            symbol: 종목 심볼
            query: 분석 질문

        Returns:
            {
                'answer': str,
                'context': str,
                'sources': List[str]
            }
        """
        # 종목 관련 컨텍스트 검색
        search_query = f"{symbol} {query}"
        results = self.vector_store.search(search_query, k=config.top_k_results)

        if not results:
            return {
                'answer': f"No information found for {symbol}",
                'context': "",
                'sources': []
            }

        # 컨텍스트 조합
        context = self.retrieve_context(search_query)

        # 답변 생성
        answer = self.generate_answer(query, context)

        # 소스 추출
        sources = [doc.metadata.get('source', 'Unknown') for doc in results]
        sources = list(set(sources))  # 중복 제거

        return {
            'answer': answer,
            'context': context,
            'sources': sources
        }

    def get_relevant_news(self, symbol: str, topic: str = None) -> List[Dict]:
        """
        종목 관련 뉴스 검색

        Args:
            symbol: 종목 심볼
            topic: 특정 주제 (선택)

        Returns:
            관련 뉴스 리스트
        """
        query = f"{symbol} stock"
        if topic:
            query += f" {topic}"

        # 뉴스만 필터링하여 검색
        results = self.vector_store.search(
            query,
            k=10,
            filter_dict={'type': 'news'}
        )

        news_list = []
        for doc in results:
            news_list.append({
                'content': doc.page_content,
                'source': doc.metadata.get('source', 'Unknown'),
                'url': doc.metadata.get('url', ''),
                'published_at': doc.metadata.get('published_at', '')
            })

        return news_list
