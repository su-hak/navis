"""
Trading Constants — Single Source of Truth

이 파일이 모든 전략/리스크/백테스트 모듈의 유일한 파라미터 출처다.
다른 곳에서 os.getenv() 로 전략 수치를 직접 읽지 말 것.

[ 운영자 파라미터 조정 방법 ]
  .env 파일에서 아래 변수를 설정하면 코드 수정 없이 반영된다.
  설정하지 않으면 이 파일의 기본값이 사용된다.
  실거래 엔진과 백테스트 엔진이 모두 이 파일을 import 하므로
  .env 에서 수정하면 양쪽에 자동으로 동일하게 적용된다.
"""
import os


def _pct(env_key: str, default: float) -> float:
    """소수 비율로 변환 (env 값은 % 단위, 예: '1.0' → 0.010)"""
    raw = os.getenv(env_key)
    return float(raw) / 100.0 if raw is not None else default


def _float(env_key: str, default: float) -> float:
    """그대로 float 변환"""
    raw = os.getenv(env_key)
    return float(raw) if raw is not None else default


# ─── Take-Profit / Stop-Loss ────────────────────────────────────────────────
# 운영자 조정 가능: .env 에 TAKE_PROFIT_PCT=6.0, STOP_LOSS_PCT=2.0 형태로 설정 (% 단위)
TAKE_PROFIT_PCT: float = _pct('TAKE_PROFIT_PCT', 0.06)    # 기본 +6%
STOP_LOSS_PCT:   float = _pct('STOP_LOSS_PCT',   0.02)    # 기본 -2%

# ATR 기반 동적 SL/TP 배율
# 운영자 조정 가능: .env 에 ATR_SL_MULTIPLIER=1.5 형태로 설정 (배율 단위)
ATR_SL_MULTIPLIER: float = _float('ATR_SL_MULTIPLIER', 1.5)   # SL = entry − 1.5 × ATR14
ATR_TP_MULTIPLIER: float = _float('ATR_TP_MULTIPLIER', 3.0)   # TP = entry + 3.0 × ATR14

# ─── Trailing Stop ───────────────────────────────────────────────────────────
# 운영자 조정 가능: .env 에 TRAILING_STOP_PCT=2.0, PARTIAL_TP_PCT=3.0 (% 단위)
TRAILING_STOP_PCT: float = _pct('TRAILING_STOP_PCT', 0.02)    # 기본 고점 대비 -2%
PARTIAL_TP_PCT:    float = _pct('PARTIAL_TP_PCT',    0.03)    # 기본 +3% 분할 청산

# ─── Position Sizing ─────────────────────────────────────────────────────────
MAX_POSITION_PCT: float = 0.10      # 단일 포지션 최대 10%
MIN_POSITION_PCT: float = 0.03      # 단일 포지션 최소 3%

# ─── Market Gate Thresholds ──────────────────────────────────────────────────
VIX_HARD_GATE:      float = 25.0    # VIX > 25 → 신규 진입 전면 차단
SPY_DAILY_DROP_GATE: float = -0.02  # SPY 당일 -2% 이하 → 차단

# ─── Scoring ─────────────────────────────────────────────────────────────────
BUY_SIGNAL_THRESHOLD: float = 75.0  # 총 점수 >= 75 → 매수 신호

# ─── Slippage / Commission (backtest) ────────────────────────────────────────
BACKTEST_SLIPPAGE_PCT:  float = 0.005   # 0.5%
BACKTEST_COMMISSION_PCT: float = 0.001  # 0.1%

# ─── Entry Spike Trigger ─────────────────────────────────────────────────────
# 운영자 조정 가능: .env 에 SPIKE_TRIGGER_PCT=1.0, MIN_GAP_PCT=3.0 (% 단위)
SPIKE_TRIGGER_PCT: float = _pct('SPIKE_TRIGGER_PCT', 0.010)  # 기본 시가 대비 +1.0%
MIN_GAP_PCT:       float = _pct('MIN_GAP_PCT',       0.03)   # 기본 갭 +3% 이상
MIN_VOLUME_RATIO:  float = _float('MIN_VOLUME_RATIO', 3.0)   # 기본 거래량 3×
