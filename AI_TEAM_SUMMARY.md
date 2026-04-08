# AI/RAG 팀 구현 완료 ✅

기획서의 **3️⃣ AI / RAG 팀** 구현이 완료되었습니다!

---

## 📌 구현 내용

### 1. 뉴스 분석 ✅
- ✅ 뉴스 수집기 (NewsAPI + RSS)
- ✅ LLM 기반 감성 분석
- ✅ 주요 이벤트 추출
- ✅ 리스크 요인 분석
- ✅ 점수 보정값 계산 (-10 ~ +10)

### 2. RAG 시스템 ✅
- ✅ FAISS 벡터 스토어
- ✅ OpenAI Embeddings
- ✅ 문서 검색 및 컨텍스트 생성
- ✅ 뉴스 저장 및 검색

### 3. LangChain Agent ✅
- ✅ Trading Agent 구현
- ✅ 프롬프트 설계 (헤지펀드 트레이더 페르소나)
- ✅ 도구 통합 (뉴스 분석, RAG 검색, 시장 리스크)
- ✅ 대화형 인터페이스

### 4. FastAPI 서버 ✅
- ✅ REST API 엔드포인트
- ✅ 뉴스 분석 API
- ✅ 점수 보정 API
- ✅ 시장 리스크 API
- ✅ Agent 분석 API
- ✅ RAG 검색 API

---

## 📁 프로젝트 구조

```
ai_team/
├── news/                       # 뉴스 모듈
│   ├── collector.py            # 뉴스 수집기 (NewsAPI + RSS)
│   └── analyzer.py             # 감성 분석 (LangChain + OpenAI)
├── rag/                        # RAG 모듈
│   ├── vector_store.py         # FAISS 벡터 스토어
│   └── retriever.py            # RAG 검색기
├── agents/                     # Agent 모듈
│   └── trading_agent.py        # 트레이딩 에이전트
├── prompts/                    # 프롬프트
│   └── templates.py            # 프롬프트 템플릿
├── api/                        # FastAPI 서버
│   └── main.py                 # API 엔드포인트
├── tests/                      # 테스트
│   ├── test_news_analyzer.py
│   └── test_rag.py
├── config.py                   # 설정
├── requirements.txt            # 의존성
├── README.md                   # 전체 문서
├── QUICKSTART.md               # 빠른 시작
├── INTEGRATION_GUIDE.md        # 통합 가이드
├── example.py                  # 사용 예제
└── run_api.py                  # API 서버 실행 스크립트
```

---

## 🚀 빠른 시작

### 1. 의존성 설치
```bash
pip install -r ai_team/requirements.txt
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성
ANTHROPIC_API_KEY=sk-your-key-here
```

### 3. API 서버 실행
```bash
python ai_team/run_api.py
```

API 문서: http://localhost:8001/docs

### 4. 예제 실행
```bash
python ai_team/example.py
```

---

## 📊 주요 기능

### 1. 뉴스 감성 분석

```python
from ai_team.news.analyzer import NewsAnalyzer

analyzer = NewsAnalyzer()
result = analyzer.analyze_news_sentiment('AAPL')

# 결과:
# {
#   'sentiment_score': 0.8,      # -1.0 ~ 1.0
#   'sentiment_label': 'positive',
#   'key_events': ['earnings beat', 'new product'],
#   'risk_factors': ['supply chain'],
#   'summary': '...',
#   'news_count': 15
# }
```

### 2. 점수 보정

```python
adjustment = analyzer.calculate_score_adjustment('AAPL')
# 반환: -10.0 ~ +10.0

# Strategy Engine 점수와 결합
base_score = 75
final_score = base_score + adjustment  # 예: 75 + 8.5 = 83.5
```

### 3. AI Agent 분석

```python
from ai_team.agents.trading_agent import TradingAgent

agent = TradingAgent()
result = agent.analyze_stock('NVDA', context={
    'base_score': 78,
    'rsi': 65
})

# 결과:
# {
#   'analysis': '종합 분석 텍스트...',
#   'score_adjustment': 7.5,
#   'recommendation': 'BUY'
# }
```

### 4. API 호출

```bash
# 뉴스 분석
curl -X POST http://localhost:8001/api/news/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}'

# 점수 보정
curl -X POST http://localhost:8001/api/news/score-adjustment \
  -H "Content-Type: application/json" \
  -d '{"symbol": "TSLA"}'

# 시장 리스크
curl http://localhost:8001/api/market/risk
```

---

## 🔗 다른 팀과의 통합

### Strategy Engine과 통합

```python
import requests

# Strategy Engine의 기본 점수
base_score = 75

# AI Team에서 점수 보정
response = requests.post(
    'http://localhost:8001/api/news/score-adjustment',
    json={'symbol': 'AAPL'}
)
adjustment = response.json()['adjustment']

# 최종 점수
final_score = base_score + adjustment
```

