# Document Ingestion & Vector Indexing Pipeline

## 1. Overview
The ingestion pipeline processes technical documentation across multiple formats (PDF, HTML, DOCX, PPTX, TXT), decomposes documents into semantic chunks, generates dense vector representations, and indexes them into Qdrant vector database under the `enterprise_rag` collection.

---

## 2. Ingestion Architecture Flow

```mermaid
flowchart LR
    Docs["Input Documents\n(PDF, HTML, DOCX, PPTX, TXT)"] --> Loaders["Document Loaders\napp/ingestion/loaders/"]
    Loaders --> Extracted["Normalized Plain Text"]
    Extracted --> Chunker["Semantic Chunker\napp/ingestion/chunking/splitter.py"]
    Chunker --> Chunks["Chunked Passages\n(~800 chars, 150 overlap)"]
    Chunks --> LocalStore[("Local Processed Cache\nprocessed_data/*.json")]
    Chunks --> Embedder["Embedding Service\napp/services/retrieval/embedding.py"]
    Embedder --> Vectors["Dense Vectors (3072-dim / 768-dim)"]
    Vectors --> Qdrant[("Qdrant Vector DB\nenterprise_rag Collection")]
```

---

## 3. Preservation of Ingestion Architecture
- **Non-destructive indexing**: Existing collections, vector points, and embedding dimensions are completely preserved.
- **Dual-mode Embedder**:
  - Primary: Google Gemini `gemini-embedding-2-preview` (3072 dimensions) with exponential backoff for quota limits.
  - Fallback: Local `sentence-transformers` (`all-mpnet-base-v2`, 768 dimensions) for offline/air-gapped operations.
