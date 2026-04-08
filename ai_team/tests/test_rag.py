"""
Tests for RAG System
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from ai_team.rag.vector_store import VectorStoreManager


class TestVectorStoreManager:
    """VectorStoreManager 테스트"""

    @pytest.fixture
    def temp_dir(self):
        """임시 디렉토리 생성"""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def vector_store(self, temp_dir):
        """VectorStoreManager 인스턴스 생성"""
        return VectorStoreManager(persist_directory=temp_dir)

    def test_add_documents(self, vector_store):
        """문서 추가 테스트"""
        documents = [
            {
                'text': 'Apple announced new iPhone with AI features',
                'metadata': {'source': 'Tech News', 'type': 'news'}
            },
            {
                'text': 'Tesla stock surges on earnings beat',
                'metadata': {'source': 'Financial Times', 'type': 'news'}
            }
        ]

        vector_store.add_documents(documents)

        # 통계 확인
        stats = vector_store.get_stats()
        assert stats['document_count'] > 0

    def test_search(self, vector_store):
        """검색 테스트"""
        # 문서 추가
        documents = [
            {
                'text': 'Apple launches new MacBook Pro with M3 chip',
                'metadata': {'source': 'Apple News'}
            }
        ]
        vector_store.add_documents(documents)

        # 검색
        results = vector_store.search('Apple MacBook', k=1)

        # 결과 확인
        assert len(results) > 0

    def test_add_news(self, vector_store):
        """뉴스 추가 테스트"""
        news_list = [
            {
                'title': 'Tesla announces new Gigafactory',
                'description': 'Tesla is building a new factory in Texas',
                'content': 'Full article content here',
                'source': 'Reuters',
                'url': 'https://example.com',
                'published_at': '2024-01-01'
            }
        ]

        vector_store.add_news(news_list)

        stats = vector_store.get_stats()
        assert stats['document_count'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
