# Execution Team 배포 가이드

**작성일**: 2026-04-07
**대상**: Execution Team FastAPI 서버 배포

---

## 📋 배포 전 체크리스트

- [ ] `requirements.txt` 파일 확인
- [ ] `start.sh` 실행 권한 확인
- [ ] 환경변수 설정 완료
- [ ] Alpaca API 키 발급 완료

---

## 🚀 배포 방법

### 1. Railway 배포

#### 1-1. Railway CLI 설치 (선택)
```bash
npm install -g @railway/cli
```

#### 1-2. 배포
```bash
# Railway에 로그인
railway login

# 프로젝트 생성
railway init

# 환경변수 설정
railway variables set ALPACA_API_KEY=your_key_here
railway variables set ALPACA_SECRET_KEY=your_secret_here
railway variables set ALPACA_BASE_URL=https://paper-api.alpaca.markets

# 배포
railway up
```

### 2. Heroku 배포

```bash
# Heroku CLI 설치 및 로그인
heroku login

# 앱 생성
heroku create your-execution-team-app

# 환경변수 설정
heroku config:set ALPACA_API_KEY=your_key_here
heroku config:set ALPACA_SECRET_KEY=your_secret_here
heroku config:set ALPACA_BASE_URL=https://paper-api.alpaca.markets

# 배포
git push heroku master
```

### 3. Docker 배포

```bash
# Dockerfile이 있는 경우
docker build -t execution-team .
docker run -p 8000:8000 --env-file .env execution-team
```

---

## ⚙️ 필수 환경변수

배포 플랫폼에 다음 환경변수를 설정하세요:

| 환경변수 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `ALPACA_API_KEY` | ✅ | Alpaca API 키 | `PKUOJ4ZWX...` |
| `ALPACA_SECRET_KEY` | ✅ | Alpaca Secret 키 | `DRg4ASRo...` |
| `ALPACA_BASE_URL` | ✅ | Alpaca API URL | `https://paper-api.alpaca.markets` |
| `ENABLE_CIRCUIT_BREAKER` | ⚠️ | 서킷 브레이커 활성화 | `true` |
| `MAX_RETRY_ATTEMPTS` | ⚠️ | 최대 재시도 횟수 | `3` |
| `ORDER_STORAGE_PATH` | ⚠️ | 주문 저장 경로 | `logs/execution/orders` |
| `LOG_LEVEL` | ⚠️ | 로그 레벨 | `INFO` |
| `PORT` | ⚠️ | 서버 포트 (자동 설정됨) | `8000` |

---

## 📂 배포 파일 설명

### `requirements.txt`
Python 패키지 의존성 목록. Railpack/Heroku가 이 파일을 읽고 자동으로 패키지를 설치합니다.

### `start.sh`
서버 시작 스크립트. uvicorn으로 FastAPI 앱을 실행합니다.

```bash
#!/bin/bash
exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
```

### `Procfile`
Railway/Heroku용 프로세스 정의 파일.

```
web: uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
```

### `runtime.txt`
Python 버전 지정.

```
python-3.11
```

---

## 🔍 배포 확인

### 1. 헬스 체크
```bash
curl https://your-app-url.railway.app/health
```

**예상 응답**:
```json
{
  "status": "healthy",
  "timestamp": "2026-04-07T12:00:00"
}
```

### 2. API 문서 확인
브라우저에서 접속:
```
https://your-app-url.railway.app/docs
```

Swagger UI가 표시되면 정상입니다.

---

## ⚠️ 주의사항

### Paper Trading vs Live Trading

**Paper Trading (권장)**:
```bash
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```
- ✅ 가상 돈으로 테스트
- ✅ 실제 손실 없음
- ✅ API 동작 확인용

**Live Trading (주의!)**:
```bash
ALPACA_BASE_URL=https://api.alpaca.markets
```
- ⚠️ 실제 돈 사용
- ⚠️ 실제 손실 발생 가능
- ⚠️ 충분한 테스트 후에만 사용

### 환경변수 보안
- API 키를 코드에 직접 넣지 마세요
- `.env` 파일을 Git에 커밋하지 마세요
- 배포 플랫폼의 환경변수 설정 기능을 사용하세요

---

## 🛠 트러블슈팅

### Q1. "Railpack could not determine how to build the app"
**원인**: `requirements.txt` 파일이 없음
**해결**: `requirements.txt` 파일 생성 확인

### Q2. "Script start.sh not found"
**원인**: `start.sh` 파일이 없거나 실행 권한 없음
**해결**:
```bash
chmod +x start.sh
```

### Q3. "ALPACA_API_KEY is not set"
**원인**: 환경변수가 설정되지 않음
**해결**: 배포 플랫폼에서 환경변수 설정

### Q4. "Module not found: execution_team"
**원인**: 모듈 경로 문제
**해결**: `PYTHONPATH` 설정 또는 절대 import 사용

---

## 📊 로컬 테스트

배포 전 로컬에서 테스트:

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 수정

# 서버 실행
./start.sh

# 또는
uvicorn api:app --reload
```

브라우저에서 `http://localhost:8000/docs` 접속

---

## 📈 성능 최적화

### Worker 수 조정
```bash
# start.sh 수정
exec uvicorn api:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers 4 \  # CPU 코어 수에 맞게 조정
    --log-level info
```

### Gunicorn 사용 (프로덕션)
```bash
pip install gunicorn

# Procfile 수정
web: gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}
```

---

## ✅ 배포 성공 확인

1. ✅ 앱이 정상적으로 시작됨
2. ✅ `/health` 엔드포인트 응답
3. ✅ `/docs` Swagger UI 접근 가능
4. ✅ Alpaca 브로커 연결 성공
5. ✅ 주문 API 동작 확인

---

**작성자**: Execution Team Lead
**작성일**: 2026-04-07
**상태**: ✅ 배포 준비 완료
