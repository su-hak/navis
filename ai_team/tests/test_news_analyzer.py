"""
Tests for News Analyzer
"""

import pytest
from unittest.mock import Mock, patch

from ai_team.news.analyzer import NewsAnalyzer


class TestNewsAnalyzer:
    """NewsAnalyzer 테스트"""

    @pytest.fixture
    def analyzer(self):
        """NewsAnalyzer 인스턴스 생성"""
        return NewsAnalyzer()

    @patch('ai_team.news.analyzer.NewsCollector')
    def test_analyze_news_sentiment_no_news(self, mock_collector, analyzer):
        """뉴스가 없을 때 중립 반환"""
        # Mock 설정
        mock_collector.return_value.collect_news.return_value = []

        # 테스트
        result = analyzer.analyze_news_sentiment('AAPL')

        # 검증
        assert result['sentiment_score'] == 0.0
        assert result['sentiment_label'] == 'neutral'
        assert result['news_count'] == 0

    def test_calculate_score_adjustment_range(self, analyzer):
        """점수 보정값이 범위 내에 있는지 확인"""
        # Mock을 사용하여 뉴스 분석 결과 설정
        with patch.object(analyzer, 'analyze_news_sentiment') as mock_analyze:
            mock_analyze.return_value = {
                'sentiment_score': 0.8,
                'sentiment_label': 'positive',
                'key_events': ['New product launch'],
                'risk_factors': [],
                'summary': 'Positive news',
                'news_count': 10
            }

            adjustment = analyzer.calculate_score_adjustment('AAPL')

            # 범위 확인
            assert -10.0 <= adjustment <= 10.0

    def test_get_news_count(self, analyzer):
        """뉴스 개수 조회 테스트"""
        with patch.object(analyzer.news_collector, 'get_news_count') as mock_count:
            mock_count.return_value = 5

            count = analyzer.get_news_count('TSLA')

            assert count == 5
            mock_count.assert_called_once_with('TSLA')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
