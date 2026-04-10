# Git Push 가이드

## 레포지토리 구조

```
C:/navis/                          ← 루트 Git 레포 (navis.git)
├── .git/                          ← 루트 Git
├── data_collection/               ← 루트 Git이 관리 (자체 .git 없음)
│   └── monitoring/watchlist_generator.py
│
├── backend/                       ← 서브모듈 (navis_backend.git)
├── ai_team/                       ← 독립 Git 레포 (ai_team.git)
├── notification_team/             ← 독립 Git 레포 (notification_team.git)
├── risk_team/                     ← 독립 Git 레포 (risk_team.git)
└── strategy_engine/               ← 독립 Git 레포 (strategy_engine.git)
```

| 서비스 | Git 형태 | 원격 레포 |
|--------|----------|-----------|
| navis (루트) | 루트 레포 | `github.com/su-hak/navis.git` |
| data_collection | 루트 레포의 서브디렉토리 | `github.com/su-hak/trading-data-collection.git` |
| backend | 서브모듈 | `github.com/su-hak/navis_backend.git` |
| ai_team | 독립 레포 | `github.com/su-hak/ai_team.git` |
| notification_team | 독립 레포 | `github.com/su-hak/notification_team.git` |
| risk_team | 독립 레포 | `github.com/su-hak/risk_team.git` |
| strategy_engine | 독립 레포 | `github.com/su-hak/strategy_engine.git` |

---

## 서비스별 Push 방법

### navis (루트 전체)

`auto_trading_bot_v2.py`, `telegram_bot.py`, `.env` 등 루트 파일 변경 시

```bash
# 위치: C:/navis (어디서든 가능)
git add .
git commit -m "커밋 메시지"
git push origin master
```

---

### data_collection

`data_collection/` 하위 파일 변경 시 — **루트에서 subtree push** 사용

```bash
# 위치: C:/navis (루트에서 실행해야 함)
git add .
git commit -m "커밋 메시지"

# navis.git에 전체 커밋
git push origin master

# trading-data-collection.git에 data_collection/ 서브트리만 push
git subtree push --prefix=data_collection data-collection master
```

> **주의**: `cd data_collection` 후 git 명령 실행 금지.
> `data_collection/`에는 `.git`이 없으므로 루트 git을 조작하게 됨.

---

### backend

`backend/` 서브모듈 변경 시 — **두 단계** 필요

```bash
# [1단계] backend 자체 레포에 push
cd C:/navis/backend
git add .
git commit -m "커밋 메시지"
git push origin master

# [2단계] 루트에서 서브모듈 포인터 갱신
cd C:/navis
git add backend
git commit -m "backend 서브모듈 포인터 업데이트"
git push origin master
```

> **주의**: 2단계를 빠뜨리면 navis 루트는 이전 버전의 backend를 가리킴.

---

### ai_team

```bash
cd C:/navis/ai_team
git add .
git commit -m "커밋 메시지"
git push origin master
```

---

### notification_team

```bash
cd C:/navis/notification_team
git add .
git commit -m "커밋 메시지"
git push origin master
```

---

### risk_team

```bash
cd C:/navis/risk_team
git add .
git commit -m "커밋 메시지"
git push origin master
```

---

### strategy_engine

```bash
cd C:/navis/strategy_engine
git add .
git commit -m "커밋 메시지"
git push origin master
```

---

## 여러 서비스 동시 변경 시 순서

```bash
# 1. 독립 레포들 먼저 push
cd C:/navis/ai_team && git push origin master
cd C:/navis/risk_team && git push origin master
# ... 기타 독립 레포

# 2. backend 변경이 있으면 서브모듈 push 후 루트 포인터 갱신
cd C:/navis/backend && git push origin master
cd C:/navis && git add backend && git commit -m "backend 포인터 갱신" && git push origin master

# 3. 루트 및 data_collection push
cd C:/navis
git push origin master
git subtree push --prefix=data_collection data-collection master
```

---

## 현재 설정된 Remote 목록

```bash
# 루트(C:/navis)에서 확인
git remote -v
# origin        https://github.com/su-hak/navis.git
# data-collection  https://github.com/su-hak/trading-data-collection.git
```

---

## 자주 발생하는 실수

### 실수 1: data_collection 안에서 git 명령 실행

```bash
# 위험 - 루트 git을 조작함
cd data_collection
git remote remove origin   # ← 루트의 origin이 삭제됨!
```

**해결**: 항상 `C:/navis` 루트에서 `git subtree` 사용

---

### 실수 2: backend 서브모듈 포인터 미갱신

```bash
# backend 내부만 push하고 루트 갱신을 빠뜨리면
# navis 루트는 이전 버전 backend를 참조하게 됨
git -C backend push origin master
# → 루트에서 git add backend + commit + push 필수
```

---

### 실수 3: non-fast-forward 오류

리모트에 로컬에 없는 커밋이 있을 때 발생.

```bash
# 독립 레포인 경우
git pull origin master --rebase
git push origin master

# data_collection subtree인 경우 (히스토리가 다를 때)
git subtree split --prefix=data_collection -b tmp-branch
git push data-collection tmp-branch:master --force
git branch -D tmp-branch
```
