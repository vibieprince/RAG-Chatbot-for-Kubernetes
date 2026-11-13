from langchain_openai import ChatOpenAI
from app.config import settings
from app.gateway.manager import gateway_manager

def get_langchain_llm(feature: str = "rag", force_fallback: bool = False):
    """
    Returns an LLM client:
    - Primary: LiteLLM-backed ChatOpenAI when gateway is awake and ready.
    - Fallback: Direct ChatGroq when LiteLLM is unready, cold-starting, or unconfigured.
    """
    if force_fallback or not gateway_manager.is_cached_ready():
        if settings.GROQ_API_KEY:
            from langchain_groq import ChatGroq
            groq_key = (
                settings.GROQ_API_KEY.get_secret_value()
                if hasattr(settings.GROQ_API_KEY, "get_secret_value")
                else str(settings.GROQ_API_KEY)
            )
            return ChatGroq(
                api_key=groq_key,
                model=settings.GROQ_MODEL,
                temperature=0,
            )

    return ChatOpenAI(
        api_key=settings.LITELLM_MASTER_KEY or "sk-proxy-key",
        base_url=settings.LITELLM_BASE_URL,
        model="rag-primary",
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
