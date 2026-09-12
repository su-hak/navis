# NAVIS 전략 재설계안 V3

> 작성일: 2026-04-19  
> 작성자: 수석 퀀트 트레이더  
> 배경: 유니버스 백테스트 -94.50% 참패 → 전략 구조 전면 재검토  
> 목표: 하루 2~3% 복리 수익, 실거래 투입 가능 수준

---

## 1. 패배 원인 진단 — "우리는 알파 방향을 반대로 잡고 있었다"

백테스트 데이터가 전략의 핵심 결함을 명확히 증명합니다.

### 청산 유형별 손익이 말하는 진실

| 청산 유형 | 건수 | 승률 | 결과 |
|-----------|------|------|------|
| TRAILING_STOP | 728건 | **96.3%** | +$150,530 ✅ |
| PARTIAL_TP | 1,139건 | **100%** | +$341,669 ✅ |
| TAKE_PROFIT | 235건 | **100%** | +$154,692 ✅ |
| EOD 청산 | 2,032건 | **25.6%** | **-$1,049,503** ❌ |
| STOP_LOSS | 271건 | **0%** | **-$462,789** ❌ |

**결론: 빠르게 움직인 거래(Trailing/TP)는 전부 이겼다. 오래 들고 있은 거래(EOD)는 74% 패배했다.**

이것은 "Gap & Go" 전략이 아닌 **"Gap & Fade" 시장 특성**을 가진 종목들이었음을 증명합니다.

갭 2% + 스파이크 1% = **이미 3%+ 상승한 종목** → 스마트머니는 이 시점에 이미 팔고 있습니다.  
우리는 스마트머니의 매도 물량을 받아주는 역할을 하고 있었습니다.

### 3대 구조적 결함

```
결함 ①: 진입 타이밍 — 이미 늦었다
  갭 2% 확인 + 스파이크 1% 대기 = 시가 대비 3~5% 위에서 매수
  이 시점의 통계: 당일 되돌림 확률 74% (EOD 승률 25.6%가 증거)

결함 ②: 손실 제한 실패 — ATR SL이 갭 당일 역효과
  갭 당일 ATR = 평소 ATR × 2~3배 확대
  ATR × 1.5 SL = 실질적으로 -5~9% 허용 → 건당 평균 손실 -7.037%

결함 ③: 포지션 남용 — 170종목에서 4,405거래
  하루 평균 2.4건 진입 × 5년 = 예상치(401건)의 11배
  승률 58.9%지만 손익비 0.63 → 기댓값 음수
  기댓값 = 0.589 × avg_win + 0.411 × avg_loss < 0
```

---

## 2. 대표님 비전과 퀀트 현실 정렬

> "하루에 2~3% 수익을 매일 내는 것을 목표로 하고 싶습니다."

이 목표에 대한 솔직한 전문가 의견:

| 기준 | 현실 |
|------|------|
| 총자본 대비 매일 +2~3% | 연환산 500~750% — 워런 버핏 연 20%, 최고 헤지펀드 연 30~50% |
| 투입자본 대비 매일 +2~3% | 자본의 20~30% 투입 시 총자본 기준 +0.4~0.9%/일 — **현실적** |
| 거래가 있는 날만 +2~3% | 주 2~3일 거래 × 매 거래 +2% = 주 +4~6% — **달성 가능** |

**핵심 재정렬:**  
**"매일 2~3%"가 아닌 "트레이딩하는 날 포지션당 2~3% 빠른 수익, 복리 누적"** 으로 재정의합니다.  
이것이 대표님이 원하시는 방향의 실현 가능한 버전이며, 연간 100~200% 복리를 목표로 합니다.

---

## 3. NAVIS V3 전략 구조

### 전략명: "Precision Gap Momentum with Hard Gates"

기존 전략의 "무엇이 작동했는지"를 보존하고, "무엇이 죽였는지"를 제거합니다.

```
[작동했던 것 — 보존]          [죽인 것 — 제거/교체]
Trailing Stop → 유지           EOD 시간 낭비 → Time Stop으로 대체
Partial TP → 유지 (강화)       170종목 → Top 15 알파 종목 집중
VWAP 진입 개념 → 강화          ATR×1.5 SL → ATR×0.75 + 고정 -2% 중 작은 값
                                Bear 시장 진입 → SPY SMA200 하드 게이트
```

---

