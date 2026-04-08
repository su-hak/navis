# AI Team 올바른 설정 가이드 ✅

## ⚠️ 중요: Anthropic Claude API 사용

AI Team은 **Anthropic Claude API**를 사용합니다 (뉴스 분석, AI Agent 등).

---

## 1️⃣ Anthropic API 키 발급

### 단계별 가이드

1. **https://console.anthropic.com/** 방문
2. 로그인 또는 회원가입
3. "API Keys" 메뉴로 이동
4. "Create Key" 클릭
5. 생성된 키 복사 (sk-ant-로 시작)

---

## 2️⃣ .env 파일 설정

`.env` 파일을 열고 다음을 확인/추가하세요:

```bash
# AI Team - Anthropic Claude API 키 (필수)
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

**이미 있는 것 확인됨**:
```bash
ANTHROPIC_API_KEY=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
```

✅ 이미 설정되어 있습니다!

---

## 3️⃣ 실행

```bash
# 프로젝트 루트에서
python run_ai_example.py
```

또는 API 서버:

```bash
python run_ai_team.py
```

---

## 📊 사용하는 API

### 주요 기능: Anthropic Claude API
- ✅ 뉴스 감성 분석
- ✅ AI Agent (도구 사용)
- ✅ RAG 답변 생성
- ✅ 시장 리스크 분석

**모델**: `claude-3-5-sonnet-20241022`

### 선택적: OpenAI API
- RAG 임베딩 (벡터 DB용)
- 설정하지 않으면 임베딩 기능만 제한됨

---

## 💰 비용 안내

### Anthropic Claude API 가격 (2024년 기준)

**Claude 3.5 Sonnet**:
- Input: $3 / 1M tokens
- Output: $15 / 1M tokens

**예상 비용**:
- 종목 1개 분석: 약 $0.005 - $0.02
- 하루 100종목: 약 $0.50 - $2

**OpenAI 대비 저렴!**
- GPT-4 Turbo: $10 / $30 (input/output)
- Claude 3.5: $3 / $15 (input/output)

---

## 🔧 수정 사항 요약

### API 변경
- ❌ OpenAI API (GPT-4)
- ✅ Anthropic Claude API (Claude 3.5 Sonnet)

### 코드 변경
- `langchain_openai.ChatOpenAI` → `langchain_anthropic.ChatAnthropic`
- `create_openai_functions_agent` → `create_tool_calling_agent`
- `config.openai_api_key` → `config.anthropic_api_key`

### 환경 변수
- ✅ `ANTHROPIC_API_KEY` (필수)
- ⚪ `OPENAI_API_KEY` (선택 - RAG embeddings용)

---

## ✅ 설정 확인

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY

# Linux/Mac
echo $ANTHROPIC_API_KEY
```

또는:

```bash
# .env 파일 확인
type .env | findstr ANTHROPIC  # Windows
grep ANTHROPIC .env            # Linux/Mac
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

### "ANTHROPIC_API_KEY가 설정되지 않았습니다"

**해결**: `.env` 파일 확인
- 이미 설정되어 있음을 확인했으므로 발생하지 않아야 함

### "Invalid API key"

**해결**:
1. API 키가 올바른지 확인 (sk-ant-로 시작)
2. https://console.anthropic.com/ 에서 키 활성화 확인
3. 계정에 크레딧이 있는지 확인

### 임베딩 오류 발생 시

RAG 기능 사용 시 OpenAI embeddings 필요:

```bash
# .env 파일에 추가
OPENAI_API_KEY=sk-your-openai-key
```

또는 임베딩 없이 사용 (뉴스 분석만).

---

## 📚 API 비교

| 항목 | OpenAI GPT-4 | Anthropic Claude 3.5 |
|------|--------------|---------------------|
| Input 가격 | $10/1M | $3/1M |
| Output 가격 | $30/1M | $15/1M |
| 컨텍스트 | 128K tokens | 200K tokens |
| Tool Calling | ✅ | ✅ |
| 한국어 지원 | ✅ | ✅ |

---

## 🎉 완료!

이제 Anthropic Claude API를 사용하여 AI Team이 작동합니다.

```bash
python run_ai_example.py
```

모든 것이 정상 작동해야 합니다! 🚀
