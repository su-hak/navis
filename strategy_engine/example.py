"""
전략 엔진 사용 예시

실제 사용 시나리오를 보여주는 예제 코드입니다.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# 프로젝트 루트를 path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from strategy_engine.indicators.technical_indicators import TechnicalIndicators
from strategy_engine.filters.stock_filter import StockFilter, FilterCriteria
from strategy_engine.scoring.score_calculator import ScoreCalculator, ScoreWeights
from strategy_engine.signals.signal_generator import SignalGenerator, TradingConditions


def create_sample_ohlcv_data(days: int = 100) -> pd.DataFrame:
    """샘플 OHLCV 데이터 생성"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    close_prices = 100 + np.cumsum(np.random.randn(days) * 2 + 0.3)

    data = []
    for i, close in enumerate(close_prices):
        high = close * (1 + abs(np.random.randn() * 0.02))
        low = close * (1 - abs(np.random.randn() * 0.02))
        open_price = low + (high - low) * np.random.rand()
        volume = int(1000000 + np.random.randn() * 200000)

        data.append({
            'timestamp': dates[i].isoformat(),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': max(100000, volume)
        })

    return pd.DataFrame(data)


def example_1_technical_indicators():
    """예제 1: 기술적 지표 계산"""
    print("\n" + "=" * 60)
    print("예제 1: 기술적 지표 계산")
    print("=" * 60)

    # 샘플 데이터 생성
    df = create_sample_ohlcv_data(100)

    # 기술적 지표 계산
    indicators = TechnicalIndicators.calculate_all_indicators(df)

    print(f"\n[AAPL 기술적 지표]")
    print(f"  RSI: {indicators.rsi:.2f}")
    print(f"  MACD: {indicators.macd:.4f}")
    print(f"  MACD Signal: {indicators.macd_signal:.4f}")
    print(f"  MACD Histogram: {indicators.macd_histogram:.4f}")
    print(f"  Bollinger Upper: ${indicators.bb_upper:.2f}")
    print(f"  Bollinger Middle: ${indicators.bb_middle:.2f}")
    print(f"  Bollinger Lower: ${indicators.bb_lower:.2f}")
    print(f"  Bollinger Position: {indicators.bb_position:.2%}")
    print(f"  SMA 20: ${indicators.sma_20:.2f}")
    print(f"  SMA 50: ${indicators.sma_50:.2f}")
    print(f"  SMA 200: ${indicators.sma_200:.2f}")
    print(f"  Volume Ratio: {indicators.volume_ratio:.2f}x")
    print(f"  Price Change: {indicators.price_change_pct:.2f}%")
    print(f"  Trend Strength: {indicators.trend_strength:.2f}/100")


def example_2_stock_filtering():
    """예제 2: 종목 필터링"""
    print("\n" + "=" * 60)
    print("예제 2: 종목 필터링")
    print("=" * 60)

    # 여러 종목의 샘플 데이터
    stock_data = {
        'AAPL': create_sample_ohlcv_data(100),
        'TSLA': create_sample_ohlcv_data(100),
        'NVDA': create_sample_ohlcv_data(100),
        'AMD': create_sample_ohlcv_data(100),
        'MSFT': create_sample_ohlcv_data(100),
    }

    # 뉴스 데이터 (예시)
    news_data = {
        'AAPL': 5,
        'TSLA': 8,
        'NVDA': 12,
        'AMD': 3,
        'MSFT': 6,
    }

    # 필터링 기준 설정
    criteria = FilterCriteria(
        min_volume_ratio=1.2,
        min_volatility=0.01,
        max_volatility=0.20,
        min_price=5.0,
        min_trend_strength=50.0,
        uptrend_only=True,
    )

    # 필터링 실행
    stock_filter = StockFilter(criteria)
    results = stock_filter.filter_stocks(stock_data, news_data)

    print(f"\n[필터링 결과]")
    for result in results:
        status = "✅ 통과" if result.passed else "❌ 미통과"
        print(f"\n{result.symbol}: {status}")
        for reason in result.reasons[:3]:  # 상위 3개 사유만 표시
            print(f"  {reason}")

    # 통과한 종목
    passed_stocks = stock_filter.get_passed_stocks(results)
    print(f"\n[필터링 통과 종목]: {', '.join(passed_stocks) if passed_stocks else '없음'}")

    # 상위 종목
    top_stocks = stock_filter.get_top_stocks(results, top_n=3, sort_by='volume_ratio')
    print(f"[상위 3개 종목 (거래량 기준)]: {', '.join(top_stocks) if top_stocks else '없음'}")


