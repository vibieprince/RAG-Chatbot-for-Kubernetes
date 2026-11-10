# System Architecture & Technical Specification

## 1. Architectural Overview & Design Principles

The **Enterprise Kubernetes Agentic RAG Platform** is an enterprise-oriented technical assistant designed for container orchestration, cluster administration, and defensive security. 

The architecture moves away from naive, single-prompt RAG tutorials to an engineered, modular platform adhering to these core principles:

1. **Defense-in-Depth AI Security**: Multi-tier security boundaries prevent prompt injection, jailbreaks, and destructive cyber abuse before queries touch agent reasoning or vector storage.
2. **True End-to-End Streaming**: Live Server-Sent Events (SSE) transport model tokens directly to the user interface with single-generation guarantees.
3. **Agentic Context Routing**: LangGraph state machine dynamically differentiates conversational queries from deep technical questions requiring documentation retrieval.
4. **Two-Stage Hybrid Retrieval**: Dense vector similarity search on Qdrant paired with local CPU cross-encoder reranking via FlashRank (`ms-marco-MiniLM-L-6-v2`).
5. **Gateway Resilience & Fallbacks**: Unified OpenAI-compatible routing via LiteLLM with transparent fallbacks to direct Groq provider inference.
6. **Observability by Design**: Distributed tracing and span instrumentation powered by Pydantic Logfire across every execution boundary.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    Client["🖥️ Streamlit UI\n(ui/app.py)"] <-->|HTTP POST / SSE Stream| API["⚡ FastAPI Application\n(app/main.py)"]

    subgraph SECURITY_GATEWAY ["🛡️ Layer 1: Defense-in-Depth Security Gateway"]
        direction TB
        NORM["Input Normalizer\n(Unicode NFKC · Zero-Width Stripping · Base64 Extraction)"]
        SIG["Heuristic Signature Detector\n(Jailbreaks · Delimiters · Cyber Abuse)"]
        SCOPE["Semantic Policy Engine\n(Domain Scope Validator)"]
        ML_ADAPT["ML Jailbreak Adapter\n(zhx123/ftrobertallm Isolation)"]
        
        NORM --> SIG --> SCOPE --> ML_ADAPT
    end

    API --> SECURITY_GATEWAY
    SECURITY_GATEWAY -->|"❌ Block / Refuse"| REFUSAL["Immediate Safe Refusal Stream"] --> Client

    subgraph AGENT_CORE ["🧠 Layer 2: LangGraph Agent & Streaming Engine"]
        direction TB
        PLANNER["🗺️ Planner Node\n(Intent Evaluation & Search Formulation)"]
        ROUTER{"Route Decision"}
        RETRIEVER["🔍 Retriever Node\n(Vector Search + Trust Boundary + Reranking)"]
        RESPONDER["💬 Responder Node / Streaming LLM\n(Prompt Construction & Token Streaming)"]
        CHECKPOINTER[("💾 MemorySaver\n(Session History Checkpointing)")]

        PLANNER --> ROUTER
        ROUTER -->|Technical Query| RETRIEVER
        ROUTER -->|Conversational| RESPONDER
        RETRIEVER --> RESPONDER
        RESPONDER <--> CHECKPOINTER
    end

    SECURITY_GATEWAY -->|"✅ Allow"| PLANNER

    subgraph RETRIEVAL_INFRA ["🔎 Layer 3: Knowledge Retrieval Layer"]
        direction TB
        QDRANT[("🗄️ Qdrant Vector DB\n(enterprise_rag collection)")]
        TRUST_BOUND["🛡️ Trust Boundary Sanitizer\n(Indirect Prompt Injection Scrubbing)"]
        FLASHRANK["⚡ FlashRank Cross-Encoder\n(ms-marco-MiniLM-L-6-v2 ONNX)"]

        QDRANT --> TRUST_BOUND --> FLASHRANK
    end

    RETRIEVER <--> QDRANT
    RETRIEVER --> TRUST_BOUND

    subgraph INFERENCE_GATEWAY ["🌐 Layer 4: LLM Inference Infrastructure"]
        direction TB
        LITELLM["LiteLLM Proxy Gateway\n(127.0.0.1:4000/v1)"]
        GROQ_FALLBACK["Direct AsyncGroq Fallback\n(api.groq.com)"]
        MODELS["Llama 3.3 70B Versatile / GPT-OSS 20B"]

        LITELLM -->|Primary Routing| MODELS
        LITELLM -.->|If proxy offline| GROQ_FALLBACK
        GROQ_FALLBACK --> MODELS
    end

    RESPONDER --> INFERENCE_GATEWAY
    INFERENCE_GATEWAY -->|Server-Sent Events| Client

    subgraph OBSERVABILITY ["📡 Layer 5: Observability & Monitoring"]
        LOGFIRE["🔥 Pydantic Logfire\n(Distributed Spans & Metrics)"]
        LANGSMITH["🦜 LangSmith\n(Agent Graph Step Traces)"]
    end

    API -.-> LOGFIRE
    AGENT_CORE -.-> LANGSMITH
