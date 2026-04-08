"""
SQLite Database Schema
MySQL 대신 SQLite 사용 (설치 불필요)
"""

import sqlite3
import os

# SQLite 테이블 생성 SQL
CREATE_TABLES_SQL = {
    'stock_prices': """
        CREATE TABLE IF NOT EXISTS stock_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            timeframe TEXT DEFAULT 'daily',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timestamp, timeframe)
        );
        CREATE INDEX IF NOT EXISTS idx_stock_symbol_timestamp ON stock_prices(symbol, timestamp);
        CREATE INDEX IF NOT EXISTS idx_stock_timestamp ON stock_prices(timestamp);
    """,

    'volume_metrics': """
        CREATE TABLE IF NOT EXISTS volume_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date DATE NOT NULL,
            volume INTEGER,
            volume_ma_20 REAL,
            volume_ma_50 REAL,
            volume_ratio REAL,
            volume_surge INTEGER DEFAULT 0,
            relative_volume REAL,
            money_flow REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, date)
        );
        CREATE INDEX IF NOT EXISTS idx_volume_symbol_date ON volume_metrics(symbol, date);
    """,

    'volatility_metrics': """
        CREATE TABLE IF NOT EXISTS volatility_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date DATE NOT NULL,
            volatility REAL,
            atr REAL,
            atr_percent REAL,
            bb_upper REAL,
            bb_middle REAL,
            bb_lower REAL,
            bb_width REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, date)
        );
        CREATE INDEX IF NOT EXISTS idx_volatility_symbol_date ON volatility_metrics(symbol, date);
    """,

    'news': """
        CREATE TABLE IF NOT EXISTS news (
            id TEXT PRIMARY KEY,
            headline TEXT,
            summary TEXT,
            author TEXT,
            created_at DATETIME,
            updated_at DATETIME,
            url TEXT,
            symbols TEXT,
            text_length INTEGER,
            priority TEXT DEFAULT 'normal',
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_news_created_at ON news(created_at);
    """,

    'financial_metrics': """
        CREATE TABLE IF NOT EXISTS financial_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            market_cap INTEGER,
            enterprise_value INTEGER,
            trailing_pe REAL,
            forward_pe REAL,
            peg_ratio REAL,
            price_to_book REAL,
            price_to_sales REAL,
            ev_to_revenue REAL,
            ev_to_ebitda REAL,
            profit_margin REAL,
            operating_margin REAL,
            return_on_assets REAL,
            return_on_equity REAL,
            revenue INTEGER,
            revenue_growth REAL,
            earnings_growth REAL,
            debt_to_equity REAL,
            current_ratio REAL,
            quick_ratio REAL,
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_financial_symbol ON financial_metrics(symbol);
        CREATE INDEX IF NOT EXISTS idx_financial_retrieved ON financial_metrics(retrieved_at);
    """,

    'institutional_holders': """
        CREATE TABLE IF NOT EXISTS institutional_holders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            holder_name TEXT,
            shares INTEGER,
            date_reported DATE,
            pct_out REAL,
            value INTEGER,
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_institutional_symbol ON institutional_holders(symbol);
        CREATE INDEX IF NOT EXISTS idx_institutional_date ON institutional_holders(date_reported);
    """,

    'insider_transactions': """
        CREATE TABLE IF NOT EXISTS insider_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            insider_name TEXT,
            transaction_type TEXT,
            shares INTEGER,
            price REAL,
            value INTEGER,
            start_date DATE,
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_insider_symbol ON insider_transactions(symbol);
        CREATE INDEX IF NOT EXISTS idx_insider_date ON insider_transactions(start_date);
    """,

    'ownership_summary': """
        CREATE TABLE IF NOT EXISTS ownership_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            institutional_ownership_pct REAL,
            insider_ownership_pct REAL,
            float_shares INTEGER,
            shares_outstanding INTEGER,
            shares_short INTEGER,
            short_percent_of_float REAL,
            short_ratio REAL,
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ownership_symbol ON ownership_summary(symbol);
        CREATE INDEX IF NOT EXISTS idx_ownership_retrieved ON ownership_summary(retrieved_at);
    """
}


def get_db_path():
    """SQLite DB 파일 경로"""
    # data_collection 폴더에 저장
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'trading.db')


def create_connection():
    """SQLite 연결 생성"""
    db_path = get_db_path()
    print(f"SQLite database: {db_path}")
    return sqlite3.connect(db_path)


def create_tables(connection):
    """모든 테이블 생성"""
    cursor = connection.cursor()

    try:
        for table_name, create_sql in CREATE_TABLES_SQL.items():
            print(f"Creating table: {table_name}")
            # SQLite는 세미콜론으로 구분된 여러 문장 실행 가능
            cursor.executescript(create_sql)
            connection.commit()
            print(f"✓ Table {table_name} created successfully")

        print("\n✓ All tables created successfully!")

    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        connection.rollback()
        raise

    finally:
        cursor.close()


def drop_tables(connection):
    """모든 테이블 삭제 (주의!)"""
    cursor = connection.cursor()

    try:
        tables = [
            'insider_transactions',
            'institutional_holders',
            'ownership_summary',
            'financial_metrics',
            'news',
            'volatility_metrics',
            'volume_metrics',
            'stock_prices'
        ]

        for table in tables:
            print(f"Dropping table: {table}")
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            connection.commit()
            print(f"✓ Table {table} dropped")

    except Exception as e:
        print(f"Error dropping tables: {str(e)}")
        connection.rollback()
        raise

    finally:
        cursor.close()


def get_table_info(connection, table_name: str):
    """테이블 정보 조회"""
    cursor = connection.cursor()

    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        return columns

    except Exception as e:
        print(f"Error getting table info for {table_name}: {str(e)}")
        return None

    finally:
        cursor.close()


# Example usage
if __name__ == "__main__":
    print("="*60)
    print("SQLite Database Initialization")
    print("="*60)

    connection = create_connection()

    try:
        print("\nCreating database tables...")
        create_tables(connection)

        # Show table info
        print("\n" + "="*60)
        print("Table Schema")
        print("="*60)
        for table_name in CREATE_TABLES_SQL.keys():
            print(f"\n{table_name}:")
            info = get_table_info(connection, table_name)
            if info:
                for column in info:
                    print(f"  {column}")

        print("\n" + "="*60)
        print("Database ready at:", get_db_path())
        print("="*60)

    finally:
        connection.close()
