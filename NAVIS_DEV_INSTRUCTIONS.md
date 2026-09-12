# NAVIS 개발팀 기술 지시서
**작성일**: 2026-04-20  
**최종 업데이트**: 2026-05-03 (P17 부분합격 확정 → P18 착수 지시 추가)  
**작성자**: 퀀트 트레이더  
**대상**: 개발 1팀  
**연관 문서**: NAVIS_QUANT_ROADMAP.md, NAVIS_PHASE2_ARCHIVE.md, NAVIS_P18_IMPLEMENTATION.md

---

## 현재 상태: Phase 3 (V4 페이퍼 트레이딩) + P18 백테스트 병행 진행 중 🔄

Phase 1(V4 전략 완성)과 Phase 2(보조 전략 탐색, P11~P16)가 완료되었습니다.  
Phase 2의 전 전략(PEAD, Gap Fade Down, NH52 브레이크아웃, 팩터 모멘텀, 페어 트레이딩)은 폐기 확정.  
→ 상세 결과 및 폐기 근거: **`NAVIS_PHASE2_ARCHIVE.md`** 참조

---

## Phase 3 — V4 실전 검증

### V4 Multi-Day Hold — 최종 확정 파라미터

| 파라미터 | 값 | 근거 |
|---------|-----|------|
| 유니버스 | ITC 16종목 | P8~P10 검증 완료 |
| 갭업 기준 | 3.0%+ | PMS 기본값 |
| entry-start | 20 (09:50 ET) | P10에서 최고 PF |
| Multi-Day Trailing | 5% | P8에서 최적 |
| Multi-Day Max Days | 10거래일 | P8에서 최적 |
| 포지션 크기 | 30% (MAX_INVESTMENT_PERCENT) | PMS_POSITION_PCT — 검증 후 50% 상향 예정 |
| 최대 동시 포지션 | 2 | PMS_MAX_POSITIONS |
| 레짐 필터 | SPY > SMA200 | 필수 유지 |

**V4 엣지 원천**: 어닝 서프라이즈 후 기관 매수 지속 (PEAD + 고베타 IT·반도체)  
- 진입: 갭업 3%+ → 풀백 → 09:50 ET VWAP 재돌파  
- 레짐 필터: 2022년 하락장 자동 차단 확인

---

### Step 3-A: 페이퍼 트레이딩 (현재 진행 중)

**목적**: 백테스트 결과와 실시간 신호가 일치하는지 검증.  
Alpaca Paper Trading 계정으로 실제 주문 없이 실시간 시뮬레이션.

**합격 기준**: 누적 3건 이상 실행 후 실전 PF vs 백테스트 PF 괴리 **±0.15 이내**

**모니터링 항목 (매 거래 후 즉시 기록)**:

```
거래 기록 양식:
- 날짜 / 종목
- 갭업 % / 진입 시각 / 진입가
- 청산 시각 / 청산가 / 청산 유형
- 실현 손익 %
- 백테스트 예상 대비 괴리 여부
```

**보고 양식**:

```
거래 #N 보고
날짜: YYYY-MM-DD
종목: XXXX
갭업: +X.X%
진입: HH:MM ET @ $XXX.XX
청산: HH:MM ET @ $XXX.XX (유형: TRAILING_STOP / MAX_HOLD / STOP_LOSS)
손익: +/-X.X%

백테스트 비교:
- 동일 조건 백테스트 평균 손익: X.X%
- 괴리: X.X%p (±0.15 이내 여부: 합격/불합격)

특이사항: (슬리피지, 유동성 문제, 신호 지연 등)
```

---

### Step 3-B: 소규모 실전 (Step 3-A 합격 후)

**조건**: Step 3-A 합격 후에만 진입 (합격 기준 미달 시 절대 진입 금지)

- 전체 자본의 **20%만** 투입
- MDD 5% 도달 시 **자동 중단** (규칙 엄수, 예외 없음)
- 월 수익률 목표: 0~2% (연 3건 전략이므로 월 단위 목표 의미 없음 — 신호 품질 검증이 목적)

---

### 라이브 봇 설정 확인 사항

현재 배포된 `auto_trading_bot_v2.py`에서 아래 항목이 V4 백테스트 설정과 일치하는지 확인 필요:

| 항목 | 백테스트 설정 | 봇 확인 필요 |
|------|------------|------------|
| MAX_INVESTMENT_PERCENT | 30% | 기본값 10% → 변경 필요 |
| MAX_POSITIONS | 2 | 기본값 5 → 변경 필요 |
| TRAILING_STOP_PCT | 5.0% | .env 확인 |
| TAKE_PROFIT_PCT | 없음 (제거) | .env에서 제거 |
| entry-start | 20 (09:50 ET) | `PMS_ENTRY_START_MINUTE` 확인 |
| Trailing stop 조건 | `pl_pct > 0` 조건 **없음** | `_stop_loss_monitor` 코드 확인 |

