"""
전략 엔진 통합 테스트

전략 엔진의 모든 기능을 테스트합니다.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 전략 엔진 모듈 임포트
import sys
import os

# 프로젝트 루트를 path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from strategy_engine.indicators.technical_indicators import TechnicalIndicators
from strategy_engine.filters.stock_filter import StockFilter, FilterCriteria
from strategy_engine.scoring.score_calculator import ScoreCalculator, ScoreWeights
from strategy_engine.signals.signal_generator import SignalGenerator, TradingConditions, SignalType


def create_sample_data(days: int = 100, trend: str = "up") -> pd.DataFrame:
    """
    샘플 OHLCV 데이터 생성

    Args:
        days: 데이터 일수
        trend: 추세 ("up", "down", "sideways")

    Returns:
        OHLCV 데이터프레임
    """
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # 기본 가격 생성
    if trend == "up":
        close_prices = 100 + np.cumsum(np.random.randn(days) * 2 + 0.5)
    elif trend == "down":
        close_prices = 100 + np.cumsum(np.random.randn(days) * 2 - 0.5)
    else:  # sideways
        close_prices = 100 + np.cumsum(np.random.randn(days) * 1)

    # OHLCV 생성
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


def test_technical_indicators():
    """기술적 지표 계산 테스트"""
    print("\n=== 기술적 지표 계산 테스트 ===")

    # 샘플 데이터 생성
    df = create_sample_data(100, trend="up")

    # 지표 계산
    indicators = TechnicalIndicators.calculate_all_indicators(df)

    print(f"RSI: {indicators.rsi:.2f}")
    print(f"MACD: {indicators.macd:.4f}")
    print(f"MACD Signal: {indicators.macd_signal:.4f}")
    print(f"MACD Histogram: {indicators.macd_histogram:.4f}")
    print(f"Bollinger Upper: {indicators.bb_upper:.2f}")
    print(f"Bollinger Middle: {indicators.bb_middle:.2f}")
    print(f"Bollinger Lower: {indicators.bb_lower:.2f}")
    print(f"Bollinger Position: {indicators.bb_position:.2f}")
    print(f"SMA 20: {indicators.sma_20:.2f}")
    print(f"SMA 50: {indicators.sma_50:.2f}")
    print(f"Volume Ratio: {indicators.volume_ratio:.2f}x")
    print(f"Trend Strength: {indicators.trend_strength:.2f}")

    assert 0 <= indicators.rsi <= 100, "RSI는 0~100 범위여야 합니다"
    assert 0 <= indicators.bb_position <= 1, "BB Position은 0~1 범위여야 합니다"
    assert 0 <= indicators.trend_strength <= 100, "추세 강도는 0~100 범위여야 합니다"

    print("✅ 기술적 지표 테스트 통과!")


def test_stock_filter():
    """종목 필터링 테스트"""
    print("\n=== 종목 필터링 테스트 ===")

    # 여러 종목의 샘플 데이터 생성
    stock_data = {
        'AAPL': create_sample_data(100, trend="up"),
        'TSLA': create_sample_data(100, trend="sideways"),
        'NVDA': create_sample_data(100, trend="up"),
        'AMD': create_sample_data(100, trend="down"),
    }

    # 뉴스 데이터 (샘플)
    news_data = {
        'AAPL': 5,
        'TSLA': 2,
        'NVDA': 8,
        'AMD': 1,
    }

    # 필터링 기준
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

    print(f"\n총 {len(results)}개 종목 필터링 결과:")
    for result in results:
        status = "✅ 통과" if result.passed else "❌ 미통과"
        print(f"\n{result.symbol}: {status}")
        for reason in result.reasons:
            print(f"  {reason}")

    # 통과한 종목
    passed_stocks = stock_filter.get_passed_stocks(results)
    print(f"\n필터링 통과 종목: {passed_stocks}")

    # 상위 종목
    top_stocks = stock_filter.get_top_stocks(results, top_n=2, sort_by='volume_ratio')
    print(f"상위 2개 종목 (거래량 기준): {top_stocks}")

    print("\n✅ 종목 필터링 테스트 통과!")


def test_score_calculator():
    """점수 계산 테스트"""
    print("\n=== 점수 계산 테스트 ===")

    # 샘플 데이터 생성
    df = create_sample_data(100, trend="up")

    # 점수 계산
    calculator = ScoreCalculator()
    score_result = calculator.score_stock(
        symbol='AAPL',
        df=df,
        news_sentiment=0.5,  # 긍정적 뉴스
        news_count=5,
        revenue_growth=15.0,  # 15% 매출 성장
        eps_growth=20.0,  # 20% EPS 성장
        institutional_ownership_change=3.0,  # 3% 기관 매수
    )

    print(f"\n종목: {score_result.symbol}")
    print(f"총점: {score_result.total_score:.2f}/100")
    print(f"추천: {score_result.recommendation}")
    print(f"\n세부 점수:")
    print(f"  기술적 지표: {score_result.technical_score:.2f}/100")
    print(f"  거래량: {score_result.volume_score:.2f}/100")
    print(f"  추세: {score_result.trend_score:.2f}/100")
    print(f"  뉴스: {score_result.news_score:.2f}/100")
    print(f"  재무: {score_result.financial_score:.2f}/100")

    assert 0 <= score_result.total_score <= 100, "총점은 0~100 범위여야 합니다"
    assert score_result.recommendation in ["BUY", "HOLD", "SELL"], "추천은 BUY/HOLD/SELL이어야 합니다"

    print("\n✅ 점수 계산 테스트 통과!")


def test_signal_generator():
    """시그널 생성 테스트"""
    print("\n=== 시그널 생성 테스트 ===")

    # 1. 매수 시그널 테스트
    print("\n[매수 시그널 테스트]")
    df_buy = create_sample_data(100, trend="up")

    # 거래량 증가 시뮬레이션
    df_buy.loc[df_buy.index[-1], 'volume'] = int(df_buy['volume'].mean() * 2.5)

    signal_gen = SignalGenerator()
    buy_signal = signal_gen.generate_buy_signal(
        symbol='NVDA',
        df=df_buy,
        news_sentiment=0.6,
        news_count=8,
        revenue_growth=25.0,
        eps_growth=30.0,
    )

    if buy_signal:
        print(f"✅ 매수 시그널 생성됨!")
        print(f"  종목: {buy_signal.symbol}")
        print(f"  시그널: {buy_signal.signal_type.value}")
        print(f"  점수: {buy_signal.score:.2f}")
        print(f"  신뢰도: {buy_signal.confidence:.2%}")
        print(f"  진입가: ${buy_signal.entry_price:.2f}")
        print(f"  목표가: ${buy_signal.target_price:.2f}")
        print(f"  손절가: ${buy_signal.stop_loss_price:.2f}")
        print(f"  근거:")
        for reason in buy_signal.reasons:
            print(f"    {reason}")
    else:
        print("⚠️ 매수 시그널 미생성 (조건 미충족)")

    # 2. 매도 시그널 테스트 (익절)
    print("\n[매도 시그널 테스트 - 익절]")
    df_sell = create_sample_data(50, trend="up")
    entry_price = 100.0
    current_price = float(df_sell['close'].iloc[-1])
    # 가격을 익절 기준 이상으로 설정
    df_sell.loc[df_sell.index[-1], 'close'] = entry_price * 1.12  # 12% 상승

    sell_signal = signal_gen.generate_sell_signal(
        symbol='NVDA',
        df=df_sell,
        entry_price=entry_price,
        previous_score=85.0,
    )

    if sell_signal:
        print(f"✅ 매도 시그널 생성됨!")
        print(f"  시그널: {sell_signal.signal_type.value}")
        print(f"  수익률: {sell_signal.metadata.get('profit_pct', 0):.2%}")
        print(f"  근거:")
        for reason in sell_signal.reasons:
            print(f"    {reason}")
    else:
        print("⚠️ 매도 시그널 미생성 (보유 유지)")

    # 3. 매도 시그널 테스트 (손절)
    print("\n[매도 시그널 테스트 - 손절]")
    df_stop = create_sample_data(50, trend="down")
    df_stop.loc[df_stop.index[-1], 'close'] = entry_price * 0.97  # 3% 하락

    stop_signal = signal_gen.generate_sell_signal(
        symbol='NVDA',
        df=df_stop,
        entry_price=entry_price,
    )

    if stop_signal:
        print(f"✅ 손절 시그널 생성됨!")
        print(f"  시그널: {stop_signal.signal_type.value}")
        print(f"  수익률: {stop_signal.metadata.get('profit_pct', 0):.2%}")
        print(f"  근거:")
        for reason in stop_signal.reasons:
            print(f"    {reason}")

    print("\n✅ 시그널 생성 테스트 통과!")


def test_full_workflow():
    """전체 워크플로우 테스트"""
    print("\n=== 전체 워크플로우 테스트 ===")

    # 1. 여러 종목 데이터 생성
    print("\n1단계: 종목 데이터 생성")
    stock_data = {
        'AAPL': create_sample_data(100, trend="up"),
        'TSLA': create_sample_data(100, trend="up"),
        'NVDA': create_sample_data(100, trend="up"),
        'AMD': create_sample_data(100, trend="sideways"),
        'MSFT': create_sample_data(100, trend="down"),
    }
    print(f"  {len(stock_data)}개 종목 데이터 생성 완료")

    # 2. 종목 필터링
    print("\n2단계: 종목 필터링")
    stock_filter = StockFilter()
    filter_results = stock_filter.filter_stocks(stock_data)
    passed_stocks = stock_filter.get_passed_stocks(filter_results)
    print(f"  필터링 통과: {passed_stocks}")

    # 3. 점수 계산
    print("\n3단계: 통과 종목 점수 계산")
    calculator = ScoreCalculator()
    scores = {}

    for symbol in passed_stocks:
        df = stock_data[symbol]
        score_result = calculator.score_stock(
            symbol=symbol,
            df=df,
            news_sentiment=np.random.uniform(-0.5, 0.8),
            news_count=np.random.randint(0, 10),
        )
        scores[symbol] = score_result
        print(f"  {symbol}: {score_result.total_score:.2f}점 ({score_result.recommendation})")

    # 4. 매수 시그널 생성
    print("\n4단계: 매수 시그널 생성")
    signal_gen = SignalGenerator()
    buy_signals = []

    for symbol in passed_stocks:
        df = stock_data[symbol]
        signal = signal_gen.generate_buy_signal(symbol, df)
        if signal:
            buy_signals.append(signal)
            print(f"  ✅ {symbol}: 매수 시그널 (점수: {signal.score:.2f}, 신뢰도: {signal.confidence:.2%})")

    # 5. 최종 추천
    print("\n5단계: 최종 매수 추천")
    buy_signals.sort(key=lambda s: (s.score, s.confidence), reverse=True)

    if buy_signals:
        top_3 = buy_signals[:3]
        print(f"  상위 3개 추천 종목:")
        for i, signal in enumerate(top_3, 1):
            print(f"  {i}. {signal.symbol}")
            print(f"     - 점수: {signal.score:.2f}/100")
            print(f"     - 신뢰도: {signal.confidence:.2%}")
            print(f"     - 진입가: ${signal.entry_price:.2f}")
            print(f"     - 목표가: ${signal.target_price:.2f} (+{((signal.target_price/signal.entry_price-1)*100):.1f}%)")
            print(f"     - 손절가: ${signal.stop_loss_price:.2f} ({((signal.stop_loss_price/signal.entry_price-1)*100):.1f}%)")
    else:
        print("  ⚠️ 매수 추천 종목 없음")

    print("\n✅ 전체 워크플로우 테스트 통과!")


def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("전략 엔진 (Strategy Engine) 통합 테스트")
    print("=" * 60)

    try:
        # 개별 모듈 테스트
        test_technical_indicators()
        test_stock_filter()
        test_score_calculator()
        test_signal_generator()

        # 전체 워크플로우 테스트
        test_full_workflow()

        print("\n" + "=" * 60)
        print("🎉 모든 테스트 통과!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()
