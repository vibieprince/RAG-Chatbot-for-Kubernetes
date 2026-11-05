import logfire

from nemoguardrails import RailsConfig, LLMRails
from nemoguardrails.integrations.langchain.llm_adapter import (
    LangChainLLMAdapter
)

from app.gateway.client import get_langchain_llm
from app.guardrails.colang_rules import (
    COLANG_CONTENT,
    YAML_CONTENT,
    RAIL_INDICATORS
)

_rails: LLMRails | None = None


def initialize_rails() -> None:
    """
    Build the NeMo LLMRails singleton at app startup.
    Uses centralized LiteLLM gateway for intent classification at the gate.
    """
    global _rails
    guard_llm = get_langchain_llm(feature="guardrails")

    config = RailsConfig.from_content(
        colang_content=COLANG_CONTENT,
        yaml_content=YAML_CONTENT
    )

    # Adapt LangChain LLM to NeMo's LLMModel interface
    nemo_llm = LangChainLLMAdapter(guard_llm)

    _rails = LLMRails(config, llm=nemo_llm)

    logfire.info(
        "🛡️ NeMo Guardrails initialised (via LiteLLM gateway)."
    )
    


def guard(message: str) -> tuple[bool, str | None]:
    """
    Run a user message through the NeMo rails gate.

    Returns:
        (True,  rail_response) — a rail fired; return this response immediately,
                                skip the RAG pipeline entirely.
        (False, None)          — message is clean; proceed to LangGraph.
    """
    if _rails is None:
        logfire.error("❌ Guardrails not initialised — failing closed.")
        raise RuntimeError("NeMo Guardrails is not initialized. Cannot evaluate security rails.")

    with logfire.span("🛡️ Guardrails Check"):
        result = _rails.generate(messages=[{"role": "user", "content": message}])

        # NeMo returns {'role': 'assistant', 'content': '...'} — extract text
        content = result.get("content", "") if isinstance(result, dict) else str(result)

        fired = any(indicator in content for indicator in RAIL_INDICATORS)

        if fired:
            logfire.info(f"🛡️ Guardrails fired | query='{message[:80]}'")
            return True, content

        logfire.info("✅ Guardrails passed.")
        return False, None