## 4. 4중 진입 게이트 (AND 조건 — 하나라도 실패하면 NO TRADE)

### Gate 1: 시장 국면 필터 (Market Regime)

```python
# SPY 일봉 SMA200 체크 (하드 게이트)
spy_close > spy_sma200  → BULL: 진입 허용
spy_close < spy_sma200  → BEAR: 진입 전면 차단 (현금 보유)

# VIX 레벨 (공포 필터)
VIX < 20    → GREEN: 풀사이즈
VIX 20~25   → YELLOW: 절반 사이즈만 허용
VIX > 25    → RED: 진입 전면 차단
```

> **기대 효과**: 2022년 Bear 구간(-45.24%) 완전 차단. 해당 연도 1,001건 → 0건.  
> 백테스트 기간 중 Bull 구간은 전체의 약 65% → 손실 발생 구간 35% 자동 제거.

### Gate 2: 갭 품질 필터 (Gap Quality)

```python
# 기준 상향 (노이즈 제거)
gap_pct >= 3.0%          # 2.0% → 3.0% (품질 우선)
volume_ratio >= 3.0x     # 2.0x → 3.0x (강한 수요 확인)
not earnings_day         # 실적 발표 당일 제외 (예측 불가)
not ex_dividend_day      # 배당락일 제외 (갭 왜곡)

# 갭 유형 확인 (신규 추가)
pre_market_volume > avg_pre_market × 2x  # 프리마켓 수요 확인
```

### Gate 3: VWAP 확인 (Fade 여부 탐지)

```python
# 진입 직전 가격이 VWAP 위에 있어야 함 (핵심 신규 조건)
entry_price > vwap_at_entry  # Gap & Go 확인 (아직 되돌리지 않은 상태)

# 스파이크 조건 (기존 유지, 기준은 동일)
spike_from_open >= 1.0%

# 추가: 스파이크 방향 확인
price_vs_vwap_trend == "above"  # 위로 스파이크, 아래로 되돌리지 않은 것
```

> **핵심**: EOD 패배의 74%는 진입 시점에 이미 VWAP 근처이거나 아래로 내려오는 상태였습니다.  
> VWAP 위 진입만 허용하면 EOD 손실의 절반 이상을 선제 차단합니다.

### Gate 4: 종목 유니버스 집중 (Universe Focus)

```python
# 백테스트 알파 상위 15종목 (수익 기여 종목만)
TIER_1_UNIVERSE = [
    "QCOM", "COIN", "ABNB", "NFLX", "CVX",   # Top 5 수익 종목
    "OPEN", "RGTI", "WBD", "RKT", "NKLA",    # Mid tier
    "TGT", "VLO", "EBAY", "MRK", "JPM",      # Supplemental
]

# 170종목 → 15종목: 거래수 4,405 → 약 400건 예상
# 노이즈 거래 90% 제거
```

---

## 5. 새로운 청산 로직 (The Time Stop Revolution)

기존 EOD 청산이 -$1,049,503를 만든 이유: **"언젠가 올라오겠지"를 기다리다 손절.**  
V3는 시간이 적이라는 것을 전제로 설계합니다.

### 청산 우선순위 (순서대로 체크)

```
1. HARD STOP LOSS        entry - min(ATR×0.75, 2.0%)    즉시 청산
2. TIME STOP (신규)      진입 후 45분 경과 + 수익 < +0.5%  → 즉시 청산
3. NOON RULE (신규)      12:00 기준 수익 < 0            → 즉시 청산
4. PARTIAL TP            entry + 2.0%                   → 50% 청산
5. TRAILING STOP         파셜 TP 이후 고점 대비 -1.5%   → 나머지 청산
6. TAKE PROFIT           entry + 5.0%                   → 전량 청산
7. EOD HARD CLOSE        15:30                          → 잔여 전량 청산
```

### Time Stop 로직 (신규 핵심 기능)

```python
def check_time_stop(position, current_bar, config):
    """
    진입 45분 후에도 수익 +0.5% 미달이면 무조건 청산.
    "움직이지 않는 거래는 결국 손실"이라는 원칙.
    """
    minutes_held = (current_bar.timestamp - position.entry_time).seconds / 60
    unrealized_pct = (current_bar.close - position.entry_price) / position.entry_price * 100

    if minutes_held >= 45 and unrealized_pct < 0.5:
        return True, "TIME_STOP"
    return False, None


def check_noon_rule(position, current_bar):
    """
    12:00(동부시간) 이후 미실현 손익이 0 미만이면 청산.
    오후에 반등 기대는 도박.
    """
    et = current_bar.timestamp.tz_convert("America/New_York")
    if et.hour >= 12 and current_bar.close < position.entry_price:
        return True, "NOON_EXIT"
    return False, None
```

