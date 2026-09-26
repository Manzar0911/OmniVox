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

# Database Connection (PostgreSQL / SQLite)
# e.g., postgresql+asyncpg://avnadmin:password@pg-11e63a6f-itbeastcoder-0979.a.aivencloud.com:27142/defaultdb?ssl=require
DATABASE_URL = os.getenv("DATABASE_URL")

# Authentication & JWT Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "omnivox-secret-key-change-in-production-random-token-64chars")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# Google OAuth 2.0 Configuration (for official Gmail OAuth login)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/integrations/gmail/callback")


# LangSmith / LangChain Tracing Configuration
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT", "omnivox")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "").lower() in ("true", "1", "yes") or bool(LANGSMITH_API_KEY)

if LANGSMITH_API_KEY and LANGSMITH_TRACING:
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
    os.environ["LANGSMITH_ENDPOINT"] = LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_ENDPOINT"] = LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"



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
    """Validate configuration and print active observability status."""
    if LANGSMITH_API_KEY and LANGSMITH_TRACING:
        print(f"[config] LangSmith tracing ENABLED (Project: {LANGSMITH_PROJECT})")
    else:
        print("[config] LangSmith tracing disabled (set LANGSMITH_API_KEY in .env to enable)")



