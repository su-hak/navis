"""
FastAPI Main Application
데이터 수집 팀 API 서버
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import List, Optional
import os
from dotenv import load_dotenv
import mysql.connector

# Import collectors
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.stock_price_collector import StockPriceCollector
from collectors.volume_volatility_collector import VolumeVolatilityCollector
from collectors.news_collector import NewsCollector
from collectors.financial_collector import FinancialCollector
from collectors.institutional_collector import InstitutionalCollector
from database.repository import DataRepository

load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Data Collection API",
    description="AI 자동매매 시스템 - 데이터 수집 팀 API",
    version="1.0.0"
)

# Initialize collectors
api_key = os.getenv('APCA-API-KEY-ID')
api_secret = os.getenv('APCA-API-SECRET-KEY')

stock_collector = StockPriceCollector(api_key, api_secret)
volume_collector = VolumeVolatilityCollector(stock_collector)
news_collector = NewsCollector(api_key, api_secret)
financial_collector = FinancialCollector()
institutional_collector = InstitutionalCollector()

# Database connection helper
def get_db_connection():
    """Get MySQL connection"""
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', ''),
        database=os.getenv('MYSQL_DATABASE', 'trading_db')
    )


# ============ Health Check ============

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Data Collection API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ============ Stock Price Endpoints ============

@app.get("/api/v1/prices/{symbol}")
async def get_stock_price(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of days")
):
    """Get stock price data"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        df = await stock_collector.get_daily_bars([symbol], start_date)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        return JSONResponse(content=df.to_dict(orient='records'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/prices/{symbol}/latest")
async def get_latest_price(symbol: str):
    """Get latest price"""
    try:
        prices = await stock_collector.get_latest_price([symbol])

        if not prices or symbol not in prices:
            raise HTTPException(status_code=404, detail=f"No price found for {symbol}")

        return {
            "symbol": symbol,
            "price": prices[symbol],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/prices/batch")
async def get_batch_prices(
    symbols: List[str],
    days: int = Query(30, ge=1, le=365)
):
    """Get batch price data"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        df = await stock_collector.get_daily_bars(symbols, start_date)

        if df.empty:
            raise HTTPException(status_code=404, detail="No data found")

        return JSONResponse(content=df.to_dict(orient='records'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Volume & Volatility Endpoints ============

@app.get("/api/v1/volume/{symbol}")
async def get_volume_analysis(
    symbol: str,
    days: int = Query(30, ge=1, le=365)
):
    """Get volume analysis"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        df = await volume_collector.get_volume_analysis(symbol, start_date)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        return JSONResponse(content=df.to_dict(orient='records'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/volatility/{symbol}")
