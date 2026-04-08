# 자동매매 빠른 시작 가이드

**작성일**: 2026-04-07
**대상**: AI 자동매매 시스템 프로덕션 배포

---

## 🚀 3단계로 시작하기

### 1️⃣ 환경변수 확인

`.env` 파일이 이미 설정되어 있습니다:

```bash
# 필수 확인 항목
✓ ANTHROPIC_API_KEY       # Claude API 키
✓ ALPACA_API_KEY          # Alpaca API 키
✓ ALPACA_SECRET_KEY       # Alpaca Secret 키
✓ ALPACA_BASE_URL         # Paper Trading URL
✓ AUTO_TRADING_ENABLED    # 자동매매 활성화
```

**현재 설정 확인**:
```bash
# Windows
type .env | findstr AUTO_TRADING_ENABLED

# Linux/Mac
cat .env | grep AUTO_TRADING_ENABLED
```

**결과**:
```
AUTO_TRADING_ENABLED=true  ← 자동매매 활성화됨
```

---

### 2️⃣ 상태 확인

자동매매를 시작하기 전에 현재 상태를 확인하세요:

```bash
python check_trading_status.py
```

**확인 항목**:
- ✅ 브로커 연결 성공
- ✅ 계좌 정보 조회
- ✅ 자동매매 설정 확인
- ✅ 시장 개장 여부

---

### 3️⃣ 자동매매 시작

```bash
python auto_trading_bot.py
```

**실행 화면**:
```
======================================================================
자동매매 봇 초기화 중...
======================================================================
자동매매 활성화: True
1회 최대 투자: 현금의 10.0%
1일 최대 손실: 현금의 5.0%
최대 동시 보유: 5개
분석 주기: 60분

[1] Execution Team 초기화 중...
✓ 브로커 연결 성공 (https://paper-api.alpaca.markets)
✓ 주문 관리자 초기화 완료
✓ 실행 엔진 초기화 완료
✓ 계좌 자산: $100,000.00

[2] AI Team 초기화 중...
✓ AI Agent 초기화 완료

🚀 자동매매 봇 시작!
```

---

## 📊 팀 간 연결 상태

### ✅ 연결된 팀

| 팀 | 상태 | 환경변수 |
|----|------|----------|
| **AI Team** | ✅ 연결됨 | ANTHROPIC_API_KEY |
| **Execution Team** | ✅ 연결됨 | ALPACA_API_KEY, ALPACA_SECRET_KEY |
| **Data Collection** | ⚠️ 선택 | NEWS_API_KEY (선택) |
| **Strategy Engine** | ⚠️ 선택 | 환경변수 없음 |

### 동작 흐름

```
[자동매매 봇]
      ↓
[AI Team] ← ANTHROPIC_API_KEY 필요
  - 시장 분석
  - 매매 신호 생성
      ↓
[Execution Team] ← ALPACA_API_KEY 필요
  - 주문 실행
  - 체결 확인
      ↓
[Alpaca Broker]
  - 실제 주문 처리
```

---

## ⚙️ 현재 설정값

### 자동매매 설정 (.env)

```bash
# 자동매매 활성화
AUTO_TRADING_ENABLED=true

# 투자 금액 (퍼센트 기반)
MAX_INVESTMENT_PERCENT=10.0      # 현금의 10% 투자
MAX_DAILY_LOSS_PERCENT=5.0       # 현금의 5% 손실 제한
MAX_POSITIONS=5                  # 최대 5개 종목

# 리스크 관리
STOP_LOSS_PERCENT=2.0            # 2% 손절
TAKE_PROFIT_PERCENT=5.0          # 5% 익절

# 실행 주기
TRADING_INTERVAL_MINUTES=60      # 60분마다 분석
```

### 브로커 설정

```bash
ALPACA_API_KEY=PKUOJ4ZWX5NMWO24NVSXZF2P5L
ALPACA_SECRET_KEY=DRg4ASRoHtg3cF1QiqXaprzs4b6SGViywRMSeV78xjyW
ALPACA_BASE_URL=https://paper-api.alpaca.markets  ← Paper Trading
```

**⚠️ 중요**: 현재 **Paper Trading** 모드입니다 (가상 돈 사용)

---

## 📁 주요 파일

