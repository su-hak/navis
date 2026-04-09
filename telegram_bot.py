"""Telegram bot interface for the AI agent."""
import sys
from typing import Dict, List
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config.settings import settings
from utils.logger import logger
from agents.base_agent import BaseAgent
from tools.web_search import create_web_search_tool
from tools.calculator import create_calculator_tool
from tools.trading_tool import create_trading_tools


# Store chat histories for each user
user_chat_histories: Dict[int, List] = {}


def is_user_authorized(user_id: int) -> bool:
    """Check if a user is authorized to use the bot."""
    # If no allowed users are configured, allow everyone
    if not settings.allowed_user_ids:
        return True
    # Otherwise, check if user is in the allowed list
    return user_id in settings.allowed_user_ids


TRADING_SYSTEM_PROMPT = """당신은 Navis 자동매매 시스템의 AI 트레이딩 어시스턴트입니다.

사용 가능한 도구:
- get_account: 계좌 잔고, 자산, 매수 가능 금액 조회
- get_positions: 현재 보유 포지션 조회
- execute_order: 매수/매도 주문 실행 (BUY/SELL)
- cancel_order: 주문 취소
- get_execution_stats: 주문 통계 조회
- web_search: 시장 뉴스 및 종목 정보 검색
- calculator: 수익률, 투자금 계산

중요 규칙:
1. execute_order를 호출하기 전에 반드시 사용자에게 주문 내용을 확인받으세요.
   예: "AAPL 10주 시장가 매수 주문을 실행할까요?"
2. 매도 시 보유 수량을 먼저 get_positions로 확인하세요.
3. 숫자는 항상 한국어 형식으로 표시하세요. (예: $1,234.56, +2.5%)
4. 주문 결과는 성공/실패 여부와 체결가를 명확히 알려주세요.
5. 확실하지 않은 정보는 web_search로 확인한 후 답변하세요."""


def create_agent_tools():
    """Create and return all available tools for the agent."""
    tools = [
        create_web_search_tool(),
        create_calculator_tool(),
        *create_trading_tools(),
    ]
    return tools


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # Check if user is authorized
    if not is_user_authorized(user_id):
        await update.message.reply_text(
            "❌ 죄송합니다. 이 봇을 사용할 권한이 없습니다.\n"
            "관리자에게 문의하세요."
        )
        logger.warning(f"Unauthorized access attempt by user {user_id} ({user_name})")
        return

    # Initialize chat history for new user
    if user_id not in user_chat_histories:
        user_chat_histories[user_id] = []

    welcome_message = f"""안녕하세요, {user_name}님! 👋

저는 {settings.agent_name}입니다.
{settings.agent_description}

저는 다음과 같은 도구를 사용할 수 있습니다:
• 웹 검색 (최신 정보 찾기)
• 계산기 (수학 계산)

무엇을 도와드릴까요?

명령어:
/start - 봇 시작
/clear - 대화 기록 초기화
/help - 도움말"""

    await update.message.reply_text(welcome_message)
    logger.info(f"User {user_id} ({user_name}) started the bot")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    user_id = update.effective_user.id

    # Check if user is authorized
    if not is_user_authorized(user_id):
        await update.message.reply_text(
            "❌ 죄송합니다. 이 봇을 사용할 권한이 없습니다.\n"
            "관리자에게 문의하세요."
        )
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        return

    help_message = """📚 도움말

저는 Claude 기반 AI 에이전트입니다. 다양한 질문에 답변하고 작업을 수행할 수 있습니다.

사용 가능한 기능:
• 웹에서 최신 정보 검색
• 수학 계산 수행
• 일반적인 질문 답변
• 복잡한 작업을 단계별로 수행

명령어:
/start - 봇 시작 및 소개
/clear - 대화 기록 초기화
/help - 이 도움말 표시

예시 질문:
• "2024년 파리 올림픽은 언제 열렸어?"
• "123 * 456을 계산해줘"
• "파이썬으로 리스트를 정렬하는 방법 알려줘"

그냥 질문을 입력하시면 됩니다!"""

    await update.message.reply_text(help_message)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /clear command to clear chat history."""
    user_id = update.effective_user.id

    # Check if user is authorized
    if not is_user_authorized(user_id):
        await update.message.reply_text(
            "❌ 죄송합니다. 이 봇을 사용할 권한이 없습니다.\n"
            "관리자에게 문의하세요."
        )
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        return

    if user_id in user_chat_histories:
        user_chat_histories[user_id] = []

    await update.message.reply_text(
        "✅ 대화 기록이 초기화되었습니다. 새로운 대화를 시작합니다!"
    )
    logger.info(f"User {user_id} cleared their chat history")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages from users."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_message = update.message.text

    # Check if user is authorized
    if not is_user_authorized(user_id):
        await update.message.reply_text(
            "❌ 죄송합니다. 이 봇을 사용할 권한이 없습니다.\n"
            "관리자에게 문의하세요."
        )
        logger.warning(f"Unauthorized message from user {user_id} ({user_name}): {user_message}")
        return

    # Initialize chat history if needed
    if user_id not in user_chat_histories:
        user_chat_histories[user_id] = []

    logger.info(f"User {user_id} ({user_name}): {user_message}")

    # Send typing indicator
    await update.message.chat.send_action("typing")

    try:
        # Create agent with tools
        tools = create_agent_tools()
        agent = BaseAgent(tools=tools, system_prompt=TRADING_SYSTEM_PROMPT, verbose=False)

        # Get response from agent
        response = agent.run(
            query=user_message,
            chat_history=user_chat_histories[user_id]
        )

        # Update chat history
        user_chat_histories[user_id].append({
            "role": "user",
            "content": user_message
        })
        user_chat_histories[user_id].append({
            "role": "assistant",
            "content": response
        })

        # Keep only last 10 exchanges (20 messages) to manage memory
        if len(user_chat_histories[user_id]) > 20:
            user_chat_histories[user_id] = user_chat_histories[user_id][-20:]

        # Send response
        await update.message.reply_text(response)
        logger.info(f"Sent response to user {user_id}: {response[:100]}...")

    except Exception as e:
        error_message = f"죄송합니다. 오류가 발생했습니다: {str(e)}"
        await update.message.reply_text(error_message)
        logger.error(f"Error handling message from user {user_id}: {str(e)}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the Telegram bot."""
    # Check if bot token is set
    if not settings.telegram_bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        print("Please set your Telegram bot token in the .env file.")
        sys.exit(1)

    # Check if Anthropic API key is set
    if not settings.anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY not found in environment variables.")
        print("Please set your Anthropic API key in the .env file.")
        sys.exit(1)

    logger.info("Starting Telegram bot...")

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info(f"Bot started successfully as {settings.agent_name}")
    print(f"\n{'='*60}")
    print(f"  {settings.agent_name} Telegram Bot")
    print(f"  Bot is running... Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    # stop_signals=None: 서브 스레드에서 실행 시 signal handler 등록 시도 방지
    application.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)


if __name__ == "__main__":
    main()
