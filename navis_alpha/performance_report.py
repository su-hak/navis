"""
NAVIS ALPHA v1.0 — 페이퍼 트레이딩 성과 추적 리포트

navis_alpha_tracking.csv를 읽어 백테스트 기준(OOS CAGR 12.16%)과 비교합니다.
Phase A 합격 기준: 월 수익률 백테스트 대비 -3%p 이내.

사용:
    python -m navis_alpha.performance_report
"""
from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path
from typing import List

# Phase A 합격 기준
BACKTEST_MONTHLY_RETURN = (1 + 0.1216) ** (1 / 12) - 1  # ~0.959%/월 (OOS 12.16% 기준)
PASS_THRESHOLD_DELTA    = -0.03   # 백테스트 대비 -3%p 이내

TRACKING_FILE = Path("navis_alpha_tracking.csv")


def load_tracking() -> List[dict]:
    if not TRACKING_FILE.exists():
        return []
    rows = []
    with open(TRACKING_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def calc_monthly_return(rows: List[dict]) -> List[dict]:
    results = []
    for i in range(1, len(rows)):
        prev_eq = float(rows[i - 1]["equity"])
        curr_eq = float(rows[i]["equity"])
        if prev_eq <= 0:
            continue
        monthly_ret = (curr_eq - prev_eq) / prev_eq
        results.append({
            "date":         rows[i]["date"],
            "equity":       curr_eq,
            "monthly_ret":  monthly_ret,
            "n_holdings":   rows[i]["n_holdings"],
        })
    return results


def print_report():
    rows = load_tracking()
    if len(rows) < 2:
        print("데이터 부족 — 최소 2회 리밸런싱 후 리포트가 생성됩니다.")
        return

    monthly = calc_monthly_return(rows)

    print("=" * 60)
    print(f"NAVIS ALPHA v1.0 페이퍼 트레이딩 성과 리포트")
    print(f"생성일: {date.today()}")
    print("=" * 60)

    # 월별 성과
    print(f"\n{'날짜':12} {'월수익':>9} {'백테기준':>9} {'갭':>7} {'판정':>5}")
    print("-" * 50)

    total_pass  = 0
    total_fail  = 0
    cum_ret     = 1.0
    bt_cum_ret  = 1.0

    for m in monthly:
        ret   = m["monthly_ret"]
        delta = ret - BACKTEST_MONTHLY_RETURN
        passed = delta >= PASS_THRESHOLD_DELTA
        total_pass += int(passed)
        total_fail += int(not passed)
        cum_ret    *= (1 + ret)
        bt_cum_ret *= (1 + BACKTEST_MONTHLY_RETURN)

        status = "✅" if passed else "❌"
        print(
            f"{m['date']:12} "
            f"{ret*100:>+8.2f}% "
            f"{BACKTEST_MONTHLY_RETURN*100:>+8.2f}% "
            f"{delta*100:>+6.2f}%p "
            f"{status}"
        )

    # 누적 성과
    n_months     = len(monthly)
    cagr         = cum_ret ** (12 / n_months) - 1 if n_months > 0 else 0
    bt_cagr      = bt_cum_ret ** (12 / n_months) - 1 if n_months > 0 else 0
    initial_eq   = float(rows[0]["equity"])
    current_eq   = float(rows[-1]["equity"])

    print("-" * 50)
    print(f"\n누적 성과 ({n_months}개월)")
    print(f"  현재 자산:           ${current_eq:>12,.0f}")
    print(f"  누적 수익률:         {(cum_ret-1)*100:>+.2f}%")
    print(f"  연환산 CAGR:         {cagr*100:>+.2f}%")
    print(f"  백테스트 기준 CAGR:  {bt_cagr*100:>+.2f}%  (OOS 12.16%)")
    print(f"\n  합격 월:  {total_pass}개월")
    print(f"  불합격 월: {total_fail}개월")

    # Phase A 판정
    print("\n" + "=" * 60)
    if n_months >= 6:
        pass_rate = total_pass / n_months
        if pass_rate >= 0.67:  # 6개월 중 4개월 이상 통과
            print("Phase A 판정: ✅ 통과 — 실전 진입 승인 조건 충족")
            print(f"  (합격률 {pass_rate*100:.0f}% ≥ 67%)")
        else:
            print("Phase A 판정: ❌ 미통과 — 추가 관찰 필요")
            print(f"  (합격률 {pass_rate*100:.0f}% < 67%)")
    else:
        remaining = 6 - n_months
        print(f"Phase A 진행 중 — {n_months}/6개월 완료 ({remaining}개월 남음)")

    print("=" * 60)


if __name__ == "__main__":
    print_report()
