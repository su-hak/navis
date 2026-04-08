"""
Configuration Management
환경 변수 및 설정 관리
"""

import os
from typing import List
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()


class Config:
    """애플리케이션 설정"""

    # Alpaca API
    ALPACA_API_KEY = os.getenv('APCA-API-KEY-ID')
    ALPACA_API_SECRET = os.getenv('APCA-API-SECRET-KEY')
    ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

    # MySQL Database
    # Railway DATABASE_URL 지원
    _database_url = os.getenv('DATABASE_URL') or os.getenv('MYSQL_URL')

    if _database_url and _database_url.startswith('mysql://'):
        # Parse Railway DATABASE_URL
        parsed = urlparse(_database_url)
        MYSQL_HOST = parsed.hostname or 'localhost'
        MYSQL_PORT = parsed.port or 3306
        MYSQL_USER = parsed.username or 'root'
        MYSQL_PASSWORD = parsed.password or ''
        MYSQL_DATABASE = parsed.path[1:] if parsed.path else 'trading_db'
    else:
        # Use individual environment variables
        MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
        MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
        MYSQL_USER = os.getenv('MYSQL_USER', 'root')
        MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
        MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'trading_db')

    # API Server
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('PORT', os.getenv('API_PORT', 8001)))  # Railway uses PORT

    # Data Collection Settings
    DEFAULT_WATCHLIST: List[str] = [
        'AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT',
        'GOOGL', 'AMZN', 'META', 'NFLX', 'SPY'
    ]

    # Timezone
    MARKET_TIMEZONE = 'America/New_York'

    @classmethod
    def validate(cls):
        """설정 검증"""
        errors = []

        if not cls.ALPACA_API_KEY:
            errors.append("APCA-API-KEY-ID is not set")

        if not cls.ALPACA_API_SECRET:
            errors.append("APCA-API-SECRET-KEY is not set")

        if not cls.MYSQL_PASSWORD:
            errors.append("MYSQL_PASSWORD is not set (warning)")

        if errors:
            print("\nConfiguration Errors:")
            for error in errors:
                print(f"  - {error}")
            return False

        return True

    @classmethod
    def get_db_config(cls) -> dict:
        """데이터베이스 설정 반환"""
        return {
            'host': cls.MYSQL_HOST,
            'port': cls.MYSQL_PORT,
            'user': cls.MYSQL_USER,
            'password': cls.MYSQL_PASSWORD,
            'database': cls.MYSQL_DATABASE
        }

    @classmethod
    def get_alpaca_config(cls) -> dict:
        """Alpaca API 설정 반환"""
        return {
            'api_key': cls.ALPACA_API_KEY,
            'api_secret': cls.ALPACA_API_SECRET,
            'base_url': cls.ALPACA_BASE_URL
        }

    @classmethod
    def display(cls):
        """설정 표시"""
        print("\n" + "="*60)
        print("Configuration Settings")
        print("="*60)
        print(f"Alpaca API Key: {cls.ALPACA_API_KEY[:10]}..." if cls.ALPACA_API_KEY else "Alpaca API Key: Not Set")
        print(f"MySQL Host: {cls.MYSQL_HOST}:{cls.MYSQL_PORT}")
        print(f"MySQL Database: {cls.MYSQL_DATABASE}")
        print(f"API Server: {cls.API_HOST}:{cls.API_PORT}")
        print(f"Default Watchlist: {', '.join(cls.DEFAULT_WATCHLIST)}")
        print("="*60 + "\n")


# Example usage
if __name__ == "__main__":
    Config.display()

    if Config.validate():
        print("✓ Configuration is valid")
    else:
        print("✗ Configuration has errors")
