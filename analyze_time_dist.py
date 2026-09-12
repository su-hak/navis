import pandas as pd
import glob

# 최신 CSV 찾기
files = sorted(glob.glob("backtest_results/universe_bt_*.csv"))
latest = files[-1]
print(f"분석 파일: {latest}")
print()

df = pd.read_csv(latest)
df["entry_dt"] = pd.to_datetime(df["entry_dt"], utc=True).dt.tz_convert("America/New_York")
df["entry_hour"] = df["entry_dt"].dt.hour
df["entry_minute"] = df["entry_dt"].dt.minute
df["is_09xx"] = df["entry_hour"] == 9
df["win"] = df["pnl"] > 0

print("=== 진입 시간대별 전체 성과 (09:xx vs 기타) ===")
summary = df.groupby("is_09xx").agg(
    trades=("pnl", "count"),
    wins=("win", "sum"),
    total_pnl=("pnl", "sum"),
    avg_pnl=("pnl", "mean"),
)
summary["win_rate"] = (summary["wins"] / summary["trades"] * 100).round(1)
summary.index = summary.index.map({True: "09:xx", False: "10:xx+"})
summary["total_pnl"] = summary["total_pnl"].map("${:,.0f}".format)
summary["avg_pnl"] = summary["avg_pnl"].map("${:,.0f}".format)
print(summary.to_string())
print()

print("=== 09:xx 5분 단위 세분화 ===")
df_09 = df[df["is_09xx"]].copy()
df_09["minute_bucket"] = (df_09["entry_minute"] // 5 * 5)

detail = df_09.groupby("minute_bucket").agg(
    trades=("pnl", "count"),
    wins=("win", "sum"),
    total_pnl=("pnl", "sum"),
    avg_pnl=("pnl", "mean"),
)
detail["win_rate"] = (detail["wins"] / detail["trades"] * 100).round(1)
detail["total_pnl"] = detail["total_pnl"].map("${:,.0f}".format)
detail["avg_pnl"] = detail["avg_pnl"].map("${:,.0f}".format)
detail.index = detail.index.map(lambda m: f"09:{m:02d}-{m+4:02d}")
print(detail.to_string())
print()

print("=== 09:xx STOP_LOSS vs 정상 마감 ===")
df_09_sl = df_09.groupby("signal_type").agg(
    trades=("pnl", "count"),
    wins=("win", "sum"),
    total_pnl=("pnl", "sum"),
)
df_09_sl["win_rate"] = (df_09_sl["wins"] / df_09_sl["trades"] * 100).round(1)
df_09_sl["total_pnl"] = df_09_sl["total_pnl"].map("${:,.0f}".format)
print(df_09_sl.to_string())
print()

print("=== 10:xx+ 시간대 세분화 ===")
df_10plus = df[~df["is_09xx"]].copy()
df_10plus["minute_bucket"] = df_10plus["entry_hour"].astype(str) + ":xx"
hour_detail = df_10plus.groupby("minute_bucket").agg(
    trades=("pnl", "count"),
    wins=("win", "sum"),
    total_pnl=("pnl", "sum"),
    avg_pnl=("pnl", "mean"),
)
hour_detail["win_rate"] = (hour_detail["wins"] / hour_detail["trades"] * 100).round(1)
hour_detail["total_pnl"] = hour_detail["total_pnl"].map("${:,.0f}".format)
hour_detail["avg_pnl"] = hour_detail["avg_pnl"].map("${:,.0f}".format)
print(hour_detail.to_string())
print()

print("=== 시나리오 요약 ===")
n_total = len(df)
n_09 = df["is_09xx"].sum()
wins_09 = df[df["is_09xx"]]["win"].sum()
loss_09 = n_09 - wins_09
pnl_09 = df[df["is_09xx"]]["pnl"].sum()
pnl_10plus = df[~df["is_09xx"]]["pnl"].sum()
pnl_total = df["pnl"].sum()

print(f"전체 거래: {n_total}건, 총 PnL: ${pnl_total:,.0f}")
print(f"09:xx 거래: {n_09}건 ({n_09/n_total*100:.1f}%)")
print(f"  승: {wins_09}건 / 패: {loss_09}건 / 승률: {wins_09/n_09*100:.1f}%")
print(f"  09:xx PnL: ${pnl_09:,.0f}")
print(f"10:xx+ 거래: {n_total-n_09}건")
print(f"  10:xx+ PnL: ${pnl_10plus:,.0f}")
print()
print(f"[시나리오] 09:xx 진입 전면 제외 시:")
print(f"  예상 잔여 PnL: ${pnl_10plus:,.0f}")
print(f"  예상 잔여 거래 수: {n_total-n_09}건")
