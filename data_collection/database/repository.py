"""
Data Repository
데이터 적재 및 조회 로직
"""

import mysql.connector
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime
import json


class DataRepository:
    """데이터 저장소"""

    def __init__(self, connection):
        """
        초기화

        Args:
            connection: MySQL connection
        """
        self.connection = connection

    def save_stock_prices(self, df: pd.DataFrame, timeframe: str = 'daily'):
        """
        주가 데이터 저장

        Args:
            df: DataFrame with columns: symbol, timestamp, open, high, low, close, volume
            timeframe: 'daily', '1min', '5min', etc.
        """
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO stock_prices
                (symbol, timestamp, open, high, low, close, volume, timeframe)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                open = VALUES(open),
                high = VALUES(high),
                low = VALUES(low),
                close = VALUES(close),
                volume = VALUES(volume)
            """

            records = []
            for _, row in df.iterrows():
                records.append((
                    row['symbol'],
                    row['timestamp'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    timeframe
                ))

            cursor.executemany(insert_sql, records)
            self.connection.commit()
            print(f"✓ Saved {len(records)} stock price records")

        except Exception as e:
            print(f"Error saving stock prices: {str(e)}")
            self.connection.rollback()
            raise

        finally:
            cursor.close()

    def save_volume_metrics(self, df: pd.DataFrame):
        """
        거래량 지표 저장

        Args:
            df: DataFrame with volume metrics
        """
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO volume_metrics
                (symbol, date, volume, volume_ma_20, volume_ma_50, volume_ratio,
                 volume_surge, relative_volume, money_flow)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                volume = VALUES(volume),
                volume_ma_20 = VALUES(volume_ma_20),
                volume_ma_50 = VALUES(volume_ma_50),
                volume_ratio = VALUES(volume_ratio),
                volume_surge = VALUES(volume_surge),
                relative_volume = VALUES(relative_volume),
                money_flow = VALUES(money_flow)
            """

            records = []
            for _, row in df.iterrows():
                records.append((
                    row['symbol'],
                    row['timestamp'].date() if hasattr(row['timestamp'], 'date') else row['timestamp'],
                    int(row['volume']),
                    float(row.get('volume_ma_20', 0)) if pd.notna(row.get('volume_ma_20')) else None,
                    float(row.get('volume_ma_50', 0)) if pd.notna(row.get('volume_ma_50')) else None,
                    float(row.get('volume_ratio', 0)) if pd.notna(row.get('volume_ratio')) else None,
                    bool(row.get('volume_surge', False)),
                    float(row.get('relative_volume', 0)) if pd.notna(row.get('relative_volume')) else None,
                    float(row.get('money_flow', 0)) if pd.notna(row.get('money_flow')) else None
                ))

            cursor.executemany(insert_sql, records)
            self.connection.commit()
            print(f"✓ Saved {len(records)} volume metric records")

        except Exception as e:
            print(f"Error saving volume metrics: {str(e)}")
            self.connection.rollback()
            raise

        finally:
            cursor.close()

    def save_volatility_metrics(self, df: pd.DataFrame):
        """
        변동성 지표 저장

        Args:
            df: DataFrame with volatility metrics
        """
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO volatility_metrics
                (symbol, date, volatility, atr, atr_percent,
                 bb_upper, bb_middle, bb_lower, bb_width)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                volatility = VALUES(volatility),
                atr = VALUES(atr),
                atr_percent = VALUES(atr_percent),
                bb_upper = VALUES(bb_upper),
                bb_middle = VALUES(bb_middle),
                bb_lower = VALUES(bb_lower),
                bb_width = VALUES(bb_width)
            """

            records = []
            for _, row in df.iterrows():
                records.append((
                    row['symbol'],
                    row['timestamp'].date() if hasattr(row['timestamp'], 'date') else row['timestamp'],
                    float(row.get('volatility', 0)) if pd.notna(row.get('volatility')) else None,
                    float(row.get('atr', 0)) if pd.notna(row.get('atr')) else None,
                    float(row.get('atr_percent', 0)) if pd.notna(row.get('atr_percent')) else None,
                    float(row.get('bb_upper', 0)) if pd.notna(row.get('bb_upper')) else None,
                    float(row.get('bb_middle', 0)) if pd.notna(row.get('bb_middle')) else None,
                    float(row.get('bb_lower', 0)) if pd.notna(row.get('bb_lower')) else None,
                    float(row.get('bb_width', 0)) if pd.notna(row.get('bb_width')) else None
                ))

            cursor.executemany(insert_sql, records)
            self.connection.commit()
            print(f"✓ Saved {len(records)} volatility metric records")

        except Exception as e:
            print(f"Error saving volatility metrics: {str(e)}")
            self.connection.rollback()
            raise

        finally:
            cursor.close()

    def save_news(self, news_list: List[Dict]):
        """
        뉴스 데이터 저장

        Args:
            news_list: List of news dictionaries
        """
        if not news_list:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO news
                (id, headline, summary, author, created_at, updated_at, url, symbols, text_length, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                headline = VALUES(headline),
                summary = VALUES(summary),
                updated_at = VALUES(updated_at)
            """

            records = []
            for news in news_list:
                records.append((
                    news['id'],
                    news.get('headline', ''),
                    news.get('summary', ''),
                    news.get('author', ''),
                    news.get('created_at'),
                    news.get('updated_at') or news.get('created_at'),
                    news.get('url', ''),
                    json.dumps(news.get('symbols', [])),
                    news.get('text_length', 0),
                    news.get('priority', 'normal')
                ))

            cursor.executemany(insert_sql, records)
            self.connection.commit()
            print(f"✓ Saved {len(records)} news records")

        except Exception as e:
            print(f"Error saving news: {str(e)}")
            self.connection.rollback()
            raise

        finally:
            cursor.close()

    def save_financial_metrics(self, metrics: Dict):
        """
        재무 지표 저장

        Args:
            metrics: Financial metrics dictionary
        """
        if not metrics or 'symbol' not in metrics:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO financial_metrics
                (symbol, market_cap, enterprise_value, trailing_pe, forward_pe, peg_ratio,
                 price_to_book, price_to_sales, ev_to_revenue, ev_to_ebitda,
                 profit_margin, operating_margin, return_on_assets, return_on_equity,
                 revenue, revenue_growth, earnings_growth, debt_to_equity,
                 current_ratio, quick_ratio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            record = (
                metrics['symbol'],
                metrics.get('market_cap', 0) or 0,
                metrics.get('enterprise_value', 0) or 0,
                metrics.get('trailing_pe', 0) or None,
                metrics.get('forward_pe', 0) or None,
                metrics.get('peg_ratio', 0) or None,
                metrics.get('price_to_book', 0) or None,
                metrics.get('price_to_sales', 0) or None,
                metrics.get('ev_to_revenue', 0) or None,
                metrics.get('ev_to_ebitda', 0) or None,
                metrics.get('profit_margin', 0) or None,
                metrics.get('operating_margin', 0) or None,
                metrics.get('return_on_assets', 0) or None,
                metrics.get('return_on_equity', 0) or None,
                metrics.get('revenue', 0) or 0,
                metrics.get('revenue_growth', 0) or None,
                metrics.get('earnings_growth', 0) or None,
                metrics.get('debt_to_equity', 0) or None,
                metrics.get('current_ratio', 0) or None,
                metrics.get('quick_ratio', 0) or None
            )

            cursor.execute(insert_sql, record)
            self.connection.commit()
            print(f"✓ Saved financial metrics for {metrics['symbol']}")

        except Exception as e:
            print(f"Error saving financial metrics: {str(e)}")
            self.connection.rollback()
            raise

        finally:
            cursor.close()

    def save_institutional_holders(self, df: pd.DataFrame):
        """
        기관 투자자 데이터 저장

        Args:
            df: DataFrame with institutional holders
        """
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO institutional_holders
                (symbol, holder_name, shares, date_reported, pct_out, value)
                VALUES (%s, %s, %s, %s, %s, %s)
            """

            records = []
            for _, row in df.iterrows():
                records.append((
                    row.get('Symbol', ''),
                    row.get('Holder', ''),
                    int(row.get('Shares', 0)) if pd.notna(row.get('Shares')) else None,
                    row.get('Date Reported'),
                    float(row.get('% Out', 0)) if pd.notna(row.get('% Out')) else None,
                    int(row.get('Value', 0)) if pd.notna(row.get('Value')) else None
                ))

            cursor.executemany(insert_sql, records)
            self.connection.commit()
            print(f"✓ Saved {len(records)} institutional holder records")

        except Exception as e:
            print(f"Error saving institutional holders: {str(e)}")
            self.connection.rollback()
            raise

        finally:
            cursor.close()

    def save_ownership_summary(self, summary: Dict):
        """
        소유권 요약 저장

        Args:
            summary: Ownership summary dictionary
        """
        if not summary or 'symbol' not in summary:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO ownership_summary
                (symbol, institutional_ownership_pct, insider_ownership_pct,
                 float_shares, shares_outstanding, shares_short,
                 short_percent_of_float, short_ratio)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            record = (
                summary['symbol'],
                summary.get('institutional_ownership_pct', 0) or None,
                summary.get('insider_ownership_pct', 0) or None,
                summary.get('float_shares', 0) or 0,
                summary.get('shares_outstanding', 0) or 0,
                summary.get('shares_short', 0) or 0,
                summary.get('short_percent_of_float', 0) or None,
                summary.get('short_ratio', 0) or None
            )

            cursor.execute(insert_sql, record)
            self.connection.commit()
            print(f"✓ Saved ownership summary for {summary['symbol']}")

        except Exception as e:
            print(f"Error saving ownership summary: {str(e)}")
            self.connection.rollback()
            raise

        finally:
            cursor.close()

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        최신 가격 조회

        Args:
            symbol: 종목 심볼

        Returns:
            Latest close price
        """
        cursor = self.connection.cursor()

        try:
            query = """
                SELECT close FROM stock_prices
                WHERE symbol = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """

            cursor.execute(query, (symbol,))
            result = cursor.fetchone()

            return float(result[0]) if result else None

        except Exception as e:
            print(f"Error getting latest price for {symbol}: {str(e)}")
            return None

        finally:
            cursor.close()

    def get_stock_prices(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = 'daily'
    ) -> pd.DataFrame:
        """
        주가 데이터 조회

        Args:
            symbol: 종목 심볼
            start_date: 시작 날짜
            end_date: 종료 날짜
            timeframe: 시간 프레임

        Returns:
            DataFrame with price data
        """
        cursor = self.connection.cursor(dictionary=True)

        try:
            query = """
                SELECT * FROM stock_prices
                WHERE symbol = %s
                AND timestamp >= %s
                AND timestamp <= %s
                AND timeframe = %s
                ORDER BY timestamp ASC
            """

            cursor.execute(query, (symbol, start_date, end_date, timeframe))
            results = cursor.fetchall()

            return pd.DataFrame(results) if results else pd.DataFrame()

        except Exception as e:
            print(f"Error getting stock prices: {str(e)}")
            return pd.DataFrame()

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
        repo = DataRepository(connection)

        # Test: Save dummy stock price
        test_df = pd.DataFrame([{
            'symbol': 'TEST',
            'timestamp': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 103.0,
            'volume': 1000000
        }])

        repo.save_stock_prices(test_df)

        # Test: Get latest price
        latest = repo.get_latest_price('TEST')
        print(f"Latest price for TEST: {latest}")

    finally:
        connection.close()
