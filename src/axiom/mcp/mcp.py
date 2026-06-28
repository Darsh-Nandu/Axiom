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
        "You have access to two tools: "
        "web_search for finding current information on the web, "
        "and run_code for executing Python code in a secure sandbox. "
        "Use web_search when you need recent or real-time information. "
        "Use run_code when the user wants to run or test Python code."
    ),
)