def example_3_score_calculation():
    """예제 3: 점수 계산"""
    print("\n" + "=" * 60)
    print("예제 3: 점수 계산")
    print("=" * 60)

    # 샘플 데이터
    df = create_sample_ohlcv_data(100)

    # 점수 계산기 생성
    calculator = ScoreCalculator()

    # 점수 계산
    score_result = calculator.score_stock(
        symbol='AAPL',
        df=df,
        news_sentiment=0.6,  # 긍정적 뉴스
        news_count=8,
        revenue_growth=18.0,  # 18% 매출 성장
        eps_growth=25.0,  # 25% EPS 성장
        institutional_ownership_change=4.0,  # 4% 기관 매수
    )

    print(f"\n[AAPL 종합 점수]")
    print(f"  총점: {score_result.total_score:.2f}/100")
    print(f"  추천: {score_result.recommendation}")
    print(f"\n[세부 점수]")
    print(f"  기술적 지표: {score_result.technical_score:.2f}/100")
    print(f"  거래량: {score_result.volume_score:.2f}/100")
    print(f"  추세: {score_result.trend_score:.2f}/100")
    print(f"  뉴스: {score_result.news_score:.2f}/100")
    print(f"  재무: {score_result.financial_score:.2f}/100")

    # 점수 해석
    if score_result.total_score >= 75:
        print(f"\n💰 강력 매수 추천! (점수: {score_result.total_score:.1f})")
    elif score_result.total_score >= 50:
        print(f"\n📊 보유 권장 (점수: {score_result.total_score:.1f})")
    else:
        print(f"\n📉 매도 고려 (점수: {score_result.total_score:.1f})")


def example_4_buy_signal():
    """예제 4: 매수 시그널 생성"""
    print("\n" + "=" * 60)
    print("예제 4: 매수 시그널 생성")
    print("=" * 60)

    # 샘플 데이터
    df = create_sample_ohlcv_data(100)

    # 거래량 증가 시뮬레이션
    df.loc[df.index[-1], 'volume'] = int(df['volume'].mean() * 2.5)

    # 시그널 생성기
    signal_gen = SignalGenerator()

    # 매수 시그널 생성
    buy_signal = signal_gen.generate_buy_signal(
        symbol='NVDA',
        df=df,
        news_sentiment=0.7,
        news_count=10,
        revenue_growth=30.0,
        eps_growth=35.0,
    )

    if buy_signal:
        print(f"\n🚀 매수 시그널 생성!")
        print(f"  종목: {buy_signal.symbol}")
        print(f"  점수: {buy_signal.score:.2f}/100")
        print(f"  신뢰도: {buy_signal.confidence:.2%}")
        print(f"  진입가: ${buy_signal.entry_price:.2f}")
        print(f"  목표가: ${buy_signal.target_price:.2f} (+{((buy_signal.target_price/buy_signal.entry_price-1)*100):.1f}%)")
        print(f"  손절가: ${buy_signal.stop_loss_price:.2f} ({((buy_signal.stop_loss_price/buy_signal.entry_price-1)*100):.1f}%)")
        print(f"\n[시그널 근거]")
        for reason in buy_signal.reasons:
            print(f"  {reason}")
    else:
        print("\n⚠️ 매수 시그널 미생성 (조건 미충족)")


