"""
어제 거래 종목에 대해 2%, 4%, 6% 익절 가능 여부 분석
사용법: python -m tools.analyze_tp_levels
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

# Windows venv에서는 C:/navis/.env, WSL에서는 /mnt/c/navis/.env
load_dotenv("C:/navis/.env")
load_dotenv("/mnt/c/navis/.env")

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
ALPACA_DATA_URL   = "https://data.alpaca.markets"

ET = ZoneInfo("America/New_York")

HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

TP_LEVELS = [0.02, 0.04, 0.06, 0.10, 0.12]   # 분석할 익절 수준


def get_last_trading_day_et() -> str:
    """마지막 거래일 반환 (ET 16:00 이후면 오늘, 이전이면 전 거래일)"""
    now_et = datetime.now(ET)
    market_closed = now_et.hour >= 16

    if market_closed:
        # 오늘 장이 닫혔으면 오늘이 마지막 거래일
        candidate = now_et
    else:
        candidate = now_et - timedelta(days=1)

    # 주말 건너뜀 (토=5, 일=6 → 금요일로)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)

    return candidate.strftime("%Y-%m-%d")


def fetch_fills(date_str: str) -> list:
    """해당 날짜의 FILL 체결 내역 조회"""
    # Alpaca activities: transaction_time은 UTC ISO 형식
    # after = 당일 UTC 자정, 클라이언트에서 날짜 필터링
    after_ts = f"{date_str}T00:00:00Z"
    with httpx.Client(timeout=10) as client:
        resp = client.get(
            f"{ALPACA_BASE_URL}/v2/account/activities/FILL",
            headers=HEADERS,
            params={"after": after_ts, "direction": "asc", "page_size": 100},
        )
        resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    # ET 기준 당일(09:30~16:00) = UTC 13:30~20:00 → date_str 날짜의 UTC 데이터 필터
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return [f for f in data if f.get("transaction_time", "") < f"{next_day}T00:00:00Z"]


def fetch_bars(symbol: str, date_str: str) -> list:
    """해당 날짜의 1분봉 조회"""
    start = f"{date_str}T09:30:00-04:00"
    end   = f"{date_str}T16:00:00-04:00"
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            f"{ALPACA_DATA_URL}/v2/stocks/{symbol}/bars",
            headers=HEADERS,
            params={"timeframe": "1Min", "start": start, "end": end,
                    "limit": 400, "feed": "iex"},
        )
        resp.raise_for_status()
    return resp.json().get("bars", [])


def _weighted_avg(fills: list) -> tuple[float, str, str]:
    """partial fill 목록에서 가중평균 체결가, 최초/최종 시각 반환"""
    total_qty = sum(int(f["qty"]) for f in fills)
    avg_price = sum(float(f["price"]) * int(f["qty"]) for f in fills) / total_qty
    times = sorted(f["transaction_time"] for f in fills)
    return avg_price, times[0], times[-1]


def analyze_trade(buy_fills: list, sell_fills: list, bars: list) -> dict:
    """매수~매도 구간에서 각 익절 수준 도달 여부 확인"""
    buy_price, buy_time_start, buy_time_end = _weighted_avg(buy_fills)
    sell_price, sell_time_start, sell_time_end = _weighted_avg(sell_fills)
    symbol = buy_fills[0]["symbol"]

    actual_pnl_pct = (sell_price - buy_price) / buy_price * 100

    # 매수 체결 완료 ~ 매도 체결 완료 구간의 봉만 필터
    window = [
        b for b in bars
        if buy_time_end <= b["t"] <= sell_time_end
    ]

    result = {
        "symbol":         symbol,
        "buy_time":       buy_time_end[:16],
        "sell_time":      sell_time_end[:16],
        "buy_price":      buy_price,
        "sell_price":     sell_price,
        "actual_pnl_pct": actual_pnl_pct,
        "outcome":        "WIN" if actual_pnl_pct > 0 else "LOSS",
    }

    for tp in TP_LEVELS:
        target = buy_price * (1 + tp)
        reached = any(float(b["h"]) >= target for b in window)
        result[f"tp_{int(tp*100)}pct"] = reached

    return result


def main():
    date_str = get_last_trading_day_et()
    print(f"\n{'='*60}")
    print(f"  분석 날짜: {date_str} (ET 기준)")
    print(f"{'='*60}\n")

    fills = fetch_fills(date_str)
    if not fills:
        print("체결 내역 없음")
        sys.exit(0)

    # order_id 기준으로 partial fill 그룹핑
    from collections import defaultdict
    order_fills: dict = defaultdict(list)
    for f in fills:
        order_fills[f["order_id"]].append(f)

    # symbol별로 매수/매도 주문 분류 (order 단위)
    buy_orders_by_sym:  dict = defaultdict(list)
    sell_orders_by_sym: dict = defaultdict(list)
    for order_id, order_list in order_fills.items():
        sym  = order_list[0]["symbol"]
        side = order_list[0]["side"]
        # 마지막 체결 시각 기준으로 정렬
        order_list.sort(key=lambda x: x["transaction_time"])
        if side == "buy":
            buy_orders_by_sym[sym].append(order_list)
        elif side == "sell":
            sell_orders_by_sym[sym].append(order_list)

    results = []
    symbols_needed = set()
    pairs = []

    for symbol, buy_list in buy_orders_by_sym.items():
        sell_list = sell_orders_by_sym.get(symbol, [])
        # FIFO 매칭: 매수 주문 순 × 매도 주문 순
        for buy_order, sell_order in zip(buy_list, sell_list):
            pairs.append((buy_order, sell_order))
            symbols_needed.add(symbol)

    if not pairs:
        print("매수-매도 쌍을 찾을 수 없음 (당일 미청산 포지션일 수 있음)")
        sys.exit(0)

    # 분봉 데이터 수집
    bars_cache = {}
    print(f"분봉 데이터 수집 중: {', '.join(symbols_needed)}")
    for sym in symbols_needed:
        try:
            bars_cache[sym] = fetch_bars(sym, date_str)
            print(f"  {sym}: {len(bars_cache[sym])}봉")
        except Exception as e:
            print(f"  {sym}: 분봉 조회 실패 ({e})")
            bars_cache[sym] = []

    # 분석
    for buy_order, sell_order in pairs:
        sym = buy_order[0]["symbol"]
        r = analyze_trade(buy_order, sell_order, bars_cache.get(sym, []))
        results.append(r)

    # 결과 출력
    lvl_ints = [int(tp * 100) for tp in TP_LEVELS]
    header_tps = "  ".join(f"TP{l:2d}%" for l in lvl_ints)
    print(f"\n{'─'*70}")
    print(f"{'종목':<6} {'매수가':>8} {'매도가':>8} {'실제PnL':>8}  {'결과':<5}  {header_tps}")
    print(f"{'─'*70}")

    tp_counts = {l: 0 for l in lvl_ints}
    win_count = loss_count = 0

    for r in results:
        tp_flags = "  ".join("O" if r[f"tp_{l}pct"] else "X" for l in lvl_ints)
        outcome = r["outcome"]
        print(
            f"{r['symbol']:<6} "
            f"${r['buy_price']:>7.2f} "
            f"${r['sell_price']:>7.2f} "
            f"{r['actual_pnl_pct']:>+7.2f}%  "
            f"{outcome:<5}  {tp_flags}"
        )
        for l in lvl_ints:
            if r[f"tp_{l}pct"]:
                tp_counts[l] += 1
        if outcome == "WIN": win_count += 1
        else: loss_count += 1

    total = len(results)
    print(f"\n{'─'*70}")
    print(f"총 {total}건  (실제 승: {win_count} / 패: {loss_count})")
    print(f"\n익절 수준별 도달 가능 건수:")
    for lvl in lvl_ints:
        cnt = tp_counts[lvl]
        pct = cnt / total * 100 if total else 0
        bar = "#" * cnt + "." * (total - cnt)
        print(f"  TP {lvl:2d}%:  {cnt:2d}/{total}  ({pct:.0f}%)  [{bar}]")

    print(f"\n※ 분봉 데이터 없는 종목은 도달 여부가 X로 표시될 수 있음")
    print(f"{'='*60}\n")

    # ── trading_learnings.md 자동 저장 ────────────────────────
    save_to_learnings(date_str, results, tp_counts, win_count, loss_count, total)


def save_to_learnings(
    date_str: str,
    results: list,
    tp_counts: dict,
    win_count: int,
    loss_count: int,
    total: int,
):
    """분석 결과를 .claude/trading_learnings.md에 누적 저장"""
    # 파일 경로: 스크립트 기준 상위 디렉터리의 .claude/trading_learnings.md
    import pathlib
    base = pathlib.Path(__file__).parent.parent
    learnings_path = base / ".claude" / "trading_learnings.md"

    if not learnings_path.exists():
        return  # 파일 없으면 저장 생략

    # 이미 해당 날짜 항목이 있으면 덮어쓰지 않음
    existing = learnings_path.read_text(encoding="utf-8")
    section_header = f"## [{date_str}]"
    if section_header in existing:
        print(f"[학습데이터] {date_str} 항목이 이미 존재합니다 - 저장 생략")
        return

    lvl_ints = [int(tp * 100) for tp in TP_LEVELS]

    # 종목별 결과 테이블
    tp_header = " | ".join(f"TP{l}%" for l in lvl_ints)
    tp_sep    = " | ".join(":---:" for _ in lvl_ints)
    rows = []
    for r in results:
        tp_vals = " | ".join("O" if r.get(f"tp_{l}pct") else "X" for l in lvl_ints)
        rows.append(
            f"| {r['symbol']:<6} | ${r['buy_price']:>7.2f} | ${r['sell_price']:>7.2f} "
            f"| {r['actual_pnl_pct']:>+6.2f}% | {r['outcome']:<4} | {tp_vals} |"
        )

    tp_summary_rows = []
    for lvl in lvl_ints:
        cnt = tp_counts.get(lvl, 0)
        pct = cnt / total * 100 if total else 0
        tp_summary_rows.append(f"| TP {lvl:2d}% | {cnt}/{total} | {pct:.0f}% |")

    entry = f"""
---

{section_header} 익절 수준별 도달 가능성 분석

**실제 결과**: 총 {total}건 / 승 {win_count} / 패 {loss_count}

| 종목 | 매수가 | 매도가 | 실제 손익 | 결과 | {tp_header} |
|:---|---:|---:|---:|:---:| {tp_sep} |
{chr(10).join(rows)}

| 익절 기준 | 도달 가능 | 이론 승률 |
|:---:|:---:|:---:|
{chr(10).join(tp_summary_rows)}

"""

    with open(learnings_path, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"[학습데이터] {learnings_path} 저장 완료")


if __name__ == "__main__":
    main()
