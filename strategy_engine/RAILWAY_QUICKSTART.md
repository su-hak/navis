# 🚀 Railway 빠른 배포 가이드

## ✅ 1단계: Railway CLI 설치

### Windows (PowerShell)

```powershell
npm install -g @railway/cli
```

설치 확인:
```powershell
railway --version
```

---

## 🔑 2단계: Railway 로그인

```powershell
railway login
```

브라우저가 열리면 GitHub 계정으로 로그인하세요.

---

## 📦 3단계: 배포

### Option A: 자동 배포 (권장)

```powershell
cd C:\navis\strategy_engine
railway init
railway up
```

### Option B: GitHub 연동

1. GitHub에 코드 푸시
```powershell
cd C:\navis
git init
git add strategy_engine/
git commit -m "Add strategy engine API"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/navis.git
git push -u origin main
```

2. Railway 대시보드에서:
   - "New Project" → "Deploy from GitHub repo"
   - 레포지토리 선택
   - Root Directory: `strategy_engine`
   - 자동 배포 시작

---

## ✅ 4단계: 확인

```powershell
# 앱 열기
railway open

# 로그 확인
railway logs

# 상태 확인
railway status
```

API 문서: `https://YOUR_APP.railway.app/docs`

---

## 🎯 테스트

### curl로 테스트

```bash
# 헬스체크
curl https://YOUR_APP.railway.app/health

# API 정보
curl https://YOUR_APP.railway.app/
```

### Python으로 테스트

```python
import requests

BASE_URL = "https://YOUR_APP.railway.app"
response = requests.get(f"{BASE_URL}/health")
print(response.json())
```

---

## 🔄 업데이트

코드 수정 후:

```powershell
cd C:\navis\strategy_engine
railway up
```

또는 GitHub 연동 시 자동 배포:
```powershell
git add .
git commit -m "Update API"
git push
```

---

## 💡 환경변수 설정

Railway 대시보드 또는 CLI로:

```powershell
railway variables set KEY=VALUE
```

---

## 📊 주요 명령어

| 명령어 | 설명 |
|--------|------|
| `railway login` | 로그인 |
| `railway init` | 프로젝트 초기화 |
| `railway up` | 배포 |
| `railway open` | 앱 열기 |
| `railway logs` | 로그 확인 |
| `railway status` | 상태 확인 |
| `railway variables` | 환경변수 관리 |

---

## 🚨 문제 해결

### Railway CLI 설치 안됨

Node.js가 설치되어 있는지 확인:
```powershell
node --version
npm --version
```

Node.js 설치: https://nodejs.org

### 빌드 실패

로그 확인:
```powershell
railway logs
```

대부분 의존성 문제이므로 `requirements_api.txt` 확인

---

## ✅ 배포 완료 체크리스트

- [ ] Railway CLI 설치
- [ ] Railway 로그인
- [ ] 프로젝트 초기화 (`railway init`)
- [ ] 배포 (`railway up`)
- [ ] API 문서 확인 (`/docs`)
- [ ] 헬스체크 확인 (`/health`)

---

**배포 시간**: 약 2-3분
**비용**: 무료 ($5 크레딧/월)
**자동 HTTPS**: ✅ 제공됨
