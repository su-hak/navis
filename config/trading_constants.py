"""
Trading Constants — Single Source of Truth

이 파일이 모든 전략/리스크/백테스트 모듈의 유일한 파라미터 출처다.
다른 곳에서 TP/SL/포지션 수치를 하드코딩하지 말 것.
"""

# ─── Take-Profit / Stop-Loss ────────────────────────────────────────────────
# .env 의 TAKE_PROFIT_PERCENT, signal_generator 의 0.10, risk_manager 의 0.06 을
# 이 상수 하나로 통일. (BUG-01)
TAKE_PROFIT_PCT: float = 0.06       # +6% 고정 TP (ATR 미적용 fallback)
STOP_LOSS_PCT: float = 0.02         # -2% 고정 SL  (ATR 미적용 fallback)

# ATR 기반 동적 SL/TP 배율 (risk_manager.calculate_stops 에서 사용)
ATR_SL_MULTIPLIER: float = 1.5      # SL = entry − 1.5 × ATR14
ATR_TP_MULTIPLIER: float = 3.0      # TP = entry + 3.0 × ATR14

# ─── Trailing Stop ───────────────────────────────────────────────────────────
TRAILING_STOP_PCT: float = 0.02     # 고점 대비 -2% 에서 청산
PARTIAL_TP_PCT: float = 0.03        # +3% 에서 50% 분할 청산

# ─── Position Sizing ─────────────────────────────────────────────────────────
MAX_POSITION_PCT: float = 0.10      # 단일 포지션 최대 10%
MIN_POSITION_PCT: float = 0.03      # 단일 포지션 최소 3%

# ─── Market Gate Thresholds ──────────────────────────────────────────────────
VIX_HARD_GATE: float = 25.0         # VIX > 25 → 신규 진입 전면 차단
SPY_DAILY_DROP_GATE: float = -0.02  # SPY 당일 -2% 이하 → 차단

# ─── Scoring ─────────────────────────────────────────────────────────────────
BUY_SIGNAL_THRESHOLD: float = 75.0  # 총 점수 >= 75 → 매수 신호 (백테스트로 재검증 필요)

# ─── Slippage / Commission (backtest) ────────────────────────────────────────
BACKTEST_SLIPPAGE_PCT: float = 0.005    # 0.5% — 갭 스톡 MARKET 주문 현실적 슬리피지
BACKTEST_COMMISSION_PCT: float = 0.001  # 0.1%

# ─── Entry Spike Trigger ─────────────────────────────────────────────────────
SPIKE_TRIGGER_PCT: float = 0.015    # 시가 대비 +1.5% 스파이크 → 진입 트리거
MIN_GAP_PCT: float = 0.03           # 전일 종가 대비 +3% 이상 갭
MIN_VOLUME_RATIO: float = 3.0       # 평균 대비 3× 이상 거래량
