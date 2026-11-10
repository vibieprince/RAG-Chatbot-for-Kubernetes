# Docker Deployment & Production Considerations

## 1. Overview & Topology

The platform supports flexible deployment options ranging from lightweight local development to containerized self-hosted infrastructure.

The core services boundary includes:
- **FastAPI Application (`app.main:app`)**: Serves the REST API and Server-Sent Events on port 8000.
- **Streamlit Application (`ui/app.py`)**: Web user interface on port 8501.
- **LiteLLM Gateway (`docker-compose.yml`)**: OpenAI-compatible LLM routing proxy running on port 4000.
- **Qdrant Vector Database**: Vector storage and similarity search (Qdrant Cloud or local container on port 6333).

---

## 2. Docker Compose Deployment (`docker-compose.yml`)

The provided `docker-compose.yml` orchestrates the LiteLLM proxy gateway:

```yaml
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    container_name: kubernetes-rag-litellm

    command:
      - "--config"
      - "/app/config.yaml"
      - "--port"
      - "4000"

    ports:
      - "127.0.0.1:4000:4000"

    volumes:
      - ./litellm/config.yaml:/app/config.yaml:ro

    env_file:
      - .env

    restart: unless-stopped
```

### Starting the Container
```powershell
docker compose up -d litellm
```

### Checking Container Health
```powershell
docker compose ps
docker compose logs -f litellm
```

---

## 3. Self-Hosting Qdrant Locally

If not using Qdrant Cloud, Qdrant can be hosted locally via Docker:

```powershell
docker run -d \
  --name qdrant-local \
  -p 6333:6333 \
  -v qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant:latest
```

In `.env`, configure:
```ini
QDRANT_CLUSTER_ENDPOINT=http://127.0.0.1:6333
QDRANT_API_KEY=
```

---

## 4. Production Hardening & Recommendations

1. **Reverse Proxy & TLS Termination**: Deploy behind Nginx, Traefik, or an AWS/GCP Ingress controller with SSL termination.
2. **Buffer Disabling for SSE**: When placing an Nginx proxy in front of FastAPI, disable proxy buffering for streaming routes:
   ```nginx
   location /query/stream {
       proxy_pass http://127.0.0.1:8000;
       proxy_set_header Connection '';
       proxy_http_version 1.1;
       chunked_transfer_encoding off;
       proxy_buffering off;
       proxy_cache off;
   }
   ```
   *FastAPI already emits `X-Accel-Buffering: no` on the response header.*
3. **Horizontal Scaling**:
   - The FastAPI backend is stateless; multiple instances can sit behind a round-robin load balancer.
   - For multi-instance memory persistence, replace the local in-memory `MemorySaver` checkpointer with a distributed checkpointer (e.g., Redis or PostgreSQL `PostgresSaver`).
4. **License & Cost Compliance**:
   - All libraries (FastAPI, LangGraph, Qdrant Client, FlashRank, Guardrails AI) use permissive open-source licenses (MIT, Apache 2.0, BSD).
   - Zero mandatory paid SaaS commitments are required.
