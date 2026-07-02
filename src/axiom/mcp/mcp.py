import os
import traceback
import contextlib
from io import StringIO
from typing import Any
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

from axiom.utils.logger import logger

load_dotenv()


mcp = FastMCP(
    name="Axiom MCP Server",
    instructions=(
        "You have access to one tool: "
        "web_search for finding current information on the web, "
        "Use web_search when you need recent or real-time information. "
    ),
)

_tavily_client: TavilyClient | None = None

def _get_tavily_client() -> TavilyClient:
    """Returns the Tavily client, creating it on the first call."""
    global _tavily_client
    if _tavily_client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError(
                "TAVILY_API_KEY not found in enviroment."
                "Add it to your .env file."
                "Get a free key at https://tavily.com"
            )
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


@mcp.tool()
def web_search(query: str) -> str:
    """
    Search the web for current information using Tavily.

    Use this when:
    - The user asks about recent events or news
    - You need facts you are not confident about
    - The topic changes over time (prices, scores, weather)

    Args:
        query: The search query. Be specific for better results.

    Returns:
        A formatted summary with a direct answer and source URLs.
    """
    logger.info(f"[MCP:web_search] Query: '{query}'")

    try:
        client = _get_tavily_client()
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )

        output = []

        if response.get("answer"):
            output.append(f"Answer: {response['answer']}\n")

        output.append("Sources:")
        for i, result in enumerate(response.get("results", []), 1):
            preview = result.get("content", "")[:300]
            output.append(
                f"{i}. {result['title']}\n"
                f"   URL: {result['url']}\n"
                f"   {preview}..."
            )

        result_count = len(response.get("results", []))
        logger.info(f"[MCP:web_search] Returned {result_count} results.")
        return "\n".join(output)

    except Exception as e:
        logger.error(f"[MCP:web_search] Failed: {e}")
        return f"Web search failed: {str(e)}"