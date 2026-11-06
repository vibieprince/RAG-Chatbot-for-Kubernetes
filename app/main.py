# ============================================================
# CRITICAL: logfire MUST be configured before ALL other imports
# so that spans from all modules are captured from the start.
# ============================================================
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import logfire
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

from fastapi import FastAPI, Response, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agents.graph import rag_agent
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
    return {
        "status": "healthy",
        "service": "Enterprise Kubernetes Agentic RAG",
        "version": "2.0.0",
        "features": {
            "ai_security_gateway": True,
            "realtime_streaming": True,
            "qdrant_retrieval": True,
            "flashrank_reranking": True
        }
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
async def query_stream_endpoint(request: QueryRequest):
    """
    Genuine End-to-End Token Streaming Endpoint.
    Streams Server-Sent Events (SSE) representing security decisions,
    retrieval status, document sources, and live model tokens.
    """
    return StreamingResponse(
        stream_rag_pipeline(request.q, request.thread_id or "default_user"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/query")
def query_sync_endpoint(request: QueryRequest):
    """
    Synchronous POST endpoint (preserved for backwards-compatibility).
    Applies the full defense-in-depth security gateway before LangGraph execution.
    """
    q = request.q
    thread_id = request.thread_id or "default_user"

    # Gate 1: Security Gateway
    sec_decision = security_gateway.evaluate_query(q)
    if sec_decision.decision != Decision.ALLOW:
        logfire.warning(f"🛡️ Blocked request at security gateway | Category: {sec_decision.category}")
        return {
            "question": q,
            "answer": sec_decision.safe_response,
            "thought_process": [
                f"Security Gate: {sec_decision.decision.value}",
                f"Category: {sec_decision.category.value}",
                f"Reason: {sec_decision.reason}"
            ],
            "security": sec_decision.dict(),
            "status": f"Blocked: {sec_decision.category.value}",
            "sources": []
        }

    # Gate 2: LangGraph Agent Execution
    initial_state = {
        "messages": [{"role": "user", "content": q}],
        "current_query": q,
        "documents": [],
        "plan": ["Start"],
        "status": "Initializing Graph..."
    }
    config = {"configurable": {"thread_id": thread_id}}

    try:
        final_output = rag_agent.invoke(initial_state, config=config)
        return {
            "question": q,
            "answer": final_output.get("final_answer"),
            "thought_process": final_output.get("plan"),
            "status": final_output.get("status"),
            "sources": final_output.get("documents", []),
            "security": sec_decision.dict()
        }
    except Exception as e:
        logfire.error(f"❌ Backend Execution Failed: {e}")
        return {
            "question": q,
            "answer": "An internal error occurred while processing your request. Please try again.",
            "thought_process": ["Error during execution"],
            "status": "error",
            "sources": []
        }

# Mount static files for the modern frontend (Chat app & Recruiter Landing Page)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
