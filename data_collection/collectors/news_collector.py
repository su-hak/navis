"""
뉴스 수집 및 정제 모듈
- Alpaca News API 활용
- 뉴스 크롤링 및 정제
- 감성 분석 데이터 수집
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
import pandas as pd
import re
from bs4 import BeautifulSoup


class NewsCollector:
    """뉴스 수집 및 정제기"""

    def __init__(self, api_key: str, api_secret: str):
        """
        초기화

        Args:
            api_key: Alpaca API Key
            api_secret: Alpaca API Secret
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://data.alpaca.markets/v1beta1/news"

    async def get_stock_news(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        종목 관련 뉴스 수집

        Args:
            symbols: 종목 심볼 리스트 (None이면 전체)
            start_date: 시작 날짜
            end_date: 종료 날짜
            limit: 최대 뉴스 개수

        Returns:
            List of news dictionaries
        """
        if end_date is None:
            end_date = datetime.now()

        if start_date is None:
            start_date = end_date - timedelta(days=1)

        # Build query parameters
        params = {
            'limit': limit,
            'start': start_date.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'end': end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        }

        if symbols:
            params['symbols'] = ','.join(symbols)

        headers = {
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.api_secret
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, headers=headers) as response:
                    if response.status != 200:
                        print(f"Error: HTTP {response.status}")
                        return []

                    data = await response.json()
                    news_list = []

                    for article in data.get('news', []):
                        news_item = {
                            'id': article.get('id', ''),
                            'headline': article.get('headline', ''),
                            'summary': article.get('summary', ''),
                            'author': article.get('author', ''),
                            'created_at': article.get('created_at', ''),
                            'updated_at': article.get('updated_at', ''),
                            'url': article.get('url', ''),
                            'symbols': article.get('symbols', [])
                        }
                        news_list.append(news_item)

                    return news_list

        except Exception as e:
            print(f"Error fetching news: {str(e)}")
            return []

    async def get_latest_news(
        self,
        symbol: str,
        hours: int = 24,
        limit: int = 20
    ) -> List[Dict]:
        """
        최신 뉴스 조회

        Args:
            symbol: 종목 심볼
            hours: 최근 N시간
            limit: 최대 개수

        Returns:
            List of recent news
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)

        return await self.get_stock_news([symbol], start_date, end_date, limit)

    def clean_text(self, text: str) -> str:
        """
        텍스트 정제

        Args:
            text: 원본 텍스트

        Returns:
            정제된 텍스트
        """
        if not text:
            return ""

        # Remove HTML tags
        text = BeautifulSoup(text, 'html.parser').get_text()

        # Remove URLs
        text = re.sub(r'http\S+|www.\S+', '', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)

        return text.strip()

    async def get_cleaned_news(
        self,
        symbols: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        정제된 뉴스 데이터

        Args:
            symbols: 종목 심볼 리스트
            start_date: 시작 날짜
            end_date: 종료 날짜
            limit: 최대 개수

        Returns:
            List of cleaned news
        """
        news_list = await self.get_stock_news(symbols, start_date, end_date, limit)

        cleaned_news = []
        for news in news_list:
            cleaned_item = {
                'id': news['id'],
                'headline': self.clean_text(news['headline']),
                'summary': self.clean_text(news['summary']),
                'author': news['author'],
                'created_at': news['created_at'],
                'url': news['url'],
                'symbols': news['symbols'],
                'text_length': len(self.clean_text(news['summary']))
            }
            cleaned_news.append(cleaned_item)

        return cleaned_news

    async def get_news_sentiment_data(
        self,
        symbol: str,
        days: int = 7
    ) -> pd.DataFrame:
        """
        뉴스 감성 분석용 데이터

        Args:
            symbol: 종목 심볼
            days: 최근 N일

        Returns:
            DataFrame with news data for sentiment analysis
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        news_list = await self.get_cleaned_news([symbol], start_date, end_date, limit=100)

        if not news_list:
            return pd.DataFrame()

        df = pd.DataFrame(news_list)

        # Add date column
        df['date'] = pd.to_datetime(df['created_at']).dt.date

        # Count news per day
        df['news_count'] = df.groupby('date')['id'].transform('count')

        return df

    async def get_breaking_news(
        self,
        symbols: List[str],
        minutes: int = 30
    ) -> List[Dict]:
        """
        속보 조회

        Args:
            symbols: 종목 심볼 리스트
            minutes: 최근 N분

        Returns:
            List of breaking news
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(minutes=minutes)

        news_list = await self.get_cleaned_news(symbols, start_date, end_date, limit=50)

        # Filter and prioritize
        breaking_news = []
        for news in news_list:
            # Check for breaking news keywords
            headline_lower = news['headline'].lower()
            breaking_keywords = [
                'breaking', 'alert', 'urgent', 'just in',
                'earnings', 'acquires', 'merger', 'sec filing'
            ]

            is_breaking = any(keyword in headline_lower for keyword in breaking_keywords)

            if is_breaking:
                news['priority'] = 'high'
                breaking_news.insert(0, news)
            else:
                news['priority'] = 'normal'
                breaking_news.append(news)

        return breaking_news

    async def get_news_volume(
        self,
        symbols: List[str],
        days: int = 30
    ) -> Dict[str, int]:
        """
        종목별 뉴스 볼륨

        Args:
            symbols: 종목 심볼 리스트
            days: 최근 N일

        Returns:
            {symbol: news_count} 딕셔너리
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        news_volume = {}

        for symbol in symbols:
            try:
                news_list = await self.get_stock_news([symbol], start_date, end_date, limit=1000)
                news_volume[symbol] = len(news_list)
            except Exception as e:
                print(f"Error getting news volume for {symbol}: {str(e)}")
                news_volume[symbol] = 0

        return news_volume

    async def search_keywords(
        self,
        keywords: List[str],
        symbols: Optional[List[str]] = None,
        days: int = 7
    ) -> List[Dict]:
        """
        키워드 검색

        Args:
            keywords: 검색 키워드 리스트
            symbols: 종목 필터 (선택)
            days: 검색 기간

        Returns:
            List of matching news
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        news_list = await self.get_cleaned_news(symbols, start_date, end_date, limit=200)

        matching_news = []
        for news in news_list:
            text = (news['headline'] + ' ' + news['summary']).lower()

            for keyword in keywords:
                if keyword.lower() in text:
                    news['matched_keyword'] = keyword
                    matching_news.append(news)
                    break

        return matching_news


# Example usage
async def main():
    """테스트 함수"""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('APCA-API-KEY-ID')
    api_secret = os.getenv('APCA-API-SECRET-KEY')

    if not api_key or not api_secret:
        print("Please set APCA-API-KEY-ID and APCA-API-SECRET-KEY in .env file")
        return

    collector = NewsCollector(api_key, api_secret)

    # Test: Get latest news
    symbol = 'AAPL'
    print(f"Fetching latest news for {symbol}...")
    latest_news = await collector.get_latest_news(symbol, hours=24, limit=5)

    for news in latest_news:
        print(f"\n{news['headline']}")
        print(f"Summary: {news['summary'][:100]}...")
        print(f"Created: {news['created_at']}")

    # Test: Breaking news
    symbols = ['AAPL', 'TSLA', 'NVDA']
    print(f"\n\nFetching breaking news for {symbols}...")
    breaking = await collector.get_breaking_news(symbols, minutes=120)
    print(f"Found {len(breaking)} breaking news items")

    # Test: News volume
    print(f"\n\nFetching news volume for {symbols}...")
    volume = await collector.get_news_volume(symbols, days=7)
    print(f"News volume (7 days): {volume}")


if __name__ == "__main__":
    asyncio.run(main())
