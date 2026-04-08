# 빠른 수정 가이드

## 1. UTF-8 인코딩 에러 해결 ✅

**증상**: `UnicodeEncodeError: 'cp949' codec can't encode character`

**해결**: 이미 수정됨 - `auto_trading_bot_v2.py`에서 UTF-8 인코딩 설정

## 2. 워치리스트 0개 문제

### 원인

**시뮬레이션 때문이 아닙니다!**

1. **현재 시각**: 새벽 02:47 (한국시간)
2. **미국 시장 시간**: 23:30 ~ 06:00 (한국시간)
3. **결론**: 장외 시간이라 데이터가 없거나 조건을 만족하는 종목이 없음

### 확인 방법

다음에 실행하면 더 자세한 로그가 출력됩니다:

```
미국 시장 시간: NO (장외)
처리 결과: 총 48개, 후보 0개, 스킵 48개
```

### 해결 방법

#### 방법 1: 시장 시간에 실행

**미국 시장 시간 (한국시간)**:
- 여름 (3월~11월): 22:30 ~ 05:00
- 겨울 (11월~3월): 23:30 ~ 06:00

#### 방법 2: 임계값 낮추기 (.env 파일)

```env
# 기존 (조건이 엄격)
GAP_THRESHOLD=3.0
VOLUME_RATIO_THRESHOLD=3.0

# 수정 (조건 완화)
GAP_THRESHOLD=1.0          # 3% → 1%
VOLUME_RATIO_THRESHOLD=1.5  # 3배 → 1.5배
```

#### 방법 3: 테스트 모드로 종목 추가

`data_collection/monitoring/watchlist_generator.py:57`

더 많은 종목 추가:

```python
def _get_default_universe(self) -> List[str]:
    return [
        # 기존 48개 + 추가
        'SPY', 'QQQ', 'IWM',  # ETF
        'MARA', 'RIOT',        # 비트코인 관련
        'GME', 'AMC',          # 밈 스톡
        # ... 더 추가
    ]
```

## 3. 자동매매 안전 설정 ⚠️

### 현재 상태: 위험! 🚨

로그에서 확인:
```
자동매매 활성화: True
```

이는 **실제 주문이 실행**됨을 의미합니다!

### .env 파일 수정

```env
# 반드시 false로 변경!
AUTO_TRADING_ENABLED=false
```

### Paper Trading 확인

```env
# Paper Trading (가상 계좌) 확인
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Live Trading (실전) - 절대 사용 금지!
# ALPACA_BASE_URL=https://api.alpaca.markets
```

## 4. 다시 실행

```powershell
# 1. .env 파일 수정
notepad .env

# 2. AUTO_TRADING_ENABLED=false로 변경

# 3. 다시 실행
python auto_trading_bot_v2.py
```

## 5. 예상 출력 (수정 후)

```
2026-04-08 ... - __main__ - INFO - 자동매매 활성화: False
2026-04-08 ... - __main__ - INFO - [Stage 1] 전체 시장 스캔 시작
2026-04-08 ... - __main__ - INFO -   시각: 2026-04-08 02:47:30
2026-04-08 ... - __main__ - INFO -   미국 시장 시간: NO (장외)
2026-04-08 ... - __main__ - WARNING -   장외 시간이므로 워치리스트가 비어있을 수 있습니다
2026-04-08 ... - data_collection.monitoring.watchlist_generator - INFO - 스냅샷 조회 완료: 48개
2026-04-08 ... - data_collection.monitoring.watchlist_generator - INFO - 거래량 평균 계산 완료: 48개
2026-04-08 ... - data_collection.monitoring.watchlist_generator - INFO - 처리 결과: 총 48개, 후보 0개, 스킵 48개
2026-04-08 ... - data_collection.monitoring.watchlist_generator - WARNING - 조건을 만족하는 종목이 없습니다.
2026-04-08 ... - data_collection.monitoring.watchlist_generator - WARNING - 조건: gap>3.0% OR volume>3.0배
2026-04-08 ... - data_collection.monitoring.watchlist_generator - WARNING - 시장 시간을 확인하거나 임계값을 낮춰보세요.
```

## 6. 시장 시간에 다시 테스트

**한국시간 23:00 ~ 06:00 사이에 실행하면**:
- 워치리스트에 종목이 추가될 것입니다
- Stage 2 고주기 모니터링이 시작됩니다
- 1.5% 변동 감지 시 알림이 발생합니다

## 7. 체크리스트

- [ ] UTF-8 인코딩 에러 해결됨
- [ ] .env에서 `AUTO_TRADING_ENABLED=false` 설정
- [ ] Paper Trading URL 확인
- [ ] 시장 시간 확인 (23:00~06:00)
- [ ] 필요시 임계값 낮추기

---

**작성**: 2026-04-08
**버전**: V2
