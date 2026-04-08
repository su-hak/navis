"""
AI Team 예제 실행 헬퍼 스크립트

프로젝트 루트에서 AI Team 예제를 실행하기 위한 스크립트
"""

import os
import sys
import logging
from dotenv import load_dotenv

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


def main():
    """메인 함수"""
    print("\n")
    print("="*60)
    print("AI Team 기능 시연")
    print("="*60)

    # API 키 확인
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("\n⚠️  경고: ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print("   .env 파일에 ANTHROPIC_API_KEY를 설정하세요.")
        print("   발급: https://console.anthropic.com/")
        print("\n일부 기능이 제한될 수 있습니다.")
        response = input("\n계속하시겠습니까? (y/n): ")
        if response.lower() != 'y':
            print("종료합니다.")
            return

    try:
        # 1. 뉴스 분석
        example_news_analysis()

        # 2. 시장 리스크
        example_market_risk()

        print("\n" + "="*60)
        print("더 많은 예제를 보려면 ai_team/example.py를 참조하세요.")
        print("="*60 + "\n")

    except KeyboardInterrupt:
        print("\n\n중단되었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)


if __name__ == "__main__":
    main()
