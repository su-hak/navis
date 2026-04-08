# AI Team 빠른 시작 ⚡

5분 안에 AI Team 실행하기!

---

## 1️⃣ 필수 요구사항

### API 키 발급
Anthropic Claude API 키가 필요합니다:
- https://console.anthropic.com/ 에서 발급

---

## 2️⃣ 설정

### 의존성 설치

```bash
pip install -r ai_team/requirements.txt
```

### 환경 변수 설정

`.env` 파일을 열고 다음을 추가:

```bash
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

**중요**:
- `OPENAI_API_KEY`가 아니라 `ANTHROPIC_API_KEY`입니다
- Anthropic Claude API를 사용합니다

---

## 3️⃣ 실행

### 방법 A: 간단한 예제 실행 (권장)

```bash
python run_ai_example.py
```

이 명령어로 다음을 테스트할 수 있습니다:
- ✅ 뉴스 감성 분석
- ✅ 시장 리스크 평가
- ✅ 점수 보정 계산

### 방법 B: API 서버 실행

```bash
python run_ai_team.py
```

그 다음 브라우저에서:
- API 문서: http://localhost:8001/docs
- 헬스 체크: http://localhost:8001/health

---

## 4️⃣ API 사용 예제

### Python에서 사용

```python
import requests

# 뉴스 감성 분석
response = requests.post(
    'http://localhost:8001/api/news/analyze',
    json={'symbol': 'AAPL'}
)
result = response.json()
print(f"Sentiment: {result['sentiment_score']}")

# 점수 보정
response = requests.post(
    'http://localhost:8001/api/news/score-adjustment',
    json={'symbol': 'AAPL'}
)
adjustment = response.json()['adjustment']
print(f"Adjustment: {adjustment:+.2f}")
```

### curl로 사용

```bash
# 뉴스 분석
curl -X POST http://localhost:8001/api/news/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL"}'

# 시장 리스크
curl http://localhost:8001/api/market/risk
```

---

## 5️⃣ Strategy Engine과 통합

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

# 최종 점수 계산
final_score = base_score + adjustment
print(f"Final Score: {final_score}")
```

---

## ❌ 문제 해결

### ModuleNotFoundError

```
ModuleNotFoundError: No module named 'ai_team'
```

**해결**: 프로젝트 루트(`C:\navis`)에서 실행하세요:
```bash
cd C:\navis
python run_ai_team.py
```

### API 키 오류

```
Error: ANTHROPIC_API_KEY가 설정되지 않았습니다
```

**해결**: `.env` 파일에 API 키 추가:
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 포트 사용 중

```
Error: [Errno 48] Address already in use
```

**해결**: 다른 포트 사용:
```bash
AI_TEAM_PORT=8002 python run_ai_team.py
```

---

## 📚 더 알아보기

- [RUN_GUIDE.md](ai_team/RUN_GUIDE.md) - 상세한 실행 가이드
- [README.md](ai_team/README.md) - 전체 문서
- [INTEGRATION_GUIDE.md](ai_team/INTEGRATION_GUIDE.md) - 통합 가이드
- [AI_TEAM_SUMMARY.md](AI_TEAM_SUMMARY.md) - 구현 요약

---

## ✅ 체크리스트

- [ ] Anthropic API 키 발급
- [ ] 의존성 설치 (`pip install -r ai_team/requirements.txt`)
- [ ] `.env` 파일에 `ANTHROPIC_API_KEY` 설정
- [ ] 예제 실행 (`python run_ai_example.py`)
- [ ] API 서버 실행 (`python run_ai_team.py`)
- [ ] API 문서 확인 (http://localhost:8001/docs)

---

**준비 완료!** 🎉

이제 AI Team을 다른 모듈들과 통합할 수 있습니다.
