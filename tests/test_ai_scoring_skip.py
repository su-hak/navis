"""
포지션 풀일 때 AI 스코어링 생략 로직 테스트

변경 위치: auto_trading_bot_v2.py _stage1_market_scan()
검증 내용:
  - 포지션 < max_positions  → _apply_ai_scoring 호출됨
  - 포지션 >= max_positions → _apply_ai_scoring 호출 안 됨
  - 포지션 풀이어도 워치리스트 갱신은 실행됨
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_bot(position_count: int, max_positions: int = 5):
    """AutoTradingBotV2를 __init__ 없이 생성하여 필요한 속성만 주입"""
    from auto_trading_bot_v2 import AutoTradingBotV2

    bot = object.__new__(AutoTradingBotV2)

    bot.is_running = True
    bot.max_positions = max_positions
    bot.market_scan_interval = 999999
    bot.trade_cooldown_minutes = 120
    bot._recently_sold = {}
    bot.order_manager = None

    # 포지션 mock
    fake_positions = [MagicMock(symbol=f"SYM{i}") for i in range(position_count)]
    engine = MagicMock()
    engine.get_positions.return_value = fake_positions
    bot.execution_engine = engine

    # 워치리스트 생성기 mock
    fake_watchlist = [
        {"symbol": "AAPL", "score": 10, "volume_ratio": 3.5, "reason": "갭 상승"},
        {"symbol": "TSLA", "score": 8,  "volume_ratio": 3.0, "reason": "거래량 급증"},
    ]
    wg = MagicMock()
    wg.generate_watchlist = AsyncMock(return_value=fake_watchlist)
    bot.watchlist_generator = wg

    # 고주기 모니터 mock
    monitor = MagicMock()
    monitor.is_running = False
    monitor.start = AsyncMock()
    bot.high_freq_monitor = monitor

    return bot, fake_watchlist


async def _run_one_scan(bot):
    """_stage1_market_scan을 1회만 실행하고 종료 (sleep 진입 시 루프 탈출)"""
    async def fake_sleep(_seconds):
        bot.is_running = False

    with patch("auto_trading_bot_v2.asyncio.sleep", side_effect=fake_sleep), \
         patch.object(bot, "_is_market_hours", return_value=True), \
         patch.object(bot, "_is_extended_hours", return_value=False):

        # 주말 체크용 datetime.now mock: 평일(월요일) ET 반환
        fake_et_now = MagicMock()
        fake_et_now.weekday.return_value = 0  # 월요일
        fake_et_now.strftime.return_value = "2026-04-16 10:00:00"

        with patch("auto_trading_bot_v2.datetime") as mock_dt:
            mock_dt.now.return_value = fake_et_now
            await bot._stage1_market_scan()


# ─────────────────────────────────────────
# 테스트 1: 포지션 여유 있음 → AI 스코어링 실행
# ─────────────────────────────────────────
async def test_ai_scoring_called_when_positions_available():
    bot, watchlist = _make_bot(position_count=3, max_positions=5)

    with patch.object(bot, "_apply_ai_scoring", new_callable=AsyncMock, return_value=watchlist) as mock_ai:
        await _run_one_scan(bot)

    assert mock_ai.called, "포지션 여유가 있을 때 _apply_ai_scoring이 호출되어야 합니다"
    print("PASS  포지션 3/5 → AI 스코어링 호출됨")


# ─────────────────────────────────────────
# 테스트 2: 포지션 풀 → AI 스코어링 생략
# ─────────────────────────────────────────
async def test_ai_scoring_skipped_when_positions_full():
    bot, watchlist = _make_bot(position_count=5, max_positions=5)

    with patch.object(bot, "_apply_ai_scoring", new_callable=AsyncMock, return_value=watchlist) as mock_ai:
        await _run_one_scan(bot)

    assert not mock_ai.called, "포지션이 풀일 때 _apply_ai_scoring이 호출되면 안 됩니다"
    print("PASS  포지션 5/5 → AI 스코어링 생략됨")


# ─────────────────────────────────────────
# 테스트 3: 포지션 풀이어도 워치리스트는 갱신됨
# ─────────────────────────────────────────
async def test_watchlist_still_updated_when_full():
    bot, watchlist = _make_bot(position_count=5, max_positions=5)

    with patch.object(bot, "_apply_ai_scoring", new_callable=AsyncMock, return_value=watchlist):
        await _run_one_scan(bot)

    bot.high_freq_monitor.set_watchlist.assert_called_once()
    print("PASS  포지션 5/5 → 워치리스트 갱신은 정상 실행됨")


# ─────────────────────────────────────────
# 테스트 4: 경계값 - 4/5 포지션도 AI 스코어링 실행
# ─────────────────────────────────────────
async def test_ai_scoring_called_at_one_below_max():
    bot, watchlist = _make_bot(position_count=4, max_positions=5)

    with patch.object(bot, "_apply_ai_scoring", new_callable=AsyncMock, return_value=watchlist) as mock_ai:
        await _run_one_scan(bot)

    assert mock_ai.called, "포지션 4/5일 때도 _apply_ai_scoring이 호출되어야 합니다"
    print("PASS  포지션 4/5 → AI 스코어링 호출됨 (경계값)")


if __name__ == "__main__":
    tests = [
        test_ai_scoring_called_when_positions_available,
        test_ai_scoring_skipped_when_positions_full,
        test_watchlist_still_updated_when_full,
        test_ai_scoring_called_at_one_below_max,
    ]

    results = []
    for test_fn in tests:
        try:
            asyncio.run(test_fn())
            results.append(("PASS", test_fn.__name__))
        except AssertionError as e:
            results.append(("FAIL", f"{test_fn.__name__}: {e}"))
            print(f"FAIL  {test_fn.__name__}: {e}")
        except Exception as e:
            results.append(("ERROR", f"{test_fn.__name__}: {e}"))
            print(f"ERROR {test_fn.__name__}: {e}")

    print("\n" + "=" * 50)
    passed = sum(1 for r in results if r[0] == "PASS")
    print(f"결과: {passed}/{len(results)} 통과")
    if passed < len(results):
        sys.exit(1)
