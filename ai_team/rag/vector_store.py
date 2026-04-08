"""
Vector Store Manager

FAISS를 사용한 벡터 DB 관리
"""

import os
import logging
from typing import List, Dict, Optional
import pickle

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from ai_team.config import config


logger = logging.getLogger(__name__)


class VectorStoreManager:
    """벡터 스토어 관리자"""

    def __init__(self, persist_directory: Optional[str] = None):
        """
        Args:
            persist_directory: 벡터 DB 저장 경로
        """
        self.persist_directory = persist_directory or config.vector_db_path
        os.makedirs(self.persist_directory, exist_ok=True)

        # OpenAI Embeddings 초기화
        self.embeddings = OpenAIEmbeddings(
            model=config.embedding_model,
            api_key=config.openai_api_key
        )

        # Text Splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            length_function=len,
        )

        # Vector Store
        self.vector_store: Optional[FAISS] = None

        # 기존 벡터 스토어 로드 시도
        self._load_vector_store()

    def _load_vector_store(self):
        """기존 벡터 스토어 로드"""
        index_path = os.path.join(self.persist_directory, "index.faiss")
        if os.path.exists(index_path):
            try:
                self.vector_store = FAISS.load_local(
                    self.persist_directory,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Loaded existing vector store")
            except Exception as e:
                logger.warning(f"Failed to load vector store: {e}")
                self.vector_store = None

    def add_documents(self, documents: List[Dict], metadata: Optional[Dict] = None):
        """
        문서를 벡터 스토어에 추가

        Args:
            documents: 문서 리스트 [{'text': str, 'metadata': dict}]
            metadata: 추가 메타데이터
        """
        if not documents:
            logger.warning("No documents to add")
            return

        # Document 객체로 변환
        docs = []
        for doc in documents:
            text = doc.get('text', '')
            doc_metadata = doc.get('metadata', {})

            if metadata:
                doc_metadata.update(metadata)

            # 텍스트 분할
            chunks = self.text_splitter.split_text(text)

            for i, chunk in enumerate(chunks):
                chunk_metadata = doc_metadata.copy()
                chunk_metadata['chunk_id'] = i
                docs.append(Document(page_content=chunk, metadata=chunk_metadata))

        # 벡터 스토어에 추가
        if self.vector_store is None:
            self.vector_store = FAISS.from_documents(docs, self.embeddings)
            logger.info(f"Created new vector store with {len(docs)} chunks")
        else:
            self.vector_store.add_documents(docs)
            logger.info(f"Added {len(docs)} chunks to vector store")

        # 저장
        self.save()

    def add_news(self, news_list: List[Dict]):
        """
        뉴스를 벡터 스토어에 추가

        Args:
            news_list: 뉴스 리스트 [{'title': str, 'description': str, ...}]
        """
        documents = []

        for news in news_list:
            text = f"{news['title']}\n\n{news['description']}"
            if news.get('content'):
                text += f"\n\n{news['content']}"

            documents.append({
                'text': text,
                'metadata': {
                    'source': news.get('source', 'Unknown'),
                    'url': news.get('url', ''),
                    'published_at': str(news.get('published_at', '')),
                    'type': 'news'
                }
            })

        self.add_documents(documents)

    def search(self, query: str, k: int = None, filter_dict: Optional[Dict] = None) -> List[Document]:
        """
        벡터 스토어에서 유사 문서 검색

        Args:
            query: 검색 쿼리
            k: 반환할 문서 개수
            filter_dict: 메타데이터 필터

        Returns:
            검색 결과 Document 리스트
        """
        if self.vector_store is None:
            logger.warning("Vector store is empty")
            return []

        k = k or config.top_k_results

        try:
            if filter_dict:
                results = self.vector_store.similarity_search(
                    query,
                    k=k,
                    filter=filter_dict
                )
            else:
                results = self.vector_store.similarity_search(query, k=k)

            logger.info(f"Found {len(results)} similar documents for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []

    def search_with_score(self, query: str, k: int = None) -> List[tuple]:
        """
        유사도 점수와 함께 검색

        Args:
            query: 검색 쿼리
            k: 반환할 문서 개수

        Returns:
            [(Document, score), ...] 형태의 리스트
        """
        if self.vector_store is None:
            logger.warning("Vector store is empty")
            return []

        k = k or config.top_k_results

        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            logger.info(f"Found {len(results)} similar documents with scores")
            return results

        except Exception as e:
            logger.error(f"Error searching with score: {e}")
            return []

    def save(self):
        """벡터 스토어를 디스크에 저장"""
        if self.vector_store is None:
            logger.warning("No vector store to save")
            return

        try:
            self.vector_store.save_local(self.persist_directory)
            logger.info(f"Saved vector store to {self.persist_directory}")
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")

    def clear(self):
        """벡터 스토어 초기화"""
        self.vector_store = None
        logger.info("Cleared vector store")

    def get_stats(self) -> Dict:
        """벡터 스토어 통계 반환"""
        if self.vector_store is None:
            return {'document_count': 0}

        try:
            # FAISS의 경우 인덱스 크기로 추정
            index = self.vector_store.index
            return {
                'document_count': index.ntotal if hasattr(index, 'ntotal') else 0,
                'persist_directory': self.persist_directory
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'document_count': 0}