```

---

## 3. Verified Component Boundaries & Responsibilities

### A. Presentation Layer (`ui/app.py`)
- **Technology**: Streamlit.
- **Responsibility**: Provides interactive chat interface, consumes Server-Sent Events from `/query/stream`, renders live token markdown incrementally, surfaces security audit decisions, and provides collapsible inspection of retrieved sources.
- **State Management**: Generates and preserves UUID `session_id` in `st.session_state` to link multi-turn conversations.

### B. Application & API Entrypoint (`app/main.py`)
- **Technology**: FastAPI, Uvicorn, Pydantic.
- **Responsibility**: Serves REST and streaming endpoints:
  - `POST /query/stream`: Primary SSE streaming endpoint.
  - `POST /query`: Synchronous execution endpoint.
  - `GET /api/health`: Health and feature status.
  - `GET /api/graph`: Returns Mermaid PNG diagram of the compiled LangGraph workflow.
- **Static Files**: Pre-configured static file mount.

### C. Streaming Orchestration Pipeline (`app/services/streaming.py`)
- **Technology**: Python `asyncio`, Server-Sent Events, `AsyncOpenAI`, `AsyncGroq`.
- **Responsibility**: Coordinates the asynchronous generator lifecycle:
  - Dispatches synchronous components (`evaluate_query`, `_run_planner`, `_run_retriever`) via `loop.run_in_executor()`.
  - Streams structured SSE frames (`status`, `security`, `sources`, `token`, `done`, `error`).
  - Handles client cancellations and network aborts cleanly.
  - Ensures a single LLM generation call, avoiding redundant token generation.

### D. Security & Guardrails Layer (`app/security/`)
- **Technology**: Guardrails AI, Regex, SLM Classifier (`app/security/classifier.py`).
- **Responsibility**: Enforces four-layer defense-in-depth:
  1. `normalizer.py`: Unicode NFKC normalization, zero-width stripping, base64 payload extraction.
  2. `signatures.py`: Regex pattern matching for jailbreaks, system prompt extractions, delimiters, and offensive cyber abuse.
  3. `classifier.py`: Semantic domain scope enforcement via Groq SLM with local heuristic fallback.
  4. `trust_boundary.py`: Neutralizes indirect prompt injection in retrieved document passages.

### E. Agent Orchestration Core (`app/agents/`)
- **Technology**: LangGraph (`StateGraph`), LangChain, `MemorySaver`.
- **Responsibility**:
  - `planner.py`: Analyzes conversation history and decides whether a query is conversational or requires knowledge retrieval.
  - `retriever.py`: Coordinates vector search, context sanitization, and reranking.
  - `responder.py`: Synthesizes final response for synchronous invocations with cache inspection.
  - `graph.py`: Compiles the state graph with memory checkpointing.

### F. Retrieval & Reranking Layer (`app/services/retrieval/`)
- **Technology**: Qdrant Client, FlashRank (`ms-marco-MiniLM-L-6-v2`), Gemini Embeddings, SentenceTransformers.
- **Responsibility**:
  - `embedding.py`: Probes Gemini embeddings (`gemini-embedding-2-preview`, 3072-dim) with automatic fallback to local CPU `sentence-transformers` (`all-mpnet-base-v2`, 768-dim).
  - `qdrant_service.py`: Performs vector similarity queries using Qdrant's modern `query_points` API.
  - `ranking_service.py`: Re-scores candidates using local ONNX cross-encoder reranking.

### G. Gateway & Inference Layer (`app/gateway/`, `litellm/`)
- **Technology**: LiteLLM Proxy Docker container, OpenAI SDK, Groq SDK.
- **Responsibility**:
  - `litellm/config.yaml`: Defines model routing (`rag-primary` to `rag-fallback`), retries, and master keys.
  - `app/gateway/client.py`: Provides `get_langchain_llm()` for LangGraph and extracts cache hit headers.
  - Direct async Groq fallback in `streaming.py` when LiteLLM is not running.

### H. Ingestion Subsystem (`app/ingestion/`)
- **Technology**: `pypdf`, `beautifulsoup4`, `python-docx`, `python-pptx`, LangChain text splitters.
- **Responsibility**: Universal file parser extracting text, chunking text into ~800-character passages, saving JSON metadata in `processed_data/`, and upserting points into Qdrant.

---

## 4. User Query Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Engineer / User
    participant UI as Streamlit UI (ui/app.py)
    participant API as FastAPI (app/main.py)
    participant Stream as Streaming Engine (app/services/streaming.py)
    participant Sec as Security Gateway (app/security/gateway.py)
    participant Plan as Planner (_run_planner)
    participant Ret as Qdrant + FlashRank
    participant LLM as LiteLLM / Groq

    User->>UI: Submits query ("Explain Pod autoscaling")
    UI->>API: POST /query/stream {"q": "...", "thread_id": "..."}
    API->>Stream: stream_rag_pipeline(query, thread_id)
    
    Stream-->>UI: event: status (stage="security")
    Stream->>Sec: evaluate_query(query)
    Note over Sec: Normalize NFKC, check base64, scan signatures & domain scope
    
    alt Security Refusal
        Sec-->>Stream: SecurityDecision(decision=BLOCK/REFUSE)
        Stream-->>UI: event: security (Decision details)
        Stream-->>UI: event: token (Safe refusal message)
        Stream-->>UI: event: done
        UI-->>User: Renders refusal notice
    else Security Allowed
        Sec-->>Stream: SecurityDecision(decision=ALLOW)
        Stream-->>UI: event: security (ALLOW, Latency)
        Stream-->>UI: event: status (stage="planning")
        Stream->>Plan: Evaluate intent & conversation history
        
        alt Conversational Query
            Plan-->>Stream: "CONVERSATIONAL"
            Stream-->>UI: event: status (retrieval skipped)
            Stream-->>UI: event: sources (empty)
        else Technical Research Query
            Plan-->>Stream: "Refined search query"
            Stream-->>UI: event: status (stage="retrieval")
            Stream->>Ret: Vector search (limit=15) + Trust Boundary + FlashRank (top 5)
            Ret-->>Stream: Top 5 sanitized document passages
            Stream-->>UI: event: sources (5 passages)
        end
        
        Stream-->>UI: event: status (stage="generation")
        Stream->>LLM: chat.completions.create(stream=True)
        loop Token Delivery
            LLM-->>Stream: chunk.delta.content
            Stream-->>UI: event: token ({"text": "..."})
            UI-->>User: Incremental Markdown rendering
        end
        Stream-->>UI: event: done (Summary & plan)
    end
```

