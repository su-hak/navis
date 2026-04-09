"""
QA 팀 공용 테스트 픽스처

모든 테스트 파일에서 공유하는 픽스처와 헬퍼 함수를 정의합니다.
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# 데이터 생성 헬퍼
# ============================================================

def make_ohlcv(days: int = 250, trend: str = "up", seed: int = 42) -> pd.DataFrame:
    """
    OHLCV 테스트 데이터 생성

    Args:
        days: 데이터 일수 (최소 200 권장 - 지표 워밍업)
        trend: "up" | "down" | "sideways" | "volatile"
        seed: 랜덤 시드 (재현성)

    Returns:
        DataFrame (timestamp, open, high, low, close, volume)
    """
    np.random.seed(seed)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    trend_map = {"up": 0.5, "down": -0.5, "sideways": 0.0, "volatile": 0.0}
    drift = trend_map.get(trend, 0.0)
    vol_mult = 3.0 if trend == "volatile" else 1.0

    close_prices = 100 + np.cumsum(np.random.randn(days) * 2 * vol_mult + drift)
    close_prices = np.maximum(close_prices, 1.0)  # 음수 방지

    rows = []
    for i, close in enumerate(close_prices):
        high = close * (1 + abs(np.random.randn() * 0.015))
        low = close * (1 - abs(np.random.randn() * 0.015))
        open_price = low + (high - low) * np.random.rand()
        volume = max(100_000, int(1_000_000 + np.random.randn() * 200_000))
        rows.append({
            'timestamp': dates[i].isoformat(),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': volume,
        })
    return pd.DataFrame(rows)


def make_high_volume_ohlcv(days: int = 250, seed: int = 42) -> pd.DataFrame:
    """거래량 급증 데이터 (최근 봉 거래량 3x 이상)"""
    df = make_ohlcv(days, "up", seed)
    avg_vol = df['volume'].mean()
    df.loc[df.index[-1], 'volume'] = int(avg_vol * 3.5)
    return df


def make_signal_friendly_ohlcv(days: int = 300, seed: int = 42) -> pd.DataFrame:
    """
    백테스트 시그널 생성에 유리한 데이터
    - 강한 상승 추세 (SMA20 > SMA50 > SMA200)
    - 주기적 거래량 급증 (1.5x 이상)
    - RSI 30~60 범위 유지
    """
    np.random.seed(seed)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # 강한 상승 추세 생성
    close_prices = 50.0 + np.cumsum(np.random.randn(days) * 1.5 + 1.0)
    close_prices = np.maximum(close_prices, 5.0)

    rows = []
    base_volume = 2_000_000
    for i, close in enumerate(close_prices):
        high = close * (1 + abs(np.random.randn() * 0.012))
        low = close * (1 - abs(np.random.randn() * 0.012))
        open_price = low + (high - low) * np.random.rand()

        # 주기적 거래량 급증 (20일마다)
        if i % 20 == 0:
            volume = int(base_volume * (2.0 + np.random.rand()))
        else:
            volume = max(500_000, int(base_volume + np.random.randn() * 300_000))

        rows.append({
            'timestamp': dates[i].isoformat(),
            'open': round(open_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'close': round(close, 2),
            'volume': volume,
        })
    return pd.DataFrame(rows)


# ============================================================
# pytest 픽스처
# ============================================================

@pytest.fixture(scope="session")
def uptrend_df():
    """상승 추세 250일 OHLCV 데이터"""
    return make_ohlcv(250, "up", seed=1)


@pytest.fixture(scope="session")
def downtrend_df():
    """하락 추세 250일 OHLCV 데이터"""
    return make_ohlcv(250, "down", seed=2)


@pytest.fixture(scope="session")
def sideways_df():
    """횡보 250일 OHLCV 데이터"""
    return make_ohlcv(250, "sideways", seed=3)


@pytest.fixture(scope="session")
def volatile_df():
    """고변동성 250일 OHLCV 데이터"""
    return make_ohlcv(250, "volatile", seed=4)


@pytest.fixture(scope="session")
def short_df():
    """짧은 50일 OHLCV 데이터 (워밍업 부족)"""
    return make_ohlcv(50, "up", seed=5)


@pytest.fixture
def risk_manager():
    """기본 리스크 매니저"""
    from risk_team.core.risk_manager import RiskManager
    return RiskManager(
        stop_loss_pct=0.02,
        take_profit_pct=0.06,
        max_daily_loss_pct=0.05,
        max_positions=5,
        max_exposure_pct=0.80,
        min_position_pct=0.05,
        max_position_pct=0.20,
        storage_path=None,
    )


@pytest.fixture
def account_1m():
    """100만원 계좌"""
    from risk_team.core.risk_models import AccountInfo
    return AccountInfo(
        account_id="qa-test",
        cash=1_000_000,
        portfolio_value=1_000_000,
        buying_power=1_000_000,
        equity=1_000_000,
        unrealized_pl=0.0,
        realized_pl=0.0,
    )


@pytest.fixture
def empty_positions():
    return []


@pytest.fixture
def score_calculator():
    from strategy_engine.scoring.score_calculator import ScoreCalculator
    return ScoreCalculator()


@pytest.fixture
def signal_generator():
    from strategy_engine.signals.signal_generator import SignalGenerator
    return SignalGenerator()
