
import os
import json
import uuid

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

# Connection timeout / streaming read timeout (seconds).
# The read timeout is None so the SSE stream can stay open as long as needed.
CONNECT_TIMEOUT = int(os.getenv("BACKEND_CONNECT_TIMEOUT", "10"))
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

    Returns (event_type, data_dict) or (None, None) if the line
    is not a complete data frame.
    """
    line = line.strip()
    if line.startswith("data:"):
        return "data", line[5:].strip()
    if line.startswith("event:"):
        return "event", line[6:].strip()
    return None, None


def stream_query(prompt: str, thread_id: str):
    """
    POST to /query/stream and consume the SSE response incrementally.

    Yields structured event dicts: {"type": str, "data": dict}
    Raises RuntimeError on connection/HTTP failure.
    """
    url = f"{BACKEND_URL}/query/stream"
    payload = {"q": prompt, "thread_id": thread_id}

    try:
        response = requests.post(
            url,
            json=payload,
            stream=True,
            timeout=STREAM_TIMEOUT,
            headers={"Accept": "text/event-stream"},
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "The backend took too long to connect. Please ensure FastAPI is running."
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to the backend. Please ensure FastAPI is running."
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
            # Dispatch accumulated event
            if pending_data:
                raw_data = " ".join(pending_data)
                try:
                    parsed = json.loads(raw_data)
                except json.JSONDecodeError:
                    parsed = {"raw": raw_data}
                yield {"type": current_event_type, "data": parsed}
            # Reset
            current_event_type = "message"
            pending_data = []
            continue

        key, value = _parse_sse_line(raw_line)
        if key == "event":
            current_event_type = value
        elif key == "data":
            pending_data.append(value)
        # Ignore comment lines (starting with ':') and other fields


def query_backend_sync(prompt: str, thread_id: str) -> dict:
    """
    Fallback: non-streaming request to /query.
    Used only when streaming is unavailable.
    """
    url = f"{BACKEND_URL}/query"
    payload = {"q": prompt, "thread_id": thread_id}

    try:
        response = requests.post(
            url,
            json=payload,
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
        st.rerun()

    st.caption(f"Backend: {BACKEND_URL}")


# --------------------------------------------------
# MAIN CHAT INTERFACE
# --------------------------------------------------

st.title("🤖 Enterprise Agentic Assistant")
st.caption(
    "Ask questions about Kubernetes, container orchestration, and cluster administration."
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

    logfire.info(
        "User chat interaction started: {session_id}",
        session_id=session_id,
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
            with logfire.span("SSE Streaming RAG Backend"):

                collecting_tokens = False

                for event in stream_query(prompt=prompt, thread_id=session_id):
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
            logfire.error("SSE stream failed: {error}", error=error_msg)
            status_placeholder.caption("⚠️ Request failed")
            answer_placeholder.error(error_msg)
            answer_parts = [f"**Error:** {error_msg}"]

        except Exception as exc:
            had_error = True
            logfire.error("Unexpected UI error: {error}", error=str(exc))
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
            "Chat cycle completed: {session_id}",
            session_id=session_id,
        )
