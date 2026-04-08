# AI Team 배포 상태

## ✅ 구현 완료 사항

### 1. 핵심 기능
- ✅ **뉴스 수집 및 분석**: NewsAPI + Google News RSS
- ✅ **Claude 기반 감성 분석**: Anthropic Claude 3.5 Sonnet
- ✅ **점수 보정 시스템**: -10.0 ~ +10.0 범위
- ✅ **시장 리스크 평가**: SPY/QQQ/DIA 분석
- ✅ **Native Tool Calling Agent**: 자율적 도구 선택 및 멀티스텝 추론
- ✅ **FastAPI REST API**: 포트 8001

### 2. Agent 구현
- ✅ **NativeTradingAgent**: Anthropic native tool calling 사용
  - 도구: `analyze_news_sentiment`, `get_news_count`, `assess_market_risk`
  - RAG 도구 (`search_knowledge_base`): 선택적 (LangChain 버전 문제로 optional)
  - 자율적 도구 선택: Agent가 필요에 따라 도구를 선택하고 실행
  - 멀티스텝 추론: 여러 도구를 조합하여 분석

### 3. 배포 파일
- ✅ `Dockerfile`: 컨테이너 빌드 설정
- ✅ `railway.toml`: Railway 배포 설정
- ✅ `.dockerignore`: 불필요한 파일 제외
- ✅ `requirements.txt`: 전체 의존성 (RAG 포함)
- ✅ `requirements_minimal.txt`: 최소 의존성 (RAG 제외)
- ✅ `.env.railway`: 환경 변수 템플릿

### 4. 코드 품질
- ✅ 구문 검증 완료 (6개 핵심 파일)
- ✅ Logger 초기화 순서 버그 수정
- ✅ RAG optional 처리로 안정성 확보

## ⚠️ 배포 전 필수 작업

### 1. Anthropic API 크레딧 충전
```
https://console.anthropic.com/settings/billing
```
현재 크레딧 부족으로 API 호출 불가.
최소 $5 이상 충전 권장.

### 2. Railway 환경 변수 설정
Railway 대시보드에서 다음 환경 변수 설정 필요:

**필수**:
- `ANTHROPIC_API_KEY`: Claude API 키
- `NEWS_API_KEY`: NewsAPI 키 (https://newsapi.org)

**선택** (RAG 사용 시):
- `OPENAI_API_KEY`: OpenAI 임베딩용 (RAG 활성화 원할 때만)

## 📦 배포 방법

### Option 1: 전체 기능 (RAG 포함)
```bash
# requirements.txt 사용
# Railway에서 OPENAI_API_KEY 설정 필요
```

### Option 2: 최소 기능 (RAG 제외) - 권장
```bash
# requirements_minimal.txt 사용
# ANTHROPIC_API_KEY + NEWS_API_KEY만 필요
```

**권장**: RAG는 현재 LangChain 버전 이슈로 optional 처리됨.
최소 기능으로 배포 후, 필요시 RAG 추가 권장.

Railway에서 Dockerfile을 사용하는 경우:
```dockerfile
# Dockerfile에서 requirements.txt를
# requirements_minimal.txt로 변경 가능
```

## 🔌 API 엔드포인트

배포 후 사용 가능한 엔드포인트:

### 뉴스 분석
```
POST /api/news/analyze
{
  "symbol": "AAPL"
}
```

### 점수 보정
```
POST /api/news/score-adjustment
{
  "symbol": "AAPL"
}
```

### 시장 리스크
```
GET /api/market/risk
```

### Agent 분석
```
POST /api/agent/analyze
{
  "symbol": "AAPL",
  "context": {
    "base_score": 75,
    "rsi": 65
  }
}
```

### 헬스체크
```
GET /health
```

## 🔗 다른 팀과의 통합

### Strategy Engine 통합
Strategy Engine에서 점수 보정 요청:
```python
import requests

response = requests.post(
    "https://ai-team.railway.app/api/news/score-adjustment",
    json={"symbol": "AAPL"}
)
adjustment = response.json()["adjustment"]  # -10.0 ~ +10.0
```

### Data Collection 연동
현재는 독립적으로 뉴스 수집.
향후 Data Collection에서 수집한 데이터를 받아올 수 있음.

## 📊 시스템 아키텍처

```
┌─────────────────┐
│ Strategy Engine │
│  (Railway)      │
└────────┬────────┘
         │ 점수 보정 요청
         ▼
┌─────────────────┐
│   AI Team       │◄──── News Sources (NewsAPI, RSS)
│  (Port 8001)    │
│                 │
│ - NewsAnalyzer  │
│ - NativeAgent   │
│ - RAG (opt)     │
└─────────────────┘
```

## ✅ 배포 체크리스트

- [ ] Anthropic API 크레딧 충전
- [ ] NewsAPI 키 발급 (https://newsapi.org)
- [ ] Railway 환경 변수 설정
  - [ ] ANTHROPIC_API_KEY
  - [ ] NEWS_API_KEY
  - [ ] (선택) OPENAI_API_KEY
- [ ] Railway에 ai_team 디렉토리 배포
- [ ] Health check 확인: `GET /health`
- [ ] Strategy Engine에서 통합 테스트

## 📝 다음 단계

1. **즉시**: Anthropic API 크레딧 충전
2. **배포**: Railway에 ai_team 배포
3. **테스트**: 각 엔드포인트 동작 확인
4. **통합**: Strategy Engine과 연동 테스트
5. **선택**: RAG 기능 활성화 (LangChain 버전 안정화 후)

## 🐛 알려진 이슈

### LangChain 버전 호환성
- `langchain-openai`의 `LangSmithParams` import 오류
- 해결: RAG를 optional로 처리, 시스템은 RAG 없이 정상 동작
- 영향: `search_knowledge_base` 도구만 비활성화, 나머지 기능 정상

### 해결 방법
1. 현재: RAG 제외하고 사용 (권장)
2. 향후: LangChain 버전 안정화 후 RAG 활성화

---

**최종 상태**: ✅ 배포 준비 완료 (API 크레딧 충전만 필요)
