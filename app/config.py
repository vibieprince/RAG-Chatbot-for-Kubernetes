import os
from dotenv import load_dotenv
from pydantic import SecretStr
# Load environment variables
load_dotenv()

class Settings:
    # --- GEMINI EMBEDDINGS ---
    google_api_key = os.getenv("GEMINI_API_KEY")
    GEMINI_API_KEY: SecretStr | None = SecretStr(google_api_key) if google_api_key else None

    # --- VECTOR DB (QDRANT) ---
    QDRANT_URL = os.getenv("QDRANT_CLUSTER_ENDPOINT")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_COLLECTION = "enterprise_rag"

    # --- REASONING ENGINE (GROQ) ---
    groq_key = os.getenv("GROQ_API_KEY")
    GROQ_API_KEY: SecretStr | None = SecretStr(groq_key) if groq_key else None
    GROQ_MODEL = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_API_KEY = os.getenv("GROQ_FALLBACK_API_KEY")

    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
    GEMINI_DIM = int(os.getenv("GEMINI_DIM", "3072"))
    FALLBACK_DIM = int(os.getenv("FALLBACK_DIM", "768"))
    
    # --- OBSERVABILITY ---
    LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true")
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "rag_scale_test")
    LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

    # --- LITELLM GATEWAY ---
    LITELLM_BASE_URL = os.getenv(
        "LITELLM_BASE_URL",
        "http://127.0.0.1:4000/v1"
    )

    LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY")

# Apply LangChain environment variables for automatic tracing
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGSMITH_TRACING", "true")
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "rag_scale_test")
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

settings = Settings()