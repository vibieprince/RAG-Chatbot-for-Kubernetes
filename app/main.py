# ============================================================
# CRITICAL: logfire MUST be configured before ALL other imports
# so that spans from all modules are captured from the start.
# ============================================================
import os
import asyncio
import uuid
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import logfire
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

from fastapi import FastAPI, Response, Request, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.agents.graph import rag_agent
from app.gateway.manager import gateway_manager
from app.gateway.client import is_groq_fallback_configured
from app.security.gateway import security_gateway
from app.security.models import Decision
from app.services.streaming import stream_rag_pipeline

# Initialize FastAPI app
app = FastAPI(
    title="Enterprise Kubernetes Agentic RAG API",
    description="Production Agentic RAG Platform with Defense-in-Depth AI Security & Real-Time Token Streaming",
    version="2.0.0"
)

# Request Models
class QueryRequest(BaseModel):
    q: str
    thread_id: Optional[str] = "default_user"

@app.get("/api/health")
def health_check():
    """
    Returns service health, LiteLLM gateway status, and security validator status.
    If DetectJailbreak is disabled, accurately reports degraded security rather than misleading 100% health.
    """
    sec_status = security_gateway.get_security_status()
    gw_status = gateway_manager.get_status()

    if sec_status.get("all_validators_active") and gw_status.get("ready"):
        api_status = "healthy"
    elif sec_status.get("mandatory_healthy"):
        api_status = "degraded"
    else:
        api_status = "unhealthy"

    return {
        "status": api_status,
        "service": "Enterprise Kubernetes Agentic RAG",
        "version": "2.0.0",
        "gateway": gw_status,
        "security": sec_status,
        "features": {
            "ai_security_gateway": True,
            "realtime_streaming": True,
            "qdrant_retrieval": True,
            "flashrank_reranking": True,
            "parallel_gateway_wakeup": True
        }
    }

@app.get("/api/health/gateway")
async def gateway_health_check():
    """
    Explicitly probes the LiteLLM gateway health endpoint.
    Returns HTTP 200 if gateway is confirmed ready; returns HTTP 503 if unready/timed out.
    """
    is_ready = await gateway_manager.check_health()
    status_details = gateway_manager.get_status()
    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "ready": False,
                "error": "LiteLLM gateway is not ready or waking up",
                "details": status_details,
            }
        )
    return {
        "ready": True,
        "details": status_details
    }

@app.get("/api/graph")
def get_graph_image():
    """Returns the Mermaid image of the agent workflow."""
    try:
        png_bytes = rag_agent.get_graph().draw_mermaid_png()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        return {"error": f"Could not generate graph image: {e}"}

@app.post("/query/stream")
async def query_stream_endpoint(request: QueryRequest, raw_request: Request):
    """
    Genuine End-to-End Token Streaming Endpoint.
    Streams Server-Sent Events (SSE) representing security decisions,
    retrieval status, document sources, and live model tokens.
    Initiates parallel LiteLLM wake-up concurrently with security checks.
    Respects X-LiteLLM-Wakeup-Triggered header to avoid duplicate wake-up calls.
    """
    request_id = raw_request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    wakeup_triggered = raw_request.headers.get("x-litellm-wakeup-triggered", "").lower() in ("true", "1")

    return StreamingResponse(
        stream_rag_pipeline(
            query=request.q,
            thread_id=request.thread_id or "default_user",
            request_id=request_id,
            wakeup_already_triggered=wakeup_triggered,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        }
    )

@app.post("/query")
async def query_sync_endpoint(request: QueryRequest, raw_request: Request):
    """
    Synchronous POST endpoint (preserved for backwards-compatibility).
    Applies the full defense-in-depth security gateway before LangGraph execution.
    Initiates non-blocking LiteLLM wake-up concurrently with security checks.
    """
    request_id = raw_request.headers.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
    wakeup_triggered = raw_request.headers.get("x-litellm-wakeup-triggered", "").lower() in ("true", "1")
    q = request.q
    thread_id = request.thread_id or "default_user"

    # Step 0: Non-blocking parallel wake-up probe (skips redundant ping if already triggered)
    wakeup_task = gateway_manager.start_wakeup(
        request_id=request_id,
        skip_liveliness_trigger=wakeup_triggered,
    )

    # Gate 1: Security Gateway (runs concurrently)
    sec_decision = security_gateway.evaluate_query(q)
    if sec_decision.decision != Decision.ALLOW:
        logfire.warning(
            f"🛡️ Blocked request at security gateway | Category: {sec_decision.category}",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "question": q,
                "answer": sec_decision.safe_response,
                "thought_process": [
                    f"Security Gate: {sec_decision.decision.value}",
                    f"Category: {sec_decision.category.value}",
                    f"Reason: {sec_decision.reason}"
                ],
                "security": sec_decision.dict(),
                "status": f"Blocked: {sec_decision.category.value}",
                "sources": [],
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id}
        )

    # Bounded wait for LiteLLM readiness before running LangGraph agent
    gateway_ready = False
    try:
        gateway_ready = await gateway_manager.wait_ready(
            timeout=settings.LITELLM_WAKEUP_TIMEOUT,
            request_id=request_id,
            skip_liveliness_trigger=wakeup_triggered,
        )
    except Exception:
        gateway_ready = False

    # Controlled 503 check: if LiteLLM is unready AND Groq fallback is unconfigured
    if not gateway_ready and not is_groq_fallback_configured():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "LiteLLM gateway timed out and fallback provider is not configured.",
                "status": "gateway_unavailable",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id}
        )

    # Gate 2: LangGraph Agent Execution
    initial_state = {
        "messages": [{"role": "user", "content": q}],
        "current_query": q,
        "documents": [],
        "plan": ["Start"],
        "status": "Initializing Graph..."
    }
    config = {"configurable": {"thread_id": thread_id}}
    loop = asyncio.get_running_loop()

    try:
        final_output = await loop.run_in_executor(
            None,
            lambda: rag_agent.invoke(initial_state, config=config)
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "question": q,
                "answer": final_output.get("final_answer"),
                "thought_process": final_output.get("plan"),
                "status": final_output.get("status"),
                "sources": final_output.get("documents", []),
                "security": sec_decision.dict(),
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id}
        )
    except Exception as e:
        logfire.error(f"❌ Backend Execution Failed: {e}", request_id=request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "question": q,
                "answer": "An internal error occurred while processing your request. Please try again.",
                "thought_process": ["Error during execution"],
                "status": "error",
                "sources": [],
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id}
        )

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanly closes shared network resources on application shutdown."""
    await gateway_manager.close()

# Mount static files for the modern frontend (Chat app & Recruiter Landing Page)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
