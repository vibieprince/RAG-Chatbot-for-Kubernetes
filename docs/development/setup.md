# Local Development Setup Guide

## 1. Prerequisites

- **Python**: Version `3.10` or higher (tested with Python 3.10.11 on Windows).
- **Git**: For version control.
- **Docker & Docker Compose** (Optional): For running the LiteLLM proxy gateway locally.
- **API Keys**:
  - **Groq API Key**: (Free tier) For fast LLM inference and semantic security classification.
  - **Qdrant Endpoint & API Key**: Qdrant Cloud free tier or self-hosted local instance.
  - **Gemini API Key** (Optional): For high-dimensional Gemini embeddings (`gemini-embedding-2-preview`). If omitted, the local `sentence-transformers` fallback (`all-mpnet-base-v2`) activates automatically.
  - **Pydantic Logfire Token** (Optional): For distributed tracing.

---

## 2. Environment Setup

### Step 1: Clone and Create Virtual Environment
```powershell
# Clone the repository
git clone <repository_url>
cd "RAG Chatbot for Kubernetes"

# Create a virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate on Linux/macOS
source venv/bin/activate
```

### Step 2: Install Python Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy the template `.env.example` to `.env`:
```powershell
cp .env.example .env
```

Populate `.env` with your credentials:
```ini
GROQ_API_KEY=gsk_your_groq_api_key
GROQ_FALLBACK_API_KEY=gsk_your_groq_api_key

QDRANT_CLUSTER_ENDPOINT=https://your-cluster-url.qdrant.tech
QDRANT_API_KEY=your_qdrant_api_key

# Optional: Gemini embeddings (leave blank to use local fallback)
GEMINI_API_KEY=your_gemini_key

# Optional: LiteLLM Gateway
LITELLM_BASE_URL=http://127.0.0.1:4000/v1
LITELLM_MASTER_KEY=sk-local-dev-key

# UI and Backend URL
BACKEND_URL=http://127.0.0.1:8000
```

---

## 3. Running the Services

### Option A: Running with LiteLLM Gateway via Docker Compose
```powershell
# 1. Start the LiteLLM proxy container
docker compose up -d litellm

# 2. Start the FastAPI backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 3. Start the Streamlit chat frontend (in a separate terminal)
streamlit run ui/app.py --server.port 8501
```

### Option B: Running Fully In-Process (Direct Groq Fallback)
If Docker is not installed or you prefer running without containers, the backend automatically detects when LiteLLM is offline and falls back directly to Groq inference:
```powershell
# 1. Start the FastAPI backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Start the Streamlit frontend
streamlit run ui/app.py --server.port 8501
```

---

## 4. Accessing the Application

- **Streamlit Chat UI**: Open [http://localhost:8501/](http://localhost:8501/)
- **FastAPI Interactive Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs)
- **FastAPI Health Check**: Open [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **FastAPI Agent Graph Visual**: Open [http://localhost:8000/api/graph](http://localhost:8000/api/graph)
