# NAVIS 트레이딩 시스템 변경 이력 (V2)

> 작성일: 2026-04-18  
> 기준: 퀀트 트레이더 1차 감사(NAVIS_DEV_TASKLIST.md) + 2차 감사(NAVIS_DEV_TASKLIST_V2.md) 전체 반영  
> 상태: master 배포 완료

---

## Phase 1 — 1차 기술 감사 반영

### 🔴 CRIT-01 | ATR 기반 동적 SL 구현

**파일:** `risk_team/core/risk_manager.py`

```
변경 전: stop_loss = entry_price * (1 - 0.02)  # 고정 -2%
변경 후: stop_loss = entry_price - 1.5 × ATR14
```

- `calculate_atr(high, low, close, period=14)` static method 추가
- `calculate_stops(entry_price, atr=None, atr_sl_multiplier=1.5, atr_tp_multiplier=3.0)` 구현
- ATR 없을 시 고정 -2% fallback 유지
- 고변동성 종목(NVDA 등) 정상 노이즈에 잘리는 문제 해결

---

### 🔴 CRIT-02 | 포지션 사이징 축소

**파일:** `risk_team/core/position_sizer.py`

```
변경 전                변경 후
포지션 0개 → 20%      포지션 0개 → 10%
포지션 1개 → 15%      포지션 1개 → 8%
포지션 2개 → 10%      포지션 2개 → 6%
포지션 3개 → 8%       포지션 3개 → 5%
포지션 4개+ → 5%      포지션 4개+ → 3%
max: 20%               max: 10%
```

- 집중 리스크 제거, 분산 강제
- 포지션 수 증가할수록 신규 비중 자동 축소

---

### 🔴 CRIT-03 | 일일 손실 예산 검증

**파일:** `risk_team/core/risk_manager.py`

```python
# check_order() 내부 추가
if max_loss_this_trade > remaining_daily_budget * 0.5:
    quantity 강제 조정 또는 진입 차단
```

- 단일 거래의 최대 손실 ≤ 잔여 일일 예산 50% 강제
- 연속 손실 시 자동으로 베팅 사이즈 감소

---

### 🟡 IMP-01 | VIX/SPY 하드 게이트

**파일:** `strategy_engine/market_gate/market_gate.py` (신규)

```python
차단 조건:
  VIX > 25.0          # 극단적 공포 구간
  SPY < MA200         # 장기 하락 추세
  SPY 당일 변화 ≤ -2% # 당일 급락
```

- 세 조건 중 하나라도 해당 시 신규 진입 전면 차단
- `MarketGateResult(allowed, reason, vix, spy_price, spy_ma200, spy_daily_change_pct)` 반환
- `_stage1_market_scan()` 진입 전 매 사이클 체크

---

### 🟡 IMP-02 | 갭 방향 검증 (Gap & Go / Gap & Fade 구분)

**파일:** `strategy_engine/filters/gap_validator.py` (신규)

```python
검증 방법: 9:30~9:40 1분봉 첫 캔들 분석
  갭 상승 + 첫 캔들 양봉 → Gap & Go → 진입 허용
  갭 상승 + 첫 캔들 음봉 → Gap & Fade → 진입 차단
```

- 갭 이후 페이드 되는 종목 자동 제외
- `_execute_buy_signal_inner()` 에서 체크

---

### 🟡 IMP-03 | Trailing Stop + 분할 청산

**파일:** `auto_trading_bot_v2.py`

```
변경 전: 고정 TP +5% 도달 시 전량 청산
변경 후:
  +3% 도달 → 50% 분할 청산 (이익 확정)
  이후 고점 대비 -2% 하락 → 나머지 전량 청산
```

- `_highest_price`, `_partial_tp_done` 상태 추적
- +30% 가는 갭 스톡에서 초기 이익만 먹고 끝나는 문제 해결

---

### 🟡 IMP-04 | 부분 체결 처리

**파일:** `execution_team/core/execution_engine.py`

```
변경 전: 10초 타임아웃, 미체결 시 실패 처리
변경 후: 30초 타임아웃, 부분 체결 수량 감지 → 잔량 취소 → 부분 수량으로 진행
```

