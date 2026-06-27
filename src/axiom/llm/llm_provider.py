from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from axiom.utils.logger import logger
from axiom.configs.config import config

from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def get_gemini(model: str = config['llm']['default_gemini_model']) -> ChatGoogleGenerativeAI:
    """This function returns an instance of an llm powered by gemini api key"""
    return ChatGoogleGenerativeAI(
        model=model,
        temperature= config['llm']['temperature'],
        timeout= config['llm']['timeout'],
        max_retries= config['llm']['max_retries'],
    )

def get_groq(model: str = config['llm']['default_groq_model']) -> ChatGroq:
    """This function returns an instance of an llm powered by groq api key"""
    return ChatGroq(
        model=model,
        temperature= config['llm']['temperature'],
        timeout= config['llm']['timeout'],
        max_retries= config['llm']['max_retries'],
    )


# Factory
class Model():
    @staticmethod
    def set(provider_name: str, model: Optional[str] = None):
        if provider_name == "gemini":
            logger.info("Gemini provider selected")
            return get_gemini(model or config['llm']['default_gemini_model'])
        
        elif provider_name == "groq":
            logger.info("Groq provider selected")
            return get_groq(model or config['llm']['default_groq_model'])
        
        else:
            logger.warning("Unknown provider entered")
            raise ValueError(
                f"{provider_name} is not a valid provider."
            )