---

## 5. Streaming Lifecycle & Data Flow

```mermaid
flowchart TD
    Start(["Client Initiates POST /query/stream"]) --> S1["Yield event: status (stage=security)"]
    S1 --> SecEval["Async ThreadPool: security_gateway.evaluate_query()"]
    
    SecEval --> SecCheck{"Decision == ALLOW?"}
    
    SecCheck -->|No| SecBlocked["Yield event: security (Decision details)\nYield event: status (stage=blocked)\nYield event: token (Refusal message)\nYield event: done (status=Blocked)"]
    SecBlocked --> StreamEnd(["Stream Terminated"])
    
    SecCheck -->|Yes| SecPass["Yield event: security (ALLOW, latency)\nYield event: status (stage=planning)"]
    SecPass --> PlanEval["Async ThreadPool: _run_planner()"]
    
    PlanEval --> IntentCheck{"Intent == CONVERSATIONAL?"}
    
    IntentCheck -->|Yes| ConvRoute["Yield event: status (retrieval skipped)\nYield event: sources (empty)"]
    IntentCheck -->|No| TechRoute["Yield event: status (stage=retrieval)\nAsync ThreadPool: Qdrant query_points(15)\nAsync ThreadPool: sanitize_and_isolate_context()\nAsync ThreadPool: FlashRank rerank_documents(top_n=5)\nYield event: sources (5 verified chunks)"]
    
    ConvRoute --> GenStage["Yield event: status (stage=generation)"]
    TechRoute --> GenStage
    
    GenStage --> LLMCall["_get_async_inference_stream()\nTry LiteLLM Proxy -> Fallback Direct AsyncGroq"]
    
    LLMCall --> TokenLoop{"Tokens Available in Stream?"}
    TokenLoop -->|Yes| YieldToken["Yield event: token (text=chunk)"] --> TokenLoop
    TokenLoop -->|No / Stream Complete| DoneEvent["Yield event: done (thread_id, plan, sources)"]
    DoneEvent --> StreamEnd
    
    LLMCall -.->|Exception Raised| ErrorEvent["Yield event: error (code, message)"] --> StreamEnd
```

