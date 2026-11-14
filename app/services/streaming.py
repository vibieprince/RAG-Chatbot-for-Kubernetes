"""
End-to-End Streaming Pipeline — Production Async Architecture.

Design Decisions:
  1. Parallel Cold-Start Wakeup:
     Immediately upon request receipt, initiates an async background health/liveliness
     probe to LiteLLM (unless already initiated by the frontend).
     Cold-start waking overlaps with input normalization,
     Guardrails-AI security evaluation, and initial SSE framing.
  2. Single Generation Call:
     Planner and retriever run during planning/retrieval stages. The responder
     is executed as a single streaming LLM call via AsyncOpenAI / AsyncGroq.
  3. Non-blocking Async I/O:
     Synchronous components (Qdrant search, FlashRank reranking, LangChain planner)
     are executed via loop.run_in_executor() without blocking the FastAPI event loop.
  4. Reliable Intent Planning & Fallbacks:
     - Greetings ("Hello", "Hi", "Hii") never trigger Qdrant/FlashRank under any failure.
     - Technical queries use primary LiteLLM or verified direct Groq fallback.
     - Controlled error emission if both routes are unavailable (no silent routing of arbitrary input).
  5. Correlation ID Tracing:
     Propagates X-Request-ID across SSE events, Logfire spans, and model requests.
  6. Structured SSE Event Protocol:
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
import uuid
from typing import AsyncGenerator, Dict, Any, List, Optional

import logfire
from openai import AsyncOpenAI

from app.config import settings
from app.gateway.manager import gateway_manager
from app.gateway.client import is_groq_fallback_configured
from app.security.gateway import security_gateway
from app.security.models import Decision
from app.agents.nodes.planner import execute_planner, is_conversational_greeting, PlannerUnavailableError


# ---------------------------------------------------------------------------
# SSE Formatting
# ---------------------------------------------------------------------------

def format_sse(event_type: str, data: Dict[str, Any]) -> str:
    """Formats a payload into standard Server-Sent Events (SSE) specification."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# --------------------------------------------------
# Async Inference Streaming (LiteLLM Proxy with Groq Direct Fallback)
# --------------------------------------------------

async def _get_async_inference_stream(
    prompt: str,
    history_messages: List[Dict[str, str]],
    gateway_ready: bool = True,
    request_id: Optional[str] = None,
):
    """
    Initiates an asynchronous streaming chat completion request.
    1. If gateway_ready is True, tries LiteLLM proxy gateway (rag-primary).
    2. If gateway is unready or LiteLLM fails, falls back directly to AsyncGroq.
    Both paths enforce stream=True for zero-buffer real-time streaming.
    """
    messages = history_messages + [{"role": "user", "content": prompt}]
    extra_headers = {"X-Request-ID": request_id} if request_id else {}

    # 1. Primary Path: LiteLLM Gateway (only if gateway confirmed ready or not ruled out)
    if gateway_ready:
        try:
            client = AsyncOpenAI(
                api_key=settings.LITELLM_MASTER_KEY or "sk-proxy-key",
                base_url=settings.LITELLM_BASE_URL,
                timeout=10.0,
                default_headers=extra_headers,
            )
            return await client.chat.completions.create(
                model="rag-primary",
                messages=messages,
                temperature=0.1,
                stream=True,
            )
        except Exception as proxy_err:
            logfire.warning(
                "LiteLLM proxy request failed ({err}). Engaging direct Groq fallback.",
                err=str(proxy_err),
                request_id=request_id or "unknown",
            )

    # 2. Resilient Fallback Path: Direct Groq Provider
    if not is_groq_fallback_configured():
        raise RuntimeError(
            "LiteLLM gateway unavailable and direct Groq fallback is not configured."
        )

    from groq import AsyncGroq

    groq_key = (
        settings.GROQ_API_KEY.get_secret_value()
        if hasattr(settings.GROQ_API_KEY, "get_secret_value") and settings.GROQ_API_KEY
        else (str(settings.GROQ_API_KEY) if settings.GROQ_API_KEY else "")
    )
    groq_client = AsyncGroq(api_key=groq_key, timeout=90.0, default_headers=extra_headers)
    return await groq_client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.1,
        stream=True,
    )


# ---------------------------------------------------------------------------
# Synchronous Stage Helpers (Executed in ThreadPoolExecutor)
# ---------------------------------------------------------------------------

