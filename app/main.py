# ============================================================
# CRITICAL: logfire MUST be configured before ALL other imports
# so that spans from all modules are captured from the start.
# ============================================================
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()
import logfire
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))

# Now safe to import app modules - logfire is already active
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
from app.agents.graph import rag_agent
from app.agents.nodes.planner import PlannerDecisionError
from app.guardrails.rails import initialize_rails, guard

from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional



@asynccontextmanager
async def lifespan(app: FastAPI):
    logfire.info("🚀 Initializing application...")

    initialize_rails()

    logfire.info("✅ Application initialization complete.")

    try:
        yield
    finally:
        logfire.info("🛑 Application shutting down...")

# Initialize FastAPI
app = FastAPI(title="Enterprise Agentic RAG API", lifespan=lifespan)

class QueryRequest(BaseModel):
    q: str
    thread_id: Optional[str] = "default_user"
    
    
@app.get("/")
def home():
    return {"message": "Enterprise LangGraph RAG API is live."}


@app.get("/graph")
def get_graph_image():
    """
    Returns the Mermaid image of the agent's workflow.
    """
    try:
        png_bytes = rag_agent.get_graph().draw_mermaid_png()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        return {"error": f"Could not generate graph image: {e}"}
    
    
@app.post("/query")
def query(request: QueryRequest):
    """
    Executes the LangGraph RAG flow with memory using a POST request.
    """
    q = request.q
    thread_id = request.thread_id

    initial_state = {
        "messages": [{"role": "user", "content": q}],
        "current_query": q,
        "documents": [],
        "plan": ["Start"],
        "status": "Initializing Graph..."
    }
    
    # Configuration for Memory (Thread ID)
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Gate 1: NeMo Guardrails — blocks off-topic, jailbreaks, and handles dialog
        rail_fired, rail_response = guard(q)
        if rail_fired:
            logfire.info(f"🛡️ Request blocked by guardrails | thread={thread_id}")
            return {
                "question": q,
                "answer": rail_response,
                "thought_process": ["Intent: Guardrails Fired", "Retrieval: Skipped"],
                "status": "Blocked by guardrails.",
                "sources": []
            }

        # Gate 2: LangGraph RAG pipeline
        # Run the graph synchronously to preserve Logfire context variables
        final_output = rag_agent.invoke(initial_state, config=config)
        
        return {
            "question": q,
            "answer": final_output.get("final_answer"),
            "thought_process": final_output.get("plan"),
            "status": final_output.get("status"),
            "sources": final_output.get("documents", [])
        }
    except Exception as e:
        logfire.error("Backend Execution Failed: {error}", error=str(e))
        return {
            "question": q,
            "answer": "I apologize, but I encountered an internal error while processing your request. Please try again later.",
            "thought_process": ["Error encountered during execution."],
            "status": "error",
            "sources": []
        }


