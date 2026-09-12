import yfinance as yf
import pandas as pd

try:
    vix = yf.download("^VIX", start="2022-01-01", end="2026-04-01", progress=False)
    print(f"VIX 데이터 로드 성공: {len(vix)}일")
    print(f"기간: {vix.index[0].date()} ~ {vix.index[-1].date()}")
    print()
    print("최근 10일:")
    print(vix[["Close"]].tail(10).to_string())
    print()
    # 2024년 NVDA 손실 집중 구간 VIX 확인
    # Close 컬럼 정규화 (MultiIndex 대응)
    close_col = vix["Close"]
    if isinstance(close_col.columns if hasattr(close_col, 'columns') else None, pd.MultiIndex):
        close_col = close_col.iloc[:, 0]
    elif hasattr(close_col, 'columns'):
        close_col = close_col.iloc[:, 0]
    close_col = close_col.squeeze()

    vix_2024 = close_col.loc["2024-01-01":"2024-06-30"]
    print("2024년 상반기 VIX 통계:")
    print(f"  평균: {float(vix_2024.mean()):.1f}")
    print(f"  최대: {float(vix_2024.max()):.1f}")
    print(f"  VIX > 20 일수: {int((vix_2024 > 20).sum())}일")
    print(f"  VIX > 25 일수: {int((vix_2024 > 25).sum())}일")
    print()
    # NVDA SL 발생 날짜 VIX
    stop_dates = ["2024-02-05", "2024-03-08", "2024-04-19", "2024-06-10", "2024-06-11"]
    print("NVDA STOP_LOSS 발생일 VIX:")
    for d in stop_dates:
        try:
            raw = close_col.loc[d]
            v = float(raw.iloc[0] if hasattr(raw, 'iloc') else raw)
            print(f"  {d}: VIX={v:.1f}")
        except Exception as e:
            print(f"  {d}: 데이터 없음 ({e})")

except Exception as e:
    print(f"ERROR: {e}")