def _run_planner(
    query: str,
    messages: List[Dict[str, str]],
    force_fallback: bool = False,
    request_id: Optional[str] = None,
) -> str:
    """
    Evaluates conversation history and user query to decide whether to search or converse.
    Uses LiteLLM if ready, or direct Groq fallback if LiteLLM is not ready.
    """
    return execute_planner(
        user_message=query,
        history_messages=messages,
        force_fallback=force_fallback,
        request_id=request_id,
    )


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
    request_id: Optional[str] = None,
    wakeup_already_triggered: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Streams Server-Sent Events representing:
      0. Parallel Wake-Up: LiteLLM background wake-up triggered concurrently
         (skips liveliness ping if already triggered by frontend)
      1. Gate 1: Security Evaluation (Overlapped with wake-up)
      2. Gate 2: Agent Planning (awaits gateway readiness or falls back to Groq) & Retrieval
      3. Gate 3: Live Incremental Token Streaming
    """
    request_id = request_id or f"req-{uuid.uuid4().hex[:12]}"
    loop = asyncio.get_running_loop()

    # --- Step 0: Parallel LiteLLM Cold-Start Wake-Up ---
    # Triggered immediately; runs concurrently with security evaluation
    wakeup_task = gateway_manager.start_wakeup(
        request_id=request_id,
        skip_liveliness_trigger=wakeup_already_triggered,
    )

    # --- Gate 1: Security Pre-Check ---
    yield format_sse("status", {
        "stage": "security",
        "message": "Evaluating query safety & domain scope...",
        "request_id": request_id,
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
            "request_id": request_id,
        })
        return

    yield format_sse("security", {
        "decision": sec_decision.decision.value,
        "category": sec_decision.category.value,
        "confidence": sec_decision.confidence,
        "reason": sec_decision.reason,
        "detectors": sec_decision.detectors,
        "latency_ms": round(sec_decision.latency_ms, 2),
        "request_id": request_id,
    })

    if sec_decision.decision != Decision.ALLOW:
        yield format_sse("status", {
            "stage": "blocked",
            "message": f"Request {sec_decision.decision.value.lower()}: {sec_decision.category.value}",
            "request_id": request_id,
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
            "request_id": request_id,
        })
        return

    # --- Gate 2a: Agent Planning ---
    yield format_sse("status", {
        "stage": "planning",
        "message": "Analyzing query intent and planning retrieval...",
        "request_id": request_id,
    })

    messages = [{"role": "user", "content": query}]
    plan: List[str] = ["Start"]
    documents: List[str] = []

    # Overlap boundary: ensure LiteLLM is ready before planner LLM execution
    gateway_ready = False
    try:
        gateway_ready = await gateway_manager.wait_ready(
            timeout=settings.LITELLM_WAKEUP_TIMEOUT,
            request_id=request_id,
            skip_liveliness_trigger=wakeup_already_triggered,
        )
    except (asyncio.TimeoutError, Exception) as wait_err:
        logfire.warning(
            "Gateway wake-up wait boundary reached: {wait_err}. Engaging Groq fallback.",
            wait_err=str(wait_err),
            request_id=request_id,
        )
        gateway_ready = False

    # Execute planner with verified fallback
    intent: Optional[str] = None
    try:
        intent = await loop.run_in_executor(
            None,
            _run_planner,
            query,
            messages,
            not gateway_ready,
            request_id,
        )
    except Exception as plan_err:
        logfire.error(f"Planner execution failed: {plan_err}", request_id=request_id)
        # Check if greeting: Greetings MUST NEVER trigger retrieval!
        if is_conversational_greeting(query):
            intent = "CONVERSATIONAL"
            plan.append("Greeting identified (fallback safe-path)")
        else:
            # Technical query where both planner routes failed: return controlled error
            yield format_sse("error", {
                "code": "PLANNER_UNAVAILABLE",
                "message": "Planning service is temporarily unavailable. Both primary gateway and fallback routes failed.",
                "request_id": request_id,
            })
            return

    if intent == "CONVERSATIONAL":
        plan = ["Intent: Conversational/Memory", "Retrieval: Skipped"]
        yield format_sse("status", {
            "stage": "retrieval",
            "message": "Conversational query — retrieval skipped.",
            "request_id": request_id,
        })
        yield format_sse("sources", {"sources": []})
    else:
        plan = ["Intent: Technical", f"Search Term: {intent}"]

        # --- Gate 2b: Retrieval & Reranking ---
        yield format_sse("status", {
            "stage": "retrieval",
            "message": f"Searching knowledge base for: {intent}",
            "request_id": request_id,
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
            "request_id": request_id,
        })
        yield format_sse("sources", {"sources": documents})

    # --- Gate 3: Single Live Token Streaming Call ---
    yield format_sse("status", {
        "stage": "generation",
        "message": "Synthesizing response — streaming live tokens...",
        "request_id": request_id,
    })

    prompt = _build_responder_prompt(intent, documents, messages)

    try:
        response_stream = await _get_async_inference_stream(
            prompt,
            [],
            gateway_ready=gateway_ready,
            request_id=request_id,
        )

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
            "request_id": request_id,
        })

    except asyncio.CancelledError:
        logfire.info("Streaming client disconnected; generator cancelled cleanly.", request_id=request_id)
        raise

    except Exception as gen_err:
        logfire.error(f"Streaming token generation failed: {gen_err}", request_id=request_id)
        yield format_sse("error", {
            "code": "GENERATION_ERROR",
            "message": f"LLM streaming error: {str(gen_err)}",
            "request_id": request_id,
        })
