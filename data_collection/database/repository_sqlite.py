"""
SQLite Data Repository
SQLite 버전 데이터 저장소
"""

import sqlite3
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime
import json


class SQLiteDataRepository:
    """SQLite 데이터 저장소"""

    def __init__(self, connection):
        """
        초기화

        Args:
            connection: SQLite connection
        """
        self.connection = connection

    def save_stock_prices(self, df: pd.DataFrame, timeframe: str = 'daily'):
        """주가 데이터 저장"""
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT OR REPLACE INTO stock_prices
                (symbol, timestamp, open, high, low, close, volume, timeframe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        """거래량 지표 저장"""
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT OR REPLACE INTO volume_metrics
                (symbol, date, volume, volume_ma_20, volume_ma_50, volume_ratio,
                 volume_surge, relative_volume, money_flow)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(row.get('volume_surge', False)),
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
        """변동성 지표 저장"""
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT OR REPLACE INTO volatility_metrics
                (symbol, date, volatility, atr, atr_percent,
                 bb_upper, bb_middle, bb_lower, bb_width)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        """뉴스 데이터 저장"""
        if not news_list:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT OR REPLACE INTO news
                (id, headline, summary, author, created_at, updated_at, url, symbols, text_length, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        """재무 지표 저장"""
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        """기관 투자자 데이터 저장"""
        if df.empty:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO institutional_holders
                (symbol, holder_name, shares, date_reported, pct_out, value)
                VALUES (?, ?, ?, ?, ?, ?)
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
        """소유권 요약 저장"""
        if not summary or 'symbol' not in summary:
            return

        cursor = self.connection.cursor()

        try:
            insert_sql = """
                INSERT INTO ownership_summary
                (symbol, institutional_ownership_pct, insider_ownership_pct,
                 float_shares, shares_outstanding, shares_short,
                 short_percent_of_float, short_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        """최신 가격 조회"""
        cursor = self.connection.cursor()

        try:
            query = """
                SELECT close FROM stock_prices
                WHERE symbol = ?
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
        """주가 데이터 조회"""
        cursor = self.connection.cursor()
        cursor.row_factory = sqlite3.Row

        try:
            query = """
                SELECT * FROM stock_prices
                WHERE symbol = ?
                AND timestamp >= ?
                AND timestamp <= ?
                AND timeframe = ?
                ORDER BY timestamp ASC
            """

            cursor.execute(query, (symbol, start_date, end_date, timeframe))
            results = cursor.fetchall()

            # Convert to list of dicts
            data = [dict(row) for row in results]

            return pd.DataFrame(data) if data else pd.DataFrame()

        except Exception as e:
            print(f"Error getting stock prices: {str(e)}")
            return pd.DataFrame()

        finally:
            cursor.close()


# Example usage
if __name__ == "__main__":
    from schema_sqlite import create_connection

    connection = create_connection()

    try:
        repo = SQLiteDataRepository(connection)

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
        print(f"\nLatest price for TEST: {latest}")

    finally:
        connection.close()
