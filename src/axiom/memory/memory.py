from typing import Optional
 
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    BaseMessage,
)
 
from axiom.database import db
from axiom.utils.logger import logger
from axiom.configs.config import config

WINDOW_SIZE: int = config.get("memory", {}).get("window_size", 20)

def load_history(session_id: str) -> list[BaseMessage]:
    """
    Fetches all messages for a session from the DB and converts
    them into LangChain message objects.
 
    agent_call → HumanMessage  (prefixed so LLM understands the context)
    agent_result → AIMessage   (prefixed so LLM understands the context)
    tool_call → AIMessage with tool_calls field populated
    tool_result → ToolMessage
    """
    rows = db.get_messages(session_id)
    messages: list[BaseMessage] = []
 
    for row in rows:
        role = row["role"]
        content = row["content"]
 
        if role == "human":
            messages.append(HumanMessage(content=content))
 
        elif role == "ai":
            messages.append(AIMessage(content=content))
 
        elif role == "tool_call":
            # AIMessage with tool_calls tells the LLM it previously
            # decided to call a tool. tool_call_id links it to its result.
            messages.append(AIMessage(
                content=content,
                tool_calls=[{
                    "id": row["tool_call_id"],
                    "name": row["tool_name"],
                    "args": {},   # args are embedded in content; kept empty here
                }]
            ))
 
        elif role == "tool_result":
            messages.append(ToolMessage(
                content=content,
                tool_call_id=row["tool_call_id"],
            ))
 
        elif role == "agent_call":
            # We prefix so the LLM remembers it delegated a sub-task
            messages.append(HumanMessage(
                content=f"[Delegated to agent '{row['agent_name']}']: {content}"
            ))
 
        elif role == "agent_result":
            messages.append(AIMessage(
                content=f"[Agent '{row['agent_name']}' returned]: {content}"
            ))
 
        else:
            logger.warning(f"Unknown role '{role}' in session {session_id}. Skipping.")
 
    return messages


def get_history_for_llm(session_id: str) -> list[BaseMessage]:
    """
    Returns the conversation history trimmed to the last WINDOW_SIZE messages.
    This is what you pass directly into the LLM call every time.
 
    Trimming prevents hitting the LLM's context window limit on long conversations.
    Full history is always preserved in the database regardless.
    """
    full_history = load_history(session_id)
 
    if len(full_history) > WINDOW_SIZE:
        logger.info(
            f"History trimmed: {len(full_history)} → {WINDOW_SIZE} messages "
            f"for session {session_id}"
        )
        return full_history[-WINDOW_SIZE:]
 
    return full_history

def add_human_message(session_id: str, content: str) -> None:
    """Call this when the user sends a message."""
    db.save_message(session_id=session_id, role="human", content=content)
    logger.info(f"[{session_id}] Human message saved.")
 
 
def add_ai_message(session_id: str, content: str) -> None:
    """Call this when the main LLM responds."""
    db.save_message(session_id=session_id, role="ai", content=content)
    logger.info(f"[{session_id}] AI message saved.")


def add_tool_call(
    session_id: str,
    tool_name: str,
    tool_call_id: str,
    content: str,
) -> None:
    """
    Call this when the LLM decides to invoke a tool.
    tool_call_id must be saved — it links this to the tool_result below.
    """
    db.save_message(
        session_id=session_id,
        role="tool_call",
        content=content,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
    )
    logger.info(f"[{session_id}] Tool call saved: {tool_name} (id={tool_call_id})")

def add_tool_result(
    session_id: str,
    tool_name: str,
    tool_call_id: str,
    content: str,
) -> None:
    """
    Call this when a tool finishes and returns a result.
    Use the same tool_call_id as the matching add_tool_call().
    """
    db.save_message(
        session_id=session_id,
        role="tool_result",
        content=content,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
    )
    logger.info(f"[{session_id}] Tool result saved: {tool_name} (id={tool_call_id})")

def add_agent_call(
    session_id: str,
    agent_name: str,
    content: str,
) -> None:
    """
    Call this when the main loop delegates a task to an agent.
    content should describe the task being handed off.
    """
    db.save_message(
        session_id=session_id,
        role="agent_call",
        content=content,
        agent_name=agent_name,
    )
    logger.info(f"[{session_id}] Agent call saved: {agent_name}")


def add_agent_result(
    session_id: str,
    agent_name: str,
    content: str,
) -> None:
    """
    Call this when an agent finishes and returns its answer.
    agent_name must match the one used in add_agent_call().
    """
    db.save_message(
        session_id=session_id,
        role="agent_result",
        content=content,
        agent_name=agent_name,
    )
    logger.info(f"[{session_id}] Agent result saved: {agent_name}")


def clear_history(session_id: str) -> None:
    """
    Deletes the session and all its messages from the database.
    Use this for a 'clear chat' feature.
    """
    db.delete_session(session_id)
    logger.info(f"Session cleared: {session_id}")