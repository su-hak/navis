"""
News Collector Module

뉴스 데이터 수집 및 크롤링
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import feedparser

from ai_team.config import config


logger = logging.getLogger(__name__)


class NewsCollector:
    """뉴스 수집기"""

    def __init__(self):
        self.news_api_key = config.news_api_key
        self.sources = config.news_sources
        self.max_news = config.max_news_per_symbol
        self.lookback_hours = config.news_lookback_hours

    def collect_news(self, symbol: str) -> List[Dict]:
        """
        특정 종목에 대한 뉴스 수집

        Args:
            symbol: 종목 심볼 (예: AAPL, TSLA)

        Returns:
            뉴스 리스트 [
                {
                    'title': str,
                    'description': str,
                    'content': str,
                    'source': str,
                    'published_at': datetime,
                    'url': str
                }
            ]
        """
        logger.info(f"Collecting news for {symbol}")

        news_list = []

        # NewsAPI 사용
        if self.news_api_key:
            news_list.extend(self._collect_from_newsapi(symbol))

        # RSS 피드 사용 (무료)
        news_list.extend(self._collect_from_rss(symbol))

        # 중복 제거 및 정렬
        news_list = self._deduplicate_news(news_list)
        news_list = sorted(news_list, key=lambda x: x['published_at'], reverse=True)

        # 최대 개수 제한
        news_list = news_list[:self.max_news]

        logger.info(f"Collected {len(news_list)} news articles for {symbol}")
        return news_list

    def _collect_from_newsapi(self, symbol: str) -> List[Dict]:
        """NewsAPI에서 뉴스 수집"""
        if not self.news_api_key:
            return []

        try:
            url = "https://newsapi.org/v2/everything"

            # 날짜 범위 설정
            from_date = datetime.now() - timedelta(hours=self.lookback_hours)

            params = {
                'q': symbol,
                'apiKey': self.news_api_key,
                'language': 'en',
                'sortBy': 'publishedAt',
                'from': from_date.isoformat(),
                'pageSize': self.max_news
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            news_list = []
            for article in data.get('articles', []):
                news_list.append({
                    'title': article.get('title', ''),
                    'description': article.get('description', ''),
                    'content': article.get('content', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'published_at': datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00')),
                    'url': article.get('url', '')
                })

            return news_list

        except Exception as e:
            logger.error(f"Error collecting from NewsAPI: {e}")
            return []

    def _collect_from_rss(self, symbol: str) -> List[Dict]:
        """RSS 피드에서 뉴스 수집 (무료 대안)"""
        news_list = []

        # Google News RSS
        try:
            rss_url = f"https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)

            for entry in feed.entries[:self.max_news]:
                # 발행 시간 파싱
                published_at = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    from time import mktime
                    published_at = datetime.fromtimestamp(mktime(entry.published_parsed))

                news_list.append({
                    'title': entry.get('title', ''),
                    'description': entry.get('summary', ''),
                    'content': entry.get('summary', ''),
                    'source': 'Google News',
                    'published_at': published_at,
                    'url': entry.get('link', '')
                })

        except Exception as e:
            logger.error(f"Error collecting from RSS: {e}")

        return news_list

    def _deduplicate_news(self, news_list: List[Dict]) -> List[Dict]:
        """뉴스 중복 제거 (제목 기준)"""
        seen_titles = set()
        unique_news = []

        for news in news_list:
            title = news['title'].lower().strip()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_news.append(news)

        return unique_news

    def get_news_count(self, symbol: str) -> int:
        """특정 종목의 최근 뉴스 개수 반환"""
        news_list = self.collect_news(symbol)
        return len(news_list)

    def search_news_by_keywords(self, keywords: List[str]) -> List[Dict]:
        """키워드로 뉴스 검색"""
        query = " OR ".join(keywords)
        return self.collect_news(query)