---

## 6. Knowledge Ingestion Pipeline Diagram

```mermaid
flowchart TD
    RawFiles["Input Technical Documentation\n(DATA/true_data & DATA/noisy_data)"] --> Scanner["run_universal_ingestion()\n(app/ingestion/processor.py)"]
    
    Scanner --> TypeRouter{"File Extension Router"}
    
    TypeRouter -->|.pdf| PDFP["PDF Parser (pypdf / pdfplumber)"]
    TypeRouter -->|.html, .htm| HTMLP["HTML Parser (BeautifulSoup4)"]
    TypeRouter -->|.docx| DOCXP["DOCX Parser (python-docx)"]
    TypeRouter -->|.pptx| PPTXP["PPTX Parser (python-pptx)"]
    TypeRouter -->|.txt| TXTP["Text Parser (Python UTF-8)"]
    
    PDFP & HTMLP & DOCXP & PPTXP & TXTP --> CleanText["Normalized Extracted Text"]
    
    CleanText --> Splitter["RecursiveCharacterTextSplitter\n(chunk_size=800, overlap=150)"]
    
    Splitter --> Chunks["Chunked Document Passages"]
    
    Chunks --> LocalSave["Save Local JSON Cache\n(processed_data/<source>/<file>.json)"]
    
    Chunks --> Embedder["embed_texts(chunks)\n(app/services/retrieval/embedding.py)"]
    
    Embedder --> ProbeEmbed{"Active Embedding Model"}
    ProbeEmbed -->|Primary| Gemini["Gemini Embedding 2 Preview\n(3072 dimensions)"]
    ProbeEmbed -->|Fallback| LocalST["all-mpnet-base-v2\n(768 dimensions)"]
    
    Gemini & LocalST --> VectorBatch["Dense Vector Records with Payload"]
    
    VectorBatch --> QdrantUpsert["QdrantClient.upsert()\nCollection: enterprise_rag"]
```

---

## 7. Security Validation Pipeline Diagram

