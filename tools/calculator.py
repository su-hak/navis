"""Calculator tool for mathematical operations."""
from utils.tool import Tool


def calculate(expression: str) -> str:
    """
    Safely evaluate a mathematical expression.

    Args:
        expression: Mathematical expression as a string

    Returns:
        Result of the calculation
    """
    try:
        # Only allow safe mathematical operations
        allowed_chars = set("0123456789+-*/().% ")
        if not all(c in allowed_chars for c in expression):
            return "Error: Invalid characters in expression. Only numbers and operators (+, -, *, /, %, parentheses) are allowed."

        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error calculating expression: {str(e)}"


def create_calculator_tool() -> Tool:
    """
    Create a calculator tool.

    Returns:
        LangChain Tool for calculations
    """
    return Tool(
        name="calculator",
        description=(
            "Useful for performing mathematical calculations. "
            "Input should be a mathematical expression like '2 + 2' or '10 * 5 + 3'. "
            "Supports +, -, *, /, %, and parentheses."
        ),
        func=calculate,
    )
