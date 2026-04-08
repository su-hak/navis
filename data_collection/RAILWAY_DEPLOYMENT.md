# Railway 배포 가이드

Railway에 데이터 수집 시스템을 배포하는 완전한 가이드입니다.

---

## 🚂 Railway 배포 구조

### 권장 구성

```
Railway Project
├── Service 1: MySQL Database (Railway 제공)
├── Service 2: Data Collector (스케줄러)
└── Service 3: API Server (FastAPI) - 선택
```

---

## 📋 사전 준비

### 1. Railway 프로젝트 생성

1. https://railway.app 로그인
2. "New Project" 클릭
3. "Deploy MySQL" 선택

### 2. MySQL 데이터베이스 생성

Railway에서 MySQL 자동 프로비저닝:
- 자동으로 호스트, 포트, 비밀번호 생성
- 환경 변수로 접근 가능

---

## 🔧 배포 파일 준비

### 필수 파일 생성

Railway는 다음 파일들이 필요합니다:

1. **Dockerfile** - 컨테이너 이미지
2. **railway.json** - Railway 설정
3. **requirements.txt** - 이미 있음
4. **.env.example** - 환경 변수 템플릿

---

## 📦 1단계: Dockerfile 생성

Railway용 최적화된 Dockerfile:

```dockerfile
# Dockerfile
FROM python:3.11-slim

# 작업 디렉토리
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 스케줄러 실행
CMD ["python", "schedulers/data_scheduler.py"]
```

**API 서버용 Dockerfile (별도 서비스):**

```dockerfile
# Dockerfile.api
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# API 서버 실행
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "$PORT"]
```

---

## ⚙️ 2단계: Railway 설정

### railway.json

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "python schedulers/data_scheduler.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

---

## 🔐 3단계: 환경 변수 설정

Railway 대시보드에서 설정:

### MySQL 연결 (자동 생성됨)

```env
# Railway MySQL 자동 변수
MYSQL_URL=mysql://user:pass@host:port/database
DATABASE_URL=mysql://user:pass@host:port/database

# 또는 개별 변수로 파싱
MYSQL_HOST=${{MYSQL.MYSQL_HOST}}
MYSQL_PORT=${{MYSQL.MYSQL_PORT}}
MYSQL_USER=${{MYSQL.MYSQL_USER}}
MYSQL_PASSWORD=${{MYSQL.MYSQL_PASSWORD}}
MYSQL_DATABASE=${{MYSQL.MYSQL_DATABASE}}
```

### Alpaca API

```env
APCA-API-KEY-ID=your_key
APCA-API-SECRET-KEY=your_secret
```

### 타임존 (중요!)

```env
TZ=America/New_York
```

---

## 📝 4단계: 배포 준비

### .dockerignore 생성

```
# .dockerignore
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
venv/
venv_data/
.env
.env.local
*.db
*.sqlite
*.sqlite3
.git/
.gitignore
.vscode/
.idea/
*.md
!README.md
logs/
*.log
```

### .gitignore 확인

```
# .gitignore
.env
.env.local
*.db
*.sqlite
__pycache__/
venv/
logs/
```

---

## 🚀 5단계: Railway 배포

### 방법 1: GitHub 연동 (권장)

1. **GitHub에 푸시**
   ```bash
   cd C:\navis\data_collection
   git init
   git add .
   git commit -m "Initial commit for Railway deployment"
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Railway에서 연결**
   - Railway 대시보드
   - "New Project" → "Deploy from GitHub repo"
   - 레포지토리 선택
   - 자동 배포 시작

### 방법 2: Railway CLI (빠름)

```bash
# Railway CLI 설치
npm install -g @railway/cli

# 로그인
railway login

# 프로젝트 초기화
cd C:\navis\data_collection
railway init

# 배포
railway up
```

---

## 🗄️ 6단계: MySQL 초기화

### Railway MySQL에 테이블 생성

**로컬에서 Railway MySQL에 연결:**

```bash
# Railway에서 MySQL 연결 정보 복사
# 환경 변수 탭에서 확인

# Python으로 테이블 생성
python -c "
import mysql.connector
import os

# Railway MySQL 정보
conn = mysql.connector.connect(
    host='your-railway-mysql-host',
    port=3306,
    user='root',
    password='your-password',
    database='railway'
)

