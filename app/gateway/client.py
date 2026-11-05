
"""
Centralized LLM Gateway Client.

Architecture:
    LangGraph / LangChain
            |
            v
       LiteLLM Proxy
            |
       +----+----+
       |         |
    Primary   Fallback
    Groq 70B  Groq 8B

LiteLLM handles:
    - Model routing
    - Automatic fallback
    - Retries
    - Response caching

No OpenAI API key or Portkey dependency required.
"""

from typing import Any

from langchain_openai import ChatOpenAI

from app.config import settings


def _get_secret_value(value: Any) -> str:
    """
    Extract a plain string from a Pydantic SecretStr
    or accept an existing string.
    """
    if value is None:
        raise ValueError("Required LiteLLM credential is missing.")

    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()

    if not isinstance(value, str) or not value.strip():
        raise ValueError("LiteLLM credential is empty or invalid.")

    return value


def get_langchain_llm(feature: str = "rag", streaming: bool = False) -> ChatOpenAI:
    """
    Returns a LangChain ChatOpenAI client connected
    to the local LiteLLM Proxy.

    Args:
        feature: Identifies the application component
                 using this LLM (planner, responder, etc.).

    Returns:
        ChatOpenAI: OpenAI-compatible client routed through LiteLLM.
    """

    master_key = _get_secret_value(
        settings.LITELLM_MASTER_KEY
    )

    base_url = settings.LITELLM_BASE_URL.rstrip("/")

    return ChatOpenAI(
        model="rag-primary",

        # LiteLLM OpenAI-compatible endpoint
        base_url=base_url,

        # LiteLLM master key, NOT an OpenAI API key
        api_key=master_key,

        temperature=0,

        # Retry and fallback are centralized in LiteLLM
        max_retries=0,

        # Allow time for gateway retries and fallback
        timeout=90,

        # Feature-level request identification
        default_headers={
            "x-litellm-feature": feature,
            "x-litellm-user": "rag-system",
        },
        streaming=streaming,
    )


def extract_cache_status(response: Any) -> str:
    """
    Extract cache information when exposed by the response.

    Cache execution is managed by LiteLLM.
    The exact cache-hit metadata depends on the LiteLLM
    version and response integration.

    Returns:
        HIT, MISS, or UNKNOWN.
    """

    metadata = getattr(response, "response_metadata", {}) or {}

    # Check common metadata representations.
    status = (
        metadata.get("cache_status")
        or metadata.get("x-litellm-cache-hit")
        or metadata.get("cache_hit")
    )

    if status is not None:
        normalized = str(status).strip().lower()

        if normalized in ("hit", "true", "1"):
            return "HIT"

        if normalized in ("miss", "false", "0"):
            return "MISS"

    # Some integrations expose HTTP headers.
    headers = metadata.get("headers", {}) or {}

    if isinstance(headers, dict):
        for key, value in headers.items():
            if key.lower() in (
                "x-litellm-cache-hit",
                "x-litellm-cache-status"
            ):
                normalized = str(value).strip().lower()

                if normalized in ("hit", "true", "1"):
                    return "HIT"

                if normalized in ("miss", "false", "0"):
                    return "MISS"

    return "UNKNOWN"
