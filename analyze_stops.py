import pandas as pd
import glob

# 최신 CSV 찾기
files = sorted(glob.glob("backtest_results/universe_bt_*.csv"))
latest = files[-1]
print(f"분석 파일: {latest}")
print()

df = pd.read_csv(latest)
stops = df[df["signal_type"] == "STOP_LOSS"].copy()
stops["entry_dt"] = pd.to_datetime(stops["entry_dt"], utc=True).dt.tz_convert("America/New_York")
stops["year"]    = stops["entry_dt"].dt.year
stops["month"]   = stops["entry_dt"].dt.month
stops["weekday"] = stops["entry_dt"].dt.day_name()
stops["hour"]    = stops["entry_dt"].dt.hour

print("=== STOP_LOSS 전체 현황 ===")
print(f"총 STOP_LOSS 건수: {len(stops)}건")
print(f"총 손실: ${stops['pnl'].sum():,.0f}")
print(f"건당 평균 손실: ${stops['pnl'].mean():,.0f}")
print()

print("=== 연도별 ===")
yr = stops.groupby("year")["pnl"].agg(["count","sum","mean"])
yr.columns = ["건수","합계","평균"]
yr["합계"] = yr["합계"].map("${:,.0f}".format)
yr["평균"] = yr["평균"].map("${:,.0f}".format)
print(yr.to_string())
print()

print("=== 종목별 (손실 큰 순) ===")
sym = stops.groupby("symbol")["pnl"].agg(["count","sum","mean"]).sort_values("sum")
sym.columns = ["건수","합계","평균"]
sym["합계"] = sym["합계"].map("${:,.0f}".format)
sym["평균"] = sym["평균"].map("${:,.0f}".format)
print(sym.to_string())
print()

print("=== 요일별 ===")
wd_order = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
wd = stops.groupby("weekday")["pnl"].agg(["count","sum","mean"])
wd.columns = ["건수","합계","평균"]
wd = wd.reindex([w for w in wd_order if w in wd.index])
wd["합계"] = wd["합계"].map("${:,.0f}".format)
wd["평균"] = wd["평균"].map("${:,.0f}".format)
print(wd.to_string())
print()

print("=== 월별 ===")
mo = stops.groupby("month")["pnl"].agg(["count","sum","mean"])
mo.columns = ["건수","합계","평균"]
mo["합계"] = mo["합계"].map("${:,.0f}".format)
mo["평균"] = mo["평균"].map("${:,.0f}".format)
print(mo.to_string())
print()

print("=== 진입 시간대별 (ET) ===")
hr = stops.groupby("hour")["pnl"].agg(["count","sum","mean"])
hr.columns = ["건수","합계","평균"]
hr["합계"] = hr["합계"].map("${:,.0f}".format)
hr["평균"] = hr["평균"].map("${:,.0f}".format)
print(hr.to_string())
print()

print("=== STOP_LOSS 개별 거래 목록 ===")
detail = stops[["entry_dt","symbol","entry_price","exit_price","qty","pnl"]].copy()
detail["entry_dt"] = detail["entry_dt"].dt.strftime("%Y-%m-%d %H:%M")
detail["pnl_str"] = detail["pnl"].map("${:,.0f}".format)
print(detail[["entry_dt","symbol","entry_price","exit_price","qty","pnl_str"]].to_string(index=False))
print()

# 전체 거래 대비 STOP_LOSS 상관 분석
print("=== 참고: STOP_LOSS vs FULL 거래 비교 ===")
print(f"전체 거래: {len(df)}건")
print(f"STOP_LOSS: {len(stops)}건 ({len(stops)/len(df)*100:.1f}%)")
print(f"STOP_LOSS 총 손실: ${stops['pnl'].sum():,.0f}")
print(f"STOP_LOSS 외 총 PnL: ${df[df['signal_type']!='STOP_LOSS']['pnl'].sum():,.0f}")
print(f"전체 총 PnL: ${df['pnl'].sum():,.0f}")
