# AI Team - Railway 배포용

비정형 데이터 해석 및 전략 보정 API 서비스

## 🚀 빠른 배포

```bash
cd ai_team
railway init
railway up
```

## 🔑 필수 환경 변수 (Railway에서 설정)

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## 📊 API 엔드포인트

**뉴스 분석:**
- `POST /api/news/analyze` - 뉴스 감성 분석
- `POST /api/news/score-adjustment` - 점수 보정 (-10 ~ +10)

**시장 리스크:**
- `GET /api/market/risk` - 시장 전체 리스크 평가

**AI Agent:**
- `POST /api/agent/analyze` - AI 종합 분석

**RAG:**
- `POST /api/rag/search` - 지식 베이스 검색
- `POST /api/rag/add-news` - 뉴스 추가

**유틸리티:**
- `GET /health` - 헬스 체크
- `GET /docs` - API 문서

## 🔗 다른 서비스와 통합

### Strategy Engine 통합

```python
import requests

# 점수 보정
response = requests.post(
    f"{AI_TEAM_URL}/api/news/score-adjustment",
    json={"symbol": "AAPL"}
)
adjustment = response.json()['adjustment']

# 최종 점수 = 기본 점수 + AI 보정
final_score = base_score + adjustment
```

## 💰 비용

- Railway: $20/month (Pro)
- Anthropic API: ~$1-2/day (100종목)

## 📚 전체 문서

자세한 내용: `RAILWAY_DEPLOYMENT.md`

## ⚠️ 주의

1. Anthropic API 크레딧 충전 필수
2. 환경 변수 설정 필수
3. CORS 설정 확인

**배포 준비 완료!** 🎉
