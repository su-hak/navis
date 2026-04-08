# AI / RAG Team

AI 자동매매 시스템의 AI/RAG 팀 모듈

## 개요

AI/RAG 팀은 비정형 데이터 해석 및 전략 보정을 담당합니다.

### 주요 기능

1. **뉴스 분석** (감성/이벤트)
   - 뉴스 수집 및 크롤링
   - LLM 기반 감성 분석
   - 주요 이벤트 및 리스크 요인 추출

2. **RAG 시스템**
   - FAISS 기반 벡터 DB
   - 문서 임베딩 및 검색
   - 컨텍스트 기반 답변 생성

3. **LangChain Agent**
   - 다양한 도구를 활용한 종목 분석
   - 자연어 대화 인터페이스
   - 전략 점수 보정 제안

4. **FastAPI 서버**
   - REST API 제공
   - 다른 팀과의 통합 지원

---

## 프로젝트 구조

```
ai_team/
├── news/                   # 뉴스 수집 및 분석
│   ├── collector.py        # 뉴스 수집기
│   └── analyzer.py         # 뉴스 감성 분석
├── rag/                    # RAG 시스템
│   ├── vector_store.py     # 벡터 스토어 관리
│   └── retriever.py        # RAG 검색기
├── agents/                 # LangChain Agent
│   └── trading_agent.py    # 트레이딩 에이전트
├── prompts/                # 프롬프트 템플릿
│   └── templates.py        # 프롬프트 정의
├── api/                    # FastAPI 서버
│   └── main.py             # API 엔드포인트
├── tests/                  # 테스트
│   ├── test_news_analyzer.py
│   └── test_rag.py
├── config.py               # 설정
├── requirements.txt        # 의존성
└── README.md               # 이 문서
```

---

## 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r ai_team/requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 API 키를 설정합니다:

```bash
# OpenAI API (필수)
ANTHROPIC_API_KEY=sk-your-openai-api-key

# News API (선택 - 무료 대안으로 RSS 사용 가능)
NEWS_API_KEY=your-news-api-key
```

### 3. API 서버 실행

```bash
# AI Team API 서버 실행
python -m uvicorn ai_team.api.main:app --host 0.0.0.0 --port 8001
```

또는:

```bash
cd ai_team/api
python main.py
```

---

## 사용 방법

### 1. 뉴스 분석

```python
from ai_team.news.analyzer import NewsAnalyzer

analyzer = NewsAnalyzer()

# 뉴스 감성 분석
result = analyzer.analyze_news_sentiment('AAPL')
print(f"Sentiment: {result['sentiment_score']}")
print(f"Key Events: {result['key_events']}")
print(f"Risk Factors: {result['risk_factors']}")

# 점수 보정값 계산
adjustment = analyzer.calculate_score_adjustment('AAPL')
print(f"Score Adjustment: {adjustment}")
```

### 2. RAG 시스템

```python
from ai_team.rag.vector_store import VectorStoreManager
from ai_team.rag.retriever import RAGRetriever

# 벡터 스토어 초기화
vector_store = VectorStoreManager()

# 뉴스 추가
news_list = [
    {
        'title': 'Apple announces new iPhone',
        'description': 'Apple unveiled the latest iPhone...',
        'source': 'TechCrunch',
        'url': 'https://...',
        'published_at': '2024-01-01'
    }
]
vector_store.add_news(news_list)

# RAG 검색
retriever = RAGRetriever(vector_store)
context = retriever.retrieve_context('What is Apple planning?')
print(context)
```

### 3. Trading Agent

```python
from ai_team.agents.trading_agent import TradingAgent

agent = TradingAgent()

# 종목 분석
result = agent.analyze_stock('TSLA', context={
    'base_score': 75,
    'rsi': 65,
    'volume_change': '+20%'
})

print(f"Analysis: {result['analysis']}")
print(f"Score Adjustment: {result['score_adjustment']}")
print(f"Recommendation: {result['recommendation']}")

# 대화
response = agent.chat("What's the market sentiment today?")
print(response)
```

---

## API 엔드포인트

### 뉴스 분석

