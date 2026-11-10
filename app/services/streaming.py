"""
End-to-End Streaming Pipeline — Production Async Architecture.

Design Decisions:
  1. Single Generation Call:
     Planner and retriever run during planning/retrieval stages. The responder
     is replaced here by a single streaming LLM call via AsyncOpenAI / AsyncGroq.
     The full LangGraph graph's responder node is NOT called from this path,
     completely eliminating the previous duplicate-generation bug.
  2. Non-blocking Async I/O:
     Synchronous components (Qdrant search, FlashRank reranking, LangChain planner)
     are executed via asyncio.get_event_loop().run_in_executor() so they do not
     block the FastAPI event loop.
  3. Incremental Token Yielding:
     Uses AsyncOpenAI (and AsyncGroq fallback) with `stream=True` and `async for`,
     allowing tokens to stream incrementally over HTTP Server-Sent Events (SSE)
     without event loop starvation.
  4. Cancellation & Disconnect Handling:
     Captures asyncio.CancelledError when the client disconnects or aborts, ensuring
     clean socket closure without orphan background tasks.
  5. Structured SSE Event Protocol:
     - status: current stage (security, planning, retrieval, generation)
     - security: security validation audit decision
     - sources: sanitized and reranked context documents
     - token: live text chunk as emitted by the model
     - done: completion payload with session ID and thought process
     - error: structured error code and message
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Dict, Any, List

import logfire
from openai import AsyncOpenAI

from app.config import settings
from app.security.gateway import security_gateway
from app.security.models import Decision


# ---------------------------------------------------------------------------
# SSE Formatting
# ---------------------------------------------------------------------------

def format_sse(event_type: str, data: Dict[str, Any]) -> str:
    """Formats a payload into standard Server-Sent Events (SSE) specification."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Async Inference Streaming (LiteLLM Proxy with Groq Direct Fallback)
# ---------------------------------------------------------------------------

async def _get_async_inference_stream(prompt: str, history_messages: List[Dict[str, str]]):
    """
    Initiates an asynchronous streaming chat completion request.
    1. Tries the LiteLLM proxy gateway (http://127.0.0.1:4000/v1).
    2. Falls back to direct Groq provider if LiteLLM is unreachable.
    Both paths enforce stream=True.
    """
    messages = history_messages + [{"role": "user", "content": prompt}]

    # 1. Primary: LiteLLM Gateway
    try:
        client = AsyncOpenAI(
            api_key=settings.LITELLM_MASTER_KEY or "sk-proxy-key",
            base_url=settings.LITELLM_BASE_URL,
            timeout=5.0,
        )
        return await client.chat.completions.create(
            model="groq/openai/gpt-oss-20b",
            messages=messages,
            temperature=0.1,
            stream=True,
        )
    except Exception as proxy_err:
        logfire.info(
            "LiteLLM proxy offline ({err}), utilizing direct Groq async provider.",
            err=str(proxy_err),
        )

    # 2. Fallback: Direct Groq
    from groq import AsyncGroq

    groq_key = (
        settings.GROQ_API_KEY.get_secret_value()
        if settings.GROQ_API_KEY
        else ""
    )
    groq_client = AsyncGroq(api_key=groq_key, timeout=90.0)
    return await groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=messages,
        temperature=0.1,
        stream=True,
    )