> ⚠️ **중요**: `_stop_loss_monitor`의 trailing stop 조건에 `pl_pct > 0`이 포함되어 있으면 손익이 마이너스일 때 trailing이 작동하지 않습니다. 백테스트와 달리 손실 중에도 최고가 대비 -5%에서 청산해야 합니다. 이 조건을 반드시 제거하십시오.

---

## 완료 작업 이력

| 작업 | 결과 |
|------|------|
| V4 전략 구현 및 최적화 (P1~P10) | **완료** — PF 2.88, Phase 3 운용 중 (연 3건) |
| PEAD / Earnings Momentum (P11~P12) | **폐기** — PF 최고 0.92. V4 진입 구조와 구조적 비호환 |
| Gap Fade (단순 당일), ORB | **폐기** — Tier 1 모멘텀 종목 부적합 |
| 유니버스 확장 (Tier 1.5, ITC Ext) | **폐기** — 신호 품질 저하 |
| V4 Multi-Day Hold | **채택** — Phase 3 주전략 청산 메커니즘 |
| Gap Fade Down (갭다운 반전 Long, P13) | **폐기** — PF 0.11, MDD 71.52%. 갭다운은 실제 악재, dead-cat bounce |
| 52주 신고가 브레이크아웃 (P14) | **폐기** — PF 0.38~0.51. 진입 시점 오버익스텐드 |
| 팩터 모멘텀 (P15) | **폐기** — CAGR 3.45%. 추세장 구조적 약점 + 데이터 warmup 부족 |
| 페어 트레이딩 (P16) | **폐기** — CAGR 1.08%. 추세장에서 공적분 페어 90일 이상 괴리 지속 |

**폐기된 전략 상세 기록** → `NAVIS_PHASE2_ARCHIVE.md`

---

## P18 — Quality + CEO Catalyst 백테스트 🔄 착수

**Phase 3와 병행 진행** (V4 신호는 저빈도이므로 P18과 충돌 없음)

### P18 결과 요약 (P17 기준선)

| 지표 | P17-3A (기준선) | P18 목표 |
|------|----------------|---------|
| CAGR | 8.98% | ≥ 12% |
| MDD | 28.81% | ≤ 20% |
| PF | 1.37 | ≥ 1.20 ✅ |

**병목**: STOP_LOSS 비율 37~43% (약세장 무방어). Catalyst/Momentum 필터로 진입 선별력 강화.

### P18 구현 지시

**전체 상세 지시**: `NAVIS_P18_IMPLEMENTATION.md`

**Day 1 (금요일 야간) 즉시 실행**:
```bash
# Form 4 캐시 사전 다운로드 (약 26분, 방치 가능)
python data/form4/preload_cache.py \
  --start 2015-01-01 \
  --universe data/universe/us_stocks_5183.parquet
```

**P18-A (1순위)**: F≥6 + SEC Form 4 CEO 내부자 매수 (90일, $10만+)
```bash
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 --catalyst --stop-loss 15.0 --max-hold 126 --start 2016-01-01
```

**P18-B (2순위, 병행)**: F≥6 + 6개월 모멘텀 상위 30%
```bash
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 --momentum --stop-loss 15.0 --max-hold 126 --start 2016-01-01
```

**보고 형식**: `NAVIS_P18_IMPLEMENTATION.md` 섹션 3 참조

### ⚠️ P18 절대 준수 사항

1. **Form 4 point-in-time**: `filing_date ≤ as_of_date` 필터 필수 — 미래 신고 참조 금지
2. **모멘텀 skip 기간**: `price[t-21] / price[t-126]` — 직전 1개월 반드시 제외
3. **파라미터 고정**: 90일 창, $10만, 상위 30% — 결과 보고 후향적 조정 금지

---

## 다음 단계 요약

| 작업 | 상태 | 담당 |
|------|------|------|
| V4 페이퍼 트레이딩 (3건 목표) | 🔄 진행 중 | 봇 자동 실행 + 수동 확인 |
| P18-A Form 4 캐시 다운로드 | 📋 즉시 착수 | Day 1 야간 |
| P18-A/B 엔진 구현 | 📋 즉시 착수 | Day 2~3 |
| P18-A/B 백테스트 실행 | 📋 착수 예정 | Day 3~4 |
| P18 결과 보고 | 📋 예정 | 완료 후 즉시 |

---

*Phase 3 V4 신호 발생 시 즉시 위 보고 양식으로 보고 바랍니다.*  
*신호 없는 주는 매주 월요일 "신호 없음" 확인 보고 1줄로 충분합니다.*  
*P18 백테스트 완료 시 `NAVIS_P18_IMPLEMENTATION.md`의 보고 형식대로 보고 바랍니다.*
