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
# 운영자 조정 가능: .env 에 ATR_SL_MULTIPLIER=0.75 형태로 설정 (배율 단위)
# V3 변경: 1.5 → 0.75 (갭 당일 ATR 2~3배 확대 문제 대응, STOP_LOSS_PCT 2%로 캡)
ATR_SL_MULTIPLIER: float = _float('ATR_SL_MULTIPLIER', 0.75)  # SL = entry − 0.75 × ATR14 (최대 -2% 캡)
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

# ─── Market Regime Filter (V3) ────────────────────────────────────────────────
# SPY > SMA200 = Bull → 진입 허용 / SPY < SMA200 = Bear → 진입 차단
SPY_SMA_PERIOD:      int   = 200    # SMA 기간 (일봉)
REGIME_FILTER_ON:    bool  = True   # True: Bear 시장 진입 차단

# ─── Time Stop (V3) ──────────────────────────────────────────────────────────
# 진입 후 N분 경과 + 수익 미달 시 강제 청산 (잠자는 포지션 차단)
TIME_STOP_MINUTES:        int   = 45    # 진입 후 45분 경과 기준
TIME_STOP_MIN_PROFIT_PCT: float = 0.005 # 최소 수익 0.5% 미달 → 청산 (소수 비율)

# ─── Noon Rule (V3) ──────────────────────────────────────────────────────────
# 12:00 ET(동부시간) 이후 미실현 손익 < 0 → 청산 (오후 희망 홀딩 차단)
NOON_RULE_ENABLED: bool = True

# ─── PMS (Precision Momentum Scalper) 전략 파라미터 ─────────────────────────
# 백테스트 격리 실험 기반 재설계 전략. 기존 V2와 완전히 다른 구조.

# Tier 1 유니버스 (20종목) — 4개 시나리오 격리 테스트 알파 검증 종목
PMS_TIER1_UNIVERSE: list = [
    # Tier A: 전 시나리오 수익 기여, 최우선 진입
    "ABNB", "DOCU", "QCOM", "LYFT", "HIMS", "NET", "DASH",
    # Tier B: 검증됨, 조건 충족 시 진입
    "NFLX", "COIN", "CVX", "WDC", "PANW", "MS", "RBLX", "TGT",
    # Tier C: 유동성 우수, 조건 매우 엄격 적용
    "NVDA", "META", "TSLA", "AMD", "MSTR",
]

# Tier 1.5 유니버스 (Tier 1 + S&P500/Nasdaq100 대형주 확장)
# 선정 기준: 시가총액 $50B+, 일평균 거래량 5M+, Tier 1 미포함
# 목적: entry-start 20 설정에서 충분한 거래 수(50건+/년) 확보 검증용 (P6-1에서 실패)
PMS_TIER1_5_UNIVERSE: list = [
    *PMS_TIER1_UNIVERSE,
    # S&P500 / Nasdaq100 대형주 추가 (Tier 1 미포함)
    "MSFT", "AAPL", "AMZN", "GOOGL", "AVGO",
    "CRM", "ORCL", "ADBE", "NOW", "CRWD",
]

# ITC 유니버스 — V4 + Multi-Day 전략 전용
# 기업용 SW/반도체/고베타 성장주. 소비자 플랫폼(AAPL/GOOGL/AMZN/META) 제외
# 제외 근거: P6-1에서 소비자 플랫폼은 3%+ 갭 후 모멘텀 미지속 확인
ITC_UNIVERSE: list = [
    "NVDA", "AMD", "COIN", "MSTR",           # 반도체/암호화폐 모멘텀
    "CRM", "ORCL", "MSFT", "AVGO", "CRWD",   # 기업용 SW/반도체
    "NFLX", "NET", "PANW", "QCOM",            # 미디어/보안/통신반도체
    "ABNB", "DASH", "DOCU",                   # 성장주
]

# ITC 유니버스 확장판 — P10-2 테스트용 (24종목)
# 추가 기준: 기업용 B2B 특성 (소비자 플랫폼 아님), 일평균 거래량 3M+
ITC_UNIVERSE_EXTENDED: list = [
    *ITC_UNIVERSE,
    "SNOW", "NOW", "ADBE", "AMAT",           # 기업 클라우드/SW/반도체 장비
    "ZS", "DDOG", "WDAY", "MRVL",            # 보안/모니터링/HR SW/네트워킹 반도체
]

# 진입 게이트 — 갭 품질
PMS_MIN_GAP_PCT:      float = 0.030   # 갭 ≥ 3.0% (기존 2.0%에서 상향)
PMS_MIN_VOLUME_RATIO: float = 3.0     # 거래량 ≥ 3.0x

# 진입 시간 창 (ET 기준)
PMS_ENTRY_START_MINUTE: int = 5    # 09:30 + 5분 = 09:35 이후 첫 5분봉부터
PMS_ENTRY_END_HOUR:     int = 10   # 10:15 ET까지만 진입 허용
PMS_ENTRY_END_MINUTE:   int = 15

# 청산 — 2단계 Partial TP
PMS_PARTIAL_TP1_PCT:   float = 0.015  # +1.5% 도달 시 1차 청산
PMS_PARTIAL_TP1_RATIO: float = 0.40   # 1차: 포지션의 40% 청산
PMS_PARTIAL_TP2_PCT:   float = 0.025  # +2.5% 도달 시 2차 청산
PMS_PARTIAL_TP2_RATIO: float = 0.30   # 2차: 포지션의 30% 청산 (총 70% 완료)
PMS_TRAILING_STOP_PCT: float = 0.012  # 잔여 30%: 고점 대비 -1.2% Trailing Stop
PMS_FULL_TP_PCT:       float = 0.050  # +5.0% 전량 청산

# 청산 — 손절 (고정 SL, ATR 기반 폐기)
PMS_SL_PCT: float = 0.015   # -1.5% 고정 손절 (VWAP 하단 or -1.5% 중 높은 값)

# 청산 — Time Stop (격리 테스트 역효과 반영, 조건 완화)
PMS_TIME_STOP_MINUTES:  int   = 120   # 2시간 경과 후 (45분 → 2시간으로 완화)
PMS_TIME_STOP_LOSS_PCT: float = 0.015 # -1.5% 실손실 시에만 청산 (양수 포지션 유지)

# 청산 — Morning Close (Noon Rule 강화판)
PMS_MORNING_CLOSE_HOUR:   int = 11   # 11:30 ET 이후
PMS_MORNING_CLOSE_MINUTE: int = 30
# Partial TP 미발동 + 수익 미실현 포지션만 강제 청산

# 포지션 관리
PMS_MAX_POSITIONS:  int   = 2     # 최대 동시 포지션 2개 (기존 5개 → 집중)
PMS_POSITION_PCT:   float = 0.15  # 총자본의 15% (V4: 30% → 15%로 축소)
PMS_MAX_DAILY_LOSS: float = 0.010 # 일일 최대 손실 1% (도달 시 당일 신규 진입 금지)

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
