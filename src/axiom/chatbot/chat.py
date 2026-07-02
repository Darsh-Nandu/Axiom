from langchain_core.messages import SystemMessage, HumanMessage

from axiom.memory.memory import get_history_for_llm, add_ai_message
from axiom.prompts import SYSTEM_PROMPT
from axiom.llm.llm_provider import Model

model = Model()
llm = model.get('groq')

def chat(prompt: str):
    history = get_history_for_llm()
    messages = [history, SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    add_ai_message(response.content)
    print(response.content)

chat("What is the capital of France?")