async def get_volatility_metrics(
    symbol: str,
    days: int = Query(30, ge=1, le=365)
):
    """Get volatility metrics"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        df = await volume_collector.get_volatility_metrics(symbol, start_date)

        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        return JSONResponse(content=df.to_dict(orient='records'))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/volume/anomalies")
async def detect_volume_anomalies(
    symbols: List[str] = Query(..., description="List of symbols"),
    threshold: float = Query(2.5, ge=1.0, le=10.0)
):
    """Detect volume anomalies"""
    try:
        anomalies = await volume_collector.detect_volume_anomalies(symbols, threshold)
        return {"anomalies": anomalies, "count": len(anomalies)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/volatility/ranking")
async def get_volatility_ranking(
    symbols: List[str] = Query(..., description="List of symbols"),
    top_n: int = Query(20, ge=1, le=100)
):
    """Get volatility ranking"""
    try:
        ranking = await volume_collector.get_volatility_ranking(symbols, top_n)
        return {"ranking": ranking, "count": len(ranking)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ News Endpoints ============

@app.get("/api/v1/news/{symbol}")
async def get_news(
    symbol: str,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back")
):
    """Get news for symbol"""
    try:
        news = await news_collector.get_latest_news(symbol, hours=hours, limit=50)
        return {"symbol": symbol, "news": news, "count": len(news)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/news/breaking")
async def get_breaking_news(
    symbols: List[str] = Query(..., description="List of symbols"),
    minutes: int = Query(30, ge=1, le=1440)
):
    """Get breaking news"""
    try:
        news = await news_collector.get_breaking_news(symbols, minutes=minutes)
        return {"breaking_news": news, "count": len(news)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/news/volume")
async def get_news_volume(
    symbols: List[str] = Query(..., description="List of symbols"),
    days: int = Query(30, ge=1, le=365)
):
    """Get news volume by symbol"""
    try:
        volume = await news_collector.get_news_volume(symbols, days=days)
        return {"news_volume": volume}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Financial Data Endpoints ============

@app.get("/api/v1/financials/{symbol}")
async def get_financial_metrics(symbol: str):
    """Get financial metrics"""
    try:
        metrics = await financial_collector.get_key_metrics(symbol)

        if 'error' in metrics:
            raise HTTPException(status_code=404, detail=metrics['error'])

        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/financials/{symbol}/growth")
async def get_growth_metrics(symbol: str):
    """Get growth metrics"""
    try:
        growth = await financial_collector.get_growth_metrics(symbol)

        if 'error' in growth:
            raise HTTPException(status_code=404, detail=growth['error'])

        return growth

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/financials/{symbol}/profitability")
async def get_profitability_metrics(symbol: str):
    """Get profitability metrics"""
    try:
        profitability = await financial_collector.get_profitability_metrics(symbol)

        if 'error' in profitability:
            raise HTTPException(status_code=404, detail=profitability['error'])

        return profitability

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/financials/{symbol}/valuation")
async def get_valuation_metrics(symbol: str):
    """Get valuation metrics"""
    try:
        valuation = await financial_collector.get_valuation_metrics(symbol)

        if 'error' in valuation:
            raise HTTPException(status_code=404, detail=valuation['error'])

        return valuation

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/financials/screen")
async def screen_stocks(
    symbols: List[str] = Query(..., description="List of symbols"),
    min_revenue_growth: float = Query(0.0, description="Minimum revenue growth"),
    min_profit_margin: float = Query(0.0, description="Minimum profit margin"),
    max_pe_ratio: float = Query(100.0, description="Maximum P/E ratio")
):
    """Screen stocks by financial criteria"""
    try:
        filtered = await financial_collector.screen_stocks(
            symbols,
            min_revenue_growth=min_revenue_growth,
            min_profit_margin=min_profit_margin,
            max_pe_ratio=max_pe_ratio
        )

        return {"filtered_stocks": filtered, "count": len(filtered)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Institutional Data Endpoints ============

@app.get("/api/v1/institutional/{symbol}")
async def get_institutional_data(symbol: str):
    """Get institutional ownership data"""
    try:
        data = await institutional_collector.get_comprehensive_ownership_data(symbol)
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/institutional/{symbol}/summary")
async def get_institutional_summary(symbol: str):
    """Get institutional ownership summary"""
    try:
        summary = await institutional_collector.get_institutional_ownership_summary(symbol)

        if 'error' in summary:
            raise HTTPException(status_code=404, detail=summary['error'])

        return summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/institutional/{symbol}/analysis")
async def get_institutional_analysis(symbol: str):
    """Get institutional ownership analysis"""
    try:
        analysis = await institutional_collector.analyze_institutional_changes(symbol)

        if 'error' in analysis:
            raise HTTPException(status_code=404, detail=analysis['error'])

        return analysis

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/institutional/{symbol}/insider")
async def get_insider_activity(
    symbol: str,
    days: int = Query(90, ge=1, le=365)
):
    """Get insider trading activity"""
    try:
        activity = await institutional_collector.analyze_insider_activity(symbol, days=days)
        return activity

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Data Collection Endpoints ============

@app.post("/api/v1/collect/prices")
async def collect_and_save_prices(
    symbols: List[str],
    days: int = Query(30, ge=1, le=365)
):
    """Collect and save price data to database"""
    try:
        start_date = datetime.now() - timedelta(days=days)
        df = await stock_collector.get_daily_bars(symbols, start_date)

        if df.empty:
            raise HTTPException(status_code=404, detail="No data collected")

        # Save to database
        connection = get_db_connection()
        try:
            repo = DataRepository(connection)
            repo.save_stock_prices(df, timeframe='daily')
        finally:
            connection.close()

        return {
            "status": "success",
            "symbols": symbols,
            "records_saved": len(df),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/collect/news")
async def collect_and_save_news(
    symbols: List[str],
    hours: int = Query(24, ge=1, le=168)
):
    """Collect and save news data to database"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)

        news_list = await news_collector.get_cleaned_news(symbols, start_date, end_date, limit=200)

        if not news_list:
            raise HTTPException(status_code=404, detail="No news collected")

        # Save to database
        connection = get_db_connection()
        try:
            repo = DataRepository(connection)
            repo.save_news(news_list)
        finally:
            connection.close()

        return {
            "status": "success",
            "symbols": symbols,
            "news_saved": len(news_list),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/collect/financials")
async def collect_and_save_financials(symbols: List[str]):
    """Collect and save financial data to database"""
    try:
        saved_count = 0
        connection = get_db_connection()

        try:
            repo = DataRepository(connection)

            for symbol in symbols:
                metrics = await financial_collector.get_key_metrics(symbol)
                if 'error' not in metrics:
                    repo.save_financial_metrics(metrics)
                    saved_count += 1

        finally:
            connection.close()

        return {
            "status": "success",
            "symbols": symbols,
            "records_saved": saved_count,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
