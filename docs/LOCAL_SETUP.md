# Local Setup & Quickstart Guide

## 1. Prerequisites
- Python 3.10+
- (Optional) Docker & Docker Compose for containerized LiteLLM / Qdrant
- Free Groq API Key and (Optional) Gemini API Key

---

## 2. Environment Configuration
Copy `.env.example` to `.env` and supply your keys:

```bash
# Vector Database (Qdrant Cloud or Local)
QDRANT_CLUSTER_ENDPOINT=https://your-qdrant-cluster.io
QDRANT_API_KEY=your_qdrant_api_key

# Embeddings
GEMINI_API_KEY=your_gemini_api_key

# Reasoning Engine (Groq Free Tier)
GROQ_API_KEY=your_groq_api_key
GROQ_FALLBACK_API_KEY=your_groq_api_key

# LiteLLM Proxy Gateway
LITELLM_BASE_URL=http://127.0.0.1:4000/v1
LITELLM_MASTER_KEY=sk-local-dev-key
```

---

## 3. Local Installation

```powershell
# Create & activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## 4. Running the Platform

### Step 1: Start LiteLLM Gateway (Optional / Docker)
```powershell
docker compose up -d litellm
```

### Step 2: Start the FastAPI Backend & Web App
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once started:
- **Interactive Chat Interface**: Open [http://localhost:8000/](http://localhost:8000/)
- **Recruiter & Architecture Showcase**: Open [http://localhost:8000/recruiter.html](http://localhost:8000/recruiter.html)
- **FastAPI OpenAPI Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 5. Running the Automated Test Suite

```powershell
$env:PYTHONPATH="."
pytest tests/test_security.py -v
```