```mermaid
flowchart TD
    InputQuery["User Input Query String"] --> Layer1["Layer 1: Normalizer & De-obfuscator\n(app/security/normalizer.py)"]
    
    subgraph L1 ["Layer 1 Operations"]
        NFKC["Unicode NFKC Normalization"]
        ZERO_WIDTH["Strip Zero-Width & Directional Characters"]
        B64_DECODE["Extract & Decode Base64 Candidates (length >= 16)"]
        NFKC --> ZERO_WIDTH --> B64_DECODE
    end
    Layer1 --- L1

    Layer1 --> Layer2["Layer 2: Heuristic Signature Validator\n(app/security/signatures.py)"]
    
    subgraph L2 ["Layer 2 Detection Patterns"]
        P_DAN["Direct Jailbreak / DAN Persona / Ignore Rules"]
        P_DELIM["Prompt Delimiter Injection (ChatML, INST, XML)"]
        P_CYBER["Offensive Cyber Abuse (Token Exfiltration, etcd wipe)"]
    end
    Layer2 --- L2

    Layer2 -->|Match Found| FastRefusal["Immediate Decision: BLOCK / REFUSE\nLatency < 2ms"]
    
    Layer2 -->|Clean Heuristics| Layer3["Layer 3: Semantic Policy & Domain Engine\n(app/security/classifier.py)"]
    
    subgraph L3 ["Layer 3 Semantic Rules"]
        ALLOW_K8S["Permit: Kubernetes Administration & Defensive Hardening"]
        REFUSE_OFF["Refuse: Off-Topic (Cooking, Poetry, Entertainment)"]
        FALLBACK_HEUR["Fallback: Deterministic Heuristics if SLM Offline"]
    end
    Layer3 --- L3

    Layer3 -->|Policy Violation| SemanticRefusal["Decision: REFUSE / BLOCK\nStructured Refusal Statement"]
    
    Layer3 -->|Scope Approved| Layer4["Layer 4: Retrieved Context Trust Boundary\n(app/security/trust_boundary.py)"]
    
    subgraph L4 ["Layer 4 Sanitization"]
        SCRUB_INJ["Scrub Indirect Prompt Injection in Docs"]
        STRIP_IMG["Neutralize Exfiltration Markdown Images"]
        WRAP_DATA["Wrap Passages in [UNTRUSTED KNOWLEDGE DATA] Delimiters"]
    end
    Layer4 --- L4

    Layer4 --> PassSafe["Decision: ALLOW\nQuery Passed to Agent Planning"]
```

---

## 8. LLM Gateway & Provider Routing Flow

```mermaid
flowchart LR
    Caller["Application Request\n(_get_async_inference_stream)"] --> PrimaryGateway{"LiteLLM Proxy\n127.0.0.1:4000/v1"}
    
    PrimaryGateway -->|Reachable| LiteLLMContainer["LiteLLM Gateway Container\n(ghcr.io/berriai/litellm)"]
    PrimaryGateway -->|Connection Timeout / Offline| GroqDirect["Direct AsyncGroq Client\n(Fallback Provider)"]

    subgraph LITELLM_INTERNALS ["LiteLLM Routing Engine"]
        direction TB
        RAG_PRI["rag-primary\n(groq/openai/gpt-oss-120b)"]
        RAG_FALL["rag-fallback\n(groq/openai/gpt-oss-20b)"]
        CACHE["In-Memory / Redis Prompt Cache"]
        RAG_PRI -.->|Failover on error| RAG_FALL
    end

    LiteLLMContainer --> LITELLM_INTERNALS
    LITELLM_INTERNALS --> CloudGroq["Groq Cloud API\n(LPU High-Speed Inference)"]
    GroqDirect --> CloudGroq
```

---

## 9. Error Handling & Failure Boundaries

| Subsystem | Potential Failure Mode | Built-in Mitigation & Recovery |
| :--- | :--- | :--- |
| **Security Gateway** | SLM classifier rate limit or connection timeout | Falls back to deterministic local keyword heuristic classifier (`_heuristic_fallback`). |
| **Security Gateway** | Upstream Hugging Face model config mismatch in `DetectJailbreak` | Safely caught by `MLJailbreakAdapter` and fails open to remaining active heuristic and semantic layers. |
| **Vector DB** | Qdrant unreachable or collection empty | `search_enterprise_knowledge` logs error to Logfire and returns empty list `[]`; agent proceeds without context. |
| **Reranker** | FlashRank ONNX model initialization error | Falls back to original Qdrant cosine similarity ordering. |
| **LLM Gateway** | LiteLLM Docker container offline | Seamlessly falls back to direct `AsyncGroq` inference. |
| **Streaming** | Client closes browser or aborts connection | Captures `asyncio.CancelledError`, cancels thread tasks, and cleanly closes socket. |
| **Streaming** | Mid-generation model disconnection | Emits structured `event: error` frame and closes stream without crashing application. |

---

## 10. Logging & Observability Topology

- **Pydantic Logfire**: Orchestrates distributed tracing across modules. Captures security gateway evaluation latency, planning decisions, Qdrant retrieval candidate counts, reranking durations, and LLM synthesis latency.
- **LangSmith**: Captures fine-grained cyclic state graph executions, state transformations, and node transitions when `LANGSMITH_TRACING=true`.
