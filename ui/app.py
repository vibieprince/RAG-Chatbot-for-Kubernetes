import json
import os
import uuid

import logfire
import requests
import streamlit as st
from dotenv import load_dotenv


# Load environment variables explicitly from the project root.
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=env_path)


# Initialize Logfire.
try:
    token = os.getenv("LOGFIRE_TOKEN")
    if not token:
        print("WARNING: LOGFIRE_TOKEN is empty or not configured.")

    logfire.configure(token=token)
    # logfire.instrument_requests() is intentionally disabled because of
    # the OpenTelemetry MeterProvider issue previously observed on Windows.
    LOGFIRE_STATUS = "Connected & Tracing"
except Exception as e:
    print(f"Logfire Init Error in UI: {e}")
    LOGFIRE_STATUS = f"Standby (Error: {e})"


# Page configuration.
st.set_page_config(
    page_title="Enterprise Agentic RAG",
    page_icon="🤖",
    layout="wide",
)


# Avatars.
AI_AVATAR = "🤖"
USER_AVATAR = "👤"


# Backend configuration.
BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000",
).strip().rstrip("/")

# Make the URL usable even if the environment variable was entered without
# a scheme (for example, 127.0.0.1:8000).
if BACKEND_URL and not BACKEND_URL.startswith(("http://", "https://")):
    BACKEND_URL = f"http://{BACKEND_URL}"

STREAM_URL = f"{BACKEND_URL}/query/stream"


# Session management.
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logfire.info(
        "New User Session Created: {session_id}",
        session_id=st.session_state.session_id,
    )

if "messages" not in st.session_state:
    st.session_state.messages = []


# Sidebar.
with st.sidebar:
    st.title("🧠 Agent OS")
    st.markdown("---")
    st.success(f"Logfire: {LOGFIRE_STATUS}")
    st.info(f"Memory ID: {st.session_state.session_id[:8]}")

    if st.button(
        "🗑️ Clear History & Memory",
        use_container_width=True,
        type="primary",
    ):
        logfire.warning(
            "Memory Wipe Triggered for session: {session_id}",
            session_id=st.session_state.session_id,
        )
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()


# Main chat.
st.title("🤖 Enterprise Agentic Assistant")


# Display existing conversation history.
for message in st.session_state.messages:
    avatar = AI_AVATAR if message["role"] == "assistant" else USER_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


def parse_sse_stream(response):
    """
    Parses a streaming response into (event_type, json_data) pairs.
    """
    current_event = None
    data_lines = []

    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.rstrip("\r\n")
        if not line:
            if current_event or data_lines:
                event_name = current_event or "message"
                payload_str = "\n".join(data_lines)
                try:
                    payload = json.loads(payload_str)
                except Exception:
                    payload = {"raw": payload_str}
                yield event_name, payload
                current_event = None
                data_lines = []
            continue

        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())

    if current_event or data_lines:
        event_name = current_event or "message"
        payload_str = "\n".join(data_lines)
        try:
            payload = json.loads(payload_str)
        except Exception:
            payload = {"raw": payload_str}
        yield event_name, payload


# Chat input and request handling.
if prompt := st.chat_input("Ask about your documentation..."):
    with logfire.span(
        "User Chat Interaction",
        user_query=prompt,
        session_id=st.session_state.session_id,
    ):
        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )

        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar=AI_AVATAR):
            payload = {
                "q": prompt,
                "thread_id": st.session_state.session_id,
            }

            response = None
            try:
                with logfire.span("Calling RAG Backend Streaming Endpoint"):
                    response = requests.post(
                        STREAM_URL,
                        json=payload,
                        stream=True,
                        timeout=(10, 120),
                    )
                    response.raise_for_status()

            except requests.RequestException as e:
                logfire.error(
                    "UI-Backend streaming request failed: {error}",
                    error=str(e),
                )
                st.error(
                    "Unable to reach the RAG backend streaming endpoint. "
                    "Check that FastAPI is running and BACKEND_URL is correct."
                )
                st.stop()

            # Stream tokens into UI
            token_list = []
            metadata_dict = {}
            error_message = None

            def token_generator():
                # nonlocal error_message
                try:
                    for event_type, event_data in parse_sse_stream(response):
                        if event_type == "token":
                            token = event_data.get("token", "")
                            if token:
                                token_list.append(token)
                                yield token
                        elif event_type == "metadata":
                            metadata_dict.update(event_data)
                        elif event_type == "done":
                            pass
                        elif event_type == "error":
                            error_message = event_data.get(
                                "error",
                                "An internal error occurred during generation."
                            )

                            if error_message:
                                token_list.append(error_message)
                                yield error_message
                except Exception as e:
                    logfire.error("Error while reading SSE stream: {error}", error=str(e))
                    error_message = f"Stream interrupted: {e}"

            with logfire.span("Streaming Response Rendering"):
                full_answer = st.write_stream(token_generator())

            if error_message and not full_answer:
                st.error(error_message)
                st.stop()
                with logfire.span("Streaming Response Rendering"):
                    full_answer = st.write_stream(token_generator())

                if not full_answer and error_message:
                    st.markdown(error_message)
                    full_answer = error_message

            # Display reasoning steps in an expander
            steps = metadata_dict.get("thought_process", [])
            if isinstance(steps, list) and steps:
                with st.expander("🔍 View Agent Thought Process", expanded=False):
                    for step in steps:
                        st.write(f"⚙️ {step}")

            # Display retrieved sources
            sources = metadata_dict.get("sources", [])
            if isinstance(sources, list) and sources:
                with st.expander("📄 View Retrieved Context (Sources)", expanded=False):
                    for i, source in enumerate(sources, start=1):
                        if isinstance(source, str):
                            st.markdown(f"**Chunk {i}**")
                            st.info(source)
                        else:
                            st.markdown(f"**Source {i}**")
                            st.write(source)

            # Record final answer in conversation history
            final_text = full_answer if isinstance(full_answer, str) else "".join(token_list)
            if final_text:
                st.session_state.messages.append(
                    {"role": "assistant", "content": final_text}
                )

            logfire.info("Chat cycle completed successfully.")