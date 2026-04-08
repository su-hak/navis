"""Main entry point for the Navis AI Agent."""
import sys
from typing import List
from utils.tool import Tool

from config.settings import settings
from utils.logger import logger
from agents.base_agent import BaseAgent
from tools.web_search import create_web_search_tool
from tools.calculator import create_calculator_tool


def create_agent_tools() -> List[Tool]:
    """
    Create and return all available tools for the agent.

    Returns:
        List of tools
    """
    tools = [
        create_web_search_tool(),
        create_calculator_tool(),
    ]

    logger.info(f"Created {len(tools)} tools: {[t.name for t in tools]}")
    return tools


def interactive_mode():
    """Run the agent in interactive mode."""
    print(f"\n{'='*60}")
    print(f"  {settings.agent_name}")
    print(f"  {settings.agent_description}")
    print(f"{'='*60}\n")
    print("Type 'quit' or 'exit' to end the conversation.\n")

    # Create agent
    tools = create_agent_tools()
    agent = BaseAgent(tools=tools, verbose=True)

    chat_history = []

    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit']:
                print("\nGoodbye!")
                break

            # Get agent response
            print(f"\n{settings.agent_name}: ", end="", flush=True)
            response = agent.run(user_input, chat_history=chat_history)
            print(response)

            # Update chat history
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": response})

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error in interactive mode: {str(e)}")
            print(f"\nError: {str(e)}")


def single_query_mode(query: str):
    """
    Run the agent with a single query.

    Args:
        query: The query to process
    """
    tools = create_agent_tools()
    agent = BaseAgent(tools=tools, verbose=False)

    response = agent.run(query)
    print(response)


def main():
    """Main function."""
    # Check if API key is set
    if not settings.anthropic_api_key:
        print("Error: ANTHROPIC_API_KEY not found in environment variables.")
        print("Please create a .env file with your API key.")
        print("Example: cp .env.example .env")
        sys.exit(1)

    # Check command line arguments
    if len(sys.argv) > 1:
        # Single query mode
        query = " ".join(sys.argv[1:])
        single_query_mode(query)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
