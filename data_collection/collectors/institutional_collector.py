"""
기관 투자자 및 13F 데이터 수집 모듈
- 기관 보유 현황
- 13F 공시 데이터
- 인사이더 거래
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp
import pandas as pd
import yfinance as yf


class InstitutionalCollector:
    """기관 투자자 데이터 수집기"""

    def __init__(self):
        """초기화"""
        self.sec_base_url = "https://www.sec.gov"

    async def get_institutional_holders(self, symbol: str) -> pd.DataFrame:
        """
        기관 투자자 보유 현황

        Args:
            symbol: 종목 심볼

        Returns:
            DataFrame with institutional holders
        """
        try:
            ticker = yf.Ticker(symbol)
            holders = ticker.institutional_holders

            if holders is None or holders.empty:
                return pd.DataFrame()

            holders['Symbol'] = symbol
            holders['Retrieved_At'] = datetime.now()

            return holders

        except Exception as e:
            print(f"Error fetching institutional holders for {symbol}: {str(e)}")
            return pd.DataFrame()

    async def get_major_holders(self, symbol: str) -> Dict:
        """
        주요 보유자 정보

        Args:
            symbol: 종목 심볼

        Returns:
            Dictionary with major holder information
        """
        try:
            ticker = yf.Ticker(symbol)
            major_holders = ticker.major_holders

            if major_holders is None or major_holders.empty:
                return {}

            result = {
                'symbol': symbol,
                'retrieved_at': datetime.now().isoformat()
            }

            # Parse major holders data
            for idx, row in major_holders.iterrows():
                key = str(row[1]).lower().replace(' ', '_').replace('%', 'pct')
                value = row[0]

                # Try to convert percentage strings to float
                if isinstance(value, str) and '%' in value:
                    try:
                        value = float(value.replace('%', ''))
                    except:
                        pass

                result[key] = value

            return result

        except Exception as e:
            print(f"Error fetching major holders for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def get_insider_transactions(self, symbol: str) -> pd.DataFrame:
        """
        인사이더 거래 내역

        Args:
            symbol: 종목 심볼

        Returns:
            DataFrame with insider transactions
        """
        try:
            ticker = yf.Ticker(symbol)
            insider_trades = ticker.insider_transactions

            if insider_trades is None or insider_trades.empty:
                return pd.DataFrame()

            insider_trades['Symbol'] = symbol

            return insider_trades

        except Exception as e:
            print(f"Error fetching insider transactions for {symbol}: {str(e)}")
            return pd.DataFrame()

    async def get_institutional_ownership_summary(self, symbol: str) -> Dict:
        """
        기관 보유 현황 요약

        Args:
            symbol: 종목 심볼

        Returns:
            Summary dictionary
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            summary = {
                'symbol': symbol,
                'institutional_ownership_pct': info.get('heldPercentInstitutions', 0) * 100 if info.get('heldPercentInstitutions') else 0,
                'insider_ownership_pct': info.get('heldPercentInsiders', 0) * 100 if info.get('heldPercentInsiders') else 0,
                'float_shares': info.get('floatShares', 0),
                'shares_outstanding': info.get('sharesOutstanding', 0),
                'shares_short': info.get('sharesShort', 0),
                'short_percent_of_float': info.get('shortPercentOfFloat', 0) * 100 if info.get('shortPercentOfFloat') else 0,
                'short_ratio': info.get('shortRatio', 0),
                'retrieved_at': datetime.now().isoformat()
            }

            # Round percentages
            for key in ['institutional_ownership_pct', 'insider_ownership_pct', 'short_percent_of_float']:
                if isinstance(summary[key], (int, float)):
                    summary[key] = round(summary[key], 2)

            return summary

        except Exception as e:
            print(f"Error fetching ownership summary for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def analyze_institutional_changes(
        self,
        symbol: str
    ) -> Dict:
        """
        기관 보유 변화 분석

        Args:
            symbol: 종목 심볼

        Returns:
            Analysis of institutional ownership changes
        """
        try:
            holders_df = await self.get_institutional_holders(symbol)

            if holders_df.empty:
                return {'symbol': symbol, 'error': 'No data available'}

            total_shares = holders_df['Shares'].sum() if 'Shares' in holders_df.columns else 0
            num_holders = len(holders_df)

            # Calculate concentration
            top_5_shares = holders_df.head(5)['Shares'].sum() if 'Shares' in holders_df.columns else 0
            concentration_ratio = (top_5_shares / total_shares * 100) if total_shares > 0 else 0

            analysis = {
                'symbol': symbol,
                'num_institutional_holders': num_holders,
                'total_institutional_shares': int(total_shares),
                'top_5_concentration_pct': round(concentration_ratio, 2),
                'top_holders': []
            }

            # Add top 5 holders
            if 'Holder' in holders_df.columns and 'Shares' in holders_df.columns:
                for idx, row in holders_df.head(5).iterrows():
                    holder_info = {
                        'name': row['Holder'],
                        'shares': int(row['Shares']) if pd.notna(row['Shares']) else 0,
                        'date_reported': str(row['Date Reported']) if 'Date Reported' in row else None,
                        'pct_out': round(row['% Out'] * 100, 2) if '% Out' in row and pd.notna(row['% Out']) else 0
                    }
                    analysis['top_holders'].append(holder_info)

            return analysis

        except Exception as e:
            print(f"Error analyzing institutional changes for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def analyze_insider_activity(
        self,
        symbol: str,
        days: int = 90
    ) -> Dict:
        """
        인사이더 거래 활동 분석

        Args:
            symbol: 종목 심볼
            days: 분석 기간 (일)

        Returns:
            Insider activity analysis
        """
        try:
            insider_df = await self.get_insider_transactions(symbol)

            if insider_df.empty:
                return {'symbol': symbol, 'message': 'No insider transactions found'}

            # Filter by date if 'Start Date' column exists
            if 'Start Date' in insider_df.columns:
                cutoff_date = datetime.now() - timedelta(days=days)
                insider_df['Start Date'] = pd.to_datetime(insider_df['Start Date'], errors='coerce')
                recent_trades = insider_df[insider_df['Start Date'] >= cutoff_date]
            else:
                recent_trades = insider_df

            if recent_trades.empty:
                return {'symbol': symbol, 'message': f'No insider transactions in last {days} days'}

            # Analyze buy vs sell
            buys = recent_trades[recent_trades['Transaction'].str.contains('Buy', case=False, na=False)] if 'Transaction' in recent_trades.columns else pd.DataFrame()
            sells = recent_trades[recent_trades['Transaction'].str.contains('Sale', case=False, na=False)] if 'Transaction' in recent_trades.columns else pd.DataFrame()

            analysis = {
                'symbol': symbol,
                'period_days': days,
                'total_transactions': len(recent_trades),
                'buy_transactions': len(buys),
                'sell_transactions': len(sells),
                'net_sentiment': 'bullish' if len(buys) > len(sells) else 'bearish' if len(sells) > len(buys) else 'neutral'
            }

            # Calculate shares if available
            if 'Shares' in recent_trades.columns:
                buy_shares = buys['Shares'].sum() if not buys.empty else 0
                sell_shares = sells['Shares'].sum() if not sells.empty else 0

                analysis['total_shares_bought'] = int(buy_shares) if pd.notna(buy_shares) else 0
                analysis['total_shares_sold'] = int(sell_shares) if pd.notna(sell_shares) else 0
                analysis['net_shares'] = int(buy_shares - sell_shares) if pd.notna(buy_shares) and pd.notna(sell_shares) else 0

            return analysis

        except Exception as e:
            print(f"Error analyzing insider activity for {symbol}: {str(e)}")
            return {'symbol': symbol, 'error': str(e)}

    async def screen_by_institutional_activity(
        self,
        symbols: List[str],
        min_institutional_pct: float = 50.0
    ) -> List[Dict]:
        """
        기관 보유 비율로 종목 스크리닝

        Args:
            symbols: 검색할 심볼 리스트
            min_institutional_pct: 최소 기관 보유 비율 (%)

        Returns:
            List of stocks meeting criteria
        """
        filtered_stocks = []

        for symbol in symbols:
            try:
                summary = await self.get_institutional_ownership_summary(symbol)

                if 'error' in summary:
                    continue

                institutional_pct = summary.get('institutional_ownership_pct', 0)

                if institutional_pct >= min_institutional_pct:
                    filtered_stocks.append({
                        'symbol': symbol,
                        'institutional_ownership_pct': institutional_pct,
                        'insider_ownership_pct': summary.get('insider_ownership_pct', 0),
                        'short_percent_of_float': summary.get('short_percent_of_float', 0)
                    })

            except Exception as e:
                print(f"Error screening {symbol}: {str(e)}")
                continue

        # Sort by institutional ownership
        filtered_stocks.sort(key=lambda x: x['institutional_ownership_pct'], reverse=True)

        return filtered_stocks

    async def get_comprehensive_ownership_data(
        self,
        symbol: str
    ) -> Dict:
        """
        종합 소유권 데이터

        Args:
            symbol: 종목 심볼

        Returns:
            Comprehensive ownership analysis
        """
        # Gather all ownership data
        institutional_summary = await self.get_institutional_ownership_summary(symbol)
        institutional_analysis = await self.analyze_institutional_changes(symbol)
        insider_analysis = await self.analyze_insider_activity(symbol, days=90)
        major_holders = await self.get_major_holders(symbol)

        comprehensive = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'institutional_summary': institutional_summary,
            'institutional_analysis': institutional_analysis,
            'insider_activity_90d': insider_analysis,
            'major_holders': major_holders
        }

        return comprehensive