@app.post("/query/stream")
def query_stream(request: QueryRequest):
    """
    Executes the LangGraph RAG flow with genuine token streaming via SSE.
    Preserves memory, guardrails, retrieval, and full metadata compatibility.
    """
    q = request.q
    thread_id = request.thread_id

    def event_stream():
        start_time = time.perf_counter()
        first_token_time = None
        accumulated_answer = []
        metadata_emitted = False
        latest_plan = ["Start"]
        latest_status = "Initializing Graph..."
        latest_sources = []

        logfire.info("Streaming request started | thread={thread_id}", thread_id=thread_id)

        try:
            # Gate 1: NeMo Guardrails
            rail_fired, rail_response = guard(q)
            if rail_fired:
                logfire.info("🛡️ Request blocked by guardrails | thread={thread_id}", thread_id=thread_id)
                meta_payload = {
                    "question": q,
                    "thought_process": ["Intent: Guardrails Fired", "Retrieval: Skipped"],
                    "status": "Blocked by guardrails.",
                    "sources": [],
                }
                yield f"event: metadata\ndata: {json.dumps(meta_payload)}\n\n"
                if rail_response:
                    yield f"event: token\ndata: {json.dumps({'token': rail_response})}\n\n"
                done_payload = {
                    "answer": rail_response,
                    "status": "Blocked by guardrails.",
                }
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                return

            # Gate 2: LangGraph RAG Pipeline
            initial_state = {
                "messages": [{"role": "user", "content": q}],
                "current_query": q,
                "documents": [],
                "plan": ["Start"],
                "status": "Initializing Graph..."
            }
            config = {"configurable": {"thread_id": thread_id}}

            final_answer_from_state = None

            for mode, payload in rag_agent.stream(
                initial_state,
                config=config,
                stream_mode=["custom", "updates"]
            ):
                if mode == "custom":
                    token_text = payload if isinstance(payload, str) else str(payload)
                    if token_text:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                            ttft = round(first_token_time - start_time, 3)
                            logfire.info("First token emitted | ttft={ttft}s", ttft=ttft)
                        accumulated_answer.append(token_text)
                        yield f"event: token\ndata: {json.dumps({'token': token_text})}\n\n"

                elif mode == "updates":
                    # Track updates from nodes (planner, retriever, responder)
                    for node_name, node_update in payload.items():
                        if isinstance(node_update, dict):
                            if "plan" in node_update and node_update["plan"]:
                                latest_plan = node_update["plan"]
                            if "status" in node_update and node_update["status"]:
                                latest_status = node_update["status"]
                            if "documents" in node_update and node_update["documents"]:
                                latest_sources = node_update["documents"]
                            if "final_answer" in node_update and node_update["final_answer"]:
                                final_answer_from_state = node_update["final_answer"]

                        if node_name in ("planner", "retriever"):
                            logfire.info(
                                "Stage completed: {node_name} | status: {status}",
                                node_name=node_name,
                                status=latest_status,
                            )

            # Emit metadata (thought process, sources, status)
            meta_payload = {
                "question": q,
                "thought_process": latest_plan,
                "status": latest_status,
                "sources": latest_sources,
            }
            yield f"event: metadata\ndata: {json.dumps(meta_payload)}\n\n"

            # Determine final answer
            full_ans = "".join(accumulated_answer)
            if not full_ans and final_answer_from_state:
                full_ans = final_answer_from_state

            total_duration = round(time.perf_counter() - start_time, 3)
            logfire.info(
                "Streaming completed | duration={duration}s | thread={thread_id}",
                duration=total_duration,
                thread_id=thread_id,
            )

            done_payload = {
                "answer": full_ans,
                "status": latest_status,
                "duration": total_duration,
            }
            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

        except Exception as e:
            logfire.error(
                "Streaming failed: {error}",
                error=str(e)
            )

            if isinstance(e, PlannerDecisionError):
                fallback_message = (
                    "I'm sorry, I couldn't determine how to process "
                    "your request. Could you please rephrase it?"
                )
                fallback_status = "Planner could not classify the request."

            else:
                fallback_message = (
                    "I'm sorry, something went wrong while processing "
                    "your request. Please try again."
                )
                fallback_status = "Request processing failed."

            # If no response was streamed, provide a complete fallback.
            # If partial output exists, explain that generation was interrupted.
            if accumulated_answer:
                fallback_message = (
                    "\n\nSorry, I couldn't complete the response. Please try again."
                )

            yield (
                f"event: token\ndata: "
                f"{json.dumps({'token': fallback_message})}\n\n"
            )

            meta_payload = {
                "question": q,
                "thought_process": latest_plan + ["Processing interrupted"],
                "status": fallback_status,
                "sources": latest_sources,
            }

            yield f"event: metadata\ndata: {json.dumps(meta_payload)}\n\n"

            yield (
                f"event: done\ndata: "
                f"{json.dumps({'answer': ''.join(accumulated_answer) + fallback_message, 'status': fallback_status})}\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )