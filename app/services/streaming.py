import json
from typing import AsyncGenerator, Dict, Any, List
import logfire
from groq import Groq
from openai import OpenAI

from app.config import settings
from app.agents.graph import rag_agent
from app.agents.state import AgentState
from app.security.gateway import security_gateway
from app.security.models import Decision

def format_sse(event_type: str, data: Dict[str, Any]) -> str:
    """Formats payload according to standard Server-Sent Events (SSE) specification."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

def get_inference_stream(prompt: str):
    """
    Attempts inference streaming:
    1. First tries LiteLLM proxy if running (http://127.0.0.1:4000/v1)
    2. Seamlessly falls back to direct Groq client if LiteLLM is not running or unreachable
    """
    # Try LiteLLM proxy first
    try:
        litellm_client = OpenAI(
            api_key=settings.LITELLM_MASTER_KEY or "sk-proxy-key",
            base_url=settings.LITELLM_BASE_URL,
            timeout=3.0
        )
        return litellm_client.chat.completions.create(
            model="groq/openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            stream=True
        )
    except Exception as proxy_err:
        logfire.info(f"LiteLLM proxy offline ({proxy_err}), using direct Groq provider fallback.")

    # Direct Groq fallback
    groq_key = settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else ""
    groq_client = Groq(api_key=groq_key, timeout=20.0)
    return groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        stream=True
    )

async def stream_rag_pipeline(query: str, thread_id: str = "default_user") -> AsyncGenerator[str, None]:
    """
    End-to-End Streaming Pipeline:
    1. Security Layer Pre-Check (Gate 1)
    2. Agentic Workflow (Gate 2 - LangGraph)
    3. Real-Time Token Generation (Gate 3 - Streaming)
    """
    yield format_sse("status", {"stage": "security", "message": "Evaluating query safety & domain scope..."})

    # 1. Gate 1: Security Validation
    sec_decision = security_gateway.evaluate_query(query)
    
    yield format_sse("security", {
        "decision": sec_decision.decision.value,
        "category": sec_decision.category.value,
        "confidence": sec_decision.confidence,
        "reason": sec_decision.reason,
        "detectors": sec_decision.detectors,
        "latency_ms": round(sec_decision.latency_ms, 2)
    })

    if sec_decision.decision != Decision.ALLOW:
        yield format_sse("status", {"stage": "blocked", "message": f"Request {sec_decision.decision.value.lower()}: {sec_decision.category.value}"})
        safe_msg = sec_decision.safe_response or "Request restricted by security policy."
        yield format_sse("token", {"text": safe_msg})
        yield format_sse("done", {
            "thread_id": thread_id,
            "status": "Blocked by security policy",
            "sources": [],
            "thought_process": [f"Security Gate: {sec_decision.decision.value}", f"Category: {sec_decision.category.value}"]
        })
        return

    # 2. Gate 2: LangGraph Agent Execution (Planner & Retriever)
    yield format_sse("status", {"stage": "planning", "message": "Analyzing query intent and planning retrieval..."})

    initial_state = {
        "messages": [{"role": "user", "content": query}],
        "current_query": query,
        "documents": [],
        "plan": ["Start"],
        "status": "Planning..."
    }
    config = {"configurable": {"thread_id": thread_id}}

    try:
        graph_output = rag_agent.invoke(initial_state, config=config)
    except Exception as e:
        logfire.warning(f"LangGraph execution fallback triggered: {e}")
        # Graceful fallback: perform direct search if agent graph hits external service issues
        from app.services.retrieval.qdrant_service import search_enterprise_knowledge
        from app.services.retrieval.ranking_service import rerank_documents
        from app.security.trust_boundary import sanitize_and_isolate_context
        
        raw_results = search_enterprise_knowledge(query, limit=10)
        sanitized = sanitize_and_isolate_context(raw_results)
        doc_contents = [d["content"] for d in sanitized]
        reranked = rerank_documents(query, doc_contents, top_n=5)
        graph_output = {
            "documents": reranked,
            "plan": ["Fallback Search", "Context Sanitized"],
            "current_query": query
        }

    plan = graph_output.get("plan", [])
    documents = graph_output.get("documents", [])
    current_intent = graph_output.get("current_query", query)

    yield format_sse("status", {"stage": "retrieval", "message": f"Retrieved and verified {len(documents)} context chunks."})
    yield format_sse("sources", {"sources": documents})

    # 3. Gate 3: Live Token Streaming
    yield format_sse("status", {"stage": "generation", "message": "Synthesizing real-time response..."})

    if current_intent == "CONVERSATIONAL":
        prompt = (
            f"You are a friendly and helpful Enterprise Kubernetes Assistant.\n"
            f"Answer the user query conversationally.\n\n"
            f"USER QUERY: {query}"
        )
    else:
        full_context = "\n\n".join(documents[:5])
        prompt = (
            f"You are a Senior Kubernetes Architect and Technical Guide.\n"
            f"Answer the user's question using the provided verified technical context.\n"
            f"Be precise, technical, provide kubectl syntax or YAML manifests when relevant.\n\n"
            f"TECHNICAL CONTEXT:\n{full_context}\n\n"
            f"USER QUESTION: {query}"
        )

    try:
        response_stream = get_inference_stream(prompt)

        full_text = ""
        for chunk in response_stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                text_part = delta.content
                full_text += text_part
                yield format_sse("token", {"text": text_part})

        yield format_sse("done", {
            "thread_id": thread_id,
            "status": "Completed successfully",
            "sources": documents,
            "thought_process": plan
        })

    except Exception as e:
        logfire.error(f"Streaming token generation failed: {e}")
        yield format_sse("error", {"code": "GENERATION_ERROR", "message": f"LLM streaming error: {str(e)}"})
