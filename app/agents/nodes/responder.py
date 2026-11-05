import logfire
from langgraph.types import StreamWriter

from app.agents.state import AgentState
from app.gateway.client import get_langchain_llm, extract_cache_status


# Initialize the responder through the centralized LiteLLM gateway with streaming enabled.
llm = get_langchain_llm(feature="responder", streaming=True)


def _extract_text(content) -> str:
    """Safely extract text from LangChain message content."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    text_parts.append(text)

        return "\n".join(text_parts)

    return str(content)


def generate_node(state: AgentState, writer: StreamWriter = None):
    """
    Synthesizes a response using documentation context and conversation history.
    All LLM requests are routed through the LiteLLM Proxy.
    Supports incremental token streaming via LangGraph StreamWriter when available.
    """

    query = state["current_query"]

    history_str = ""
    for msg in state["messages"][:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_msg = state["messages"][-1]["content"] if state["messages"] else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating conversational response using memory.")

        prompt = f"""
        You are a friendly and helpful Enterprise AI Assistant.
        Answer the user's latest message using the CONVERSATION HISTORY below.

        CONVERSATION HISTORY:
        {history_str}

        LATEST MESSAGE:
        "{user_msg}"
        """

    else:
        logfire.info("Generating technical RAG response.")

        max_context_chars = 25000
        full_context = ""

        for doc in state["documents"]:
            if len(full_context) + len(doc) < max_context_chars:
                full_context += doc + "\n\n"
            else:
                logfire.warning("Context truncated to fit Groq TPM limits.")
                break

        prompt = f"""
        You are a Senior Technical Architect.
        Answer the question using the TECHNICAL CONTEXT provided.

        TECHNICAL CONTEXT:
        {full_context}

        CONVERSATION HISTORY:
        {history_str}

        USER QUESTION:
        "{user_msg}"
        """

    with logfire.span("✍️ LLM Synthesis"):
        try:
            accumulated_chunks = []
            full_response = None

            # Stream chunks from LiteLLM Proxy
            for chunk in llm.stream(prompt):
                full_response = chunk if full_response is None else full_response + chunk
                chunk_text = _extract_text(chunk.content)
                if chunk_text:
                    accumulated_chunks.append(chunk_text)
                    if writer is not None:
                        writer(chunk_text)

            content = "".join(accumulated_chunks)
            if not content and full_response is not None:
                content = _extract_text(full_response.content)

            # Cache metadata is best-effort; LiteLLM may not expose it
            # in the LangChain response metadata.
            cache_status = extract_cache_status(full_response)
            is_cache_hit = cache_status == "HIT"

            if is_cache_hit:
                logfire.info("⚡ LiteLLM Gateway Cache Hit.")
                plan_update = state["plan"] + ["Cache: Hit ⚡"]
                status = "Cache hit — instant response."

            else:
                logfire.info(
                    f"Response synthesised via LiteLLM. "
                    f"Cache status: {cache_status}"
                )
                plan_update = state["plan"]
                status = "Response generated."

            return {
                "final_answer": content,
                "status": status,
                "plan": plan_update,
                "messages": [
                    {"role": "assistant", "content": content}
                ]
            }

        except Exception as e:
            logfire.error(f"LLM Generation failed: {e}")
            raise