자세한 내용: [INTEGRATION_GUIDE.md](ai_team/INTEGRATION_GUIDE.md)

---

## 📦 산출물 (기획서 요구사항)

### ✅ AI 분석 결과
- 감성 점수 (-1.0 ~ 1.0)
- 주요 이벤트 목록
- 리스크 요인 목록
- 뉴스 요약

### ✅ 점수 보정값
- 범위: -10.0 ~ +10.0
- 뉴스 감성 + 뉴스 개수 가중치 적용

### ✅ 뉴스 기반 리스크 판단
- 시장 전체 리스크 레벨 (low/medium/high)
- 리스크 점수 (0.0 ~ 1.0)
- 주요 리스크 요인

---

## 🎯 기획서 요구사항 대비

| 항목 | 상태 | 구현 위치 |
|------|------|----------|
| 뉴스 분석 (감성/이벤트) | ✅ | `ai_team/news/analyzer.py` |
| RAG 구축 | ✅ | `ai_team/rag/vector_store.py` |
| LangChain Agent 구성 | ✅ | `ai_team/agents/trading_agent.py` |
| 프롬프트 설계 | ✅ | `ai_team/prompts/templates.py` |
| AI 분석 결과 (점수 보정값) | ✅ | `NewsAnalyzer.calculate_score_adjustment()` |
| 뉴스 기반 리스크 판단 | ✅ | `NewsAnalyzer.assess_market_risk()` |
| API 제공 | ✅ | `ai_team/api/main.py` |

---

## 🧪 테스트

```bash
# 전체 테스트
pytest ai_team/tests/ -v

# 개별 테스트
pytest ai_team/tests/test_news_analyzer.py -v
pytest ai_team/tests/test_rag.py -v
```

---

## 📚 문서

- [README.md](ai_team/README.md) - 전체 문서
- [QUICKSTART.md](ai_team/QUICKSTART.md) - 빠른 시작 가이드
- [INTEGRATION_GUIDE.md](ai_team/INTEGRATION_GUIDE.md) - 다른 팀과의 통합 가이드
- [example.py](ai_team/example.py) - 사용 예제

---

## 🎨 핵심 특징

### 1. 페르소나 기반 프롬프트
기획서 요구사항에 따라 "공격적인 헤지펀드 트레이더" 페르소나로 설계:
- 수익 극대화 목표
- 리스크 규칙 절대 준수
- 데이터 기반 객관적 판단

### 2. 안전장치
기획서의 제한사항 준수:
- ❌ 주문 실행 금지
- ❌ 리스크 룰 변경 금지
- ✅ 분석 및 조언만 제공

### 3. 다중 데이터 소스
- NewsAPI (유료, 고품질)
- Google News RSS (무료 대안)
- 추후 확장 가능

---

## 🔧 기술 스택

- **LLM**: OpenAI GPT-4 Turbo
- **Framework**: LangChain
- **Vector DB**: FAISS
- **Embeddings**: OpenAI text-embedding-3-small
- **API Server**: FastAPI
- **News Sources**: NewsAPI, RSS Feeds

---

## 💰 비용 고려사항

### OpenAI API 비용 (참고)
- GPT-4 Turbo: $10/1M input tokens, $30/1M output tokens
- Embeddings: $0.13/1M tokens

### 비용 절감 방법
1. 캐싱 활용 (동일 종목 중복 조회 방지)
2. 배치 처리
3. 필요시 GPT-3.5-Turbo 사용 ($1/1M tokens)

---

## 🚀 다음 단계

### Phase 2 (예정)
- [ ] 백테스트 검증
- [ ] 성능 최적화 (캐싱)
- [ ] 더 많은 뉴스 소스
- [ ] 실시간 뉴스 스트리밍

### Phase 3 (예정)
- [ ] 멀티모달 (차트 이미지 분석)
- [ ] 소셜 미디어 감성
- [ ] 커스텀 LLM 파인튜닝

---

## ✅ 완료 체크리스트

- [x] 뉴스 수집 모듈
- [x] 뉴스 감성 분석
- [x] RAG 벡터 스토어
- [x] RAG 검색 및 컨텍스트 생성
- [x] LangChain Agent
- [x] 프롬프트 설계
- [x] FastAPI 서버
- [x] API 엔드포인트
- [x] 테스트 코드
- [x] 문서화
- [x] 사용 예제
- [x] 통합 가이드
- [x] 빠른 시작 가이드

---

## 🎉 완료!

AI/RAG 팀 구현이 완료되었습니다.

이제 다른 팀들과 통합하여 전체 자동매매 시스템을 완성할 수 있습니다!