### 실행 파일
- `auto_trading_bot.py` - 자동매매 메인 봇
- `check_trading_status.py` - 상태 확인 스크립트

### 설정 파일
- `.env` - 환경변수 (이미 설정됨)
- `PRODUCTION_SETUP.md` - 상세 설정 가이드

### 로그 파일
- `logs/auto_trading.log` - 자동매매 로그
- `logs/execution/execution.log` - 주문 실행 로그
- `logs/execution/orders/*.json` - 개별 주문 파일

---

## 🔍 모니터링

### 실시간 로그 확인

**Windows**:
```bash
# PowerShell
Get-Content logs\auto_trading.log -Wait -Tail 50
```

**Linux/Mac**:
```bash
tail -f logs/auto_trading.log
```

### 계좌 상태 확인

```bash
# 언제든지 실행 가능
python check_trading_status.py
```

**출력 예시**:
```
[2] 계좌 정보
----------------------------------------------------------------------
  • 계좌 ID: 0e31cabc-2863-4c6e-884f-84d9c85015ec
  • 현금: $100,000.00
  • 자산 총액: $100,000.00
  • 미실현 손익: $0.00

[3] 현재 포지션
----------------------------------------------------------------------
  포지션 없음

[5] 자동매매 설정
----------------------------------------------------------------------
  • 자동매매: 활성화 ✓
  • 1회 최대 투자: 현금의 10.0% (현재: $10,000.00)
  • 1일 최대 손실: 현금의 5.0% (현재: $5,000.00)
  • 최대 동시 보유: 5개
```

---

## ⚠️ 안전 수칙

### Paper Trading (현재)
- ✅ 가상 돈으로 테스트
- ✅ 실제 손실 없음
- ✅ 시스템 검증용

### Live Trading (향후)
- ⚠️ 실제 돈 사용
- ⚠️ 실제 손실 발생 가능
- ⚠️ 충분한 테스트 후 전환

**Live Trading 전환 방법**:
```bash
# .env 파일에서 변경
ALPACA_BASE_URL=https://api.alpaca.markets
```

---

## 🛑 중지 방법

### 자동매매 일시 중지
```bash
# Ctrl + C 누르기
# 또는 .env 수정
AUTO_TRADING_ENABLED=false
```

### 모든 포지션 청산 (긴급)
```bash
python execution_team/examples/close_all_positions.py
```

---

## 📞 문제 해결

### Q1. "자동매매가 비활성화되어 있습니다"
```bash
# .env 확인
AUTO_TRADING_ENABLED=true

# 봇 재시작
python auto_trading_bot.py
```

### Q2. "브로커 연결 실패"
```bash
# API 키 확인
cat .env | grep ALPACA_API_KEY

# 키가 맞는지 확인
python check_trading_status.py
```

### Q3. "시장이 폐장 중입니다"
- 미국 주식 시장 시간: 월~금 9:30 AM - 4:00 PM ET
- 한국 시간: 23:30 - 06:00 (서머타임 22:30 - 05:00)
- 폐장 시간에는 주문이 실행되지 않습니다

---

## 📈 다음 단계

### 1. Paper Trading 검증 (현재)
```bash
# 최소 1주일 실행
python auto_trading_bot.py

# 매일 확인
python check_trading_status.py
```

### 2. 성능 모니터링
- 주문 성공률 확인
- 손익 추적
- 로그 분석

### 3. Live Trading 준비 (향후)
- 충분한 테스트 완료 후
- 소액($100~$1,000)부터 시작
- 점진적으로 증가

---

## ✅ 체크리스트

자동매매 시작 전 확인:

- [ ] `.env` 파일에 ALPACA_API_KEY 설정됨
- [ ] `.env` 파일에 ANTHROPIC_API_KEY 설정됨
- [ ] AUTO_TRADING_ENABLED=true 설정됨
- [ ] `python check_trading_status.py` 실행 성공
- [ ] 브로커 연결 성공 확인
- [ ] Paper Trading 모드 확인 (BASE_URL)
- [ ] 로그 디렉토리 생성됨 (`logs/execution/orders`)

모두 체크되었으면:

```bash
python auto_trading_bot.py
```

---

**작성일**: 2026-04-07
**상태**: ✅ 프로덕션 배포 준비 완료