- 유동성 낮은 종목에서 주문 전량 실패하는 문제 해결

---

### 🟢 NEW-01 | 백테스트 엔진

**파일:** `backtesting/backtest_engine.py`, `backtesting/data_loader.py` (신규)

```python
BacktestConfig:
  slippage_pct, commission_rate, atr_sl_multiplier
  trailing_stop_pct, partial_tp_pct, warmup_periods

BacktestResult:
  sharpe_ratio, max_drawdown_pct, profit_factor
  win_rate_pct, equity_curve, trade_records

BacktestEngine.grid_search(daily_bars, param_grid)
  → 파라미터 조합별 결과 Sharpe 순 정렬
```

- ATR SL, Trailing Stop, 분할 청산 시뮬레이션 포함
- 통과 기준: Sharpe ≥ 1.5, MDD ≤ 20%, PF ≥ 1.5

---

### 🟢 NEW-02 | WebSocket 실시간 SL/TP 모니터

**파일:** `data_collection/monitoring/websocket_monitor.py` (신규)

```
변경 전: 10초 polling → SL 반응 최대 10초 지연
변경 후: Alpaca StockDataStream 실시간 quotes → <1초 반응
```

- `WebSocketPriceMonitor.start()` → `_subscribe_and_process()` 상시 실행
- `_check_sl_tp(symbol, price)` → SL/trailing stop/partial TP 즉시 감지
- `_on_ws_sl_hit()` 콜백으로 봇 메인 루프에 청산 신호 전달

---

### 🟢 NEW-03 | 뉴스 타이밍 필터

**파일:** `ai_team/news/analyzer.py`

```python
NEWS_FRESHNESS_RULES:
  max_age_minutes: 60      # 60분 초과 → 분석 제외
  catalyst_boost: +0.2     # 갭 직전 10분 이내 → 촉매 뉴스 추정
  stale_penalty: -0.15     # 30~60분 된 뉴스 → 신뢰도 감소
```

- `filter_news_by_timing(articles, gap_time)` 추가
- `analyze_news_sentiment(symbol, gap_time=)` — gap_time 기준 타이밍 보정

---

### 🟢 NEW-04 | 일일 거래 횟수 제한

**파일:** `auto_trading_bot_v2.py`

```python
max_entries_per_day = 5   # 일일 최대 진입
max_exits_per_day   = 10  # 일일 최대 청산
```

- 과매매(overtrading) 방지
- 자정 기준 자동 리셋

---

## Phase 2 — 2차 기술 감사 반영

### 🔴 BUG-01 | TP 파라미터 3군데 불일치 → 단일 소스 통일

**파일:** `config/trading_constants.py` (신규), `signal_generator.py`, `qa_team/backtest/engine.py`, `risk_team/config.py`, `auto_trading_bot_v2.py`

```
수정 전 (불일치):
  auto_trading_bot_v2.py  → TAKE_PROFIT_PERCENT env default 5.0%
  signal_generator.py     → TradingConditions.take_profit_pct = 0.10 (10%)
  risk_manager.py         → take_profit_pct default 0.06 (6%)

수정 후 (단일 소스):
  config/trading_constants.py → TAKE_PROFIT_PCT = 0.06
  모든 파일이 이 상수만 참조
```

백테스트와 실거래가 서로 다른 TP로 돌아가던 버그 해결.

---

### 🔴 BUG-02 | RSI 스코어링이 모멘텀 전략과 역방향 → 전략별 분리

**파일:** `strategy_engine/scoring/score_calculator.py`, `strategy_engine/signals/signal_generator.py`

```python
# 수정 전 (리버전 로직이 전 전략에 적용)
RSI 30~50 → 높은 점수 (60~100점)  ← 모멘텀 전략에서 역방향
RSI 50~70 → 낮은 점수 (40~60점)  ← 강한 모멘텀 종목이 낮은 점수

# 수정 후 (전략별 분리)
rsi_score_momentum()   → RSI 50-70 구간 최고점 (모멘텀/브레이크아웃)
rsi_score_reversion()  → RSI 30-50 구간 최고점 (리버전)

# 호출 시 전략 종류 지정
generate_buy_signal(symbol, df, strategy_type="momentum")
generate_buy_signal(symbol, df, strategy_type="reversion")
```

