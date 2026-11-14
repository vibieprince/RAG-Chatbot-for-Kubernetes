import os
import json
import uuid
import threading
from typing import Optional, Generator, Dict, Any

import logfire
import requests
import streamlit as st
from dotenv import load_dotenv


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)
load_dotenv(dotenv_path=ENV_PATH)

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

# Public LiteLLM URL for waking up Render service (no master key exposed)
_raw_litellm_url = os.getenv("LITELLM_URL") or os.getenv("LITELLM_BASE_URL", "https://kubernetes-rag-litellm.onrender.com").rstrip("/")
if _raw_litellm_url.endswith("/v1"):
    _raw_litellm_url = _raw_litellm_url[:-3]
LITELLM_LIVELINESS_URL = f"{_raw_litellm_url}/health/liveliness"

# Connection timeout / streaming read timeout (seconds).
# 90s connect timeout ensures Render free-tier cold starts do not abort prematurely.
CONNECT_TIMEOUT = int(os.getenv("BACKEND_CONNECT_TIMEOUT", "90"))
STREAM_TIMEOUT = (CONNECT_TIMEOUT, None)

AI_AVATAR = "🤖"
USER_AVATAR = "👤"


# --------------------------------------------------
# LOGFIRE INITIALIZATION
# --------------------------------------------------

try:
    logfire_token = os.getenv("LOGFIRE_TOKEN")

    if logfire_token:
        logfire.configure(token=logfire_token)
        LOGFIRE_STATUS = "Connected & Tracing"
    else:
        LOGFIRE_STATUS = "Not configured"

except Exception as exc:
    LOGFIRE_STATUS = "Standby"
    print(f"Logfire initialization failed: {exc}")


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Enterprise Agentic RAG",
    page_icon="🤖",
    layout="wide",
)


# --------------------------------------------------
# PARALLEL SERVICE WAKE-UP
# --------------------------------------------------

def trigger_litellm_wakeup_background(request_id: str) -> None:
    """
    Initiates a non-blocking background GET request to LiteLLM's public
    /health/liveliness endpoint. Does NOT expose or send LiteLLM master key.
    Runs in a detached daemon thread so it never blocks Streamlit UI or query submission.
    """
    def _worker():
        try:
            requests.get(
                LITELLM_LIVELINESS_URL,
                timeout=5.0,
                headers={
                    "User-Agent": "Streamlit-ParallelWakeupClient/2.0",
                    "X-Request-ID": request_id,
                },
            )
        except Exception:
            # Cold-start ping: connection drops or timeouts are expected while waking
            pass

    threading.Thread(
        target=_worker,
        name=f"litellm-wakeup-{request_id}",
        daemon=True,
    ).start()


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def normalize_source(source):
    """Convert a retrieved source into readable text."""
    if isinstance(source, str):
        return source
    if isinstance(source, dict):
        return (
            source.get("content")
            or source.get("text")
            or str(source)
        )
    return str(source)