**POST** `/api/news/analyze`
```json
{
  "symbol": "AAPL"
}
```

**POST** `/api/news/score-adjustment`
```json
{
  "symbol": "TSLA"
}
```

### 시장 리스크

**GET** `/api/market/risk`

### AI Agent

**POST** `/api/agent/analyze`
```json
{
  "symbol": "NVDA",
  "context": {
    "base_score": 80,
    "rsi": 70
  }
}
```

**POST** `/api/agent/chat?message=What is the market trend?`

### RAG

**POST** `/api/rag/search`
```json
{
  "query": "Tesla earnings",
  "k": 5
}
```

**POST** `/api/rag/add-news`
```json
{
  "news_list": [...]
}
```

전체 API 문서: `http://localhost:8001/docs`

---

## 다른 팀과의 통합

### Strategy Engine과 통합

```python
import requests

# Strategy Engine에서 점수 계산
base_score = 75

# AI Team에 점수 보정 요청
response = requests.post(
    'http://localhost:8001/api/news/score-adjustment',
    json={'symbol': 'AAPL'}
)
adjustment = response.json()['adjustment']

# 최종 점수
final_score = base_score + adjustment
print(f"Final Score: {final_score}")
```

### Data Collection과 통합

```python
# Data Collection에서 수집한 뉴스를 RAG에 추가
response = requests.post(
    'http://localhost:8001/api/rag/add-news',
    json={'news_list': collected_news}
)
```

---

## 산출물

### 1. AI 분석 결과

```python
{
    'sentiment_score': 0.8,       # -1.0 ~ 1.0
    'sentiment_label': 'positive',
    'key_events': ['earnings beat', 'new product'],
    'risk_factors': ['supply chain issues'],
    'summary': '...',
    'news_count': 15
}
```

### 2. 점수 보정값

```python
{
    'symbol': 'AAPL',
    'adjustment': 8.5,  # -10.0 ~ +10.0
    'timestamp': '2024-01-01T12:00:00'
}
```

### 3. 시장 리스크

```python
{
    'risk_level': 'medium',  # low/medium/high
    'risk_score': 0.5,       # 0.0 ~ 1.0
    'factors': ['inflation', 'interest rates']
}
```

---

## 테스트

```bash
# 전체 테스트 실행
pytest ai_team/tests/ -v

# 특정 테스트만 실행
pytest ai_team/tests/test_news_analyzer.py -v
```

---

## 설정 옵션

`ai_team/config.py`에서 다음 설정을 변경할 수 있습니다:

```python
# OpenAI 모델
openai_model = "gpt-4-turbo-preview"
openai_temperature = 0.3

# 뉴스 수집
max_news_per_symbol = 20
news_lookback_hours = 24

# RAG
vector_db_path = "./ai_team/data/vector_db"
embedding_model = "text-embedding-3-small"
top_k_results = 5

# 점수 보정
max_score_adjustment = 10.0
```

---

## 주의사항

### AI의 역할

✅ **허용**:
- 시장 분석 및 해석
- 뉴스 감성 분석
- 점수 보정 제안
- 리스크 경고

❌ **금지**:
- 직접 주문 실행
- 리스크 관리 규칙 변경
- 최종 매매 의사결정

### 비용 관리

- OpenAI API 사용량 모니터링 필요
- 캐싱을 통한 중복 요청 방지
- 필요시 더 저렴한 모델 사용 (gpt-3.5-turbo)

---

## 로드맵

### Phase 1 (완료)
- ✅ 뉴스 수집 및 감성 분석
- ✅ RAG 시스템 구축
- ✅ LangChain Agent 구현
- ✅ FastAPI 서버

### Phase 2 (예정)
- [ ] 백테스트 검증
- [ ] 성능 최적화
- [ ] 더 많은 뉴스 소스 추가
- [ ] 실시간 뉴스 스트리밍

### Phase 3 (예정)
- [ ] 멀티모달 분석 (차트 이미지 분석)
- [ ] 소셜 미디어 감성 분석
- [ ] 커스텀 LLM 파인튜닝

---

## 라이선스

MIT License

---

## 기여

이슈 및 풀 리퀘스트를 환영합니다!
