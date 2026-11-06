from langchain_openai import ChatOpenAI
from app.config import settings

def get_langchain_llm(feature: str = "rag") -> ChatOpenAI:
    """
    Returns a LiteLLM-backed ChatOpenAI — a drop-in for ChatGroq in LangChain nodes.

    LiteLLM provides an OpenAI-compatible proxy gateway. ChatOpenAI supports
    base_url and default_headers/extra_body to pass routing or metadata parameters.
    """
    return ChatOpenAI(
        api_key=settings.LITELLM_MASTER_KEY,
        base_url=settings.LITELLM_BASE_URL,
        model="groq/openai/gpt-oss-20b",  # Or your LiteLLM proxy route/model name
        temperature=0,
        model_kwargs={
            "extra_body": {
                "metadata": {
                    "feature": feature,
                    "_user": "rag-system",
                    "environment": "production"
                }
            }
        }
    )

def extract_cache_status(response) -> str:
    """
    Pull cache status header from LiteLLM proxy response if supported.
    Tries multiple attribute paths defensively — returns 'MISS' if not found.
    """
    for attr in ("_raw_response", "_response", "_http_response"):
        raw = getattr(response, attr, None)
        if raw is not None:
            status = getattr(raw, "headers", {}).get("x-litellm-cache-status", "")
            if status:
                return status.upper()
    return "MISS"