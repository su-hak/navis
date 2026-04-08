# MySQL 테이블 생성 쿼리

DBeaver에서 직접 실행할 수 있는 MySQL 쿼리문입니다.

---

## 📋 사전 준비

### 1. DBeaver에서 MySQL 연결

1. DBeaver 실행
2. "Database" → "New Database Connection"
3. MySQL 선택
4. 연결 정보 입력:
   - Host: `localhost`
   - Port: `3306`
   - Username: `root`
   - Password: (설정한 비밀번호)

### 2. 데이터베이스 생성

```sql
-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS trading_db;

-- 데이터베이스 선택
USE trading_db;
```

---

## 🗄️ 테이블 생성 쿼리

### 1. stock_prices (주가 데이터)

```sql
CREATE TABLE IF NOT EXISTS stock_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp DATETIME NOT NULL,
    open DECIMAL(20, 4),
    high DECIMAL(20, 4),
    low DECIMAL(20, 4),
    close DECIMAL(20, 4),
    volume BIGINT,
    timeframe VARCHAR(10) DEFAULT 'daily',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_timestamp (symbol, timestamp),
    INDEX idx_timestamp (timestamp),
    UNIQUE KEY unique_symbol_timestamp_timeframe (symbol, timestamp, timeframe)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- 일봉, 분봉 등 모든 주가 데이터 저장
- `timeframe`: 'daily', '1min', '5min' 등

---

### 2. volume_metrics (거래량 지표)

```sql
CREATE TABLE IF NOT EXISTS volume_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    volume BIGINT,
    volume_ma_20 DECIMAL(20, 2),
    volume_ma_50 DECIMAL(20, 2),
    volume_ratio DECIMAL(10, 4),
    volume_surge BOOLEAN DEFAULT FALSE,
    relative_volume DECIMAL(10, 4),
    money_flow DECIMAL(30, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_date (symbol, date),
    UNIQUE KEY unique_symbol_date (symbol, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- 거래량 이동평균, 급증 탐지
- 거래량 비율, Money Flow

---

### 3. volatility_metrics (변동성 지표)

```sql
CREATE TABLE IF NOT EXISTS volatility_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    volatility DECIMAL(10, 6),
    atr DECIMAL(20, 4),
    atr_percent DECIMAL(10, 4),
    bb_upper DECIMAL(20, 4),
    bb_middle DECIMAL(20, 4),
    bb_lower DECIMAL(20, 4),
    bb_width DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_date (symbol, date),
    UNIQUE KEY unique_symbol_date (symbol, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- Historical Volatility (연환산)
- ATR (Average True Range)
- Bollinger Bands

---

### 4. news (뉴스 데이터)

```sql
CREATE TABLE IF NOT EXISTS news (
    id VARCHAR(100) PRIMARY KEY,
    headline TEXT,
    summary TEXT,
    author VARCHAR(255),
    created_at DATETIME,
    updated_at DATETIME,
    url TEXT,
    symbols JSON,
    text_length INT,
    priority VARCHAR(20) DEFAULT 'normal',
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at),
    INDEX idx_symbols ((CAST(symbols AS CHAR(255) ARRAY)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- Alpaca News API 데이터
- `symbols`: JSON 형식으로 관련 종목 저장
- `priority`: 'high', 'normal'

---

### 5. financial_metrics (재무 지표)

```sql
CREATE TABLE IF NOT EXISTS financial_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    market_cap BIGINT,
    enterprise_value BIGINT,
    trailing_pe DECIMAL(10, 4),
    forward_pe DECIMAL(10, 4),
    peg_ratio DECIMAL(10, 4),
    price_to_book DECIMAL(10, 4),
    price_to_sales DECIMAL(10, 4),
    ev_to_revenue DECIMAL(10, 4),
    ev_to_ebitda DECIMAL(10, 4),
    profit_margin DECIMAL(10, 6),
    operating_margin DECIMAL(10, 6),
    return_on_assets DECIMAL(10, 6),
    return_on_equity DECIMAL(10, 6),
    revenue BIGINT,
    revenue_growth DECIMAL(10, 6),
    earnings_growth DECIMAL(10, 6),
    debt_to_equity DECIMAL(10, 4),
    current_ratio DECIMAL(10, 4),
    quick_ratio DECIMAL(10, 4),
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_retrieved_at (retrieved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- P/E, P/B, ROE, ROA 등 주요 재무 지표
- 성장률, 수익성, 밸류에이션 지표

---

### 6. institutional_holders (기관 투자자)

```sql
CREATE TABLE IF NOT EXISTS institutional_holders (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    holder_name VARCHAR(255),
    shares BIGINT,
    date_reported DATE,
    pct_out DECIMAL(10, 6),
    value BIGINT,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_date_reported (date_reported)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- 기관 투자자 보유 현황
- Vanguard, BlackRock 등

---

### 7. insider_transactions (인사이더 거래)

```sql
CREATE TABLE IF NOT EXISTS insider_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    insider_name VARCHAR(255),
    transaction_type VARCHAR(50),
    shares BIGINT,
    price DECIMAL(20, 4),
    value BIGINT,
    start_date DATE,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_start_date (start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- 내부자 거래 내역
- CEO, CFO 등의 매수/매도

---

### 8. ownership_summary (소유권 요약)

```sql
CREATE TABLE IF NOT EXISTS ownership_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    institutional_ownership_pct DECIMAL(10, 4),
    insider_ownership_pct DECIMAL(10, 4),
    float_shares BIGINT,
    shares_outstanding BIGINT,
    shares_short BIGINT,
    short_percent_of_float DECIMAL(10, 4),
    short_ratio DECIMAL(10, 4),
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_retrieved_at (retrieved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**설명:**
- 소유권 구조 요약
- Short Interest 포함

---

## 🚀 DBeaver에서 실행 방법

### 방법 1: 전체 실행 (권장)

1. DBeaver에서 새 SQL 에디터 열기 (`Ctrl+]`)
2. 아래 "전체 실행 스크립트" 복사
3. 붙여넣기
4. 실행 (`Ctrl+Enter` 또는 F5)

### 방법 2: 개별 실행

1. 각 테이블별로 복사
2. 하나씩 실행

---

## 📝 전체 실행 스크립트

```sql
-- ============================================================
-- Trading System Database Schema
-- ============================================================

-- 데이터베이스 생성 및 선택
CREATE DATABASE IF NOT EXISTS trading_db;
USE trading_db;

-- ============================================================
-- 1. stock_prices (주가 데이터)
-- ============================================================
CREATE TABLE IF NOT EXISTS stock_prices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp DATETIME NOT NULL,
    open DECIMAL(20, 4),
    high DECIMAL(20, 4),
    low DECIMAL(20, 4),
    close DECIMAL(20, 4),
    volume BIGINT,
    timeframe VARCHAR(10) DEFAULT 'daily',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_timestamp (symbol, timestamp),
    INDEX idx_timestamp (timestamp),
    UNIQUE KEY unique_symbol_timestamp_timeframe (symbol, timestamp, timeframe)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 2. volume_metrics (거래량 지표)
-- ============================================================
CREATE TABLE IF NOT EXISTS volume_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    volume BIGINT,
    volume_ma_20 DECIMAL(20, 2),
    volume_ma_50 DECIMAL(20, 2),
    volume_ratio DECIMAL(10, 4),
    volume_surge BOOLEAN DEFAULT FALSE,
    relative_volume DECIMAL(10, 4),
    money_flow DECIMAL(30, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_date (symbol, date),
    UNIQUE KEY unique_symbol_date (symbol, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 3. volatility_metrics (변동성 지표)
-- ============================================================
CREATE TABLE IF NOT EXISTS volatility_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    volatility DECIMAL(10, 6),
    atr DECIMAL(20, 4),
    atr_percent DECIMAL(10, 4),
    bb_upper DECIMAL(20, 4),
    bb_middle DECIMAL(20, 4),
    bb_lower DECIMAL(20, 4),
    bb_width DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol_date (symbol, date),
    UNIQUE KEY unique_symbol_date (symbol, date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 4. news (뉴스 데이터)
-- ============================================================
CREATE TABLE IF NOT EXISTS news (
    id VARCHAR(100) PRIMARY KEY,
    headline TEXT,
    summary TEXT,
    author VARCHAR(255),
    created_at DATETIME,
    updated_at DATETIME,
    url TEXT,
    symbols JSON,
    text_length INT,
    priority VARCHAR(20) DEFAULT 'normal',
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 5. financial_metrics (재무 지표)
-- ============================================================
CREATE TABLE IF NOT EXISTS financial_metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    market_cap BIGINT,
    enterprise_value BIGINT,
    trailing_pe DECIMAL(10, 4),
    forward_pe DECIMAL(10, 4),
    peg_ratio DECIMAL(10, 4),
    price_to_book DECIMAL(10, 4),
    price_to_sales DECIMAL(10, 4),
    ev_to_revenue DECIMAL(10, 4),
    ev_to_ebitda DECIMAL(10, 4),
    profit_margin DECIMAL(10, 6),
    operating_margin DECIMAL(10, 6),
    return_on_assets DECIMAL(10, 6),
    return_on_equity DECIMAL(10, 6),
    revenue BIGINT,
    revenue_growth DECIMAL(10, 6),
    earnings_growth DECIMAL(10, 6),
    debt_to_equity DECIMAL(10, 4),
    current_ratio DECIMAL(10, 4),
    quick_ratio DECIMAL(10, 4),
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_retrieved_at (retrieved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 6. institutional_holders (기관 투자자)
-- ============================================================
CREATE TABLE IF NOT EXISTS institutional_holders (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    holder_name VARCHAR(255),
    shares BIGINT,
    date_reported DATE,
    pct_out DECIMAL(10, 6),
    value BIGINT,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_date_reported (date_reported)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 7. insider_transactions (인사이더 거래)
-- ============================================================
CREATE TABLE IF NOT EXISTS insider_transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    insider_name VARCHAR(255),
    transaction_type VARCHAR(50),
    shares BIGINT,
    price DECIMAL(20, 4),
    value BIGINT,
    start_date DATE,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_start_date (start_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 8. ownership_summary (소유권 요약)
-- ============================================================
CREATE TABLE IF NOT EXISTS ownership_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    institutional_ownership_pct DECIMAL(10, 4),
    insider_ownership_pct DECIMAL(10, 4),
    float_shares BIGINT,
    shares_outstanding BIGINT,
    shares_short BIGINT,
    short_percent_of_float DECIMAL(10, 4),
    short_ratio DECIMAL(10, 4),
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_retrieved_at (retrieved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 테이블 생성 완료
-- ============================================================

-- 테이블 목록 확인
SHOW TABLES;

-- 각 테이블 구조 확인 (선택사항)
-- DESCRIBE stock_prices;
-- DESCRIBE volume_metrics;
-- DESCRIBE volatility_metrics;
-- DESCRIBE news;
-- DESCRIBE financial_metrics;
-- DESCRIBE institutional_holders;
-- DESCRIBE insider_transactions;
-- DESCRIBE ownership_summary;
```

---

## ✅ 실행 후 확인

### 테이블 목록 확인

```sql
SHOW TABLES;
```

**예상 결과:**
```
+----------------------+
| Tables_in_trading_db |
+----------------------+
| financial_metrics    |
| institutional_holders|
| insider_transactions |
| news                 |
| ownership_summary    |
| stock_prices         |
| volatility_metrics   |
| volume_metrics       |
+----------------------+
8 rows in set
```

### 테이블 구조 확인

```sql
-- 주가 데이터 테이블 확인
DESCRIBE stock_prices;

-- 모든 테이블 행 수 확인
SELECT 'stock_prices' AS table_name, COUNT(*) AS row_count FROM stock_prices
UNION ALL
SELECT 'volume_metrics', COUNT(*) FROM volume_metrics
UNION ALL
SELECT 'volatility_metrics', COUNT(*) FROM volatility_metrics
UNION ALL
SELECT 'news', COUNT(*) FROM news
UNION ALL
SELECT 'financial_metrics', COUNT(*) FROM financial_metrics
UNION ALL
SELECT 'institutional_holders', COUNT(*) FROM institutional_holders
UNION ALL
SELECT 'insider_transactions', COUNT(*) FROM insider_transactions
UNION ALL
SELECT 'ownership_summary', COUNT(*) FROM ownership_summary;
```

---

## 🔍 유용한 쿼리

### 최신 데이터 확인

```sql
-- 주가 최신 데이터
SELECT * FROM stock_prices
ORDER BY timestamp DESC
LIMIT 10;

-- 뉴스 최신 데이터
SELECT symbol, headline, created_at
FROM news
ORDER BY created_at DESC
LIMIT 10;

-- 재무 지표 최신 데이터
SELECT symbol, market_cap, trailing_pe, revenue_growth
FROM financial_metrics
ORDER BY retrieved_at DESC
LIMIT 10;
```

### 종목별 데이터 확인

```sql
-- AAPL 주가 데이터 (최근 30일)
SELECT date(timestamp) as date, open, high, low, close, volume
FROM stock_prices
WHERE symbol = 'AAPL'
  AND timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY timestamp DESC;

-- TSLA 뉴스
SELECT headline, created_at
FROM news
WHERE JSON_CONTAINS(symbols, '"TSLA"')
ORDER BY created_at DESC
LIMIT 10;
```

---

## 🗑️ 테이블 삭제 (주의!)

```sql
-- ⚠️ 주의: 모든 데이터가 삭제됩니다!

DROP TABLE IF EXISTS insider_transactions;
DROP TABLE IF EXISTS institutional_holders;
DROP TABLE IF EXISTS ownership_summary;
DROP TABLE IF EXISTS financial_metrics;
DROP TABLE IF EXISTS news;
DROP TABLE IF EXISTS volatility_metrics;
DROP TABLE IF EXISTS volume_metrics;
DROP TABLE IF EXISTS stock_prices;
```

---

## 📊 데이터베이스 정보

```sql
-- 데이터베이스 크기 확인
SELECT
    table_schema AS 'Database',
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)'
FROM information_schema.tables
WHERE table_schema = 'trading_db'
GROUP BY table_schema;

-- 테이블별 크기 확인
SELECT
    table_name AS 'Table',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)',
    table_rows AS 'Rows'
FROM information_schema.tables
WHERE table_schema = 'trading_db'
ORDER BY (data_length + index_length) DESC;
```

---

## ✅ 완료!

이제 DBeaver에서 테이블을 생성하고 데이터 수집을 시작할 수 있습니다! 🎉

**다음 단계:**
1. DBeaver에서 위 스크립트 실행
2. `python schedulers/data_scheduler.py` 실행
3. DBeaver에서 데이터 확인