def get_backend_error(response):
    """Extract a meaningful error from an HTTP response."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            return (
                payload.get("detail")
                or payload.get("error")
                or payload.get("message")
                or f"Backend returned HTTP {response.status_code}."
            )
    except ValueError:
        pass
    return f"Backend returned HTTP {response.status_code}."


def _parse_sse_line(line: str):
    """
    Parse a single SSE line.
    Returns (event_type, data_dict) or (None, None).
    """
    line = line.strip()
    if line.startswith("data:"):
        return "data", line[5:].strip()
    if line.startswith("event:"):
        return "event", line[6:].strip()
    return None, None


def stream_query(prompt: str, thread_id: str, request_id: Optional[str] = None):
    """
    POST to /query/stream and consume the SSE response incrementally.
    Passes X-Request-ID and X-LiteLLM-Wakeup-Triggered headers.
    Yields structured event dicts: {"type": str, "data": dict}
    """
    url = f"{BACKEND_URL}/query/stream"
    payload = {"q": prompt, "thread_id": thread_id}
    headers = {
        "Accept": "text/event-stream",
        "X-Request-ID": request_id or f"req-{uuid.uuid4().hex[:12]}",
        "X-LiteLLM-Wakeup-Triggered": "true",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=STREAM_TIMEOUT,
            headers=headers,
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "The backend took too long to connect. If Render is waking up from sleep, please try again in a moment."
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to the backend. Please ensure the FastAPI service is active."
        )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Unable to communicate with the backend: {exc}")

    if not response.ok:
        raise RuntimeError(get_backend_error(response))

    # --- Consume SSE stream ---
    current_event_type = "message"
    pending_data: list[str] = []

    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue

        # SSE frames are separated by blank lines
        if raw_line == "":
            if pending_data:
                raw_data = " ".join(pending_data)
                try:
                    parsed = json.loads(raw_data)
                except json.JSONDecodeError:
                    parsed = {"raw": raw_data}
                yield {"type": current_event_type, "data": parsed}
            current_event_type = "message"
            pending_data = []
            continue

        key, value = _parse_sse_line(raw_line)
        if key == "event":
            current_event_type = value
        elif key == "data":
            pending_data.append(value)


def query_backend_sync(prompt: str, thread_id: str, request_id: Optional[str] = None) -> dict:
    """
    Fallback: non-streaming request to /query.
    Used only when streaming is unavailable.
    """
    url = f"{BACKEND_URL}/query"
    payload = {"q": prompt, "thread_id": thread_id}
    headers = {
        "X-Request-ID": request_id or f"req-{uuid.uuid4().hex[:12]}",
        "X-LiteLLM-Wakeup-Triggered": "true",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(CONNECT_TIMEOUT, 180),
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "The backend took too long to respond. Please try again."
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to the backend. Please ensure FastAPI is running."
        )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Unable to communicate with the backend: {exc}")

    if not response.ok:
        raise RuntimeError(get_backend_error(response))

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("The backend returned an invalid JSON response.")

    if not isinstance(data, dict):
        raise RuntimeError("The backend returned an unexpected response format.")

    if data.get("error"):
        raise RuntimeError(str(data["error"]))

    if data.get("status") == "error":
        raise RuntimeError(str(data.get("message", "The request could not be completed.")))

    return data


# --------------------------------------------------
# SESSION MANAGEMENT
# --------------------------------------------------

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logfire.info(
        "New user session created: {session_id}",
        session_id=st.session_state.session_id,
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

# Deduplication tracker: prevents duplicate wake-ups and query submissions
if "processed_actions" not in st.session_state:
    st.session_state.processed_actions = set()


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:
    st.title("🧠 Agent OS")
    st.divider()

    if LOGFIRE_STATUS == "Connected & Tracing":
        st.success(f"Logfire: {LOGFIRE_STATUS}")
    else:
        st.info(f"Logfire: {LOGFIRE_STATUS}")

    st.caption(f"Memory ID: {st.session_state.session_id[:8]}")
    st.divider()

    if st.button("🗑️ Clear History & Memory", type="primary"):
        logfire.info("User cleared conversation history.")
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.processed_actions = set()
        st.rerun()

    st.caption(f"Backend: {BACKEND_URL}")
    st.caption(f"LiteLLM: {LITELLM_LIVELINESS_URL}")


# --------------------------------------------------
# MAIN CHAT INTERFACE
# --------------------------------------------------

st.title("🤖 Enterprise Agentic Assistant")
st.caption(
    "Ask questions about Kubernetes, container orchestration, and cluster administration.\n Services are hosted on Render free tier; parallel wake-up automatically warms LiteLLM and FastAPI simultaneously."
)
st.markdown(
    """
    <div style="
        background-color: var(--secondary-background-color);
        color: var(--text-color);
        border-left: 4px solid var(--primary-color);
        border-radius: 8px;
        padding: 10px 14px;
        margin: 8px 0 18px 0;
        font-size: 0.84rem;
        line-height: 1.5;
    ">
        <strong>Free-tier deployment notice:</strong>
        This project is hosted on Render's free service tier. After a period
        of inactivity, services may spin down and need some time to wake up.
        The first request can take longer than usual.
        <strong>If no response appears after 1 minute, refresh this page
        and submit your question again.</strong>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# DISPLAY CONVERSATION HISTORY
# --------------------------------------------------

for message in st.session_state.messages:
    avatar = AI_AVATAR if message["role"] == "assistant" else USER_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# --------------------------------------------------
# CHAT INPUT AND STREAMING EXECUTION
# --------------------------------------------------

