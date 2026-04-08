# AI Team 실행 가이드

AI Team을 실행하는 여러 방법

---

## 방법 1: 프로젝트 루트에서 실행 (권장) ⭐

가장 간단하고 권장되는 방법입니다.

### API 서버 실행

```bash
# 프로젝트 루트 (/mnt/c/navis 또는 C:\navis)에서
python run_ai_team.py
```

### 예제 실행

```bash
python run_ai_example.py
```

---

## 방법 2: Python 모듈로 실행

```bash
# API 서버
python -m uvicorn ai_team.api.main:app --host 0.0.0.0 --port 8001

# 또는
python -m ai_team.run_api
```

---

## 방법 3: ai_team 디렉토리에서 직접 실행

```bash
cd ai_team
python run_api.py
# 또는
python example.py
```

이 방법은 스크립트에 sys.path 수정 코드가 포함되어 있어 작동합니다.

---

## 환경 변수 설정

반드시 `.env` 파일에 다음을 설정하세요:

```bash
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

**참고**:
- 기존에 `OPENAI_API_KEY`로 되어 있던 부분이 `ANTHROPIC_API_KEY`로 변경되었습니다
- OpenAI API 대신 Anthropic Claude API를 사용합니다

---

## 문제 해결

### ModuleNotFoundError: No module named 'ai_team'

**원인**: Python이 ai_team 모듈을 찾지 못함

**해결책**:
1. 프로젝트 루트에서 실행하세요 (방법 1 사용)
2. 또는 PYTHONPATH 설정:
   ```bash
   # Windows PowerShell
   $env:PYTHONPATH = "C:\navis"
   python ai_team/run_api.py

   # Linux/Mac
   export PYTHONPATH=/mnt/c/navis
   python ai_team/run_api.py
   ```

### ANTHROPIC_API_KEY 오류

**원인**: API 키가 설정되지 않음

**해결책**:
`.env` 파일에 다음을 추가:
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

---

## 빠른 테스트

```bash
# 1. 프로젝트 루트로 이동
cd /mnt/c/navis  # 또는 C:\navis

# 2. 환경 변수 확인
cat .env  # Linux/Mac
type .env  # Windows

# 3. 간단한 예제 실행
python run_ai_example.py

# 4. API 서버 실행
python run_ai_team.py
```

---

## API 서버가 실행되면

브라우저에서 다음 주소로 접속:

- API 문서: http://localhost:8001/docs
- 헬스 체크: http://localhost:8001/health

---

## 추가 도움말

더 자세한 내용은 다음 문서를 참조하세요:
- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작
- [README.md](README.md) - 전체 문서
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - 통합 가이드