갭 모멘텀 종목이 RSI 스코어 낮아서 필터링되던 로직 오류 해결.

---

### 🟡 NEW-01 | 전략 유니버스 분리 + 충돌 해결

**파일:** `strategy_engine/multi_strategy/strategy_manager.py`

```
수정 전:
  momentum / breakout / reversion 3개 전략이
  동일한 종목 풀을 공유 → 같은 종목에 동시에 반대 신호 가능
  (갭 상승 종목 → 모멘텀 BUY + 리버전 SELL 동시 발생)

수정 후:
  gap_volume_screener    → momentum 유니버스  (갭 >3% + 거래량 >3×)
  near_52w_high_screener → breakout 유니버스  (52주 신고가 5% 이내)
  oversold_screener      → reversion 유니버스 (RSI <35 or 볼린저 하단)

충돌 해결 (resolve_conflicts):
  동일 종목이 여러 전략에 동시 등장 시
  → 점수 최고 전략만 진입권 획득, 나머지 유니버스에서 제거
```

전략 간 헤징(자기 포지션 상쇄) 문제 구조적 해결.

---

### 🟡 NEW-02 | 백테스트 슬리피지 현실화

**파일:** `qa_team/backtest/engine.py`

```
변경 전: slippage_rate = 0.001 (0.1%)
변경 후: slippage_rate = 0.005 (0.5%)
```

갭 스톡 MARKET 주문 실제 슬리피지(0.3~0.8%) 반영.  
0.1% 기준 백테스트는 실거래 대비 성과가 과도하게 좋게 나오는 문제 해결.

---

### 🟡 NEW-03 | 점수 임계값 최적화 기능

**파일:** `qa_team/backtest/engine.py`

```python
BacktestEngine.optimize_score_threshold(
    symbol, df,
    threshold_range=(55.0, 85.0),
    step=5.0
)
→ {'best_threshold': float, 'best_sharpe': float, 'all_results': {...}}
```

현재 75점 기준이 근거 없이 설정된 것에 대한 해결책.  
실제 데이터 기반으로 최적 임계값을 탐색할 수 있는 도구 제공.

---

## 미구현 항목 (향후 스프린트)

| 우선순위 | 항목 | 내용 |
|---------|------|------|
| 다음 스프린트 | qa_team 백테스트 ATR SL 반영 | qa_team 엔진은 여전히 고정 SL 사용 |
| 다음 스프린트 | 5분봉 백테스트 | 현재 일봉 기반 → look-ahead bias 위험 |
| 장기 | 재무 팩터 10% 구현 | 현재 `reserved` 상태 (중립 50점 고정) |
| 장기 | Kelly Criterion 포지션 사이징 | 현재 포지션 수 기반 테이블 방식 |
| 장기 | Walk-forward 최적화 | 과적합 방지, 파라미터 freeze 정책 |

---

## 파일 변경 목록 전체

### Phase 1 (신규 생성)
- `strategy_engine/market_gate/market_gate.py`
- `strategy_engine/filters/gap_validator.py`
- `backtesting/backtest_engine.py`
- `backtesting/data_loader.py`
- `data_collection/monitoring/websocket_monitor.py`

### Phase 1 (수정)
- `risk_team/core/risk_manager.py`
- `risk_team/core/position_sizer.py`
- `execution_team/core/execution_engine.py`
- `ai_team/news/analyzer.py`
- `auto_trading_bot_v2.py`

### Phase 2 (신규 생성)
- `config/trading_constants.py`

### Phase 2 (수정)
- `strategy_engine/scoring/score_calculator.py`
- `strategy_engine/signals/signal_generator.py`
- `strategy_engine/multi_strategy/strategy_manager.py`
- `qa_team/backtest/engine.py`
- `risk_team/config.py`
- `auto_trading_bot_v2.py`
