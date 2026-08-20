"""
Central configuration for the Supplier Quotation Management system.
Everything reads from environment variables (see .env.example).
The app is designed to run with ZERO keys configured (local/demo mode)
and to upgrade smoothly once you add OpenAI / Azure / SMTP credentials.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ---------------- Paths ----------------
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
VECTOR_INDEX_DIR = DATA_DIR / "vector_index"
DB_DIR = DATA_DIR / "db"
SAMPLE_DATA_DIR = BASE_DIR / "sample_data"

for d in (UPLOADS_DIR, PROCESSED_DIR, VECTOR_INDEX_DIR, DB_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------- OpenAI ----------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
HAS_OPENAI = bool(OPENAI_API_KEY)

# ---------------- Embeddings ----------------
EMBEDDINGS_MODE = os.getenv("EMBEDDINGS_MODE", "local").strip().lower()
LOCAL_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# ---------------- SMTP / Email ----------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Procurement Team")
HAS_SMTP = bool(SMTP_USERNAME and SMTP_PASSWORD)

# ---------------- Storage backend ----------------
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()  # "local" | "azure"
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "rfq-documents")
AZURE_COSMOS_ENDPOINT = os.getenv("AZURE_COSMOS_ENDPOINT", "")
AZURE_COSMOS_KEY = os.getenv("AZURE_COSMOS_KEY", "")
AZURE_COSMOS_DATABASE = os.getenv("AZURE_COSMOS_DATABASE", "quotation_management")
AZURE_COSMOS_CONTAINER = os.getenv("AZURE_COSMOS_CONTAINER", "quotations")

# ---------------- Document parsing ----------------
DOC_PARSER_MODE = os.getenv("DOC_PARSER_MODE", "local").strip().lower()  # "local" | "llamaparse"
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY", "").strip()

# ---------------- Misc ----------------
SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi (हिन्दी)"}
DEFAULT_LANGUAGE = "en"
