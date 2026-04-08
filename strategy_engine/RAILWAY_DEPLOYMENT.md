# Strategy Engine API - Railway 배포 가이드

## 📋 준비물

1. **Railway 계정** - https://railway.app
2. **GitHub 계정** (선택사항 - GitHub 연동 배포 시)
3. **배포할 코드** - strategy_engine 디렉토리

---

## 🚀 배포 방법 (3가지)

### 방법 1: Railway CLI (권장)

#### 1단계: Railway CLI 설치

```powershell
# Windows (PowerShell)
npm install -g @railway/cli

# 또는 Scoop
scoop install railway
```

#### 2단계: Railway 로그인

```powershell
railway login
```

#### 3단계: 프로젝트 초기화 및 배포

```powershell
# strategy_engine 디렉토리로 이동
cd C:\navis\strategy_engine

# Railway 프로젝트 초기화
railway init

# 배포
railway up
```

#### 4단계: 환경변수 설정 (필요시)

```powershell
# Railway 대시보드에서 설정하거나 CLI로
railway variables set PORT=8001
```

---

### 방법 2: GitHub 연동 배포

#### 1단계: GitHub 레포지토리 생성

```powershell
# Git 초기화 (아직 안했다면)
cd C:\navis
git init
git add strategy_engine/
git commit -m "Add strategy engine"

# GitHub 레포지토리 생성 후
git remote add origin https://github.com/YOUR_USERNAME/navis.git
git push -u origin main
```

#### 2단계: Railway에서 배포

1. Railway 대시보드 접속: https://railway.app
2. "New Project" 클릭
3. "Deploy from GitHub repo" 선택
4. 레포지토리 선택
5. 루트 디렉토리를 `strategy_engine`으로 설정
6. 자동 배포 시작

---

### 방법 3: Dockerfile 사용 (가장 안정적)

#### 1단계: 로컬에서 테스트

```powershell
cd C:\navis\strategy_engine

# Docker 이미지 빌드
docker build -t strategy-engine-api .

# 로컬 실행 테스트
docker run -p 8001:8001 strategy-engine-api
```

브라우저에서 확인: http://localhost:8001/docs

#### 2단계: Railway 배포

```powershell
# Railway CLI로 배포
railway up

# 또는 Docker 이미지를 Railway에 직접 배포
railway link [PROJECT_ID]
railway up
```

---

## 🔧 Railway 설정

### railway.toml 파일 (이미 생성됨)

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn strategy_engine.api.strategy_api:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### 환경 변수

Railway 대시보드에서 설정:
- `PORT`: 자동 할당됨 (수동 설정 불필요)
- `PYTHON_VERSION`: 3.11 (선택사항)

---

## ✅ 배포 확인

배포 완료 후:

```bash
# Railway가 제공하는 URL 확인
railway open

# API 문서 확인
https://YOUR_APP.railway.app/docs

# 헬스체크
https://YOUR_APP.railway.app/health
```

---

## 📊 API 엔드포인트

배포 후 사용 가능한 엔드포인트:

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/` | GET | API 정보 |
| `/health` | GET | 헬스체크 |
| `/docs` | GET | API 문서 (Swagger UI) |
| `/redoc` | GET | API 문서 (ReDoc) |
| `/indicators/calculate` | POST | 기술적 지표 계산 |
| `/filter/stocks` | POST | 종목 필터링 |
| `/score/calculate` | POST | 점수 계산 |
| `/signal/buy` | POST | 매수 시그널 생성 |
| `/signal/sell` | POST | 매도 시그널 생성 |

---

## 🧪 배포 테스트

### curl로 테스트

```bash
# 헬스체크
curl https://YOUR_APP.railway.app/health

# API 정보
curl https://YOUR_APP.railway.app/

# 점수 계산 (예시)
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
    },
    "news_sentiment": 0.5,
    "news_count": 5
  }'
```

### Python으로 테스트

```python
import requests

BASE_URL = "https://YOUR_APP.railway.app"

# 헬스체크
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# 점수 계산
data = {
    "symbol": "AAPL",
    "data": {
        "timestamp": ["2024-01-01", "2024-01-02"],
        "open": [100, 102],
        "high": [105, 107],
        "low": [99, 101],
        "close": [103, 105],
        "volume": [1000000, 1200000]
    }
}

response = requests.post(f"{BASE_URL}/score/calculate", json=data)
print(response.json())
```

---

## 🔍 모니터링

### Railway 대시보드에서 확인 가능:

1. **로그**: 실시간 애플리케이션 로그
2. **메트릭**: CPU, 메모리 사용량
3. **배포 히스토리**: 이전 배포 버전
4. **환경 변수**: 설정된 변수 확인

### 로그 확인

```powershell
# Railway CLI로 로그 확인
railway logs
```

---

## 💰 비용

Railway 무료 플랜:
- **$5 무료 크레딧** (매월)
- 500시간 실행 시간
- 512MB RAM
- 1GB 디스크

충분히 테스트 및 개발용으로 사용 가능합니다.

---

## 🚨 문제 해결

### 문제 1: 빌드 실패

**원인**: 의존성 설치 실패

**해결**:
```powershell
# requirements_api.txt 확인
# ta-lib 제거 (C 라이브러리 문제)
```

requirements_api.txt에서 `ta-lib` 라인 제거 후 재배포

### 문제 2: 포트 오류

**원인**: PORT 환경변수 미사용

**해결**: strategy_api.py 수정 필요 없음 (Railway가 자동 설정)

### 문제 3: Import 오류

**원인**: PYTHONPATH 문제

**해결**: Dockerfile에 이미 포함됨
```dockerfile
ENV PYTHONPATH=/app:$PYTHONPATH
```

---

## 🔄 업데이트 배포

```powershell
# 코드 수정 후
cd C:\navis\strategy_engine

# 재배포
railway up

# 또는 GitHub 연동 시 자동 배포
git add .
git commit -m "Update strategy engine"
git push
```

---

## 🎯 빠른 시작 (요약)

```powershell
# 1. Railway CLI 설치
npm install -g @railway/cli

# 2. 로그인
railway login

# 3. 프로젝트 디렉토리로 이동
cd C:\navis\strategy_engine

# 4. 배포
railway init
railway up

# 5. 확인
railway open
```

---

## 📞 지원

- **Railway 문서**: https://docs.railway.app
- **Railway 커뮤니티**: https://discord.gg/railway
- **전략 엔진 문서**: `README.md`

---

**배포 후 API 문서 URL**: `https://YOUR_APP.railway.app/docs`

Railway가 자동으로 HTTPS를 제공하며, 커스텀 도메인도 설정 가능합니다!