def example_5_sell_signal():
    """예제 5: 매도 시그널 생성"""
    print("\n" + "=" * 60)
    print("예제 5: 매도 시그널 생성")
    print("=" * 60)

    # 시그널 생성기
    signal_gen = SignalGenerator()

    # 시나리오 1: 익절 (목표 수익 달성)
    print("\n[시나리오 1: 익절]")
    df_profit = create_sample_ohlcv_data(50)
    entry_price = 100.0
    df_profit.loc[df_profit.index[-1], 'close'] = entry_price * 1.12  # 12% 상승

    sell_signal = signal_gen.generate_sell_signal(
        symbol='NVDA',
        df=df_profit,
        entry_price=entry_price,
        previous_score=85.0,
    )

    if sell_signal:
        profit_pct = sell_signal.metadata.get('profit_pct', 0)
        print(f"  ✅ 시그널: {sell_signal.signal_type.value}")
        print(f"  수익률: {profit_pct:.2%}")
        print(f"  근거: {sell_signal.reasons[0]}")

    # 시나리오 2: 손절 (손절 기준 도달)
    print("\n[시나리오 2: 손절]")
    df_loss = create_sample_ohlcv_data(50)
    df_loss.loc[df_loss.index[-1], 'close'] = entry_price * 0.97  # 3% 하락

    stop_signal = signal_gen.generate_sell_signal(
        symbol='NVDA',
        df=df_loss,
        entry_price=entry_price,
    )

    if stop_signal:
        profit_pct = stop_signal.metadata.get('profit_pct', 0)
        print(f"  ✅ 시그널: {stop_signal.signal_type.value}")
        print(f"  손실률: {profit_pct:.2%}")
        print(f"  근거: {stop_signal.reasons[0]}")


def example_6_full_workflow():
    """예제 6: 전체 워크플로우"""
    print("\n" + "=" * 60)
    print("예제 6: 전체 매매 워크플로우")
    print("=" * 60)

    print("\n[1단계] 종목 데이터 생성")
    stock_data = {
        'AAPL': create_sample_ohlcv_data(100),
        'TSLA': create_sample_ohlcv_data(100),
        'NVDA': create_sample_ohlcv_data(100),
        'AMD': create_sample_ohlcv_data(100),
    }
    print(f"  ✅ {len(stock_data)}개 종목 데이터 준비 완료")

    print("\n[2단계] 종목 필터링")
    stock_filter = StockFilter()
    filter_results = stock_filter.filter_stocks(stock_data)
    passed_stocks = stock_filter.get_passed_stocks(filter_results)
    print(f"  ✅ 필터링 통과: {', '.join(passed_stocks)}")

    print("\n[3단계] 점수 계산 및 순위")
    calculator = ScoreCalculator()
    scores = []

    for symbol in passed_stocks:
        df = stock_data[symbol]
        score_result = calculator.score_stock(
            symbol=symbol,
            df=df,
            news_sentiment=np.random.uniform(0.3, 0.8),
            news_count=np.random.randint(5, 15),
        )
        scores.append((symbol, score_result))

    scores.sort(key=lambda x: x[1].total_score, reverse=True)

    for symbol, score_result in scores:
        print(f"  {symbol}: {score_result.total_score:.1f}점 ({score_result.recommendation})")

    print("\n[4단계] 매수 시그널 생성")
    signal_gen = SignalGenerator()
    buy_signals = []

    for symbol in passed_stocks:
        df = stock_data[symbol]
        signal = signal_gen.generate_buy_signal(symbol, df)
        if signal:
            buy_signals.append(signal)

    buy_signals.sort(key=lambda s: (s.score, s.confidence), reverse=True)

    if buy_signals:
        print(f"  ✅ {len(buy_signals)}개 매수 시그널 생성")

        print("\n[5단계] 최종 매수 추천 (Top 3)")
        for i, signal in enumerate(buy_signals[:3], 1):
            print(f"\n  {i}. {signal.symbol}")
            print(f"     점수: {signal.score:.1f}/100 | 신뢰도: {signal.confidence:.1%}")
            print(f"     진입: ${signal.entry_price:.2f}")
            print(f"     목표: ${signal.target_price:.2f}")
            print(f"     손절: ${signal.stop_loss_price:.2f}")
    else:
        print("  ⚠️ 매수 시그널 없음")


def main():
    """메인 함수"""
    print("=" * 60)
    print("전략 엔진 (Strategy Engine) 사용 예시")
    print("=" * 60)

    # 예제 실행
    example_1_technical_indicators()
    example_2_stock_filtering()
    example_3_score_calculation()
    example_4_buy_signal()
    example_5_sell_signal()
    example_6_full_workflow()

    print("\n" + "=" * 60)
    print("🎉 모든 예제 실행 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
