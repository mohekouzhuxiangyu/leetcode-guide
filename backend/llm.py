"""DeepSeek LLM 工厂：基于 langchain-openai 的 ChatOpenAI。"""
from langchain_openai import ChatOpenAI

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


def create_llm(temperature: float = 0.3, max_tokens: int = 8192) -> ChatOpenAI:
    """创建指向 DeepSeek 的 ChatOpenAI 实例。"""
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=180,
        max_retries=2,
    )
