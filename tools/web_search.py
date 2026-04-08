"""Web search tool using DuckDuckGo."""
from duckduckgo_search import DDGS
from utils.tool import Tool


def search_web(query: str) -> str:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query string

    Returns:
        Search results as a formatted string
    """
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=5)

        if not results:
            return "No results found."

        # Format results
        formatted_results = []
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            body = result.get('body', 'No description')
            url = result.get('href', '')
            formatted_results.append(f"{i}. {title}\n{body}\nURL: {url}\n")

        return "\n".join(formatted_results)

    except Exception as e:
        return f"Error performing web search: {str(e)}"


def create_web_search_tool() -> Tool:
    """
    Create a web search tool using DuckDuckGo.

    Returns:
        Tool for web searching
    """
    return Tool(
        name="web_search",
        description=(
            "Useful for searching the web for current information, "
            "news, facts, or any information not in your knowledge base. "
            "Input should be a search query string."
        ),
        func=search_web,
    )
