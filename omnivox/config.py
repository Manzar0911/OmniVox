"""Environment configuration for OmniVox.

Supports 100% Free Local Open-Source Models (Ollama: Qwen 2.5, Llama 3.1),
AWS Bedrock, and OpenAI.
"""
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Provider mode: 'ollama', 'bedrock', or 'openai' (auto-detected if unset)
LLM_PROVIDER = os.getenv("LLM_PROVIDER")

# Local Open-Source (Ollama) - 100% Free Zero Cost
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# AWS Bedrock
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")

# Tavily AI Search (Optional: falls back to free DuckDuckGo if unset)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


def get_chat_model(temperature: float = 0.0) -> Any:
    """Instantiate the active LLM provider (Ollama, Bedrock, or OpenAI)."""
    # 1. Check if Ollama is explicitly requested or running
    if LLM_PROVIDER == "ollama" or (not AWS_ACCESS_KEY_ID and not OPENAI_API_KEY):
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=temperature,
        )

    # 2. AWS Bedrock
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(
            model=BEDROCK_MODEL_ID,
            region_name=AWS_DEFAULT_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            temperature=temperature,
        )

    # 3. OpenAI
    if OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=CHAT_MODEL, api_key=OPENAI_API_KEY, temperature=temperature)

    from langchain_ollama import ChatOllama

    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=temperature)


def validate() -> None:
    """Validate configuration. Never crashes if running with free local models."""
    pass


