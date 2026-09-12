# P18 Strategy E 진행 보고서

**작성일**: 2026-05-07  
**담당**: NAVIS 개발 2팀장  
**베이스라인**: P17-3A (F≥6, CAGR 8.98%, PF 1.37, MDD 28.81%) — 부분합격  
**목표**: CAGR ≥ 12%, MDD ≤ 20%, PF ≥ 1.20 (공식 합격)

---

## 1. 현재까지 전체 테스트 결과

| 테스트 | 조건 | CAGR | MDD | PF | Sharpe | STOP_LOSS% | 거래수 | 판정 |
|--------|------|------|-----|-----|--------|-----------|--------|------|
| **P17-3A** ★ | F≥6 (기준선) | **8.98%** | 28.81% | 1.37 | 0.48 | ~40% | 350건 | **부분합격** |
| P18-B | F≥6 + 상위30% 모멘텀 | 8.13% | 28.07% | 1.34 | 0.43 | 40.1% | 347건 | FAIL |
| P18-B-Rev | F≥6 + 하위30% 모멘텀 | 8.34% | 31.73% | 1.29 | 0.45 | 45.3% | 411건 | FAIL |
| P18-A | F≥6 + CEO Catalyst | — | — | — | — | — | — | ⏸ 대기 |
| P18-C | F≥6 + Catalyst + Momentum | — | — | — | — | — | — | ⏸ 대기 |

> ⏸ SEC EDGAR Akamai IP 차단 중 (24-72시간 자동 해제 예정). Form 4 메타데이터 적재 필요.

---

## 2. 모멘텀 필터 실험 분석

### P18-B (상위 30% — 정방향 모멘텀)
```
가설: 최근 6개월 강세 종목 (상위 30%) 중 F≥6 우량주 → 모멘텀 지속 기대
결과: CAGR 8.13% (기준선 대비 -0.85%p), STOP_LOSS 40.1%
결론: 고모멘텀 우량주 → 진입 시 이미 가격 반영, 추가 알파 없음
```

### P18-B-Rev (하위 30% — 역방향 모멘텀)
```
가설: 최근 6개월 약세 종목 (하위 30%) 중 F≥6 우량주 → "가치 반전" 기대
결과: CAGR 8.34% (기준선 대비 -0.64%p), MDD 31.73% (기준선보다 악화!)
       STOP_LOSS 45.3% (411건 중 186건) — 더 많은 낙폭
결론: "떨어지는 칼날 잡기" — 약세 종목은 계속 하락, 손절 증가로 MDD 악화
```

### 핵심 발견
**F-Score 기반 Quality-Value 전략에서 6개월 가격 모멘텀은 알파 창출 실패.**
- 상위 모멘텀: 이미 가격 반영 → 추가 상승 여지 없음
- 하위 모멘텀: 하락 지속 → 손절 증가, MDD 악화
- **F-Score 자체가 이미 재무 개선 모멘텀을 포착** → 가격 모멘텀과 이중 계산 문제

---

## 3. 공통 병목: STOP_LOSS 40%+ 문제

모든 테스트에서 약세장(2018, 2020, 2022) 기간 STOP_LOSS가 급증:

```
2018: -2.6% (코로나 전 금리 충격)
2020: +13.7% (코로나 반등 포함이지만 초기 급락)
2022: -25.3% (금리 인상 충격) ← 전략 최대 취약점
```

**손절이 줄어야 CAGR과 MDD가 개선됩니다.**
CEO Catalyst 필터 (P18-A)의 역할:
- 내부자가 자기 돈을 직접 매수한 종목만 진입
- 내부 정보에 기반한 신호 → 손절 확률 감소 기대
- Value Trap 회피 효과

---

## 4. SEC API 차단 현황 및 대기 계획

```
차단 시작: 2026-05-06 (추정)
차단 원인: Akamai CDN IP 레벨 차단 (과도한 요청으로 추정)
차단 범위: data.sec.gov/submissions/, data.sec.gov/api/xbrl/, efts.sec.gov 모두 403
해제 예상: 24-72시간 자동 해제

해제 후 즉시 실행:
  cd /c/navis/.claude/worktrees/heuristic-moore-ad2547
  python data/form4/preload_metadata.py --start 2015-01-01 \
    --universe data/universe/us_stocks_5183.parquet --resume
  # 예상 시간: ~17분 (5,161종목 × 0.2초)
  # 저장 위치: data/form4/meta/{SYMBOL}_meta.parquet
```

---

## 5. 다음 단계

### SEC 해제 후 즉시 실행 (Day 1)

```bash
# Step 1: Form 4 메타데이터 적재 (~17분)
python data/form4/preload_metadata.py \
  --start 2015-01-01 \
  --universe data/universe/us_stocks_5183.parquet

# Step 2: P18-A 백테스트 (~2시간)
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 --catalyst --catalyst-lookback 90 \
  --stop-loss -15.0 --take-profit 30.0 --max-hold-days 126 \
  --start 2016-01-01 --end 2026-01-01 \
  --label "P18-A F>=6+Catalyst"

# Step 3: P18-C 백테스트 (~2시간)
python backtesting/run_quality_value_backtest.py \
  --min-fscore 6 --catalyst --catalyst-lookback 90 \
  --momentum --momentum-top-pct 30 \
  --stop-loss -15.0 --take-profit 30.0 --max-hold-days 126 \
  --start 2016-01-01 --end 2026-01-01 \
  --label "P18-C F>=6+Catalyst+Momentum"
```

### P18-A 기대 시나리오
```
현재 STOP_LOSS 40%+ 중 CEO Catalyst 종목은 더 낮을 것으로 예상:
  - 내부자 매수 = 저점 신호 → 추가 하락 가능성 낮음
  - STOP_LOSS 25-30%로 감소 → CAGR +2-4%p 기대
  - 진입 종목 수 감소 (전체 중 10-20%만 내부자 매수 있음) → 거래 건수 감소 주의
```

---

## 6. 코드 업데이트 (이번 세션)

새로 추가된 기능:
- `MomentumScreener.screen_universe(reverse=True)` — 역방향 모멘텀 지원
- `QualityValueEngine.run(momentum_reverse=True)` — 역방향 모멘텀 파라미터 연결
- `run_quality_value_backtest.py --momentum-reverse` — CLI 플래그 추가

---

*작성: NAVIS 개발 2팀장 (Claude) | 다음 업데이트: SEC API 해제 후 P18-A/C 실행 시*
