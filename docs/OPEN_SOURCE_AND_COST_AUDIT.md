# Open Source & Cost Audit

## Executive Summary
This document provides a comprehensive audit of all dependencies, runtime models, and storage infrastructure for the **Enterprise Agentic RAG for Kubernetes** platform.

Every core component has been selected to ensure that:
1. **No mandatory paid services** are required.
2. The entire system can be run completely self-hosted or using free-tier / open-source alternatives.
3. Model weights and library licenses comply with enterprise standards.

---

## 1. Component Audit Table

| Component | Library / Model | License | Deployment Mode | API Key Required? | Cost / Tier | Hardware Requirements |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Vector Database** | Qdrant | Apache 2.0 | Self-Hostable Docker / Cloud Free Tier | Yes (if cloud), No (if local) | Free (Forever OSS) | 1 CPU core, 512MB RAM |
| **Reranker** | FlashRank (`ms-marco-MiniLM-L-6-v2`) | Apache 2.0 | Local In-Process ONNX | No | Free (Local CPU) | ~150MB RAM, CPU only |
| **Agent Orchestration** | LangGraph & LangChain | MIT | Python In-Process | No | Free (Open Source) | Negligible |
| **LLM Proxy Gateway** | LiteLLM | Apache 2.0 | Self-Hostable Docker | No | Free (Open Source) | 1 CPU core, 256MB RAM |
| **Web API Backend** | FastAPI & Uvicorn | MIT / BSD | Python In-Process | No | Free (Open Source) | Negligible |
| **Frontend UI** | Vanilla HTML5 / Modern CSS / ES6 JS | MIT | Static Files via FastAPI | No | Free (Zero Build Tools) | Browser only |
| **Security Gateway** | Heuristics + Llama-3.1-8B-Instant | MIT (Code) / Llama 3 Community (Weights) | Local Regex + Groq Free Tier / Local Ollama | Optional (if using Groq API) | Free Tier (30 RPM free on Groq) | CPU for heuristics; 4GB VRAM if local SLM |
| **Dense Embeddings** | Gemini Embedding 2 / SentenceTransformers | Apache 2.0 (`all-mpnet-base-v2`) | Google Free Tier + Local CPU Fallback | Optional (if using Gemini) | Free Tier / Free Local | CPU only for fallback (~400MB RAM) |
| **Primary Inference** | Llama 3.3 70B Versatile / GPT-OSS 20B | Llama 3 Community / MIT | Groq Inference API / Ollama Local | Optional (if using Groq) | Free Tier / Self-hostable | Cloud Free Tier or GPU if local |

---

## 2. Distinction Between Free-Tier APIs and Permanent Open Source
- **Hosted Free-Tier Providers (e.g. Groq, Google AI Studio)**: Excellent for zero-cost rapid development and live demonstration, but quotas are subject to provider policies.
- **Self-Hostable Fallbacks**:
  - Vector search: Qdrant can run via `docker run -p 6333:6333 qdrant/qdrant`.
  - Embeddings: `SentenceTransformers` (`all-mpnet-base-v2`) activates automatically when no external API key is present.
  - Inference: LiteLLM can route transparently to a local Ollama instance (`ollama run llama3`) with zero code changes.

---

## 3. License Compliance
- All client and server libraries are governed by permissive licenses (MIT, Apache 2.0, BSD-3-Clause).
- No viral copyleft licenses (GPLv3/AGPLv3) are bundled in the core backend.
