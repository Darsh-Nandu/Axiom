from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from axiom.utils.logger import logger
from axiom.config import config

from abc import ABC, abstractmethod
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class LLMClient(ABC):
    @abstractmethod
    def get_llm(self, model_name: str):
        pass


class GeminiClient(LLMClient):
    def get_llm(self, model: str = config['llm']['default_gemini_model']) -> ChatGoogleGenerativeAI:
        """This function returns an instance of an llm powered by gemini api key"""
        return ChatGoogleGenerativeAI(
            model=model,
            temperature= config['llm']['temperature'],
            timeout= config['llm']['timeout'],
            max_retries= config['llm']['max_retries'],
        )

class GroqClient(LLMClient):
    def get_llm(self, model: str = config['llm']['default_groq_model']) -> ChatGroq:
        """This function returns an instance of an llm powered by groq api key"""
        return ChatGroq(
            model=model,
            temperature= config['llm']['temperature'],
            timeout= config['llm']['timeout'],
            max_retries= config['llm']['max_retries'],
        )


# Factory
class Model():
    _registry = {
        'gemini': GeminiClient,
        'groq': GroqClient
    }
    @classmethod
    def get(cls, provider_name: str, model: Optional[str] = ""):
        if provider_name not in cls._registry:
            raise ValueError(f"Provider {provider_name} is not registered.")
        client_class = cls._registry[provider_name]()
        return client_class.get_llm(model=model)

