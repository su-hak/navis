"""
AI Team 사용 예제

이 스크립트는 AI Team의 주요 기능을 시연합니다.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# 부모 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_news_analysis():
    """뉴스 분석 예제"""
    from ai_team.news.analyzer import NewsAnalyzer

    print("\n" + "="*60)
    print("1. 뉴스 감성 분석 예제")
    print("="*60)

    analyzer = NewsAnalyzer()

    # 종목 분석
    symbol = 'AAPL'
    print(f"\n종목: {symbol}")

    # 뉴스 감성 분석
    result = analyzer.analyze_news_sentiment(symbol)

    print(f"\n감성 점수: {result['sentiment_score']:.2f} ({result['sentiment_label']})")
    print(f"뉴스 개수: {result['news_count']}")

    if result['key_events']:
        print("\n주요 이벤트:")
        for event in result['key_events']:
            print(f"  - {event}")

    if result['risk_factors']:
        print("\n리스크 요인:")
        for risk in result['risk_factors']:
            print(f"  - {risk}")

    print(f"\n요약: {result['summary']}")

    # 점수 보정값 계산
    adjustment = analyzer.calculate_score_adjustment(symbol)
    print(f"\n점수 보정값: {adjustment:+.2f}")


def example_market_risk():
    """시장 리스크 평가 예제"""
    from ai_team.news.analyzer import NewsAnalyzer

    print("\n" + "="*60)
    print("2. 시장 리스크 평가 예제")
    print("="*60)

    analyzer = NewsAnalyzer()

    result = analyzer.assess_market_risk()

    print(f"\n리스크 레벨: {result['risk_level'].upper()}")
    print(f"리스크 점수: {result['risk_score']:.2f}")

    if result['factors']:
        print("\n주요 리스크 요인:")
        for factor in result['factors']:
            print(f"  - {factor}")


def example_rag_system():
    """RAG 시스템 예제"""
    from ai_team.rag.vector_store import VectorStoreManager
    from ai_team.rag.retriever import RAGRetriever

    print("\n" + "="*60)
    print("3. RAG 시스템 예제")
    print("="*60)

    # 벡터 스토어 초기화
    vector_store = VectorStoreManager()

    # 샘플 뉴스 추가
    sample_news = [
        {
            'title': 'Apple Announces Record iPhone Sales',
            'description': 'Apple reported record-breaking iPhone sales in Q4...',
            'content': 'Full article content here...',
            'source': 'Reuters',
            'url': 'https://example.com/news1',
            'published_at': '2024-01-15'
        },
        {
            'title': 'Tesla Expands Gigafactory Production',
            'description': 'Tesla announced expansion of its Texas Gigafactory...',
            'content': 'Full article content here...',
            'source': 'Bloomberg',
            'url': 'https://example.com/news2',
            'published_at': '2024-01-14'
        }
    ]

    print("\n뉴스 추가 중...")
    vector_store.add_news(sample_news)

    # 통계
    stats = vector_store.get_stats()
    print(f"벡터 DB 문서 수: {stats['document_count']}")

    # RAG 검색
    retriever = RAGRetriever(vector_store)

    query = "What are the latest news about Apple?"
    print(f"\n검색 쿼리: {query}")

    context = retriever.retrieve_context(query, k=2)
    print(f"\n검색 결과:\n{context[:500]}...")  # 처음 500자만 출력


def example_trading_agent():
    """Trading Agent 예제"""
    from ai_team.agents.trading_agent import TradingAgent

    print("\n" + "="*60)
    print("4. Trading Agent 예제")
    print("="*60)

    agent = TradingAgent()

    # 종목 분석
    symbol = 'NVDA'
    context = {
        'base_score': 78,
        'rsi': 65,
        'macd': 'bullish',
        'volume_change': '+25%'
    }

    print(f"\n종목 분석: {symbol}")
    print(f"컨텍스트: {context}")

    result = agent.analyze_stock(symbol, context)

    print(f"\n분석 결과:")
    print(f"{result['analysis']}")
    print(f"\n점수 보정: {result['score_adjustment']:+.2f}")
    print(f"추천: {result['recommendation']}")

    # 대화
    print("\n" + "-"*60)
    print("Agent와 대화:")

    message = "What's your opinion on tech stocks today?"
    print(f"\nYou: {message}")

    response = agent.chat(message)
    print(f"\nAgent: {response}")


def example_api_integration():
    """API 통합 예제"""
    import requests

    print("\n" + "="*60)
    print("5. API 통합 예제")
    print("="*60)

    api_base_url = "http://localhost:8001"

    # 헬스 체크
    print("\nAPI 헬스 체크...")
    try:
        response = requests.get(f"{api_base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✓ API 서버 정상")
            print(f"  {response.json()}")
        else:
            print("✗ API 서버 응답 이상")
            return
    except requests.exceptions.RequestException as e:
        print(f"✗ API 서버에 연결할 수 없습니다: {e}")
        print("\n먼저 API 서버를 실행하세요:")
        print("  python -m uvicorn ai_team.api.main:app --port 8001")
        return

    # 뉴스 분석 API 호출
    print("\n뉴스 분석 API 호출...")
    response = requests.post(
        f"{api_base_url}/api/news/analyze",
        json={'symbol': 'MSFT'},
        timeout=30
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ 감성 점수: {result['sentiment_score']:.2f}")
        print(f"  뉴스 개수: {result['news_count']}")
    else:
        print(f"✗ 오류: {response.status_code}")


def main():
    """메인 함수"""
    print("\n")
    print("="*60)
    print("AI Team 기능 시연")
    print("="*60)

    # API 키 확인
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("\n⚠️  경고: ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일에 API 키를 설정하세요.")
        print("\n일부 기능이 제한될 수 있습니다.")
        input("\n계속하려면 Enter를 누르세요...")

    try:
        # 1. 뉴스 분석
        example_news_analysis()

        # 2. 시장 리스크
        example_market_risk()

        # 3. RAG 시스템
        example_rag_system()

        # 4. Trading Agent
        example_trading_agent()

        # 5. API 통합 (선택)
        print("\n" + "="*60)
        response = input("\nAPI 통합 예제를 실행하시겠습니까? (y/n): ")
        if response.lower() == 'y':
            example_api_integration()

    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)

    print("\n" + "="*60)
    print("시연 완료!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
