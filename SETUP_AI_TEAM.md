# AI Team 설정 완료 가이드

## ⚠️ 중요: API 키 설정

AI Team은 **OpenAI API**를 사용합니다 (뉴스 분석, RAG 임베딩 등).

### 1. OpenAI API 키 발급

1. https://platform.openai.com/api-keys 방문
2. 로그인 또는 회원가입
3. "Create new secret key" 클릭
4. 생성된 키 복사 (sk-로 시작)

### 2. .env 파일에 추가

`.env` 파일을 열고 다음을 추가하세요:

```bash
# AI Team - OpenAI API 키
OPENAI_API_KEY=sk-proj-your-actual-openai-key-here
```

**참고**:
- `ANTHROPIC_API_KEY`가 아니라 `OPENAI_API_KEY`입니다
- OpenAI API 키는 `sk-proj-` 또는 `sk-`로 시작합니다
- Anthropic API 키(`sk-ant-`로 시작)와는 다릅니다

### 3. 실행

```bash
# 프로젝트 루트에서
python run_ai_example.py
```

---

## 💰 비용 안내

### OpenAI API 가격 (2024년 기준)

**GPT-4 Turbo** (뉴스 분석):
- Input: $10 / 1M tokens
- Output: $30 / 1M tokens

**text-embedding-3-small** (RAG 임베딩):
- $0.02 / 1M tokens

### 예상 비용

종목 1개 분석 시:
- 뉴스 분석: 약 $0.01 - $0.05
- RAG 검색: 약 $0.001

하루 100종목 분석 시: 약 $1 - $5

### 비용 절감 방법

1. **더 저렴한 모델 사용**
   ```python
   # ai_team/config.py
   openai_model = "gpt-3.5-turbo"  # $1/1M tokens
   ```

2. **캐싱 활용** (같은 종목 중복 조회 방지)

3. **배치 처리** (한 번에 여러 종목 분석)

---

## 🔄 대안: Anthropic Claude API 사용

이미 Anthropic API 키가 있다면, 코드를 수정하여 Claude를 사용할 수 있습니다:

```python
# ai_team/news/analyzer.py
from langchain_anthropic import ChatAnthropic

self.llm = ChatAnthropic(
    model=config.anthropic_model,
    temperature=config.openai_temperature,
    api_key=config.anthropic_api_key
)
```

하지만 RAG 임베딩은 여전히 OpenAI API가 필요합니다.

---

## ✅ 설정 확인

```bash
# .env 파일 확인 (Windows)
type .env | findstr OPENAI

# .env 파일 확인 (Linux/Mac)
grep OPENAI .env
```

다음과 같이 표시되어야 합니다:
```
OPENAI_API_KEY=sk-proj-...
```

---

## 🚀 실행 테스트

```bash
python run_ai_example.py
```

성공 시:
```
============================================================
AI Team 기능 시연
============================================================

============================================================
1. 뉴스 감성 분석 예제
============================================================

종목: AAPL
...
```

---

## ❓ 문제 해결

### "OPENAI_API_KEY가 설정되지 않았습니다"

**해결**: `.env` 파일에 `OPENAI_API_KEY=sk-proj-...`를 추가하세요.

### "Invalid API key"

**해결**:
1. API 키가 올바른지 확인
2. https://platform.openai.com/api-keys 에서 키가 활성화되어 있는지 확인
3. 계정에 크레딧이 있는지 확인

### "Rate limit exceeded"

**해결**:
1. 잠시 대기 후 재시도
2. OpenAI 대시보드에서 사용량 확인

---

## 📚 추가 자료

- [OpenAI API 문서](https://platform.openai.com/docs)
- [OpenAI 가격](https://openai.com/pricing)
- [AI Team README](ai_team/README.md)
