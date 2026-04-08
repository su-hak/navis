# Navis AI Agent

범용 AI 에이전트 프로젝트 - Claude API와 LangChain/LangGraph를 사용한 도구 기반 에이전트

## 특징

- Anthropic Claude API 기반 (Claude 3.5 Sonnet)
- LangChain 프레임워크를 사용한 에이전트 구현
- 확장 가능한 도구 시스템
- 대화형 모드, 단일 쿼리 모드, 텔레그램 봇 모드 지원
- 구조화된 로깅 시스템
- 사용자별 대화 히스토리 관리 (텔레그램 봇)

## 현재 구현된 도구

- **Web Search**: DuckDuckGo를 통한 웹 검색
- **Calculator**: 수학 계산 수행

## 프로젝트 구조

```
navis/
├── agents/          # 에이전트 구현
│   ├── __init__.py
│   └── base_agent.py
├── tools/           # 도구 정의
│   ├── __init__.py
│   ├── web_search.py
│   └── calculator.py
├── config/          # 설정 파일
│   ├── __init__.py
│   └── settings.py
├── utils/           # 유틸리티 함수
│   ├── __init__.py
│   └── logger.py
├── logs/            # 로그 파일 저장
├── main.py          # CLI 메인 진입점
├── telegram_bot.py  # 텔레그램 봇 진입점
├── requirements.txt # 의존성 목록
├── .env.example     # 환경 변수 예시
└── README.md        # 이 파일
```

## 설치 및 설정

### 1. 가상 환경 활성화

```bash
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
.\venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 API 키를 설정합니다:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux/Mac
cp .env.example .env
```

`.env` 파일을 편집하여 필요한 API 키들을 입력합니다:

```
# 필수: Anthropic API 키
ANTHROPIC_API_KEY=your_actual_api_key_here

# 텔레그램 봇을 사용하는 경우 필요
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

### 4. 텔레그램 봇 설정 (선택사항)

텔레그램 봇을 사용하려면:

1. [@BotFather](https://t.me/botfather)와 대화하여 새 봇 생성
2. `/newbot` 명령어로 봇 이름과 사용자명 설정
3. BotFather가 제공하는 API 토큰을 `.env` 파일의 `TELEGRAM_BOT_TOKEN`에 입력

## 사용 방법

### 대화형 모드

에이전트와 대화하며 작업을 수행합니다:

```bash
python main.py
```

종료하려면 `quit` 또는 `exit`를 입력합니다.

### 단일 쿼리 모드

하나의 질문에 대한 답변을 받습니다:

```bash
python main.py "서울의 현재 날씨는 어때?"
```

### 텔레그램 봇 모드 (권장)

텔레그램을 통해 에이전트와 대화합니다:

```bash
python telegram_bot.py
```

봇이 실행되면 텔레그램에서 봇을 찾아 대화를 시작하세요.

**텔레그램 봇 명령어:**
- `/start` - 봇 시작 및 소개
- `/help` - 도움말 표시
- `/clear` - 대화 기록 초기화

**특징:**
- 사용자별 독립적인 대화 세션 관리
- 자동으로 최근 10개 대화 교환 유지 (메모리 관리)
- 실시간 typing 표시
- 24/7 접근 가능

## 사용 예시

### CLI 모드
```
You: 2024년 파리 올림픽은 언제 열렸어?

NavisAgent: [웹 검색 도구 사용]
2024년 파리 올림픽은 2024년 7월 26일부터 8월 11일까지 열렸습니다.

You: 123 * 456을 계산해줘

NavisAgent: [계산기 도구 사용]
123 * 456 = 56,088입니다.
```

### 텔레그램 봇 모드
```
You: /start
Bot: 안녕하세요, 홍길동님! 👋
     저는 NavisAgent입니다.
     무엇을 도와드릴까요?

You: 파이썬으로 API 요청하는 방법 알려줘
Bot: 파이썬에서 API 요청을 하는 가장 일반적인 방법은...

You: /clear
Bot: ✅ 대화 기록이 초기화되었습니다.
```

## 커스터마이징

### 새로운 도구 추가

1. `tools/` 디렉토리에 새 도구 파일 생성
2. LangChain `Tool` 객체를 반환하는 함수 작성
3. `main.py`의 `create_agent_tools()` 함수에 도구 추가

예시:

```python
# tools/my_tool.py
from langchain.tools import Tool

def my_function(input: str) -> str:
    # 도구 로직 구현
    return "결과"

def create_my_tool() -> Tool:
    return Tool(
        name="my_tool",
        description="도구 설명",
        func=my_function,
    )
```

### 에이전트 커스터마이징

`agents/base_agent.py`를 수정하거나 새로운 에이전트 클래스를 만들어 다음을 변경할 수 있습니다:

- 시스템 프롬프트
- 모델 파라미터
- 도구 사용 로직
- 대화 히스토리 관리

## 개발

### 테스트 실행

```bash
pytest
```

### 코드 포맷팅

```bash
black .
flake8
```

## 라이선스

MIT License

## 기여

이슈 및 풀 리퀘스트를 환영합니다!
