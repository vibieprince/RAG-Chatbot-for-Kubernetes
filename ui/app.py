
import os
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

REQUEST_TIMEOUT = (5, 120)

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


def query_backend(prompt, thread_id):
    """
    Send a normal non-streaming request to FastAPI.

    Distinguishes connection failures, HTTP failures,
    invalid responses and backend application errors.
    """

    url = f"{BACKEND_URL}/query"

    payload = {
        "q": prompt,
        "thread_id": thread_id,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "The backend took too long to respond. Please try again."
        )

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot connect to the backend. "
            "Please ensure FastAPI is running."
        )

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Unable to communicate with the backend: {exc}"
        )

    if not response.ok:
        raise RuntimeError(get_backend_error(response))

    try:
        data = response.json()

    except ValueError:
        raise RuntimeError(
            "The backend returned an invalid JSON response."
        )

    if not isinstance(data, dict):
        raise RuntimeError(
            "The backend returned an unexpected response format."
        )

    # Handle application-level errors even when HTTP status is 200.
    if data.get("error"):
        raise RuntimeError(str(data["error"]))

    if data.get("status") == "error":
        raise RuntimeError(
            str(data.get("message", "The request could not be completed."))
        )

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

    st.caption(
        f"Memory ID: {st.session_state.session_id[:8]}"
    )

    st.divider()

    if st.button(
        "🗑️ Clear History & Memory",
        type="primary",
    ):
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
    "Ask questions about Kubernetes, Intel hardware "
    "and enterprise networking."
)


# --------------------------------------------------
# DISPLAY CONVERSATION HISTORY
# --------------------------------------------------

for message in st.session_state.messages:

    avatar = (
        AI_AVATAR
        if message["role"] == "assistant"
        else USER_AVATAR
    )

    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# --------------------------------------------------
# CHAT INPUT AND BACKEND EXECUTION
# --------------------------------------------------

if prompt := st.chat_input("Ask about your documentation..."):

    session_id = st.session_state.session_id

    logfire.info(
        "User chat interaction started: {session_id}",
        session_id=session_id,
    )

    # Display and save user message.
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
    })

    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    # Assistant response.
    with st.chat_message("assistant", avatar=AI_AVATAR):

        answer = None
        sources = []
        thought_process = []

        with st.status(
            "🔍 Agent is thinking...",
            expanded=True,
        ) as status:

            try:
                with logfire.span("Calling RAG Backend"):

                    data = query_backend(
                        prompt=prompt,
                        thread_id=session_id,
                    )

                # Extract response fields.
                answer = data.get("answer")

                if not isinstance(answer, str) or not answer.strip():
                    raise RuntimeError(
                        "The backend completed the request "
                        "but returned an empty answer."
                    )

                sources = data.get("sources") or []
                thought_process = data.get("thought_process") or []

                if not isinstance(sources, list):
                    sources = []

                if not isinstance(thought_process, list):
                    thought_process = []

                # Display execution steps.
                if thought_process:
                    st.markdown("**⚙️ Execution Details**")

                    for step in thought_process:
                        st.write(f"• {step}")

                status.update(
                    label="✅ Answer received",
                    state="complete",
                    expanded=False,
                )

            except RuntimeError as exc:

                answer = str(exc)

                logfire.error(
                    "RAG request failed: {error}",
                    error=str(exc),
                )

                status.update(
                    label="⚠️ Request could not be completed",
                    state="error",
                    expanded=False,
                )

            except Exception as exc:

                answer = (
                    "An unexpected error occurred while processing "
                    "your request. Please try again."
                )

                logfire.error(
                    "Unexpected UI error: {error}",
                    error=str(exc),
                )

                status.update(
                    label="⚠️ Unexpected error",
                    state="error",
                    expanded=False,
                )

        # --------------------------------------------------
        # DISPLAY FINAL ANSWER
        # --------------------------------------------------

        st.markdown(answer)

        # --------------------------------------------------
        # DISPLAY RETRIEVED SOURCES
        # --------------------------------------------------

        if sources:

            with st.expander(
                f"📄 View Retrieved Context ({len(sources)} sources)"
            ):

                for index, source in enumerate(sources, start=1):

                    source_text = normalize_source(source)

                    st.markdown(f"**Source {index}**")
                    st.text(source_text)

                    if index < len(sources):
                        st.divider()

        # --------------------------------------------------
        # SAVE ASSISTANT RESPONSE
        # --------------------------------------------------

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
        })

        logfire.info(
            "Chat cycle completed: {session_id}",
            session_id=session_id,
        )