from database.schema import create_tables
create_tables(conn)
conn.close()
print('✓ Tables created!')
"
```

**또는 Railway 내에서 실행:**

1. Railway 서비스 → "Settings" → "One-off Command"
2. 명령어: `python database/schema.py`
3. 실행

---

## ⏰ 7단계: 스케줄러 확인

배포 후 로그 확인:

```bash
railway logs
```

**예상 출력:**
```
============================================================
Data Collection Scheduler Started
============================================================
Monitoring 10 symbols: AAPL, TSLA, NVDA, AMD, MSFT, ...

Scheduled Jobs:
  - Collect Daily Prices (daily_prices): ...
  - Collect Minute Bars (minute_bars): ...
  - Collect News (news_collection): ...
============================================================
```

---

## 📊 모니터링

### Railway 대시보드에서 확인

- **Deployments**: 배포 상태
- **Metrics**: CPU, 메모리 사용량
- **Logs**: 실시간 로그
- **Variables**: 환경 변수

### 헬스체크 추가 (권장)

```python
# schedulers/data_scheduler.py에 추가
from datetime import datetime

async def health_check():
    """Railway 헬스체크"""
    print(f"[{datetime.now()}] ✓ Scheduler is running")

# 스케줄러에 추가
scheduler.add_job(
    health_check,
    IntervalTrigger(minutes=5),
    id='health_check',
    name='Health Check'
)
```

---

## 💰 비용 예측

### Railway 요금

**Hobby Plan** ($5/month):
- MySQL: 포함
- Scheduler: ~$2-3/month (항상 실행)
- 총: **$5-8/month**

**Pro Plan** ($20/month):
- 더 많은 리소스
- 프로덕션 권장

### 최적화 팁

1. **스케줄 조정**
   - 분봉 수집: 시장 시간만
   - 뉴스: 30분 → 1시간

2. **리소스 제한**
   ```python
   # 동시 요청 수 제한
   semaphore = asyncio.Semaphore(5)
   ```

---

## 🔒 보안 체크리스트

- [ ] `.env` 파일 `.gitignore`에 포함
- [ ] API 키를 Railway 환경 변수로 설정
- [ ] GitHub에 `.env` 커밋 안 됨
- [ ] MySQL 비밀번호 강력하게 설정
- [ ] Railway 프로젝트를 Private으로 설정

---

## 🐛 트러블슈팅

### 배포 실패

```bash
# 로그 확인
railway logs

# 환경 변수 확인
railway variables

# 재배포
railway up --detach
```

### MySQL 연결 실패

```python
# Railway MySQL URL 파싱
# config.py 수정
import os
from urllib.parse import urlparse

database_url = os.getenv('DATABASE_URL')
if database_url:
    parsed = urlparse(database_url)
    MYSQL_HOST = parsed.hostname
    MYSQL_PORT = parsed.port
    MYSQL_USER = parsed.username
    MYSQL_PASSWORD = parsed.password
    MYSQL_DATABASE = parsed.path[1:]  # Remove leading /
```

### 타임존 문제

```dockerfile
# Dockerfile에 추가
ENV TZ=America/New_York
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
```

---

## 📈 다음 단계

배포 후:

1. **모니터링 설정**
   - Railway 메트릭 확인
   - 로그 모니터링

2. **알림 설정**
   - 텔레그램 봇 (나중에)
   - 에러 알림

3. **백업 설정**
   - Railway MySQL 자동 백업 활성화

4. **확장**
   - API 서버 추가 (별도 서비스)
   - 전략 엔진 배포

---

## ✅ 배포 체크리스트

준비:
- [ ] Railway 계정 및 MySQL 생성
- [ ] Dockerfile 작성
- [ ] railway.json 작성
- [ ] .dockerignore 작성
- [ ] 환경 변수 설정

배포:
- [ ] GitHub 푸시 (또는 Railway CLI)
- [ ] Railway 자동 배포
- [ ] MySQL 테이블 생성
- [ ] 로그 확인
- [ ] 스케줄러 작동 확인

운영:
- [ ] 모니터링 설정
- [ ] 백업 확인
- [ ] 비용 모니터링

---

**준비되셨나요?** 배포 파일을 생성해드릴까요? 🚀