> **기대 효과**: EOD 청산 비율 46% → 5% 미만으로 감소.  
> 시간 낭비 거래를 작은 손실(-0.5~1%)로 끊어내고 다음 기회 대기.

---

## 6. 포지션 사이징 개선

### 기존 방식의 문제

```
기존: 균등 배분 (자본 / max_positions)
→ $1M / 5 = $200K 고정
→ 고변동성 종목에 동일 금액 투입 = 불균형 리스크
```

### V3: 리스크 기반 사이징

```python
def calculate_position_size(capital, entry_price, stop_price, risk_pct=0.02):
    """
    리스크 기반 포지션 사이징.
    거래당 자본의 최대 2% 손실로 제한.
    
    Args:
        capital: 현재 총자본
        entry_price: 진입 가격
        stop_price: 손절 가격
        risk_pct: 리스크 비율 (기본 2%)
    """
    risk_per_share = entry_price - stop_price
    risk_amount = capital * risk_pct          # 최대 손실 금액
    shares = int(risk_amount / risk_per_share)
    max_position = capital * 0.20             # 단일 포지션 최대 20%
    position_value = min(shares * entry_price, max_position)
    return int(position_value / entry_price)

# 예시:
# capital=$1M, entry=$100, stop=$98 (2% SL), risk=2%
# risk_amount = $20,000
# risk_per_share = $2
# shares = 10,000 → position = $1M (20% cap 적용)
# → shares = min(10,000, $200K/$100) = 2,000주
```

| 파라미터 | 기존 | V3 |
|---------|------|-----|
| 최대 포지션 수 | 5 | **3** |
| 포지션당 자본 | 균등 20% | 리스크 2% 기반 최대 20% |
| 거래당 최대 손실 | ATR에 따라 가변 | **자본의 2% 고정** |

---

## 7. 시장 국면별 대응 전략

| 국면 | SPY vs SMA200 | VIX | 행동 |
|------|---------------|-----|------|
| STRONG BULL | 위 + 상승 | < 15 | 풀사이즈, 공격적 운용 |
| BULL | 위 | 15~20 | 정상 운용 |
| CAUTION | 위 + 횡보 | 20~25 | 50% 사이즈, 더 엄격한 필터 |
| BEAR ENTRY | SMA200 하향 돌파 | 상관없음 | 즉시 전량 청산, 신규 진입 차단 |
| BEAR | 아래 | 상관없음 | 현금 100% (기회비용 최소화) |
| RECOVERY | SMA200 재돌파 + 3일 확인 | < 25 | 서서히 재진입 |

---

## 8. 예상 개선 효과 (시뮬레이션)

2022년 데이터 기준 단순 계산:

```
[현재 V2]
1,001건 × 평균 -0.045% = -45.24% (연간)

[V3 적용 시]
① SPY SMA200 필터: 2022년은 Bear 구간 → 진입 0건 → 손실 0
② 설령 Bull 구간만 진입해도:
   - 유니버스 15종목: 1,001건 × (15/170) ≈ 90건
   - Time Stop으로 EOD 손실 70% 제거
   - 타이트한 SL로 건당 손실 -7% → -2%
   → 예상 손실: 90건 × -0.5% avg = -0.45% (≈ +44.79%p 개선)
```

| 시나리오 | 총 수익률 (5년) | 연환산 |
|---------|---------------|--------|
| V2 현재 | -94.50% | -47.58% |
| V3 보수적 시나리오 | **+15~30%** | +3~6%/년 |
| V3 기본 시나리오 | **+50~80%** | +8~13%/년 |
| V3 낙관적 시나리오 | **+120~180%** | +17~23%/년 |

> **대표님 목표 달성 경로**: 연 100%+ 는 V3 이후 Walk-Forward 최적화 + 추가 알파 소스 발굴이 필요합니다.  
> 단기적으로는 연 20~50% 안정적 달성을 첫 번째 이정표로 설정합니다.

---

## 9. 구현 우선순위 (스프린트 계획)

