import logfire
from app.agents.state import AgentState
from app.services.retrieval.qdrant_service import search_enterprise_knowledge
from app.services.retrieval.ranking_service import rerank_documents
from app.security.trust_boundary import sanitize_and_isolate_context

def retrieve_node(state: AgentState):
    """
    Performs vector search, semantic reranking, and trust boundary sanitization
    to neutralize potential indirect prompt injection embedded inside retrieved docs.
    """
    query = state["current_query"]
    
    # Standard Retrieval Logic
    with logfire.span("🔍 Knowledge Retrieval"):
        logfire.info(f"Searching Qdrant for: {query}")
        raw_results = search_enterprise_knowledge(query, limit=15)
        logfire.info(f"Retrieved {len(raw_results)} candidates from Vector DB")
        
        # Apply trust boundary isolation to defend against indirect prompt injection
        sanitized_results = sanitize_and_isolate_context(raw_results)
        doc_contents = [doc['content'] for doc in sanitized_results]
        
        with logfire.span("⚖️ Semantic Reranking"):
            reranked_contents = rerank_documents(query, doc_contents, top_n=5)
            logfire.info("Reranking complete. Kept top 5 most relevant chunks.")
            
        formatted_docs = reranked_contents
    
    return {
        "documents": formatted_docs,
        "status": "Found technical context.",
        "plan": state["plan"] + ["Context Retrieved & Sanitized"]
    }
