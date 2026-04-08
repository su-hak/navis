"""Simple tool class for AI agent."""
from typing import Callable, Optional


class Tool:
    """A simple tool that the agent can use."""

    def __init__(
        self,
        name: str,
        func: Callable[[str], str],
        description: str,
    ):
        """
        Initialize a tool.

        Args:
            name: The name of the tool
            func: The function to execute (takes string input, returns string output)
            description: Description of what the tool does and when to use it
        """
        self.name = name
        self.func = func
        self.description = description

    def run(self, input_str: str) -> str:
        """
        Run the tool with the given input.

        Args:
            input_str: Input string for the tool

        Returns:
            Tool output as a string
        """
        return self.func(input_str)

    def __repr__(self) -> str:
        return f"Tool(name='{self.name}')"
