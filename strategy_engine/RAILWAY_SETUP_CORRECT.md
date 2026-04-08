# Railway 올바른 배포 설정 (중복 방지)

## 🚨 중요: data_collection 중복 배포 방지

현재 프로젝트 구조:
```
navis/
├── data_collection/     ← 이미 Railway 배포됨 (스케줄링)
├── strategy_engine/     ← 지금 배포할 API
```

**strategy_engine만 배포**해야 합니다!

---

## ✅ 방법 1: Railway CLI (권장) ⭐

Railway CLI로 배포하면 **strategy_engine 디렉토리만** 배포됩니다.

```powershell
# strategy_engine 디렉토리에서 실행
cd C:\navis\strategy_engine

# 이 디렉토리만 배포됨
railway init
railway up
```

**장점**: 자동으로 현재 디렉토리만 배포

---

## ✅ 방법 2: GitHub 연동 + Root Directory 설정

### 1단계: GitHub에 전체 코드 푸시

```powershell
cd C:\navis
git init
git add .
git commit -m "Add strategy engine and data collection"
git remote add origin https://github.com/YOUR_USERNAME/navis.git
git push -u origin main
```

### 2단계: Railway에서 Root Directory 지정

1. Railway 대시보드 접속
2. "New Project" → "Deploy from GitHub repo"
3. navis 레포지토리 선택
4. **중요**: Settings → Build
5. **Root Directory** 설정: `strategy_engine`
6. Deploy

**이렇게 하면 strategy_engine만 배포됩니다!**

---

## ✅ 방법 3: 별도 GitHub 레포지토리 (가장 깔끔)

strategy_engine을 별도 레포지토리로 관리:

```powershell
# strategy_engine만 별도 레포지토리로
cd C:\navis\strategy_engine
git init
git add .
git commit -m "Initial commit: Strategy Engine API"
git remote add origin https://github.com/YOUR_USERNAME/strategy-engine.git
git push -u origin main
```

Railway에서:
- "Deploy from GitHub repo"
- strategy-engine 레포지토리 선택
- Root Directory 설정 불필요 (전체가 API)

**장점**: 완전히 독립적인 관리

---

## 🔍 배포 확인

배포 후 Railway 대시보드에서 확인:

### 올바른 배포 (strategy_engine만)
```
Deployed Files:
  api/
  indicators/
  filters/
  scoring/
  signals/
  requirements_api.txt
  railway.toml
  ✅ data_collection/ 없음
```

### 잘못된 배포 (전체 프로젝트)
```
Deployed Files:
  data_collection/      ❌ 중복!
  strategy_engine/
  agents/
  tools/
  ...
```

---

## 📋 Railway 프로젝트 구분

현재 Railway에 두 개의 프로젝트가 있어야 합니다:

| 프로젝트 | 타입 | 코드 위치 | 용도 |
|---------|------|----------|------|
| **data-collection** | 스케줄링 | `navis/data_collection/` | 데이터 수집 (이미 배포됨) |
| **strategy-engine** | API | `navis/strategy_engine/` | 전략 엔진 API (지금 배포) |

**각각 독립적인 Railway 프로젝트입니다!**

---

## 🎯 권장 배포 방법

### Option A: Railway CLI (가장 간단)

```powershell
cd C:\navis\strategy_engine
railway init      # 새 프로젝트 생성
railway up        # 이 디렉토리만 배포
```

### Option B: GitHub + Root Directory

```powershell
# 1. GitHub 전체 푸시
cd C:\navis
git push

# 2. Railway 설정
Railway Dashboard:
  → Settings → Build
  → Root Directory: strategy_engine
  → Deploy
```

---

## 🔧 railway.toml 확인

`strategy_engine/railway.toml`이 올바르게 설정되어 있습니다:

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn strategy_engine.api.strategy_api:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

**중요**: `startCommand`가 `strategy_engine.api.strategy_api`를 실행하므로 strategy_engine만 필요합니다.

---

## 🚨 문제 발생 시

### 증상: data_collection이 함께 배포됨

**원인**: Root Directory 미설정 또는 잘못된 디렉토리에서 배포

**해결**:
1. Railway 대시보드 → Settings → Build
2. Root Directory: `strategy_engine`
3. Redeploy

### 증상: Import 오류

**원인**: PYTHONPATH 문제

**해결**: Dockerfile에 이미 설정됨
```dockerfile
ENV PYTHONPATH=/app:$PYTHONPATH
```

---

## ✅ 최종 체크리스트

배포 전 확인:
- [ ] strategy_engine 디렉토리에서 실행
- [ ] Railway에서 Root Directory 설정 (GitHub 연동 시)
- [ ] data_collection과 별도 프로젝트로 생성
- [ ] railway.toml 확인

배포 후 확인:
- [ ] Railway 로그에서 data_collection 관련 로그 없음
- [ ] API만 실행 중 확인
- [ ] /docs 엔드포인트 정상 작동
- [ ] 스케줄링 작업 실행 안됨

---

## 🎯 요약

**Railway CLI 사용 시**:
```powershell
cd C:\navis\strategy_engine  # ← 이 디렉토리에서!
railway init
railway up
```

**GitHub 연동 시**:
- Root Directory: `strategy_engine` 설정 필수!

**결과**:
- ✅ data_collection: 기존 프로젝트에서 계속 스케줄링 실행
- ✅ strategy_engine: 새 프로젝트에서 API 서버 실행
- ✅ 중복 없음!

---

**중요**: 두 개는 완전히 독립적인 Railway 프로젝트입니다!
