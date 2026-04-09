"""Trading tools — execution_team 직접 통합 (HTTP 없음)."""
import json
import logging
from utils.tool import Tool

logger = logging.getLogger(__name__)

# AutoTradingBotV2가 초기화 후 등록하는 공유 execution engine
_execution_engine = None


def set_execution_engine(engine) -> None:
    """AutoTradingBotV2._init_execution_team() 완료 후 호출."""
    global _execution_engine
    _execution_engine = engine
    logger.info("Trading tools: execution engine 등록 완료")


def _engine_required(func):
    def wrapper(*args, **kwargs):
        if _execution_engine is None:
            return "오류: 거래 엔진이 아직 초기화되지 않았습니다. 잠시 후 다시 시도하세요."
        return func(*args, **kwargs)
    return wrapper


@_engine_required
def get_account(_: str) -> str:
    try:
        account = _execution_engine.get_account()
        if not account:
            return "계좌 정보를 가져올 수 없습니다."
        return json.dumps({
            "계좌_ID": account.account_id,
            "현금": f"${account.cash:,.2f}",
            "자산_총액": f"${account.equity:,.2f}",
            "포트폴리오_가치": f"${account.portfolio_value:,.2f}",
            "매수_가능_금액": f"${account.buying_power:,.2f}",
            "미실현_손익": f"${account.unrealized_pl:+,.2f}",
            "실현_손익": f"${account.realized_pl:+,.2f}",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"get_account 오류: {e}")
        return f"오류: {str(e)}"


@_engine_required
def get_positions(_: str) -> str:
    try:
        positions = _execution_engine.get_positions()
        if not positions:
            return "현재 보유 중인 포지션이 없습니다."
        result = []
        for p in positions:
            result.append({
                "종목": p.symbol,
                "수량": p.quantity,
                "평균_진입가": f"${p.avg_entry_price:,.2f}",
                "현재가": f"${p.current_price:,.2f}",
                "시장_가치": f"${p.market_value:,.2f}",
                "미실현_손익": f"${p.unrealized_pl:+,.2f}",
                "손익률": f"{p.unrealized_pl_percent:+.2f}%",
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"get_positions 오류: {e}")
        return f"오류: {str(e)}"


@_engine_required
def get_execution_stats(_: str) -> str:
    try:
        stats = _execution_engine.get_execution_stats()
        return json.dumps(stats, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"get_execution_stats 오류: {e}")
        return f"오류: {str(e)}"


@_engine_required
def execute_order(input_str: str) -> str:
    """
    매수/매도 주문 실행.
    형식: 'BUY AAPL 10' 또는 'SELL TSLA 5 | 이유'
    """
    try:
        from execution_team.core import OrderSignal, OrderAction, OrderType

        parts = input_str.strip().split("|", 1)
        order_parts = parts[0].strip().upper().split()
        reason = parts[1].strip() if len(parts) > 1 else "텔레그램 수동 지시"

        if len(order_parts) < 3:
            return "입력 형식 오류. 올바른 형식: BUY AAPL 10 또는 SELL TSLA 5"

        action_str, symbol, qty_str = order_parts[0], order_parts[1], order_parts[2]

        if action_str not in ("BUY", "SELL"):
            return "오류: 액션은 BUY 또는 SELL이어야 합니다."

        quantity = int(qty_str)
        if quantity <= 0:
            return "오류: 수량은 1 이상이어야 합니다."

        signal = OrderSignal(
            symbol=symbol,
            action=OrderAction[action_str],
            order_type=OrderType.MARKET,
            quantity=quantity,
            strategy_id="telegram_manual",
            reason=reason,
        )

        result = _execution_engine.execute_order(signal)

        if result.success:
            return json.dumps({
                "결과": "✅ 주문 성공",
                "주문_ID": result.order_id,
                "상태": result.status.value,
                "체결_수량": result.filled_quantity,
                "체결가": f"${result.filled_price:,.2f}" if result.filled_price else "처리 중",
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "결과": "❌ 주문 실패",
                "오류": result.error_message,
            }, ensure_ascii=False, indent=2)

    except ValueError:
        return "오류: 수량은 정수여야 합니다."
    except Exception as e:
        logger.error(f"execute_order 오류: {e}")
        return f"오류: {str(e)}"


@_engine_required
def cancel_order(order_id: str) -> str:
    order_id = order_id.strip()
    if not order_id:
        return "오류: 주문 ID를 입력하세요."
    try:
        success = _execution_engine.cancel_order(order_id)
        if success:
            return json.dumps({"결과": "✅ 취소 성공", "주문_ID": order_id}, ensure_ascii=False)
        return json.dumps({"결과": "❌ 취소 실패", "메시지": "이미 체결됐거나 없는 주문입니다."}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"cancel_order 오류: {e}")
        return f"오류: {str(e)}"


def create_trading_tools() -> list:
    return [
        Tool(
            name="get_account",
            func=get_account,
            description="계좌 잔고, 자산 총액, 매수 가능 금액, 미실현/실현 손익 조회. 입력값 무시.",
        ),
        Tool(
            name="get_positions",
            func=get_positions,
            description=(
                "현재 보유 중인 모든 포지션 조회. "
                "종목별 수량, 평균 진입가, 현재가, 미실현 손익, 손익률 포함. 입력값 무시."
            ),
        ),
        Tool(
            name="execute_order",
            func=execute_order,
            description=(
                "매수 또는 매도 주문 실행 (시장가). "
                "형식: 'BUY 종목코드 수량' 또는 'SELL 종목코드 수량'. "
                "예: 'BUY AAPL 10', 'SELL TSLA 5 | 익절'. "
                "반드시 사용자에게 주문 내용을 확인받은 후 호출할 것."
            ),
        ),
        Tool(
            name="cancel_order",
            func=cancel_order,
            description="주문 취소. 입력: 취소할 주문 ID 문자열.",
        ),
        Tool(
            name="get_execution_stats",
            func=get_execution_stats,
            description="주문 실행 통계 조회 (총 주문 수, 성공률 등). 입력값 무시.",
        ),
    ]
