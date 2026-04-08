# ✅ 전략 엔진 - 버그 수정 및 Railway 배포 준비 완료

## 🐛 수정된 버그

### BB Position 범위 오류 수정

**문제**: Bollinger Bands Position이 0~1 범위를 벗어남 (1.03 등)

**원인**: 가격이 상단/하단 밴드를 벗어날 때 위치 계산이 1을 초과하거나 0 미만이 될 수 있음

**수정**: `strategy_engine/indicators/technical_indicators.py:156-159`
```python
# 수정 전
position = (current_price - lower) / (upper - lower)

# 수정 후
position = (current_price - lower) / (upper - lower)
# 0~1 범위로 제한 (가격이 밴드를 벗어난 경우)
position = max(0.0, min(1.0, position))
```

**상태**: ✅ 수정 완료

---

## 🚀 Railway 배포 준비 완료

### 생성된 파일

| 파일 | 용도 |
|------|------|
| `railway.toml` | Railway 설정 (빌드 및 시작 명령) |
| `Procfile` | 프로세스 정의 |
| `requirements_api.txt` | API 전용 의존성 |
| `Dockerfile` | Docker 컨테이너 설정 |
| `.dockerignore` | Docker 빌드 제외 파일 |
| `deploy_railway.sh` | 자동 배포 스크립트 (Linux/Mac) |
| `RAILWAY_DEPLOYMENT.md` | 상세 배포 가이드 |
| `RAILWAY_QUICKSTART.md` | 빠른 시작 가이드 |

### API 서버 수정

**파일**: `strategy_engine/api/strategy_api.py`

**수정 사항**:
- Railway PORT 환경변수 지원
- 모듈 레벨에서 app 인스턴스 생성 (배포 플랫폼 호환)

```python
# 모듈 레벨에서 app 생성 (Railway가 참조 가능)
app = create_strategy_api()

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

---

## 📋 배포 전 확인사항

### 1. 버그 수정 테스트

```powershell
cd C:\navis
python strategy_engine/tests/test_strategy_engine.py
```

이제 BB Position 오류가 발생하지 않아야 합니다.

### 2. 로컬 API 서버 테스트

```powershell
cd C:\navis
python -m strategy_engine.api.strategy_api
```

브라우저: http://localhost:8001/docs

---

## 🚀 Railway 배포 (3가지 방법)

### 방법 1: Railway CLI (가장 빠름)

```powershell
# 1. Railway CLI 설치
npm install -g @railway/cli

# 2. 로그인
railway login

# 3. 배포
cd C:\navis\strategy_engine
railway init
railway up

# 4. 확인
railway open
```

**예상 시간**: 2-3분

### 방법 2: GitHub 연동 (권장 - CI/CD)

```powershell
# 1. GitHub 레포지토리 생성
cd C:\navis
git init
git add strategy_engine/
git commit -m "Add strategy engine API"
git remote add origin https://github.com/YOUR_USERNAME/navis.git
git push -u origin main

# 2. Railway 대시보드
- New Project → Deploy from GitHub repo
- 레포지토리 선택
- Root Directory: strategy_engine
```

**장점**: 코드 푸시할 때마다 자동 배포

### 방법 3: Docker (가장 안정적)

```powershell
# 1. Docker 이미지 빌드 및 테스트
cd C:\navis\strategy_engine
docker build -t strategy-engine-api .
docker run -p 8001:8001 strategy-engine-api

# 2. Railway 배포
railway login
railway init
railway up
```

---

## 📊 배포 후 테스트

### 헬스체크

```bash
curl https://YOUR_APP.railway.app/health
```

예상 응답:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00"
}
```

### API 문서

브라우저: `https://YOUR_APP.railway.app/docs`

### 점수 계산 테스트

```bash
curl -X POST "https://YOUR_APP.railway.app/score/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "data": {
      "timestamp": ["2024-01-01", "2024-01-02", "2024-01-03"],
      "open": [100, 102, 101],
      "high": [105, 107, 106],
      "low": [99, 101, 100],
      "close": [103, 105, 104],
      "volume": [1000000, 1200000, 1100000]
    }
  }'
```

---

## 🔧 Railway 설정

### 환경 변수

Railway가 자동으로 설정:
- `PORT`: 자동 할당 (코드에서 os.getenv("PORT") 사용)
- `RAILWAY_ENVIRONMENT`: production

추가 설정 불필요!

### 자동 기능

Railway가 자동으로 제공:
- ✅ HTTPS (무료)
- ✅ 커스텀 도메인
- ✅ CI/CD (GitHub 연동 시)
- ✅ 로그 및 모니터링
- ✅ 자동 재시작

---

## 💰 비용

**무료 플랜**:
- $5 크레딧/월
- 500시간 실행 시간
- 512MB RAM
- 1GB 디스크

**충분합니다!** 개발 및 테스트용으로 완벽합니다.

---

## 📁 파일 구조 (배포용)

```
strategy_engine/
├── api/
│   ├── __init__.py
│   └── strategy_api.py          ← PORT 환경변수 지원
├── indicators/
│   └── technical_indicators.py  ← BB Position 버그 수정
├── filters/
├── scoring/
├── signals/
├── tests/
├── railway.toml                 ← Railway 설정
├── Procfile                     ← 프로세스 정의
├── requirements_api.txt         ← API 의존성
├── Dockerfile                   ← Docker 설정
├── RAILWAY_QUICKSTART.md        ← 빠른 시작
└── RAILWAY_DEPLOYMENT.md        ← 상세 가이드
```

---

## ✅ 체크리스트

배포 전:
- [x] BB Position 버그 수정
- [x] API 서버 PORT 환경변수 지원
- [x] Railway 설정 파일 생성
- [x] Dockerfile 생성
- [x] requirements_api.txt 생성
- [x] 배포 문서 작성

배포:
- [ ] Railway CLI 설치
- [ ] Railway 로그인
- [ ] 프로젝트 초기화
- [ ] 배포 실행
- [ ] API 문서 확인
- [ ] 헬스체크 테스트

---

## 🎯 다음 단계

### 1. 버그 수정 확인

```powershell
cd C:\navis
python strategy_engine/tests/test_strategy_engine.py
```

### 2. Railway 배포

```powershell
cd C:\navis\strategy_engine
railway init
railway up
railway open
```

### 3. API 테스트

브라우저: `https://YOUR_APP.railway.app/docs`

---

## 📞 지원

### Railway 문제
- **문서**: https://docs.railway.app
- **커뮤니티**: https://discord.gg/railway

### 전략 엔진 문제
- **빠른 시작**: `RAILWAY_QUICKSTART.md`
- **상세 가이드**: `RAILWAY_DEPLOYMENT.md`
- **API 문서**: `README.md`

---

## 🎉 결론

**모든 준비가 완료되었습니다!**

1. ✅ 버그 수정 완료
2. ✅ Railway 배포 준비 완료
3. ✅ 문서 완비
4. 🚀 배포만 하면 됩니다!

**예상 배포 시간**: 2-3분
**비용**: 무료 ($5 크레딧/월)

---

**팀**: Strategy Engine Team
**날짜**: 2024
**상태**: ✅ 배포 준비 완료
