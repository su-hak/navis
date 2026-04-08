# 빠른 문제 해결

## ✅ 방금 해결된 문제

### 1. NewsClient import 에러
- **수정 완료**: `news_collector.py`를 REST API 방식으로 변경
- **원인**: Alpaca API 최신 버전에서 NewsClient 제거됨
- **해결**: aiohttp로 직접 API 호출

### 2. Pyarrow 경고
- **무시 가능**: 경고일 뿐, 에러 아님
- **완전 제거하려면**: `pip install pyarrow`

---

## 🚀 지금 바로 실행

### 1단계: .env 파일에 API 키 추가

```bash
notepad C:\navis\.env
```

**다음 내용 추가/수정:**
```env
# Alpaca API (필수)
APCA-API-KEY-ID=PK...your_key_here
APCA-API-SECRET-KEY=...your_secret_here

# Database (SQLite 사용시 - 선택)
DATABASE_TYPE=sqlite
```

> **⚠️ 중요**: 실제 Alpaca 키로 교체하세요!
> - 무료 가입: https://alpaca.markets
> - Paper Trading 선택
> - API Keys 메뉴에서 복사

### 2단계: Pyarrow 설치 (경고 제거)

```bash
pip install pyarrow
```

### 3단계: 다시 테스트

```bash
cd C:\navis\data_collection\collectors

# 주가 데이터 테스트
python stock_price_collector.py

# 뉴스 수집 테스트
python news_collector.py
```

---

## ✅ 예상 결과

### stock_price_collector.py
```
Fetching daily bars for ['AAPL', 'TSLA', 'NVDA']...
Daily bars:
   symbol  timestamp    close    volume
0   AAPL 2024-04-05  180.50  50000000
1   TSLA 2024-04-05  175.20  45000000
...

Latest prices: {'AAPL': 180.50, 'TSLA': 175.20, 'NVDA': 875.60}
✓ Saved price with indicators
```

### news_collector.py
```
Fetching latest news for AAPL...

Apple Announces New Product Launch
Summary: Apple Inc. announced today...
Created: 2024-04-05 10:30:00

...

Found 5 breaking news items
News volume (7 days): {'AAPL': 42, 'TSLA': 38, 'NVDA': 51}
```

---

## ❌ 여전히 에러가 난다면?

### "Please set APCA-API-KEY-ID..."
→ `.env` 파일 확인:
```bash
# 파일 위치 확인
cd C:\navis
type .env
```

### "HTTP 401" 또는 "Invalid credentials"
→ API 키가 잘못됨:
- Alpaca 사이트에서 키 재확인
- Paper Trading 키 사용하는지 확인
- 복사할 때 공백 없는지 확인

### "No data found"
→ 정상입니다:
- 시장 마감 후에는 최신 데이터가 없을 수 있음
- 다른 심볼로 시도: `MSFT`, `GOOGL`

---

## 📝 체크리스트

실행 전 확인:
- [ ] `.env` 파일에 API 키 있음
- [ ] `pip install pyarrow` 실행
- [ ] `C:\navis\data_collection\collectors` 폴더에 있음
- [ ] Alpaca Paper Trading 계정 있음

---

## 🎯 다음 단계

테스트가 성공하면:

```bash
# API 서버 실행
cd C:\navis\data_collection\api
python main.py
```

브라우저: http://localhost:8001/docs

---

**문제가 계속되면 에러 메시지를 복사해서 알려주세요!**
