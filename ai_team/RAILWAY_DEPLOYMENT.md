# AI Team Railway 배포 가이드

## 📋 배포 전 체크리스트

- [x] `Dockerfile` 준비됨
- [x] `railway.toml` 준비됨
- [x] `requirements.txt` 준비됨
- [x] `.dockerignore` 준비됨
- [ ] Railway 프로젝트 생성
- [ ] 환경 변수 설정
- [ ] 배포 및 테스트

---

## 🚀 배포 단계

### 1. Railway 프로젝트 생성

```bash
# ai_team 디렉토리에서
cd ai_team
railway init
```

또는 Railway 웹에서 "New Project" → "Deploy from GitHub repo"

---

### 2. 환경 변수 설정 (중요!)

Railway 대시보드 → Variables 탭에서 설정:

**필수:**
```
ANTHROPIC_API_KEY=sk-ant-your-actual-key
```

**선택적:**
```
OPENAI_API_KEY=sk-your-openai-key
NEWS_API_KEY=your-news-api-key
```

---

### 3. 배포

```bash
# Git이 초기화되어 있다면
git add .
git commit -m "Deploy AI Team"
railway up

# 또는 Railway CLI 없이
git push
```

---

## 🔗 다른 서비스와 통합

### Strategy Engine에서 호출

```python
import requests

# AI Team URL (Railway에서 확인)
AI_TEAM_URL = "https://your-ai-team.railway.app"

# 점수 보정 요청
response = requests.post(
    f"{AI_TEAM_URL}/api/news/score-adjustment",
    json={"symbol": "AAPL"},
    timeout=30
)

adjustment = response.json()['adjustment']
```

### Data Collection에서 뉴스 저장

```python
# 수집한 뉴스를 AI Team RAG에 저장
response = requests.post(
    f"{AI_TEAM_URL}/api/rag/add-news",
    json={"news_list": news_data},
    timeout=60
)
```

---

## 📊 배포 확인

배포 후 다음 URL로 테스트:

```bash
# 헬스 체크
curl https://your-ai-team.railway.app/health

# API 문서
https://your-ai-team.railway.app/docs

# 뉴스 분석 테스트
curl -X POST https://your-ai-team.railway.app/api/news/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}'
```

---

## 💰 비용 예상

**Railway:**
- Free tier: $5 credit (월)
- Pro: $20/month (500시간 실행)

**Anthropic API:**
- Claude 3.5 Sonnet: $3/$15 per 1M tokens
- 하루 100종목 분석: ~$1-2

**총 예상 비용:** ~$25-30/month

---

## ⚠️ 주의사항

1. **API 키 보안**
   - 환경 변수로만 관리
   - 코드에 하드코딩 금지
   - `.env` 파일은 `.gitignore`에 추가

2. **Anthropic API 크레딧**
   - 배포 전 크레딧 충전 필수
   - https://console.anthropic.com/settings/billing

3. **Rate Limiting**
   - API 호출 제한 고려
   - 필요시 캐싱 구현

---

## 🔄 업데이트

코드 변경 후:

```bash
git add .
git commit -m "Update AI Team"
git push
```

Railway가 자동으로 재배포합니다.

---

## 📞 API 엔드포인트

배포 후 사용 가능한 엔드포인트:

- `POST /api/news/analyze` - 뉴스 감성 분석
- `POST /api/news/score-adjustment` - 점수 보정
- `GET /api/market/risk` - 시장 리스크
- `POST /api/agent/analyze` - AI Agent 분석
- `POST /api/rag/search` - RAG 검색
- `POST /api/rag/add-news` - 뉴스 추가
- `GET /health` - 헬스 체크
- `GET /docs` - API 문서

---

## ✅ 배포 완료 후

1. Railway URL 확인
2. Strategy Engine에 URL 설정
3. Data Collection에 URL 설정
4. 통합 테스트
5. 모니터링 설정

---

**배포 준비 완료!** 🚀