# ---------------------------------------------------------------------------
# Synchronous Stage Helpers (Executed in ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def _run_planner(query: str, messages: List[Dict[str, str]]) -> str:
    """
    Evaluates conversation history and user query to decide whether to search or converse.
    """
    from app.gateway.client import get_langchain_llm

    llm = get_langchain_llm(feature="planner")

    history = ""
    for msg in messages[:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history += f"{role}: {msg['content']}\n"

    user_message = messages[-1]["content"] if messages else ""

    prompt = f"""You are an intelligent Assistant Planner.
Analyze the conversation history and the latest user message.

CONVERSATION HISTORY:
{history}

LATEST MESSAGE:
"{user_message}"

Task:
1. If the latest message is a greeting (hi, hello) or a question that can be answered using ONLY the conversation history above (e.g., "what is my name"), respond with 'CONVERSATIONAL'.
2. If it is a technical question about Kubernetes, Intel, or Networking that requires fresh documentation, output a refined search query.

Output ONLY 'CONVERSATIONAL' or the search query."""

    with logfire.span("🧠 Planner Decision (Streaming)"):
        response = llm.invoke(prompt)
        content_str = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
        decision = content_str.strip()
        logfire.info(f"Intent identified: {decision}")

    return decision


def _run_retriever(search_query: str) -> List[str]:
    """
    Performs vector search in Qdrant, applies trust-boundary isolation, and runs FlashRank reranking.
    """
    from app.services.retrieval.qdrant_service import search_enterprise_knowledge
    from app.services.retrieval.ranking_service import rerank_documents
    from app.security.trust_boundary import sanitize_and_isolate_context

    with logfire.span("🔍 Knowledge Retrieval (Streaming)"):
        logfire.info(f"Searching Qdrant for: {search_query}")
        raw_results = search_enterprise_knowledge(search_query, limit=15)
        logfire.info(f"Retrieved {len(raw_results)} candidates from Vector DB")

        sanitized = sanitize_and_isolate_context(raw_results)
        doc_contents = [doc["content"] for doc in sanitized]

        with logfire.span("⚖️ Semantic Reranking (Streaming)"):
            reranked = rerank_documents(search_query, doc_contents, top_n=5)
            logfire.info("Reranking complete — kept top 5 chunks.")

    return reranked


def _build_responder_prompt(
    intent: str,
    documents: List[str],
    messages: List[Dict[str, str]],
) -> str:
    """Formats context and instructions for the final streaming synthesis."""
    history_str = ""
    for msg in messages[:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = messages[-1]["content"] if messages else ""

    if intent == "CONVERSATIONAL":
        return (
            "You are a friendly and helpful Enterprise Kubernetes Assistant.\n"
            "Answer the user's latest message using the CONVERSATION HISTORY below.\n\n"
            f"CONVERSATION HISTORY:\n{history_str}\n\n"
            f"LATEST MESSAGE:\n\"{user_msg}\""
        )

    max_context_chars = 25_000
    full_context = ""
    for doc in documents:
        if len(full_context) + len(doc) < max_context_chars:
            full_context += doc + "\n\n"
        else:
            logfire.warning("Streaming context truncated to fit model token limits.")
            break

    return (
        "You are a Senior Kubernetes Architect and Technical Guide.\n"
        "Answer the user's question using the provided verified technical context.\n"
        "Be precise and technical; provide kubectl syntax or YAML manifests where relevant.\n\n"
        f"TECHNICAL CONTEXT:\n{full_context}\n\n"
        f"CONVERSATION HISTORY:\n{history_str}\n\n"
        f"USER QUESTION:\n\"{user_msg}\""
    )


# ---------------------------------------------------------------------------
# End-to-End Async Streaming Pipeline
# ---------------------------------------------------------------------------

async def stream_rag_pipeline(
    query: str,
    thread_id: str = "default_user",
) -> AsyncGenerator[str, None]:
    """
    Streams Server-Sent Events representing:
      1. Gate 1: Security Evaluation
      2. Gate 2: Agent Planning & Knowledge Retrieval
      3. Gate 3: Live Incremental Token Streaming
    """
    loop = asyncio.get_running_loop()

    # --- Gate 1: Security Pre-Check ---
    yield format_sse("status", {
        "stage": "security",
        "message": "Evaluating query safety & domain scope...",
    })

    try:
        sec_decision = await loop.run_in_executor(
            None, security_gateway.evaluate_query, query
        )
    except Exception as sec_err:
        logfire.error(f"Security gateway error during streaming: {sec_err}")
        yield format_sse("error", {
            "code": "SECURITY_SERVICE_ERROR",
            "message": "Security service temporarily unavailable. Request not processed.",
        })
        return

    yield format_sse("security", {
        "decision": sec_decision.decision.value,
        "category": sec_decision.category.value,
        "confidence": sec_decision.confidence,
        "reason": sec_decision.reason,
        "detectors": sec_decision.detectors,
        "latency_ms": round(sec_decision.latency_ms, 2),
    })

    if sec_decision.decision != Decision.ALLOW:
        yield format_sse("status", {
            "stage": "blocked",
            "message": f"Request {sec_decision.decision.value.lower()}: {sec_decision.category.value}",
        })
        safe_msg = sec_decision.safe_response or "Request restricted by security policy."
        yield format_sse("token", {"text": safe_msg})
        yield format_sse("done", {
            "thread_id": thread_id,
            "status": "Blocked by security policy",
            "sources": [],
            "thought_process": [
                f"Security Gate: {sec_decision.decision.value}",
                f"Category: {sec_decision.category.value}",
            ],
        })
        return

    # --- Gate 2a: Agent Planning ---
    yield format_sse("status", {
        "stage": "planning",
        "message": "Analyzing query intent and planning retrieval...",
    })

    messages = [{"role": "user", "content": query}]
    plan: List[str] = ["Start"]
    documents: List[str] = []

    try:
        intent = await loop.run_in_executor(None, _run_planner, query, messages)
    except Exception as plan_err:
        logfire.error(f"Planner execution failed: {plan_err}")
        # Graceful fallback: treat intent as the technical query itself
        intent = query
        plan.append("Planner Fallback: Direct Query")

    if intent == "CONVERSATIONAL":
        plan = ["Intent: Conversational/Memory", "Retrieval: Skipped"]
        yield format_sse("status", {
            "stage": "retrieval",
            "message": "Conversational query — retrieval skipped.",
        })
        yield format_sse("sources", {"sources": []})
    else:
        plan = ["Intent: Technical", f"Search Term: {intent}"]

        # --- Gate 2b: Retrieval & Reranking ---
        yield format_sse("status", {
            "stage": "retrieval",
            "message": f"Searching knowledge base for: {intent}",
        })

        try:
            documents = await loop.run_in_executor(None, _run_retriever, intent)
            plan.append("Context Retrieved & Sanitized")
        except Exception as ret_err:
            logfire.warning(f"Retrieval error: {ret_err}. Proceeding without context.")
            documents = []
            plan.append("Retrieval Warning: No Context Available")

        yield format_sse("status", {
            "stage": "retrieval",
            "message": f"Retrieved and verified {len(documents)} context chunks.",
        })
        yield format_sse("sources", {"sources": documents})

    # --- Gate 3: Single Live Token Streaming Call ---
    yield format_sse("status", {
        "stage": "generation",
        "message": "Synthesizing response — streaming live tokens...",
    })

    prompt = _build_responder_prompt(intent, documents, messages)

    try:
        response_stream = await _get_async_inference_stream(prompt, [])

        with logfire.span("✍️ LLM Synthesis (Streaming)"):
            full_text = ""
            async for chunk in response_stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    text_part = delta.content
                    full_text += text_part
                    yield format_sse("token", {"text": text_part})

        yield format_sse("done", {
            "thread_id": thread_id,
            "status": "Completed successfully",
            "sources": documents,
            "thought_process": plan,
        })

    except asyncio.CancelledError:
        logfire.info("Streaming client disconnected; generator cancelled cleanly.")
        raise

    except Exception as gen_err:
        logfire.error(f"Streaming token generation failed: {gen_err}")
        yield format_sse("error", {
            "code": "GENERATION_ERROR",
            "message": f"LLM streaming error: {str(gen_err)}",
        })
