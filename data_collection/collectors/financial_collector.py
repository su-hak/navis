"""
재무 데이터 수집 모듈
- 재무제표 데이터
- 주요 재무 지표
- 밸류에이션 지표
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
import pandas as pd
import yfinance as yf


class FinancialCollector:
    """재무 데이터 수집기"""

    def __init__(self):
        """초기화"""
        pass

    async def get_financial_statements(
        self,
        symbol: str
    ) -> Dict[str, pd.DataFrame]:
        """
        재무제표 조회

        Args:
            symbol: 종목 심볼

        Returns:
            Dictionary with income_statement, balance_sheet, cash_flow
        """
        try:
            ticker = yf.Ticker(symbol)

            statements = {
                'income_statement': ticker.income_stmt,
                'balance_sheet': ticker.balance_sheet,
                'cash_flow': ticker.cashflow
            }

            return statements

        except Exception as e:
            print(f"Error fetching financial statements for {symbol}: {str(e)}")
            return {
                'income_statement': pd.DataFrame(),
                'balance_sheet': pd.DataFrame(),
                'cash_flow': pd.DataFrame()
            }

    async def get_key_metrics(self, symbol: str) -> Dict:
        """
        주요 재무 지표

        Args:
            symbol: 종목 심볼

        Returns:
            Dictionary of key financial metrics
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            metrics = {
                'symbol': symbol,
                'market_cap': info.get('marketCap', 0),
                'enterprise_value': info.get('enterpriseValue', 0),
                'trailing_pe': info.get('trailingPE', 0),
                'forward_pe': info.get('forwardPE', 0),
                'peg_ratio': info.get('pegRatio', 0),
                'price_to_book': info.get('priceToBook', 0),
                'price_to_sales': info.get('priceToSalesTrailing12Months', 0),
                'ev_to_revenue': info.get('enterpriseToRevenue', 0),
                'ev_to_ebitda': info.get('enterpriseToEbitda', 0),
                'profit_margin': info.get('profitMargins', 0),
                'operating_margin': info.get('operatingMargins', 0),
                'return_on_assets': info.get('returnOnAssets', 0),
                'return_on_equity': info.get('returnOnEquity', 0),
                'revenue': info.get('totalRevenue', 0),
                'revenue_per_share': info.get('revenuePerShare', 0),
                'revenue_growth': info.get('revenueGrowth', 0),
                'earnings_growth': info.get('earningsGrowth', 0),
                'current_ratio': info.get('currentRatio', 0),
                'quick_ratio': info.get('quickRatio', 0),
                'debt_to_equity': info.get('debtToEquity', 0),
                'gross_margin': info.get('grossMargins', 0),
                'ebitda_margin': info.get('ebitdaMargins', 0),
                'free_cash_flow': info.get('freeCashflow', 0),
                'operating_cash_flow': info.get('operatingCashflow', 0),
                'beta': info.get('beta', 0),
                'shares_outstanding': info.get('sharesOutstanding', 0),
                'float_shares': info.get('floatShares', 0),
                'shares_short': info.get('sharesShort', 0),
                'short_ratio': info.get('shortRatio', 0),
                'short_percent': info.get('shortPercentOfFloat', 0),
                'held_percent_insiders': info.get('heldPercentInsiders', 0),
                'held_percent_institutions': info.get('heldPercentInstitutions', 0),
                'last_updated': datetime.now().isoformat()
            }

            return metrics

        except Exception as e:
            print(f"Error fetching key metrics for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def get_earnings_data(self, symbol: str) -> pd.DataFrame:
        """
        실적 데이터

        Args:
            symbol: 종목 심볼

        Returns:
            DataFrame with earnings history
        """
        try:
            ticker = yf.Ticker(symbol)
            earnings = ticker.earnings_dates

            if earnings is None or earnings.empty:
                return pd.DataFrame()

            return earnings.reset_index()

        except Exception as e:
            print(f"Error fetching earnings data for {symbol}: {str(e)}")
            return pd.DataFrame()

    async def get_growth_metrics(self, symbol: str) -> Dict:
        """
        성장성 지표

        Args:
            symbol: 종목 심볼

        Returns:
            Dictionary with growth metrics
        """
        try:
            ticker = yf.Ticker(symbol)
            income_stmt = ticker.income_stmt

            if income_stmt.empty:
                return {}

            # Get revenue and earnings growth
            revenues = income_stmt.loc['Total Revenue'] if 'Total Revenue' in income_stmt.index else None
            net_income = income_stmt.loc['Net Income'] if 'Net Income' in income_stmt.index else None

            growth_metrics = {
                'symbol': symbol,
                'revenue_growth_yoy': 0,
                'earnings_growth_yoy': 0,
                'revenue_cagr_3y': 0,
                'earnings_cagr_3y': 0
            }

            if revenues is not None and len(revenues) >= 2:
                # YoY growth (most recent vs previous year)
                revenue_growth = ((revenues.iloc[0] - revenues.iloc[1]) / revenues.iloc[1]) * 100
                growth_metrics['revenue_growth_yoy'] = round(revenue_growth, 2)

                # 3-year CAGR
                if len(revenues) >= 4:
                    years = 3
                    cagr = (((revenues.iloc[0] / revenues.iloc[3]) ** (1 / years)) - 1) * 100
                    growth_metrics['revenue_cagr_3y'] = round(cagr, 2)

            if net_income is not None and len(net_income) >= 2:
                if net_income.iloc[1] != 0:
                    earnings_growth = ((net_income.iloc[0] - net_income.iloc[1]) / abs(net_income.iloc[1])) * 100
                    growth_metrics['earnings_growth_yoy'] = round(earnings_growth, 2)

                if len(net_income) >= 4 and net_income.iloc[3] > 0:
                    years = 3
                    cagr = (((net_income.iloc[0] / net_income.iloc[3]) ** (1 / years)) - 1) * 100
                    growth_metrics['earnings_cagr_3y'] = round(cagr, 2)

            return growth_metrics

        except Exception as e:
            print(f"Error calculating growth metrics for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def get_profitability_metrics(self, symbol: str) -> Dict:
        """
        수익성 지표

        Args:
            symbol: 종목 심볼

        Returns:
            Dictionary with profitability metrics
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            profitability = {
                'symbol': symbol,
                'gross_margin': info.get('grossMargins', 0) * 100 if info.get('grossMargins') else 0,
                'operating_margin': info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else 0,
                'profit_margin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
                'ebitda_margin': info.get('ebitdaMargins', 0) * 100 if info.get('ebitdaMargins') else 0,
                'roa': info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0,
                'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
                'roic': 0  # Calculate if needed
            }

            # Round values
            for key in profitability:
                if isinstance(profitability[key], (int, float)) and key != 'symbol':
                    profitability[key] = round(profitability[key], 2)

            return profitability

        except Exception as e:
            print(f"Error fetching profitability metrics for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def get_valuation_metrics(self, symbol: str) -> Dict:
        """
        밸류에이션 지표

        Args:
            symbol: 종목 심볼

        Returns:
            Dictionary with valuation metrics
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            valuation = {
                'symbol': symbol,
                'pe_ratio': info.get('trailingPE', 0),
                'forward_pe': info.get('forwardPE', 0),
                'peg_ratio': info.get('pegRatio', 0),
                'price_to_book': info.get('priceToBook', 0),
                'price_to_sales': info.get('priceToSalesTrailing12Months', 0),
                'ev_to_revenue': info.get('enterpriseToRevenue', 0),
                'ev_to_ebitda': info.get('enterpriseToEbitda', 0),
                'market_cap': info.get('marketCap', 0),
                'enterprise_value': info.get('enterpriseValue', 0)
            }

            # Round values
            for key in valuation:
                if isinstance(valuation[key], (int, float)) and key != 'symbol':
                    if key in ['market_cap', 'enterprise_value']:
                        valuation[key] = int(valuation[key])
                    else:
                        valuation[key] = round(valuation[key], 2)

            return valuation

        except Exception as e:
            print(f"Error fetching valuation metrics for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def get_comprehensive_analysis(
        self,
        symbol: str
    ) -> Dict:
        """
        종합 재무 분석

        Args:
            symbol: 종목 심볼

        Returns:
            Dictionary with comprehensive financial data
        """
        # Gather all metrics
        key_metrics = await self.get_key_metrics(symbol)
        growth_metrics = await self.get_growth_metrics(symbol)
        profitability_metrics = await self.get_profitability_metrics(symbol)
        valuation_metrics = await self.get_valuation_metrics(symbol)

        comprehensive = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'key_metrics': key_metrics,
            'growth': growth_metrics,
            'profitability': profitability_metrics,
            'valuation': valuation_metrics
        }

        return comprehensive

    async def screen_stocks(
        self,
        symbols: List[str],
        min_revenue_growth: float = 0,
        min_profit_margin: float = 0,
        max_pe_ratio: float = 100
    ) -> List[Dict]:
        """
        재무 기준으로 종목 스크리닝

        Args:
            symbols: 검색할 심볼 리스트
            min_revenue_growth: 최소 매출 성장률 (%)
            min_profit_margin: 최소 순이익률 (%)
            max_pe_ratio: 최대 PER

        Returns:
            List of stocks meeting criteria
        """
        filtered_stocks = []

        for symbol in symbols:
            try:
                metrics = await self.get_key_metrics(symbol)

                if 'error' in metrics:
                    continue

                # Apply filters
                revenue_growth = metrics.get('revenue_growth', 0) or 0
                profit_margin = metrics.get('profit_margin', 0) or 0
                pe_ratio = metrics.get('trailing_pe', 0) or 0

                if (revenue_growth >= min_revenue_growth and
                    profit_margin >= min_profit_margin and
                    0 < pe_ratio <= max_pe_ratio):

                    filtered_stocks.append({
                        'symbol': symbol,
                        'revenue_growth': round(revenue_growth * 100, 2),
                        'profit_margin': round(profit_margin * 100, 2),
                        'pe_ratio': round(pe_ratio, 2),
                        'market_cap': metrics.get('market_cap', 0)
                    })

            except Exception as e:
                print(f"Error screening {symbol}: {str(e)}")
                continue

        # Sort by revenue growth
        filtered_stocks.sort(key=lambda x: x.get('revenue_growth', 0), reverse=True)

        return filtered_stocks


# Example usage
async def main():
    """테스트 함수"""
    collector = FinancialCollector()

    symbol = 'AAPL'

    # Test: Get key metrics
    print(f"Fetching key metrics for {symbol}...")
    metrics = await collector.get_key_metrics(symbol)
    print(f"\nKey metrics:")
    for key, value in metrics.items():
        if key not in ['symbol', 'last_updated']:
            print(f"  {key}: {value}")

    # Test: Growth metrics
    print(f"\n\nFetching growth metrics for {symbol}...")
    growth = await collector.get_growth_metrics(symbol)
    print(f"Growth metrics: {growth}")

    # Test: Profitability
    print(f"\n\nFetching profitability metrics for {symbol}...")
    profitability = await collector.get_profitability_metrics(symbol)
    print(f"Profitability: {profitability}")

    # Test: Screening
    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']
    print(f"\n\nScreening stocks: {symbols}")
    filtered = await collector.screen_stocks(
        symbols,
        min_revenue_growth=0.1,
        min_profit_margin=0.1,
        max_pe_ratio=50
    )
    print(f"Filtered stocks: {filtered}")


if __name__ == "__main__":
    asyncio.run(main())