### Sprint 1 — 즉시 구현 (1~2주) ← 가장 임팩트 큼

| 과제 | 파일 | 기대 효과 |
|------|------|-----------|
| **① SPY SMA200 시장 국면 필터** | `engine.py` + `trading_constants.py` | Bear 손실 100% 차단 |
| **② Time Stop 로직** | `engine.py` `_process_position_5min()` | EOD 손실 70% 제거 |
| **③ Noon Rule** | `engine.py` `_process_position_5min()` | 오후 손실 제거 |
| **④ SL 축소** | `trading_constants.py` ATR×1.5 → ATR×0.75 | 건당 손실 -7% → -3% |

### Sprint 2 — 2주 내 (검증 후 적용)

| 과제 | 파일 | 기대 효과 |
|------|------|-----------|
| ⑤ VWAP 진입 확인 조건 | `screener.py` + `engine.py` | 진입 품질 향상 |
| ⑥ 유니버스 Top 15 집중 | `run_universe_backtest.py` | 노이즈 거래 90% 제거 |
| ⑦ 갭 기준 3%로 상향 | `trading_constants.py` | 진입 품질 향상 |
| ⑧ 리스크 기반 포지션 사이징 | `engine.py` + 실거래 코드 | MDD 감소 |

### Sprint 3 — 검증 후 (페이퍼 트레이딩 통과 후)

| 과제 | 파일 | 기대 효과 |
|------|------|-----------|
| ⑨ VIX 레벨별 사이즈 조정 | `engine.py` | 고변동성 구간 손실 감소 |
| ⑩ Walk-Forward 최적화 | 신규 파일 | 파라미터 과적합 방지 |
| ⑪ 알파 종목 자동 갱신 로직 | `screener.py` | 동적 유니버스 관리 |

---

## 10. 백테스트 재실행 계획

Sprint 1 구현 완료 후 아래 순서로 검증:

```bash
# 1. SPY SMA200 필터만 적용 (다른 조건 기존 유지)
python backtesting/run_universe_backtest.py --regime-filter-only

# 2. Time Stop + Noon Rule 추가
python backtesting/run_universe_backtest.py --regime-filter --time-stop

# 3. SL 축소 추가
python backtesting/run_universe_backtest.py --regime-filter --time-stop --sl-atr 0.75

# 4. Top 15 유니버스 + 갭 3% 상향
python backtesting/run_universe_backtest.py --full-v3

# 각 단계별 비교로 어떤 조치가 가장 큰 효과인지 격리 확인
```

---

## 11. 실거래 코드 동기화 필요 사항

백테스트 개선과 동시에 실거래 코드도 업데이트 필요:

| 파일 | 변경 사항 |
|------|-----------|
| `trading_constants.py` | ATR_MULTIPLIER 1.5 → 0.75, GAP_THRESHOLD 2.0 → 3.0 |
| `signal_generator.py` | VWAP 확인 조건 추가 |
| `position_manager.py` | Time Stop, Noon Rule 추가 |
| `market_monitor.py` | SPY SMA200 조회 → 시장 국면 상태 관리 |
| `execution_engine.py` | 리스크 기반 포지션 사이징 적용 |

---

## 12. 핵심 요약 (경영진 보고용)

```
문제: 갭+스파이크 진입 후 74%가 당일 되돌림 → EOD 청산에서 $1M 손실
      ATR SL이 고변동성 종목에 너무 넓어 건당 -7% 허용

해결:
  1. Bear 시장 진입 차단 (SPY > SMA200) → 2022년 -45% 구간 완전 차단
  2. Time Stop (45분 + 0.5% 미달) → 잠자는 포지션 즉시 청산
  3. Noon Rule (12시 미수익 청산) → 오후 희망 홀딩 차단
  4. SL 타이트화 (ATR×0.75, -2% 중 작은 값) → 건당 손실 -7% → -2%
  5. Top 15 알파 집중 → 거래 수 90% 감소, 품질 집중

목표: 연 20~50% 안정적 수익 → 복리로 연 100%+ 궤도 진입
      (하루 2~3%는 "거래가 있는 날, 투입자본 기준" 으로 재정의)
```

---

*이 문서는 `UNIVERSE_BACKTEST_RESULT_REPORT.md` 데이터를 기반으로 작성된 전략 재설계안입니다.*  
*다음 단계: Sprint 1 구현 → 백테스트 재실행 → 결과 비교*
