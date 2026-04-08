"""Base agent implementation using Claude API directly."""
from typing import List, Optional, Dict, Any
from anthropic import Anthropic
from utils.tool import Tool
from config.settings import settings
from utils.logger import logger


class BaseAgent:
    """Base AI agent using Claude API with tool calling."""

    def __init__(
        self,
        tools: List[Tool],
        system_prompt: Optional[str] = None,
        verbose: bool = True
    ):
        """
        Initialize the agent.

        Args:
            tools: List of tools available to the agent
            system_prompt: Custom system prompt (optional)
            verbose: Whether to print verbose output
        """
        self.tools = tools
        self.verbose = verbose
        self.system_prompt = system_prompt or self._default_system_prompt()

        # Initialize Claude client
        self.client = Anthropic(api_key=settings.anthropic_api_key)

        # Convert LangChain tools to Anthropic tool format
        self.anthropic_tools = self._convert_tools_to_anthropic_format()

        logger.info(f"Agent initialized with {len(tools)} tools")

    def _convert_tools_to_anthropic_format(self) -> List[Dict[str, Any]]:
        """Convert LangChain tools to Anthropic tool format."""
        anthropic_tools = []
        for tool in self.tools:
            anthropic_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Input for the tool"
                        }
                    },
                    "required": ["input"]
                }
            })
        return anthropic_tools

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        """Execute a tool by name."""
        for tool in self.tools:
            if tool.name == tool_name:
                try:
                    result = tool.func(tool_input)
                    return str(result)
                except Exception as e:
                    return f"Error executing tool: {str(e)}"
        return f"Tool {tool_name} not found"

    def _default_system_prompt(self) -> str:
        """Get the default system prompt."""
        return f"""{settings.agent_description}

You are a helpful AI assistant with access to various tools. Use the tools when needed to answer questions or complete tasks.

When using tools:
1. Think step by step about what information you need
2. Use the appropriate tool to get that information
3. Provide clear and concise answers based on the results

Always be helpful, accurate, and honest. If you're not sure about something, say so."""

    def run(self, query: str, chat_history: Optional[List] = None) -> str:
        """
        Run the agent with a query.

        Args:
            query: User's question or task
            chat_history: Optional chat history for context

        Returns:
            Agent's response
        """
        try:
            logger.info(f"Processing query: {query}")

            # Build messages from chat history
            messages = []
            if chat_history:
                for msg in chat_history:
                    role = "user" if msg["role"] == "user" else "assistant"
                    messages.append({
                        "role": role,
                        "content": msg["content"]
                    })

            # Add current query
            messages.append({
                "role": "user",
                "content": query
            })

            # Agent loop with tool calling
            max_iterations = 10
            for iteration in range(max_iterations):
                # Call Claude API
                response = self.client.messages.create(
                    model=settings.model_name,
                    max_tokens=settings.max_tokens,
                    temperature=settings.temperature,
                    system=self.system_prompt,
                    tools=self.anthropic_tools if self.tools else None,
                    messages=messages
                )

                if self.verbose:
                    logger.debug(f"Iteration {iteration + 1}, stop_reason: {response.stop_reason}")

                # Check if we need to execute tools
                if response.stop_reason == "tool_use":
                    # Add assistant's response to messages
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # Execute tools and collect results
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input.get("input", "")

                            if self.verbose:
                                logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

                            # Execute the tool
                            tool_result = self._execute_tool(tool_name, tool_input)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_result
                            })

                    # Add tool results to messages
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Continue the loop to get the next response
                    continue

                elif response.stop_reason == "end_turn":
                    # Extract the final response
                    final_response = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_response += block.text

                    logger.info(f"Response generated: {final_response[:100]}...")
                    return final_response

                else:
                    # Unexpected stop reason
                    logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                    return "I apologize, but I couldn't generate a complete response."

            # Max iterations reached
            logger.warning("Max iterations reached")
            return "I apologize, but I reached the maximum number of steps without completing the task."

        except Exception as e:
            logger.error(f"Error running agent: {str(e)}")
            return f"An error occurred: {str(e)}"

    def stream(self, query: str, chat_history: Optional[List] = None):
        """
        Stream the agent's response.
        Note: Currently returns the full response as streaming with tool use is complex.

        Args:
            query: User's question or task
            chat_history: Optional chat history for context

        Yields:
            Chunks of the response
        """
        try:
            logger.info(f"Streaming query: {query}")

            # For now, just return the full response
            # Proper streaming with tool use requires more complex implementation
            response = self.run(query, chat_history)
            yield {"output": response}

        except Exception as e:
            logger.error(f"Error streaming response: {str(e)}")
            yield {"error": str(e)}
