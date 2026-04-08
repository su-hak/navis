# Alpaca 무료 계정 문제 해결 완료

## ✅ 해결된 문제

### 문제: "subscription does not permit querying recent SIP data"

**원인:**
- Alpaca 무료 계정은 **SIP 데이터** 접근 불가
- **IEX 데이터만** 사용 가능

**해결:**
- `stock_price_collector.py` 수정 완료
- `feed=DataFeed.IEX` 추가

---

## 🚀 다음 단계

### 1. Pyarrow 설치 (경고 제거)

```bash
pip install pyarrow
```

### 2. 다시 테스트

```bash
cd C:\navis\data_collection\collectors
python stock_price_collector.py
```

**이제 성공해야 합니다!**

```
Fetching daily bars for ['AAPL', 'TSLA', 'NVDA']...
✓ Daily bars: 90 records
✓ Latest prices: {'AAPL': 180.50, 'TSLA': 175.20, 'NVDA': 875.60}
```

---

## 📊 데이터 피드 비교

| 피드 | 접근 | 데이터 범위 | 지연 시간 |
|------|------|------------|----------|
| **IEX** | ✅ 무료 | 일봉, 분봉 | 15분 지연 |
| **SIP** | ❌ 유료 | 실시간 전체 | 실시간 |

**IEX로 충분합니다!**
- 일봉 데이터: 완벽
- 분봉 데이터: 15분 지연 (자동매매에 OK)
- 과거 데이터: 전체 접근 가능

---

## 🔧 Yahoo Finance 레이트 리미팅

**재무 데이터 429 에러:**
- Yahoo Finance가 일시적으로 차단
- **해결:** 5분 후 재시도

```bash
# 5분 후 다시 실행
python financial_collector.py
```

또는 재시도 간격 추가 (나중에):
```python
import time
time.sleep(2)  # 각 요청 사이 2초 대기
```

---

## ✅ 현재 상태

- ✅ API 키 설정 완료
- ✅ IEX 데이터 피드 설정 완료
- ✅ 뉴스 수집 작동 중
- ⏳ Pyarrow 설치 필요
- ⏳ Yahoo Finance 레이트 리미팅 대기

---

**지금 실행:**

```bash
# 1. Pyarrow 설치
pip install pyarrow

# 2. 테스트
cd C:\navis\data_collection\collectors
python stock_price_collector.py
```
