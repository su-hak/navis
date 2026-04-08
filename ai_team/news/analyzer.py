"""
News Analyzer Module

뉴스 감성 분석 및 이벤트 감지
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from ai_team.news.collector import NewsCollector
from ai_team.config import config


logger = logging.getLogger(__name__)


class NewsSentiment(BaseModel):
    """뉴스 감성 분석 결과"""
    sentiment_score: float = Field(
        description="감성 점수 (-1.0 ~ 1.0, -1.0: 매우 부정, 0: 중립, 1.0: 매우 긍정)"
    )
    sentiment_label: str = Field(
        description="감성 라벨 (positive, neutral, negative)"
    )
    key_events: List[str] = Field(
        description="주요 이벤트 목록"
    )
    risk_factors: List[str] = Field(
        description="리스크 요인 목록"
    )
    summary: str = Field(
        description="뉴스 요약"
    )


class NewsAnalyzer:
    """뉴스 분석기"""

    def __init__(self):
        self.news_collector = NewsCollector()

        # Anthropic Claude LLM 초기화
        self.llm = ChatAnthropic(
            model=config.anthropic_model,
            temperature=config.anthropic_temperature,
            api_key=config.anthropic_api_key
        )

        # Pydantic 파서
        self.parser = PydanticOutputParser(pydantic_object=NewsSentiment)

        # 프롬프트 템플릿
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """당신은 금융 뉴스 분석 전문가입니다.
주어진 뉴스들을 분석하여 종목에 대한 감성 점수와 주요 이벤트, 리스크 요인을 파악하세요.

{format_instructions}

분석 기준:
1. 감성 점수 (-1.0 ~ 1.0)
   - 긍정적 뉴스: 실적 상승, 신제품 출시, 파트너십, 긍정적 전망
   - 부정적 뉴스: 실적 하락, 소송, 규제, 경영진 문제
   - 뉴스가 없으면 0.0

2. 주요 이벤트
   - 실적 발표, M&A, 신제품, 규제 변화 등

3. 리스크 요인
   - 소송, 규제 조사, 경쟁 심화, 매크로 리스크 등
"""),
            ("user", "종목: {symbol}\n\n최근 뉴스:\n{news_text}")
        ])

    def analyze_news_sentiment(self, symbol: str) -> Dict:
        """
        뉴스 감성 분석

        Args:
            symbol: 종목 심볼

        Returns:
            {
                'sentiment_score': float (-1.0 ~ 1.0),
                'sentiment_label': str (positive/neutral/negative),
                'key_events': List[str],
                'risk_factors': List[str],
                'summary': str,
                'news_count': int
            }
        """
        logger.info(f"Analyzing news sentiment for {symbol}")

        try:
            # 뉴스 수집
            news_list = self.news_collector.collect_news(symbol)

            if not news_list:
                logger.warning(f"No news found for {symbol}")
                return {
                    'sentiment_score': 0.0,
                    'sentiment_label': 'neutral',
                    'key_events': [],
                    'risk_factors': [],
                    'summary': 'No recent news available',
                    'news_count': 0
                }

            # 뉴스 텍스트 준비
            news_text = self._format_news_for_analysis(news_list)

            # LLM 분석
            chain = self.prompt_template | self.llm | self.parser

            result = chain.invoke({
                "symbol": symbol,
                "news_text": news_text,
                "format_instructions": self.parser.get_format_instructions()
            })

            # 결과 반환
            return {
                'sentiment_score': result.sentiment_score,
                'sentiment_label': result.sentiment_label,
                'key_events': result.key_events,
                'risk_factors': result.risk_factors,
                'summary': result.summary,
                'news_count': len(news_list)
            }

        except Exception as e:
            logger.error(f"Error analyzing news for {symbol}: {e}")
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'key_events': [],
                'risk_factors': [],
                'summary': f'Error: {str(e)}',
                'news_count': 0
            }

    def _format_news_for_analysis(self, news_list: List[Dict]) -> str:
        """뉴스 리스트를 분석용 텍스트로 변환"""
        news_texts = []

        for i, news in enumerate(news_list[:10], 1):  # 최대 10개
            text = f"{i}. [{news['source']}] {news['title']}"
            if news['description']:
                text += f"\n   {news['description']}"
            news_texts.append(text)

        return "\n\n".join(news_texts)

    def get_news_count(self, symbol: str) -> int:
        """최근 뉴스 개수 반환"""
        return self.news_collector.get_news_count(symbol)

    def calculate_score_adjustment(self, symbol: str) -> float:
        """
        뉴스 기반 점수 보정값 계산

        Args:
            symbol: 종목 심볼

        Returns:
            점수 보정값 (-10.0 ~ +10.0)
        """
        analysis = self.analyze_news_sentiment(symbol)

        sentiment_score = analysis['sentiment_score']
        news_count = analysis['news_count']

        # 감성 점수를 점수 보정값으로 변환
        # sentiment_score: -1.0 ~ 1.0
        # adjustment: -10.0 ~ +10.0
        base_adjustment = sentiment_score * config.max_score_adjustment

        # 뉴스 개수에 따른 가중치 (뉴스가 많을수록 신뢰도 증가)
        if news_count == 0:
            weight = 0.0
        elif news_count < 3:
            weight = 0.5
        elif news_count < 10:
            weight = 0.8
        else:
            weight = 1.0

        adjustment = base_adjustment * weight

        logger.info(
            f"Score adjustment for {symbol}: {adjustment:.2f} "
            f"(sentiment: {sentiment_score:.2f}, news_count: {news_count})"
        )

        return round(adjustment, 2)

    def assess_market_risk(self) -> Dict:
        """
        전체 시장 리스크 평가

        Returns:
            {
                'risk_level': str (low/medium/high),
                'risk_score': float (0.0 ~ 1.0),
                'factors': List[str]
            }
        """
        # 주요 지수 뉴스 분석
        indices = ['SPY', 'QQQ', 'DIA']

        risk_scores = []
        all_risk_factors = []

        for index in indices:
            analysis = self.analyze_news_sentiment(index)
            # 부정적 감성을 리스크로 변환
            risk_score = max(0, -analysis['sentiment_score'])
            risk_scores.append(risk_score)
            all_risk_factors.extend(analysis['risk_factors'])

        # 평균 리스크 점수
        avg_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0

        # 리스크 레벨 결정
        if avg_risk_score < 0.3:
            risk_level = 'low'
        elif avg_risk_score < 0.6:
            risk_level = 'medium'
        else:
            risk_level = 'high'

        return {
            'risk_level': risk_level,
            'risk_score': round(avg_risk_score, 2),
            'factors': list(set(all_risk_factors))[:5]  # 중복 제거 후 상위 5개
        }
