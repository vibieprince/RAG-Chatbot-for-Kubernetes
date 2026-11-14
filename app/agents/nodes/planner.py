import re
from typing import List, Dict, Any, Optional
import logfire

from app.agents.state import AgentState
from app.gateway.client import get_langchain_llm, is_groq_fallback_configured
from app.gateway.manager import gateway_manager


class PlannerUnavailableError(RuntimeError):
    """Raised when both primary and fallback planner routes are unavailable."""
    pass


# Strict list of basic conversational greetings
GREETING_PHRASES = {
    "hi", "hii", "hiii", "hello", "helloo", "hey", "heyy", "hey there",
    "greetings", "good morning", "good afternoon", "good evening", "good day",
    "how are you", "how are you doing", "how are you today", "who are you",
    "what are you", "what can you do", "help", "thanks", "thank you"
}

CONVERSATIONAL_WORDS = {
    "hi", "hii", "hiii", "hello", "helloo", "hey", "heyy", "there",
    "greetings", "good", "morning", "afternoon", "evening", "day",
    "how", "are", "you", "doing", "today", "who", "what", "can",
    "do", "help", "assistant", "bot", "please", "thanks", "thank",
    "is", "it", "going", "up", "a", "an", "the", "with"
}

K8S_TECHNICAL_TERMS = {
    "k8s", "kubernetes", "pod", "pods", "deployment", "deployments",
    "service", "services", "ingress", "kubectl", "cluster", "clusters",
    "namespace", "namespaces", "helm", "docker", "container", "containers",
    "rbac", "etcd", "configmap", "configmaps", "secret", "secrets",
    "daemonset", "daemonsets", "statefulset", "statefulsets", "cni", "csi",
    "kubelet", "kube-proxy", "node", "nodes", "crashloopbackoff", "flannel",
    "calico", "cilium", "prometheus", "hpa", "vpa", "networkpolicy", "pvc", "pv"
}


def is_conversational_greeting(text: str) -> bool:
    """
    Deterministically identifies unambiguous greetings that should never trigger retrieval.
    Guarantees no false positives on technical queries.
    """
    if not text:
        return True

    # Strip punctuation and lowercase
    cleaned = re.sub(r"[^\w\s]", "", text).strip().lower()
    if not cleaned:
        return True

    # If it contains any Kubernetes technical terms, it is NOT a simple greeting
    words = set(cleaned.split())
    if words.intersection(K8S_TECHNICAL_TERMS):
        return False

    # Check exact phrase
    if cleaned in GREETING_PHRASES:
        return True

    # Check short sentences (<= 8 words) where all words are conversational/greeting tokens
    if len(words) <= 8 and words.issubset(CONVERSATIONAL_WORDS):
        return True

    return False


def execute_planner(
    user_message: str,
    history_messages: Optional[List[Dict[str, str]]] = None,
    force_fallback: bool = False,
    request_id: Optional[str] = None,
) -> str:
    """
    Executes intent planning using primary gateway or direct Groq fallback.
    - If user message is a greeting, guarantees CONVERSATIONAL without search.
    - If technical query, refines the search query.
    - If primary planner fails, attempts verified direct Groq fallback.
    - If both fail, raises PlannerUnavailableError for technical queries.
    """
    history_messages = history_messages or []

    # Fast path: check unambiguous greeting before attempting network calls
    if is_conversational_greeting(user_message):
        logfire.info("Greeting identified deterministically: routing to CONVERSATIONAL", query=user_message)
        return "CONVERSATIONAL"

    history_str = ""
    for msg in history_messages[:-1]:
        role = "User" if msg.get("role") == "user" else "Assistant"
        history_str += f"{role}: {msg.get('content', '')}\n"

    prompt = f"""You are an intelligent Assistant Planner for an Enterprise Kubernetes system.
Analyze the conversation history and the latest user message.

CONVERSATION HISTORY:
{history_str}

LATEST MESSAGE:
"{user_message}"

Task:
1. If the latest message is a greeting (hi, hello) or a question that can be answered using ONLY the conversation history above (e.g., "what is my name"), respond with 'CONVERSATIONAL'.
2. If it is a technical question about Kubernetes, container orchestration, systems engineering, or defensive cluster hardening that requires fresh documentation, output a refined search query.

Output ONLY 'CONVERSATIONAL' or the search query."""

    primary_err: Optional[Exception] = None

    # Route 1: LiteLLM Primary Gateway (if ready and not forced to fallback)
    if not force_fallback and (gateway_manager.is_cached_ready() or not is_groq_fallback_configured()):
        try:
            with logfire.span("🧠 Planner Decision (Primary Gateway)"):
                llm = get_langchain_llm(feature="planner", force_fallback=False, request_id=request_id)
                response = llm.invoke(prompt)
                content_str = response.content if isinstance(response.content, str) else str(response.content)
                decision = content_str.strip()
                logfire.info(f"Planner intent identified via Primary Gateway: {decision}")
                return decision
        except Exception as exc:
            primary_err = exc
            logfire.warning(
                "Primary gateway planner execution failed: {err}. Attempting Groq fallback.",
                err=str(exc)
            )

    # Route 2: Verified Direct Groq Fallback
    if is_groq_fallback_configured():
        try:
            with logfire.span("🧠 Planner Decision (Direct Groq Fallback)"):
                fallback_llm = get_langchain_llm(feature="planner", force_fallback=True, request_id=request_id)
                response = fallback_llm.invoke(prompt)
                content_str = response.content if isinstance(response.content, str) else str(response.content)
                decision = content_str.strip()
                logfire.info(f"Planner intent identified via Groq Fallback: {decision}")
                return decision
        except Exception as fallback_exc:
            logfire.error(
                "Groq fallback planner execution failed: {err}",
                err=str(fallback_exc)
            )

    # Both routes failed:
    # 1. If it was a greeting that somehow bypassed fast-path, return CONVERSATIONAL
    if is_conversational_greeting(user_message):
        return "CONVERSATIONAL"

    # 2. For technical questions, DO NOT silently route arbitrary input to retrieval!
    raise PlannerUnavailableError(
        f"Planner service unavailable: primary route ({primary_err}) and Groq fallback failed."
    )


def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    LangGraph Planner Node for synchronous agent graph.
    """
    messages = state.get("messages", [])
    user_message = messages[-1]["content"] if messages else ""

    decision = execute_planner(user_message, messages)

    if decision == "CONVERSATIONAL":
        return {
            "current_query": "CONVERSATIONAL",
            "status": "Handling conversationally (using memory)...",
            "plan": ["Intent: Conversational/Memory", "Retrieval: Skipped"]
        }

    return {
        "current_query": decision,
        "status": f"Technical research needed. Searching for: {decision}",
        "plan": ["Intent: Technical", f"Search Term: {decision}"]
    }
