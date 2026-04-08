# AI Team 빠른 시작 가이드

AI/RAG 팀을 5분 안에 실행해보세요!

---

## 1. 설치

### 의존성 설치

```bash
pip install -r ai_team/requirements.txt
```

---

## 2. 환경 변수 설정

`.env` 파일을 생성하고 OpenAI API 키를 추가하세요:

```bash
# .env 파일 생성
ANTHROPIC_API_KEY=sk-your-openai-api-key-here
```

OpenAI API 키 발급: https://platform.openai.com/api-keys

---

## 3. 예제 실행

### 옵션 A: Python 스크립트로 테스트

```bash
python ai_team/example.py
```

이 스크립트는 다음을 시연합니다:
- 뉴스 감성 분석
- 시장 리스크 평가
- RAG 시스템
- Trading Agent

### 옵션 B: API 서버 실행

```bash
python ai_team/run_api.py
```

또는:

```bash
python -m uvicorn ai_team.api.main:app --host 0.0.0.0 --port 8001
```

API 문서: http://localhost:8001/docs

---

## 4. 기본 사용법

### Python 코드에서 사용

```python
from ai_team.news.analyzer import NewsAnalyzer

# 뉴스 분석기 초기화
analyzer = NewsAnalyzer()

# 뉴스 감성 분석
result = analyzer.analyze_news_sentiment('AAPL')
print(f"Sentiment: {result['sentiment_score']}")

# 점수 보정값 계산
adjustment = analyzer.calculate_score_adjustment('AAPL')
print(f"Adjustment: {adjustment}")
```

### API로 사용

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

## 5. 다른 팀과 통합

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
print(f"Final Score: {final_score}")
```

---

## 6. 테스트 실행

```bash
pytest ai_team/tests/ -v
```

---

## 트러블슈팅

### OpenAI API 키 오류

```
Error: OpenAI API key not found
```

**해결**: `.env` 파일에 `ANTHROPIC_API_KEY`를 추가하세요.

### 모듈을 찾을 수 없음

```
ModuleNotFoundError: No module named 'ai_team'
```

**해결**: 프로젝트 루트 디렉토리에서 실행하세요.

### FAISS 설치 오류

**해결**: 플랫폼에 맞는 FAISS 설치:
```bash
# CPU 버전
pip install faiss-cpu

# GPU 버전 (CUDA 필요)
pip install faiss-gpu
```

---

## 다음 단계

- [전체 문서](README.md) 읽기
- [API 문서](http://localhost:8001/docs) 탐색
- 커스텀 프롬프트 설계

---

## 지원

문제가 발생하면 이슈를 등록하세요!
