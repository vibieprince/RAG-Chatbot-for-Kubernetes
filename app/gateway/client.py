from typing import Optional
from langchain_openai import ChatOpenAI
from app.config import settings
from app.gateway.manager import gateway_manager


def is_groq_fallback_configured() -> bool:
    """Checks if a valid Groq API key is configured for fallback."""
    if not settings.GROQ_API_KEY:
        return False
    key_val = (
        settings.GROQ_API_KEY.get_secret_value()
        if hasattr(settings.GROQ_API_KEY, "get_secret_value")
        else str(settings.GROQ_API_KEY)
    )
    return bool(key_val and key_val.strip())


def get_langchain_llm(
    feature: str = "rag",
    force_fallback: bool = False,
    request_id: Optional[str] = None,
):
    """
    Returns an LLM client:
    - Primary: LiteLLM-backed ChatOpenAI when gateway is awake and ready.
    - Fallback: Direct ChatGroq when LiteLLM is unready, cold-starting, or explicitly bypassed.
    """
    extra_headers = {"X-Request-ID": request_id} if request_id else {}

    if force_fallback or not gateway_manager.is_cached_ready():
        if is_groq_fallback_configured():
            from langchain_groq import ChatGroq
            groq_key = (
                settings.GROQ_API_KEY.get_secret_value()
                if hasattr(settings.GROQ_API_KEY, "get_secret_value") and settings.GROQ_API_KEY
                else str(settings.GROQ_API_KEY)
            )
            return ChatGroq(
                api_key=groq_key,
                model=settings.GROQ_MODEL,
                temperature=0,
                default_headers=extra_headers,
            )
        if force_fallback:
            raise RuntimeError("Fallback requested but Groq API key is not configured.")

    return ChatOpenAI(
        api_key=settings.LITELLM_MASTER_KEY or "sk-proxy-key",
        base_url=settings.LITELLM_BASE_URL,
        model="rag-primary",
        temperature=0,
        default_headers=extra_headers,
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
