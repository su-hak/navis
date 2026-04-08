# MySQL 설치 및 설정 가이드 (Windows)

## 빠른 해결 방법

MySQL이 설치되지 않았거나 실행되지 않는 것 같습니다. 두 가지 옵션이 있습니다:

### 옵션 1: MySQL 설치 (권장)
### 옵션 2: SQLite 사용 (간단, 테스트용)

---

## 옵션 1: MySQL 설치 및 설정

### 1단계: MySQL 다운로드

**MySQL Community Server 다운로드**
- URL: https://dev.mysql.com/downloads/mysql/
- 버전: MySQL 8.0 (Windows x64)
- 파일: MySQL Installer for Windows

### 2단계: MySQL 설치

1. 다운로드한 `mysql-installer-community-8.0.xx.msi` 실행
2. Setup Type: **Developer Default** 선택
3. Check Requirements 단계에서 필요한 패키지 설치
4. Installation 클릭하여 설치 진행

### 3단계: MySQL 설정

**Configure MySQL Server**

1. **Type and Networking**
   - Config Type: Development Computer
   - Port: 3306 (기본값)
   - ✅ Open Windows Firewall port for network access

2. **Authentication Method**
   - ✅ Use Strong Password Encryption

3. **Accounts and Roles**
   - Root Password 설정 (기억하세요!)
   - 예: `root123` (개발용)

4. **Windows Service**
   - ✅ Configure MySQL Server as a Windows Service
   - Service Name: MySQL80
   - ✅ Start the MySQL Server at System Startup

5. **Apply Configuration**
   - Execute 클릭

### 4단계: MySQL 서비스 확인

**PowerShell에서 확인:**

```powershell
# MySQL 서비스 상태 확인
Get-Service MySQL80

# 서비스가 Stopped이면 시작
Start-Service MySQL80

# 또는 services.msc를 실행하여 GUI로 확인
services.msc
```

### 5단계: 데이터베이스 생성

**MySQL Workbench 또는 커맨드라인 사용:**

```powershell
# MySQL 로그인
mysql -u root -p
# 비밀번호 입력

# 데이터베이스 생성
CREATE DATABASE trading_db;

# 확인
SHOW DATABASES;

# 종료
EXIT;
```

**또는 PowerShell에서 직접:**

```powershell
mysql -u root -p -e "CREATE DATABASE trading_db;"
```

### 6단계: .env 파일 설정

프로젝트 루트의 `.env` 파일에 MySQL 정보 추가:

```env
# MySQL Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root123
MYSQL_DATABASE=trading_db
```

### 7단계: 연결 테스트

```bash
cd data_collection/database
python schema.py
```

성공 메시지가 나오면 완료!

---

## 옵션 2: SQLite 사용 (간편)

MySQL 설치가 부담스러우면 SQLite를 사용하세요. 파일 기반이라 설치 불필요합니다.

### 1단계: SQLite 스키마 사용

```bash
cd data_collection/database
python schema_sqlite.py
```

### 2단계: .env 파일 설정

```env
# SQLite Database (MySQL 대신)
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=./trading.db
```

**장점:**
- 설치 불필요
- 설정 간단
- 개발/테스트에 적합

**단점:**
- 동시 쓰기 성능 낮음
- 대규모 프로덕션에는 부적합

---

## 트러블슈팅

### 에러 1: "Access denied for user 'root'@'localhost'"

**해결:**
```powershell
# MySQL 재설정
mysql -u root -p
ALTER USER 'root'@'localhost' IDENTIFIED BY 'new_password';
FLUSH PRIVILEGES;
```

### 에러 2: "MySQL service is not starting"

**해결:**
```powershell
# 서비스 재시작
Stop-Service MySQL80
Start-Service MySQL80

# 로그 확인
Get-Content "C:\ProgramData\MySQL\MySQL Server 8.0\Data\*.err"
```

### 에러 3: "Port 3306 is already in use"

**해결:**
```powershell
# 포트 사용 프로세스 확인
netstat -ano | findstr :3306

# 프로세스 종료 (PID 확인 후)
taskkill /PID <PID> /F
```

### 에러 4: "Can't connect to MySQL server on 'localhost' (10061)"

**해결 순서:**
1. MySQL 서비스 실행 확인
   ```powershell
   Get-Service MySQL80
   Start-Service MySQL80
   ```

2. 방화벽 확인
   - Windows 방화벽에서 포트 3306 허용

3. MySQL 재설치
   - 위 설치 가이드 다시 따라하기

---

## MySQL vs SQLite 선택 가이드

| 상황 | 권장 |
|------|------|
| 빠른 테스트/개발 | SQLite |
| 학습 목적 | SQLite |
| 로컬 개발 환경 | MySQL |
| 팀 협업 | MySQL |
| 프로덕션 배포 | MySQL |
| 대용량 데이터 | MySQL |

---

## 추가 도구 (선택사항)

### MySQL Workbench
- GUI 데이터베이스 관리 도구
- 다운로드: https://dev.mysql.com/downloads/workbench/
- 테이블 확인, 쿼리 실행 등

### HeidiSQL (대안)
- 무료, 가벼운 MySQL 클라이언트
- 다운로드: https://www.heidisql.com/

---

## 도움이 필요하면

1. MySQL 공식 문서: https://dev.mysql.com/doc/
2. 에러 메시지 검색: Google에서 "MySQL <에러 코드>"
3. Stack Overflow: https://stackoverflow.com/questions/tagged/mysql

---

**다음 단계:** MySQL 설정이 완료되면 `QUICKSTART.md`로 돌아가세요!
