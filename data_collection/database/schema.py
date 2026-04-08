"""
Database Schema
MySQL 테이블 스키마 정의
"""

CREATE_TABLES_SQL = {
    'stock_prices': """
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
    """,

    'volume_metrics': """
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
    """,

    'volatility_metrics': """
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
    """,

    'news': """
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
    """,

    'financial_metrics': """
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
    """,

    'institutional_holders': """
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
    """,

    'insider_transactions': """
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
    """,

    'ownership_summary': """
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
    """
}


def create_tables(connection):
    """
    모든 테이블 생성

    Args:
        connection: MySQL connection
    """
    cursor = connection.cursor()

    try:
        for table_name, create_sql in CREATE_TABLES_SQL.items():
            print(f"Creating table: {table_name}")
            cursor.execute(create_sql)
            connection.commit()
            print(f"✓ Table {table_name} created successfully")

    except Exception as e:
        print(f"Error creating tables: {str(e)}")
        connection.rollback()
        raise

    finally:
        cursor.close()


def drop_tables(connection):
    """
    모든 테이블 삭제 (주의!)

    Args:
        connection: MySQL connection
    """
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
    """
    테이블 정보 조회

    Args:
        connection: MySQL connection
        table_name: 테이블 이름

    Returns:
        Table schema information
    """
    cursor = connection.cursor()

    try:
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        return columns

    except Exception as e:
        print(f"Error getting table info for {table_name}: {str(e)}")
        return None

    finally:
        cursor.close()


# Example usage
if __name__ == "__main__":
    import mysql.connector
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Connect to MySQL
    connection = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', ''),
        database=os.getenv('MYSQL_DATABASE', 'trading_db')
    )

    try:
        print("Creating database tables...")
        create_tables(connection)
        print("\n✓ All tables created successfully!")

        # Show table info
        print("\n=== Table Schema ===")
        for table_name in CREATE_TABLES_SQL.keys():
            print(f"\n{table_name}:")
            info = get_table_info(connection, table_name)
            if info:
                for column in info:
                    print(f"  {column}")

    finally:
        connection.close()