if prompt := st.chat_input("Ask about Kubernetes..."):

    session_id = st.session_state.session_id
    action_token = f"{session_id}:{len(st.session_state.messages)}:{prompt.strip()}"

    # Deduplication check: prevent duplicate submission for the same user interaction
    if action_token in st.session_state.processed_actions:
        st.stop()

    st.session_state.processed_actions.add(action_token)

    # Correlation ID for this interaction
    request_id = f"req-{uuid.uuid4().hex[:12]}"

    # Phase 2: Parallel Wake-up — Trigger background GET to LiteLLM /health/liveliness
    # Runs in a separate daemon thread; does NOT block UI or delay query submission
    trigger_litellm_wakeup_background(request_id)

    logfire.info(
        "User chat interaction started: {session_id} | RequestID: {request_id}",
        session_id=session_id,
        request_id=request_id,
        prompt_snippet=prompt[:60],
    )

    # Display and save user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    # --- Assistant response ---
    with st.chat_message("assistant", avatar=AI_AVATAR):

        answer_parts: list[str] = []
        sources: list = []
        thought_process: list = []
        had_error = False

        # Progress display while security/planning/retrieval stages run
        status_placeholder = st.empty()
        # Token streaming target
        answer_placeholder = st.empty()
        # Sources displayed after generation
        sources_placeholder = st.empty()

        try:
            with logfire.span("SSE Streaming RAG Backend", request_id=request_id):

                collecting_tokens = False

                for event in stream_query(prompt=prompt, thread_id=session_id, request_id=request_id):
                    etype = event["type"]
                    edata = event["data"]

                    if etype == "status":
                        stage = edata.get("stage", "")
                        message_text = edata.get("message", "")
                        stage_icons = {
                            "security": "🛡️",
                            "planning": "🧠",
                            "retrieval": "🔍",
                            "generation": "✍️",
                            "blocked": "🚫",
                        }
                        icon = stage_icons.get(stage, "⚙️")
                        status_placeholder.caption(f"{icon} {message_text}")

                    elif etype == "security":
                        decision = edata.get("decision", "UNKNOWN")
                        latency = edata.get("latency_ms", 0)
                        if decision == "ALLOW":
                            status_placeholder.caption(
                                f"✅ Security passed ({latency:.0f}ms)"
                            )
                        else:
                            category = edata.get("category", "")
                            status_placeholder.caption(
                                f"🛡️ Security: {decision} — {category}"
                            )

                    elif etype == "sources":
                        raw_sources = edata.get("sources", [])
                        if isinstance(raw_sources, list):
                            sources = raw_sources

                    elif etype == "token":
                        text_chunk = edata.get("text", "")
                        if text_chunk:
                            collecting_tokens = True
                            answer_parts.append(text_chunk)
                            # Render incremental markdown
                            answer_placeholder.markdown("".join(answer_parts))

                    elif etype == "done":
                        thought_process = edata.get("thought_process", [])
                        if not sources:
                            sources = edata.get("sources", [])
                        status_placeholder.caption("✅ Response complete")

                    elif etype == "error":
                        code = edata.get("code", "ERROR")
                        msg = edata.get("message", "An error occurred.")
                        status_placeholder.caption(f"⚠️ {code}")
                        if not answer_parts:
                            answer_placeholder.error(msg)
                            answer_parts.append(f"**Error:** {msg}")
                        had_error = True

        except RuntimeError as exc:
            had_error = True
            error_msg = str(exc)
            logfire.error("SSE stream failed: {error}", error=error_msg, request_id=request_id)
            status_placeholder.caption("⚠️ Request failed")
            answer_placeholder.error(error_msg)
            answer_parts = [f"**Error:** {error_msg}"]

        except Exception as exc:
            had_error = True
            logfire.error("Unexpected UI error: {error}", error=str(exc), request_id=request_id)
            status_placeholder.caption("⚠️ Unexpected error")
            answer_placeholder.error(
                "An unexpected error occurred. Please try again."
            )
            answer_parts = ["An unexpected error occurred. Please try again."]

        # Clear the status caption once done (keep answer)
        if not had_error:
            status_placeholder.empty()

        # --- Display retrieved sources ---
        if sources:
            with sources_placeholder.expander(
                f"📄 View Retrieved Context ({len(sources)} sources)"
            ):
                for index, source in enumerate(sources, start=1):
                    source_text = normalize_source(source)
                    st.markdown(f"**Source {index}**")
                    st.text(source_text)
                    if index < len(sources):
                        st.divider()

        # --- Save to session history ---
        final_answer = "".join(answer_parts)
        st.session_state.messages.append({
            "role": "assistant",
            "content": final_answer,
        })

        logfire.info(
            "Chat cycle completed: {session_id} | RequestID: {request_id}",
            session_id=session_id,
            request_id=request_id,
        )
