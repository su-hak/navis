"""
Data Collection Scheduler
APScheduler를 사용한 정기 데이터 수집
"""

import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import mysql.connector
import os
from dotenv import load_dotenv
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.stock_price_collector import StockPriceCollector
from collectors.volume_volatility_collector import VolumeVolatilityCollector
from collectors.news_collector import NewsCollector
from collectors.financial_collector import FinancialCollector
from collectors.institutional_collector import InstitutionalCollector
from database.repository import DataRepository

load_dotenv()


class DataCollectionScheduler:
    """데이터 수집 스케줄러"""

    def __init__(self, watchlist: list):
        """
        초기화

        Args:
            watchlist: 모니터링할 종목 리스트
        """
        self.watchlist = watchlist
        self.scheduler = AsyncIOScheduler()

        # Initialize collectors
        api_key = os.getenv('APCA-API-KEY-ID')
        api_secret = os.getenv('APCA-API-SECRET-KEY')

        self.stock_collector = StockPriceCollector(api_key, api_secret)
        self.volume_collector = VolumeVolatilityCollector(self.stock_collector)
        self.news_collector = NewsCollector(api_key, api_secret)
        self.financial_collector = FinancialCollector()
        self.institutional_collector = InstitutionalCollector()

    def get_db_connection(self):
        """MySQL 연결 생성"""
        return mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', 3306)),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            database=os.getenv('MYSQL_DATABASE', 'trading_db')
        )

    async def collect_daily_prices(self):
        """일봉 데이터 수집 (매일 시장 마감 후)"""
        print(f"\n[{datetime.now()}] Collecting daily prices...")

        try:
            start_date = datetime.now() - timedelta(days=5)  # Last 5 days
            df = await self.stock_collector.get_daily_bars(self.watchlist, start_date)

            if df.empty:
                print("No daily price data collected")
                return

            # Save to database
            connection = self.get_db_connection()
            try:
                repo = DataRepository(connection)
                repo.save_stock_prices(df, timeframe='daily')
                print(f"✓ Saved {len(df)} daily price records")
            finally:
                connection.close()

        except Exception as e:
            print(f"Error collecting daily prices: {str(e)}")

    async def collect_minute_bars(self):
        """분봉 데이터 수집 (시장 시간 중 매 5분)"""
        print(f"\n[{datetime.now()}] Collecting minute bars...")

        try:
            start_date = datetime.now() - timedelta(hours=2)
            df = await self.stock_collector.get_minute_bars(
                self.watchlist,
                start_date,
                minutes=5
            )

            if df.empty:
                print("No minute bar data collected")
                return

            # Save to database
            connection = self.get_db_connection()
            try:
                repo = DataRepository(connection)
                repo.save_stock_prices(df, timeframe='5min')
                print(f"✓ Saved {len(df)} minute bar records")
            finally:
                connection.close()

        except Exception as e:
            print(f"Error collecting minute bars: {str(e)}")

    async def collect_volume_metrics(self):
        """거래량 지표 수집 (매일 시장 마감 후)"""
        print(f"\n[{datetime.now()}] Collecting volume metrics...")

        try:
            start_date = datetime.now() - timedelta(days=5)
            connection = self.get_db_connection()

            try:
                repo = DataRepository(connection)

                for symbol in self.watchlist:
                    try:
                        df = await self.volume_collector.get_volume_analysis(symbol, start_date)

                        if not df.empty:
                            repo.save_volume_metrics(df)
                            print(f"✓ Saved volume metrics for {symbol}")

                    except Exception as e:
                        print(f"Error collecting volume metrics for {symbol}: {str(e)}")
                        continue

            finally:
                connection.close()

        except Exception as e:
            print(f"Error in volume metrics collection: {str(e)}")

    async def collect_volatility_metrics(self):
        """변동성 지표 수집 (매일 시장 마감 후)"""
        print(f"\n[{datetime.now()}] Collecting volatility metrics...")

        try:
            start_date = datetime.now() - timedelta(days=5)
            connection = self.get_db_connection()

            try:
                repo = DataRepository(connection)

                for symbol in self.watchlist:
                    try:
                        df = await self.volume_collector.get_volatility_metrics(symbol, start_date)

                        if not df.empty:
                            repo.save_volatility_metrics(df)
                            print(f"✓ Saved volatility metrics for {symbol}")

                    except Exception as e:
                        print(f"Error collecting volatility metrics for {symbol}: {str(e)}")
                        continue

            finally:
                connection.close()

        except Exception as e:
            print(f"Error in volatility metrics collection: {str(e)}")

    async def collect_news(self):
        """뉴스 수집 (매 30분)"""
        print(f"\n[{datetime.now()}] Collecting news...")

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=1)

            news_list = await self.news_collector.get_cleaned_news(
                self.watchlist,
                start_date,
                end_date,
                limit=100
            )

            if not news_list:
                print("No news collected")
                return

            # Save to database
            connection = self.get_db_connection()
            try:
                repo = DataRepository(connection)
                repo.save_news(news_list)
                print(f"✓ Saved {len(news_list)} news articles")
            finally:
                connection.close()

        except Exception as e:
            print(f"Error collecting news: {str(e)}")

    async def collect_financial_data(self):
        """재무 데이터 수집 (주 1회)"""
        print(f"\n[{datetime.now()}] Collecting financial data...")

        try:
            connection = self.get_db_connection()

            try:
                repo = DataRepository(connection)

                for symbol in self.watchlist:
                    try:
                        metrics = await self.financial_collector.get_key_metrics(symbol)

                        if 'error' not in metrics:
                            repo.save_financial_metrics(metrics)
                            print(f"✓ Saved financial metrics for {symbol}")

                    except Exception as e:
                        print(f"Error collecting financial data for {symbol}: {str(e)}")
                        continue

            finally:
                connection.close()

        except Exception as e:
            print(f"Error in financial data collection: {str(e)}")

    async def collect_institutional_data(self):
        """기관 데이터 수집 (주 1회)"""
        print(f"\n[{datetime.now()}] Collecting institutional data...")

        try:
            connection = self.get_db_connection()

            try:
                repo = DataRepository(connection)

                for symbol in self.watchlist:
                    try:
                        # Get institutional holders
                        holders_df = await self.institutional_collector.get_institutional_holders(symbol)
                        if not holders_df.empty:
                            repo.save_institutional_holders(holders_df)
                            print(f"✓ Saved institutional holders for {symbol}")

                        # Get ownership summary
                        summary = await self.institutional_collector.get_institutional_ownership_summary(symbol)
                        if 'error' not in summary:
                            repo.save_ownership_summary(summary)
                            print(f"✓ Saved ownership summary for {symbol}")

                    except Exception as e:
                        print(f"Error collecting institutional data for {symbol}: {str(e)}")
                        continue

            finally:
                connection.close()

        except Exception as e:
            print(f"Error in institutional data collection: {str(e)}")

    def setup_schedules(self):
        """스케줄 설정"""
        # Daily prices - 매일 오후 5시 (미국 시장 마감 후)
        self.scheduler.add_job(
            self.collect_daily_prices,
            CronTrigger(hour=17, minute=0, timezone='America/New_York'),
            id='daily_prices',
            name='Collect Daily Prices'
        )

        # Minute bars - 시장 시간 중 매 5분 (월-금, 9:30 AM - 4:00 PM ET)
        self.scheduler.add_job(
            self.collect_minute_bars,
            CronTrigger(
                day_of_week='mon-fri',
                hour='9-15',
                minute='*/5',
                timezone='America/New_York'
            ),
            id='minute_bars',
            name='Collect Minute Bars'
        )

        # Volume & Volatility metrics - 매일 오후 6시
        self.scheduler.add_job(
            self.collect_volume_metrics,
            CronTrigger(hour=18, minute=0, timezone='America/New_York'),
            id='volume_metrics',
            name='Collect Volume Metrics'
        )

        self.scheduler.add_job(
            self.collect_volatility_metrics,
            CronTrigger(hour=18, minute=10, timezone='America/New_York'),
            id='volatility_metrics',
            name='Collect Volatility Metrics'
        )

        # News - 매 30분
        self.scheduler.add_job(
            self.collect_news,
            IntervalTrigger(minutes=30),
            id='news_collection',
            name='Collect News'
        )

        # Financial data - 매주 일요일 오전 2시
        self.scheduler.add_job(
            self.collect_financial_data,
            CronTrigger(day_of_week='sun', hour=2, minute=0),
            id='financial_data',
            name='Collect Financial Data'
        )

        # Institutional data - 매주 일요일 오전 3시
        self.scheduler.add_job(
            self.collect_institutional_data,
            CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='institutional_data',
            name='Collect Institutional Data'
        )

    def start(self):
        """스케줄러 시작"""
        self.setup_schedules()
        self.scheduler.start()
        print("\n" + "="*60)
        print("Data Collection Scheduler Started")
        print("="*60)
        print(f"Monitoring {len(self.watchlist)} symbols: {', '.join(self.watchlist)}")
        print("\nScheduled Jobs:")
        for job in self.scheduler.get_jobs():
            print(f"  - {job.name} ({job.id}): {job.trigger}")
        print("="*60 + "\n")

    def stop(self):
        """스케줄러 중지"""
        self.scheduler.shutdown()
        print("\nScheduler stopped")


# Example usage
async def main():
    """메인 함수"""
    # Define watchlist
    watchlist = [
        'AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT',
        'GOOGL', 'AMZN', 'META', 'NFLX', 'SPY'
    ]

    # Create scheduler
    scheduler = DataCollectionScheduler(watchlist)

    # Start scheduler
    scheduler.start()

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()


if __name__ == "__main__":
    asyncio.run(main())