# Example usage
async def main():
    """테스트 함수"""
    collector = InstitutionalCollector()

    symbol = 'AAPL'

    # Test: Institutional holders
    print(f"Fetching institutional holders for {symbol}...")
    holders_df = await collector.get_institutional_holders(symbol)
    print(f"\nTop 5 institutional holders:")
    print(holders_df.head())

    # Test: Ownership summary
    print(f"\n\nFetching ownership summary for {symbol}...")
    summary = await collector.get_institutional_ownership_summary(symbol)
    print(f"Ownership summary: {summary}")

    # Test: Institutional changes
    print(f"\n\nAnalyzing institutional changes for {symbol}...")
    changes = await collector.analyze_institutional_changes(symbol)
    print(f"Institutional analysis: {changes}")

    # Test: Insider activity
    print(f"\n\nAnalyzing insider activity for {symbol}...")
    insider_activity = await collector.analyze_insider_activity(symbol, days=90)
    print(f"Insider activity (90 days): {insider_activity}")

    # Test: Screening
    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'MSFT']
    print(f"\n\nScreening by institutional ownership: {symbols}")
    filtered = await collector.screen_by_institutional_activity(symbols, min_institutional_pct=50.0)
    print(f"Filtered stocks: {filtered}")


if __name__ == "__main__":
    asyncio.run(main())
