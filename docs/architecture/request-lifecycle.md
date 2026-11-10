# Complete Request Lifecycle

## 1. Overview

This document details the exact sequence of operations that occur when a user submits a query to the **Enterprise Kubernetes Agentic RAG Platform**. The platform supports two operational paths:
1. **Streaming Endpoint (`POST /query/stream`)**: Primary production path delivering real-time Server-Sent Events (SSE).
2. **Synchronous Endpoint (`POST /query`)**: Preserved for backwards compatibility and batch evaluation integrations.

---

## 2. End-to-End Streaming Query Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as Engineer / User
    participant UI as Streamlit UI (ui/app.py)
    participant API as FastAPI (app/main.py)
    participant Stream as Stream Pipeline (app/services/streaming.py)
    participant Sec as Security Gateway (app/security/gateway.py)
    participant Plan as Planner (_run_planner)
    participant Qdrant as Qdrant DB (enterprise_rag)
    participant Rerank as FlashRank Reranker (ms-marco-MiniLM)
    participant LLM as LiteLLM / Groq Provider

    User->>UI: Submits Query ("How do I configure Ingress?")
    UI->>API: POST /query/stream {"q": "...", "thread_id": "..."}
    API->>Stream: stream_rag_pipeline(q, thread_id)
    
    %% Stage 1: Security
    Stream-->>UI: event: status {"stage": "security", "message": "Evaluating query safety..."}
    Stream->>Sec: evaluate_query(q)
    Note over Sec: Normalizes NFKC, extracts base64, scans signatures & semantic scope
    
    alt Security Violation Detected (BLOCK / REFUSE)
        Sec-->>Stream: SecurityDecision(decision=BLOCK/REFUSE, category=...)
        Stream-->>UI: event: security {"decision": "BLOCK", "category": ...}
        Stream-->>UI: event: status {"stage": "blocked", "message": "Request blocked: ..."}
        Stream-->>UI: event: token {"text": "Refusal statement..."}
        Stream-->>UI: event: done {"status": "Blocked by security policy"}
        UI-->>User: Displays refusal message & warning banner
    else Security Clean (ALLOW)
        Sec-->>Stream: SecurityDecision(decision=ALLOW, category=BENIGN)
        Stream-->>UI: event: security {"decision": "ALLOW", "latency_ms": 1.2}
        
        %% Stage 2: Planning
        Stream-->>UI: event: status {"stage": "planning", "message": "Analyzing query intent..."}
        Stream->>Plan: _run_planner(q, conversation_history)
        
        alt Intent is Conversational
            Plan-->>Stream: "CONVERSATIONAL"
            Stream-->>UI: event: status {"stage": "retrieval", "message": "Conversational query - retrieval skipped."}
            Stream-->>UI: event: sources {"sources": []}
        else Intent is Technical Research
            Plan-->>Stream: "Refined search query"
            
            %% Stage 3: Retrieval & Reranking
            Stream-->>UI: event: status {"stage": "retrieval", "message": "Searching knowledge base..."}
            Stream->>Qdrant: query_points(vector, limit=15)
            Qdrant-->>Stream: 15 candidate chunks
            Note over Stream: Trust Boundary cleans indirect prompt injections
            Stream->>Rerank: rerank_documents(query, candidates, top_n=5)
            Rerank-->>Stream: Top 5 high-precision chunks
            Stream-->>UI: event: status {"stage": "retrieval", "message": "Retrieved 5 verified chunks."}
            Stream-->>UI: event: sources {"sources": ["Chunk 1...", "Chunk 2..."]}
        end
        
        %% Stage 4: Generation
        Stream-->>UI: event: status {"stage": "generation", "message": "Synthesizing response..."}
        Stream->>LLM: chat.completions.create(prompt, stream=True)
        
        loop Incremental Token Delivery
            LLM-->>Stream: chunk.delta.content ("Kubernetes ")
            Stream-->>UI: event: token {"text": "Kubernetes "}
            UI-->>User: Incremental Markdown rendering
        end
        
        Stream-->>UI: event: done {"status": "Completed successfully", "thought_process": [...]}
        UI-->>User: Finalizes response, hides status spinner, updates memory
    end
```

---

## 3. Detailed Step Breakdown

### Step 1: Client Request Ingestion
- User enters text in the Streamlit web interface (`ui/app.py`).
- The client constructs an HTTP payload:
  ```json
  {
    "q": "How to scale deployment replicas in Kubernetes?",
    "thread_id": "session_a8f9c10e"
  }
  ```
- The client issues an HTTP `POST` to `/query/stream` with `Accept: text/event-stream`.
- A streaming connection is established using `requests.post(..., stream=True)` with indefinite read timeout to support long answers.

### Step 2: Gate 1 — Security Evaluation
- Before initializing any agent planning or vector search, the query enters `app.security.gateway.security_gateway.evaluate_query`.
- **Normalization**: Zero-width unicode characters are stripped, NFKC decomposition applied, and base64 chunks decoded.
- **Signatures**: Regex heuristics scan for system prompt extraction, jailbreaks, delimiters, and offensive cyber abuse.
- **Scope Classification**: The semantic policy engine validates whether the inquiry falls within Kubernetes, container operations, or defensive security.
- **Short-Circuit Refusal**: If flagged:
  1. An `event: security` payload is yielded with category and detector metadata.
  2. An `event: token` payload is emitted carrying the safe response text.
  3. An `event: done` payload terminates the stream.
  4. Vector search and LLM synthesis are completely bypassed (0 LLM inference tokens spent).

### Step 3: Gate 2 — Intent Planning
- Clean queries advance to planning.
- In `_run_planner`, the LLM assesses conversation history alongside the current user query.
- Output:
  - `"CONVERSATIONAL"`: Conversational greetings, politeness, or memory inquiries (e.g., "What was my name?"). Knowledge retrieval is skipped.
  - Refined technical query string: Technical inquiries about Kubernetes, CNI, storage, Pods, or YAML configurations.

### Step 4: Gate 3 — Knowledge Retrieval & Trust Boundary
- For technical queries:
  1. Dense vector embedding generated via `embed_query`.
  2. Modern Qdrant `query_points` API retrieves the top 15 candidate documents.
  3. **Trust Boundary Isolation**: Retrieved text runs through `sanitize_and_isolate_context()`, stripping indirect prompt injection patterns and markdown exfiltration images.
  4. **FlashRank Reranking**: The cross-encoder re-scores the 15 candidates against the query and returns the top 5 most semantically relevant chunks.
  5. The sanitized chunks are yielded to the frontend via `event: sources`.

### Step 5: Gate 4 — Live Token Synthesis
- Context and conversation history are combined into the technical synthesis prompt (`_build_responder_prompt`).
- An asynchronous streaming completion request is initiated via `_get_async_inference_stream()`:
  - First attempts the LiteLLM proxy gateway (`http://127.0.0.1:4000/v1`).
  - If unreachable, falls back seamlessly to direct `AsyncGroq`.
- Live token fragments are yielded over SSE as `event: token`.
- On completion, `event: done` delivers the thought process summary and session identifiers.
