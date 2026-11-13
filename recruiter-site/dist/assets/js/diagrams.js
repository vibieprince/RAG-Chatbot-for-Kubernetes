/**
 * MERMAID DIAGRAM CONTROLLER & LIGHT THEME ENGINE
 * Renders real architecture and workflow diagrams locally with expand, collapse, and modal view.
 */

window.RAG_DIAGRAMS = {
  // Pinned light-theme configuration for Mermaid.js
  themeConfig: {
    startOnLoad: false,
    securityLevel: 'loose',
    theme: 'base',
    themeVariables: {
      background: '#FFFFFF',
      primaryColor: '#E8F0FC',
      primaryTextColor: '#202631',
      primaryBorderColor: '#4F83CC',
      lineColor: '#667085',
      secondaryColor: '#F0F3F7',
      secondaryTextColor: '#202631',
      secondaryBorderColor: '#CBD5E1',
      tertiaryColor: '#FFFFFF',
      tertiaryTextColor: '#202631',
      tertiaryBorderColor: '#E3E8EF',
      mainBkg: '#FFFFFF',
      nodeBorder: '#4F83CC',
      clusterBkg: '#F8FAFC',
      clusterBorder: '#CBD5E1',
      edgeLabelBackground: '#FFFFFF',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif',
      fontSize: '13px'
    },
    flowchart: {
      curve: 'basis',
      padding: 16,
      nodeSpacing: 40,
      rankSpacing: 45,
      htmlLabels: true
    },
    sequence: {
      actorMargin: 50,
      actorFontSize: 13,
      actorFontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      actorBorder: '#CBD5E1',
      actorBkg: '#F0F3F7',
      actorTextColor: '#202631',
      noteBkgColor: '#FEF3C7',
      noteBorderColor: '#FDE68A',
      noteTextColor: '#92400E',
      messageColor: '#202631',
      mirrorActors: false
    }
  },

  // 100% verified diagram definitions from repository documentation
  definitions: {
    systemArchitecture: `
flowchart TD
    Client["🖥️ Streamlit UI<br/><code>ui/app.py</code>"] <-->|HTTP POST / SSE Stream| API["⚡ FastAPI Application<br/><code>app/main.py</code>"]

    subgraph SECURITY_GATEWAY ["🛡️ Layer 1: Defense-in-Depth Security Gateway"]
        direction TB
        NORM["Input Normalizer<br/>(NFKC · Zero-Width Stripping · Base64 Extraction)"]
        SIG["Heuristic Signature Detector<br/>(Jailbreaks · Delimiters · Cyber Abuse)"]
        SCOPE["Semantic Policy Engine<br/>(Kubernetes Domain Scope Validator)"]
        ML_ADAPT["ML Jailbreak Adapter<br/>(zhx123/ftrobertallm Isolation)"]
        NORM --> SIG --> SCOPE --> ML_ADAPT
    end

    API --> SECURITY_GATEWAY
    SECURITY_GATEWAY -->|"❌ Block / Refuse"| REFUSAL["Immediate Safe Refusal Stream"] --> Client

    subgraph AGENT_CORE ["🧠 Layer 2: LangGraph Agent & Streaming Engine"]
        direction TB
        PLANNER["🗺️ Planner Node<br/>(Intent Evaluation & Search Formulation)"]
        ROUTER{"Route Decision"}
        RETRIEVER["🔍 Retriever Node<br/>(Vector Search + Trust Boundary + Reranking)"]
        RESPONDER["💬 Responder Node / Streaming LLM<br/>(Prompt Construction & Token Streaming)"]
        CHECKPOINTER[("💾 MemorySaver<br/>(Session History Checkpointing)")]

        PLANNER --> ROUTER
        ROUTER -->|"Technical Query"| RETRIEVER
        ROUTER -->|"Conversational"| RESPONDER
        RETRIEVER --> RESPONDER
        RESPONDER <--> CHECKPOINTER
    end

    SECURITY_GATEWAY -->|"✅ Allow"| PLANNER

    subgraph RETRIEVAL_INFRA ["🔎 Layer 3: Knowledge Retrieval Layer"]
        direction TB
        QDRANT[("🗄️ Qdrant Vector DB<br/>(enterprise_rag collection)")]
        TRUST_BOUND["🛡️ Trust Boundary Sanitizer<br/>(Indirect Prompt Injection Scrubbing)"]
        FLASHRANK["⚡ FlashRank Cross-Encoder<br/>(ms-marco-MiniLM-L-6-v2 ONNX)"]
        QDRANT --> TRUST_BOUND --> FLASHRANK
    end

    RETRIEVER <--> QDRANT
    RETRIEVER --> TRUST_BOUND

    subgraph INFERENCE_GATEWAY ["🌐 Layer 4: LLM Inference Infrastructure"]
        direction TB
        LITELLM["LiteLLM Proxy Gateway<br/>(127.0.0.1:4000/v1)"]
        GROQ_FALLBACK["Direct AsyncGroq Fallback<br/>(api.groq.com)"]
        MODELS["Llama 3.3 70B Versatile / GPT-OSS 20B"]
        LITELLM -->|"Primary Routing"| MODELS
        LITELLM -.->|"If proxy offline"| GROQ_FALLBACK
        GROQ_FALLBACK --> MODELS
    end

    RESPONDER --> INFERENCE_GATEWAY
    INFERENCE_GATEWAY -->|"Server-Sent Events"| Client
`,

    requestLifecycle: `
sequenceDiagram
    autonumber
    actor User as Engineer / User
    participant UI as Streamlit UI (ui/app.py)
    participant API as FastAPI (app/main.py)
    participant Stream as Streaming Pipeline (streaming.py)
    participant Sec as Security Gateway (gateway.py)
    participant Plan as Planner (_run_planner)
    participant Qdrant as Qdrant DB (enterprise_rag)
    participant Rerank as FlashRank Reranker
    participant LLM as LiteLLM / Groq Provider

    User->>UI: Submits Query ("How do I configure Ingress?")
    UI->>API: POST /query/stream {"q": "...", "thread_id": "..."}
    API->>Stream: stream_rag_pipeline(q, thread_id)
    
    Stream-->>UI: event: status {"stage": "security", "message": "Evaluating safety..."}
    Stream->>Sec: evaluate_query(q)
    
    alt Security Violation (BLOCK / REFUSE)
        Sec-->>Stream: SecurityDecision(decision=BLOCK/REFUSE)
        Stream-->>UI: event: security {"decision": "BLOCK", ...}
        Stream-->>UI: event: token {"text": "Refusal statement..."}
        Stream-->>UI: event: done
        UI-->>User: Renders safe refusal notice
    else Security Allowed (ALLOW)
        Sec-->>Stream: SecurityDecision(decision=ALLOW, latency_ms=1.6)
        Stream-->>UI: event: security {"decision": "ALLOW", "latency_ms": 1.6}
        Stream-->>UI: event: status {"stage": "planning", "message": "Analyzing intent..."}
        Stream->>Plan: _run_planner(q, history)
        
        alt Conversational Query
            Plan-->>Stream: "CONVERSATIONAL"
            Stream-->>UI: event: status {"stage": "retrieval", "message": "Skipped retrieval."}
            Stream-->>UI: event: sources {"sources": []}
        else Technical Research Query
            Plan-->>Stream: "Refined search query"
            Stream-->>UI: event: status {"stage": "retrieval", "message": "Searching vector DB..."}
            Stream->>Qdrant: query_points(vector, limit=15)
            Qdrant-->>Stream: 15 candidate chunks
            Note over Stream: Trust Boundary scrubs indirect prompt injection
            Stream->>Rerank: rerank_documents(candidates, top_n=5)
            Rerank-->>Stream: Top 5 high-precision chunks
            Stream-->>UI: event: sources {"sources": ["Chunk 1...", "Chunk 2..."]}
        end
        
        Stream-->>UI: event: status {"stage": "generation", "message": "Synthesizing..."}
        Stream->>LLM: chat.completions.create(prompt, stream=True)
        
        loop Incremental Token Delivery
            LLM-->>Stream: chunk.delta.content
            Stream-->>UI: event: token {"text": "..."}
            UI-->>User: Incremental Markdown rendering
        end
        
        Stream-->>UI: event: done {"status": "Completed successfully"}
        UI-->>User: Stream completed
    end
`,

    securityPipeline: `
flowchart TD
    RawQuery["Raw User Query String"] --> Layer1["Layer 1: Normalizer & De-obfuscator<br/><code>app/security/normalizer.py</code>"]
    
    subgraph L1_OPS ["Normalization Steps"]
        direction TB
        NFKC["Unicode NFKC Normalization"]
        ZW["Zero-Width Character Stripping"]
        B64["Base64 Candidate Extraction & Decoding (length >= 16)"]
        NFKC --> ZW --> B64
    end
    Layer1 --- L1_OPS

    Layer1 --> Layer2["Layer 2: Heuristic Signature Scanner<br/><code>app/security/signatures.py</code>"]
    
    subgraph L2_PATTERNS ["Pattern Classes"]
        direction TB
        P1["Direct Jailbreak (DAN, Ignore Instructions)"]
        P2["Delimiter Injection (ChatML, INST, System XML)"]
        P3["Cyber Attack Operations (Token stealing, etcd wipe)"]
    end
    Layer2 --- L2_PATTERNS

    Layer2 -->|"Signature Match"| Block1["🚨 Immediate Block/Refuse<br/>(Latency < 2ms)"]
    Layer2 -->|"Clean Heuristics"| Layer3["Layer 3: Semantic Policy Engine<br/><code>app/security/classifier.py</code>"]

    subgraph L3_SCOPE ["Scope Verification"]
        direction TB
        POLICY["Kubernetes Technical Scope Validation"]
        PERMIT["Defensive Security Allowed (RBAC, Seccomp)"]
        REFUSE["Off-Topic Refused (Cooking, Poetry)"]
    end
    Layer3 --- L3_SCOPE

    Layer3 -->|"Policy Violation"| Block2["🛡️ Structured Refusal<br/>(Latency < 250ms)"]
    Layer3 -->|"Scope Approved"| Layer4["Layer 4: Context Trust Boundary<br/><code>app/security/trust_boundary.py</code>"]

    subgraph L4_ISOLATION ["Context Sanitization"]
        direction TB
        SCRUB["Strip Indirect Instructions & Malicious Images"]
        BOUNDARY["Enclose in [UNTRUSTED KNOWLEDGE DATA] Delimiters"]
    end
    Layer4 --- L4_ISOLATION

    Layer4 --> SafeInference["✅ Safe LLM Synthesis & Token Streaming"]
`,

    retrievalWorkflow: `
flowchart TD
    UserQuery["User Technical Query<br/>(e.g., 'How to configure Calico CNI?')"] --> EmbedQuery["embed_query()<br/>Dense query vector"]
    
    EmbedQuery --> QdrantSearch["Qdrant query_points()<br/>Collection: enterprise_rag<br/>Limit: 15 candidates"]
    
    QdrantSearch --> RawResults["15 Raw Document Records<br/>(Payload: text, source, score)"]
    
    RawResults --> TrustBoundary["sanitize_and_isolate_context()<br/><code>app/security/trust_boundary.py</code>"]
    
    subgraph TB_OPS ["Trust Boundary Defense"]
        SCRUB["Scrub indirect prompt injection markers"]
        NO_IMG["Omit markdown image links"]
        BLOCKS["Wrap in [UNTRUSTED KNOWLEDGE DATA] tags"]
    end
    TrustBoundary --- TB_OPS
    
    TrustBoundary --> FlashRank["FlashRank Cross-Encoder<br/>(ms-marco-MiniLM-L-6-v2 ONNX)"]
    
    FlashRank --> RankedChunks["Top 5 High-Precision Passages"]
    RankedChunks --> ContextPrompt["Injected into LLM Synthesis Prompt"]
`,

    gatewayFailover: `
flowchart LR
    Caller["Application Request<br/>(_get_async_inference_stream)"] --> PrimaryGateway{"Primary: LiteLLM Proxy<br/>127.0.0.1:4000/v1"}
    
    PrimaryGateway -->|"Reachable"| LiteLLMContainer["LiteLLM Gateway Container<br/>(ghcr.io/berriai/litellm)"]
    PrimaryGateway -->|"Timeout / Offline"| GroqDirect["Direct AsyncGroq Client<br/>(Fallback Provider)"]

    subgraph LITELLM_INTERNALS ["LiteLLM Routing Engine"]
        direction TB
        RAG_PRI["rag-primary<br/>(groq/openai/gpt-oss-120b)"]
        RAG_FALL["rag-fallback<br/>(groq/openai/gpt-oss-20b)"]
        CACHE["Prompt Cache (x-litellm-cache-status)"]
        RAG_PRI -.->|"Failover on error"| RAG_FALL
    end

    LiteLLMContainer --> LITELLM_INTERNALS
    LITELLM_INTERNALS --> CloudGroq["Groq Cloud API<br/>(High-Speed LPU Inference)"]
    GroqDirect --> CloudGroq
`
  },

  // Initialize and render all diagrams on page
  init: function () {
    if (typeof mermaid === 'undefined') {
      console.warn("Mermaid.js library not loaded yet.");
      return;
    }

    try {
      mermaid.initialize(this.themeConfig);
      this.renderAll();
      this.bindControls();
    } catch (e) {
      console.error("Failed to initialize Mermaid:", e);
    }
  },

  // Render each diagram in its container
  renderAll: function () {
    const keys = Object.keys(this.definitions);
    keys.forEach(key => {
      const el = document.getElementById(`mermaid-${key}`);
      if (!el) return;

      const code = this.definitions[key];
      const id = `svg-${key}-${Math.random().toString(36).substr(2, 9)}`;

      mermaid.render(id, code)
        .then(result => {
          el.innerHTML = result.svg;
        })
        .catch(err => {
          console.error(`Error rendering diagram ${key}:`, err);
          el.innerHTML = `<div style="padding: 16px; color: #667085; font-size: 13px; text-align: center;">Diagram preview available in repository documentation.</div>`;
        });
    });
  },

  // Bind Show, Hide, Expand Modal, and Restore controls for every diagram
  bindControls: function () {
    const boxes = document.querySelectorAll('.diagram-box');

    boxes.forEach(box => {
      const diagramKey = box.getAttribute('data-diagram');
      if (!diagramKey) return;

      const stage = box.querySelector('.diagram-stage');
      const toggleBtn = box.querySelector('.btn-toggle-diagram');
      const expandBtn = box.querySelector('.btn-expand-diagram');

      // Toggle Show / Hide
      if (toggleBtn && stage) {
        toggleBtn.addEventListener('click', () => {
          const isCollapsed = stage.classList.contains('collapsed');
          if (isCollapsed) {
            stage.classList.remove('collapsed');
            toggleBtn.innerHTML = `
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 15l-6-6-6 6"/></svg>
              <span>Hide</span>
            `;
          } else {
            stage.classList.add('collapsed');
            toggleBtn.innerHTML = `
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
              <span>Show</span>
            `;
          }
        });
      }

      // Expand to Fullscreen Modal
      if (expandBtn) {
        expandBtn.addEventListener('click', () => {
          this.openModal(diagramKey);
        });
      }
    });

    // Modal Close button & Backdrop click
    const modal = document.getElementById('diagram-modal');
    const closeBtn = document.getElementById('diagram-modal-close');

    if (closeBtn && modal) {
      closeBtn.addEventListener('click', () => {
        this.closeModal();
      });
    }

    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          this.closeModal();
        }
      });
    }

    // Keyboard ESC to close modal
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeModal();
      }
    });
  },

  openModal: function (diagramKey) {
    const modal = document.getElementById('diagram-modal');
    const body = document.getElementById('diagram-modal-svg');
    const title = document.getElementById('diagram-modal-title');
    if (!modal || !body) return;

    const sourceEl = document.getElementById(`mermaid-${diagramKey}`);
    if (sourceEl) {
      body.innerHTML = sourceEl.innerHTML;
    }

    if (title) {
      const titles = {
        systemArchitecture: 'System Architecture Specification',
        requestLifecycle: 'Complete Request Lifecycle Sequence',
        securityPipeline: 'Defense-in-Depth AI Security Pipeline',
        retrievalWorkflow: 'Knowledge Retrieval & FlashRank Cross-Encoder Workflow',
        gatewayFailover: 'LiteLLM Gateway & Provider Failover Topology'
      };
      title.textContent = titles[diagramKey] || 'Architecture Diagram';
    }

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  },

  closeModal: function () {
    const modal = document.getElementById('diagram-modal');
    if (modal) {
      modal.classList.remove('active');
      document.body.style.overflow = '';
    }
  }
};
