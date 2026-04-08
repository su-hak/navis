# 문제 해결 가이드

## 문제 1: 의존성 충돌 에러

### 에러 메시지:
```
ERROR: pip's dependency resolver does not currently take into account all the packages...
langchain 1.2.15 requires pydantic<3.0.0,>=2.7.4, but you have pydantic 2.6.1...
```

### ✅ 해결 방법:

**방법 1: 업데이트된 requirements.txt 재설치 (권장)**
```bash
cd data_collection
pip install --upgrade -r requirements.txt
```

**방법 2: 충돌 무시하고 계속**
- 경고는 나타나지만 기능에는 문제없습니다
- 그냥 계속 진행하세요

**방법 3: 개별 패키지 업그레이드**
```bash
pip install --upgrade pydantic>=2.7.4
pip install --upgrade lxml>=5.3.0
pip install --upgrade requests>=2.32.5
```

---

## 문제 2: MySQL 연결 에러

### 에러 메시지:
```
mysql.connector.errors.DatabaseError: 2003 (HY000):
Can't connect to MySQL server on 'localhost:3306' (10061)
```

### ✅ 빠른 해결: SQLite 사용 (권장)

MySQL 대신 SQLite를 사용하면 설치 불필요합니다:

```bash
cd data_collection
python setup_database.py
# 옵션 1 선택 (SQLite)
```

### ✅ MySQL을 사용하고 싶다면:

#### 1단계: MySQL이 실행 중인지 확인

**PowerShell에서:**
```powershell
# MySQL 서비스 확인
Get-Service MySQL80

# Stopped 상태면 시작
Start-Service MySQL80
```

**또는 GUI로:**
```powershell
# 서비스 관리자 열기
services.msc
# MySQL80 찾아서 우클릭 > 시작
```

#### 2단계: MySQL이 설치되지 않았다면

상세 가이드 참조:
```bash
# INSTALL_MYSQL.md 파일 참조
```

또는 빠른 설치:
1. https://dev.mysql.com/downloads/mysql/ 방문
2. MySQL Installer 다운로드
3. Developer Default 선택하여 설치
4. Root 비밀번호 설정

#### 3단계: 데이터베이스 생성

```powershell
# MySQL 로그인
mysql -u root -p

# 데이터베이스 생성
CREATE DATABASE trading_db;
EXIT;
```

#### 4단계: .env 파일 확인

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_actual_password
MYSQL_DATABASE=trading_db
```

---

## 문제 3: Alpaca API 키 에러

### 에러 메시지:
```
Error: Invalid API credentials
```

### ✅ 해결 방법:

1. **API 키 확인**
   - https://app.alpaca.markets 로그인
   - API Keys 메뉴에서 키 확인/재발급

2. **.env 파일 확인**
   ```env
   APCA-API-KEY-ID=PKxxxxxxxxxxxxxxxx
   APCA-API-SECRET-KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

3. **페이퍼 트레이딩 키 사용 확인**
   - Paper Trading 계정의 키를 사용하세요
   - Live Trading 키는 실제 돈이 움직입니다!

---

## 문제 4: 모듈 import 에러

### 에러 메시지:
```
ModuleNotFoundError: No module named 'alpaca'
```

### ✅ 해결 방법:

```bash
# 모든 의존성 재설치
cd data_collection
pip install -r requirements.txt

# 특정 패키지만 설치
pip install alpaca-py
```

---

## 문제 5: 데이터 수집 테스트 실패

### 에러 메시지:
```
No data found for AAPL
```

### ✅ 해결 방법:

**1. 시장 시간 확인**
- 미국 주식 시장 시간: 월-금 9:30-16:00 ET
- 시장 마감 후에는 최신 데이터가 없을 수 있습니다

**2. API 레이트 리미트**
- Alpaca: 200 requests/minute
- 너무 많은 요청을 보냈다면 1분 대기

**3. 네트워크 연결 확인**
```bash
ping google.com
```

---

## 문제 6: SQLite 파일 권한 에러

### 에러 메시지:
```
PermissionError: [Errno 13] Permission denied: 'trading.db'
```

### ✅ 해결 방법:

**1. 파일 삭제 후 재생성**
```bash
cd data_collection
rm trading.db  # 또는 del trading.db (Windows)
python setup_database.py
```

**2. 관리자 권한으로 실행**
```powershell
# PowerShell을 관리자 권한으로 실행
```

---

## 빠른 체크리스트

설치가 안 되면 다음을 순서대로 확인하세요:

- [ ] Python 3.10 이상 설치되어 있나요?
  ```bash
  python --version
  ```

- [ ] data_collection 폴더에 있나요?
  ```bash
  pwd  # 또는 cd (Windows)
  ```

- [ ] requirements.txt 설치했나요?
  ```bash
  pip install -r requirements.txt
  ```

- [ ] .env 파일에 API 키가 있나요?
  ```bash
  cat .env  # 또는 type .env (Windows)
  ```

- [ ] 데이터베이스 초기화했나요?
  ```bash
  python setup_database.py
  ```

---

## 여전히 안 된다면?

### 최소 동작 테스트

데이터베이스 없이 collector만 테스트:

```python
# test_minimal.py
import asyncio
from collectors.stock_price_collector import StockPriceCollector

async def test():
    # .env에서 읽어오기
    import os
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('APCA-API-KEY-ID')
    api_secret = os.getenv('APCA-API-SECRET-KEY')

    collector = StockPriceCollector(api_key, api_secret)
    prices = await collector.get_latest_price(['AAPL'])
    print(f"AAPL 최신 가격: ${prices['AAPL']:.2f}")

asyncio.run(test())
```

```bash
python test_minimal.py
```

성공하면 collector는 정상입니다. 데이터베이스 설정만 확인하면 됩니다.

---

## 도움 받기

1. **에러 메시지 전체 복사**
2. **실행한 명령어 기록**
3. **환경 정보 확인**:
   ```bash
   python --version
   pip list | grep -E "alpaca|mysql|pydantic"
   ```

---

## 자주 하는 실수

1. ❌ data_collection 폴더 밖에서 실행
   - ✅ `cd data_collection` 먼저 실행

2. ❌ .env 파일이 잘못된 위치
   - ✅ 프로젝트 루트에 위치해야 함

3. ❌ MySQL 비밀번호 따옴표로 감싸기
   - ✅ `MYSQL_PASSWORD=123456` (따옴표 없이)

4. ❌ API 키에 공백 포함
   - ✅ `APCA-API-KEY-ID=PKxxx` (앞뒤 공백 없이)

---

**다음 단계**: 문제가 해결되면 `QUICKSTART.md`로 돌아가세요!
