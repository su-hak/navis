# Railway 배포 빠른 가이드

5분 안에 Railway에 배포하기!

---

## 🚀 빠른 배포 (5분)

### 1️⃣ Railway 프로젝트 생성 (1분)

1. https://railway.app 로그인
2. "New Project" 클릭
3. "Provision MySQL" 선택 (자동으로 DB 생성됨)

### 2️⃣ GitHub에 푸시 (2분)

```bash
cd C:\navis\data_collection

# Git 초기화 (처음이면)
git init
git add .
git commit -m "Railway deployment ready"

# GitHub 레포지토리 생성 후
git remote add origin https://github.com/yourusername/trading-data-collection.git
git push -u origin main
```

### 3️⃣ Railway에서 배포 (1분)

1. Railway 대시보드에서 "New Service"
2. "GitHub Repo" 선택
3. 레포지토리 선택
4. 자동 빌드 시작!

### 4️⃣ 환경 변수 설정 (1분)

Railway 대시보드 → 서비스 선택 → "Variables" 탭:

```env
APCA-API-KEY-ID=your_alpaca_key
APCA-API-SECRET-KEY=your_alpaca_secret
TZ=America/New_York
```

MySQL은 자동으로 `DATABASE_URL` 환경 변수가 설정됩니다!

---

## ✅ 배포 확인

### 로그 확인

Railway 대시보드 → "Logs" 탭:

```
============================================================
Data Collection Scheduler Started
============================================================
Monitoring 10 symbols: AAPL, TSLA, NVDA, ...

Scheduled Jobs:
  - Collect Daily Prices: ...
  - Collect News: ...
============================================================
```

성공! 🎉

---

## 📊 다음 단계

### MySQL 테이블 생성

**옵션 A: Railway CLI로 원격 실행**

```bash
# Railway CLI 설치
npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 연결
railway link

# 테이블 생성
railway run python database/schema.py
```

**옵션 B: 로컬에서 Railway MySQL에 연결**

```python
# Railway 대시보드에서 DATABASE_URL 복사
# Python으로 테이블 생성

import mysql.connector
from urllib.parse import urlparse

database_url = "mysql://root:password@host:port/database"  # Railway에서 복사
parsed = urlparse(database_url)

conn = mysql.connector.connect(
    host=parsed.hostname,
    port=parsed.port,
    user=parsed.username,
    password=parsed.password,
    database=parsed.path[1:]
)

from database.schema import create_tables
create_tables(conn)
conn.close()
print("✓ Tables created!")
```

---

## 💰 비용

- **MySQL**: 무료 (5 GB 스토리지)
- **Scheduler**: $5/월 (항상 실행)
- **총**: **$5/월**

Hobby Plan 권장!

---

## 🔧 추가 설정 (선택)

### API 서버 추가 (별도 서비스)

1. Railway에서 "New Service"
2. 같은 GitHub 레포 선택
3. "Settings" → "Build"
   - Dockerfile Path: `Dockerfile.api`
4. "Variables" 탭에서 동일한 환경 변수 설정

이제 API 서버도 실행됩니다!

---

## 📱 모니터링

### Railway 대시보드

- **Deployments**: 배포 상태
- **Metrics**: CPU, 메모리
- **Logs**: 실시간 로그

### 텔레그램 알림 (나중에 추가)

스케줄러에서 텔레그램으로 알림 전송 가능!

---

## ❓ 문제 해결

### 배포 실패

```bash
# 로그 확인
railway logs

# 재배포
railway up
```

### MySQL 연결 실패

- Railway 대시보드에서 `DATABASE_URL` 확인
- `config.py`가 자동으로 파싱함

### 스케줄러 안 돌아감

- 로그에서 에러 확인
- 환경 변수 (`APCA-API-KEY-ID`) 확인

---

## ✅ 완료!

이제 클라우드에서 자동으로 데이터를 수집합니다! 🚀

**다음:**
- 전략 엔진 팀 구현
- AI/RAG 팀 구현
- 리스크 관리 팀 구현

---

**질문이 있으면 `RAILWAY_DEPLOYMENT.md`를 참조하세요!**
