# Configuration & Environment Reference

## 1. Overview

Application configuration is loaded from environment variables and `.env` files via `pydantic` and `python-dotenv`.

Centralized settings reside in `app/config.py` under the `Settings` class, accessed via the global `settings` instance.

---

## 2. Environment Variables Reference Table

| Variable Name | Module | Type | Default Value | Required? | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GROQ_API_KEY` | `app/config.py` | String (SecretStr) | None | **Yes** | Primary API key for Groq LPU inference (Llama 3.3). |
| `GROQ_FALLBACK_API_KEY` | `app/config.py` | String | None | No | Secondary API key for Groq fallback routing. |
| `GROQ_MODEL` | `app/config.py` | String | `llama-3.3-70b-versatile` | No | Default model name for Groq inference. |
| `QDRANT_CLUSTER_ENDPOINT` | `app/config.py` | String (URL) | None | **Yes** | Qdrant vector database URL (e.g. `https://xxx.qdrant.tech` or `http://localhost:6333`). |
| `QDRANT_API_KEY` | `app/config.py` | String | None | Conditional | API key for Qdrant Cloud. Not required for local self-hosted Qdrant. |
| `QDRANT_COLLECTION` | `app/config.py` | String | `enterprise_rag` | No | Vector collection name storing document embeddings. |
| `GEMINI_API_KEY` | `app/config.py` | String (SecretStr) | None | No | Google Gemini API key for `gemini-embedding-2-preview`. If omitted, local fallback is used. |
| `GEMINI_DIM` | `app/config.py` | Integer | `3072` | No | Vector dimensions for Gemini embeddings. |
| `FALLBACK_DIM` | `app/config.py` | Integer | `768` | No | Vector dimensions for `all-mpnet-base-v2` fallback embeddings. |
| `BATCH_SIZE` | `app/config.py` | Integer | `50` | No | Chunk batch size for embedding generation. |
| `LITELLM_BASE_URL` | `app/config.py` | String (URL) | `http://127.0.0.1:4000/v1` | No | Address of the LiteLLM proxy gateway. |
| `LITELLM_MASTER_KEY` | `app/config.py` | String | None | No | Master authorization key for LiteLLM gateway. |
| `BACKEND_URL` | `ui/app.py` | String (URL) | `http://127.0.0.1:8000` | No | Base URL of the FastAPI backend for the Streamlit UI. |
| `BACKEND_CONNECT_TIMEOUT` | `ui/app.py` | Integer | `10` | No | Seconds to wait when opening connection to FastAPI. |
| `LOGFIRE_TOKEN` | `app/main.py`, `ui/app.py` | String | None | No | Authentication token for Pydantic Logfire tracing. |
| `LANGSMITH_TRACING` | `app/config.py` | Boolean string | `"true"` | No | Enables LangChain tracing to LangSmith. |
| `LANGSMITH_API_KEY` | `app/config.py` | String | None | No | API key for LangSmith project tracking. |
| `LANGSMITH_PROJECT` | `app/config.py` | String | `"rag_scale_test"` | No | Project name within LangSmith dashboard. |
| `LANGSMITH_ENDPOINT` | `app/config.py` | String (URL) | `https://api.smith.langchain.com` | No | Endpoint URL for LangSmith tracing ingestion. |

---

## 3. Configuration Safety & Secrets Management

- **No Hardcoded Credentials**: No production keys or secrets are committed to git.
- **Pydantic SecretStr**: Secrets (`GROQ_API_KEY`, `GEMINI_API_KEY`) are wrapped in Pydantic `SecretStr` objects to prevent accidental leaking in terminal logs, stack traces, or serialization dumps.
- **Environment Template**: `.env.example` provides empty placeholders and documented defaults.
