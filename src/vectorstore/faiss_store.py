"""
Builds and queries a FAISS vector index over all parsed RFQ/quotation text,
so the query bot can do retrieval-augmented answers.

Embeddings:
  - EMBEDDINGS_MODE=local  -> sentence-transformers, multilingual (EN+HI), free, no key
  - EMBEDDINGS_MODE=openai -> OpenAI embeddings (needs OPENAI_API_KEY), better quality
"""
from pathlib import Path
from typing import List, Dict, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

import config

_embeddings_singleton = None


def get_embeddings():
    """Lazily builds and caches the embeddings model (local or OpenAI)."""
    global _embeddings_singleton
    if _embeddings_singleton is not None:
        return _embeddings_singleton

    if config.EMBEDDINGS_MODE == "openai" and config.HAS_OPENAI:
        from langchain_openai import OpenAIEmbeddings
        _embeddings_singleton = OpenAIEmbeddings(
            api_key=config.OPENAI_API_KEY, model="text-embedding-3-small"
        )
    else:
        # Local, multilingual (works for Hindi + English), no API key required.
        from langchain_community.embeddings import HuggingFaceEmbeddings
        _embeddings_singleton = HuggingFaceEmbeddings(
            model_name=config.LOCAL_EMBEDDING_MODEL
        )
    return _embeddings_singleton


def documents_from_parsed(parsed_records: List[Dict]) -> List[Document]:
    """
    parsed_records: list of {"raw_text": str, "source": str, "file_type": str,
                              "supplier_name": Optional[str], ...}
    Splits each into chunks and wraps as LangChain Documents with metadata.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    docs: List[Document] = []
    for rec in parsed_records:
        text = rec.get("raw_text", "")
        if not text.strip():
            continue
        chunks = splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            docs.append(Document(
                page_content=chunk,
                metadata={
                    "source": rec.get("source", "unknown"),
                    "file_type": rec.get("file_type", "unknown"),
                    "supplier_name": rec.get("supplier_name"),
                    "chunk_index": i,
                },
            ))
    return docs


def build_index(parsed_records: List[Dict], index_path: Optional[str] = None) -> FAISS:
    docs = documents_from_parsed(parsed_records)
    if not docs:
        raise ValueError("No text content found to index.")
    embeddings = get_embeddings()
    store = FAISS.from_documents(docs, embeddings)
    if index_path:
        Path(index_path).mkdir(parents=True, exist_ok=True)
        store.save_local(index_path)
    return store


def load_index(index_path: str) -> Optional[FAISS]:
    p = Path(index_path)
    if not p.exists() or not any(p.iterdir()):
        return None
    embeddings = get_embeddings()
    return FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)


def add_documents(store: FAISS, parsed_records: List[Dict], index_path: Optional[str] = None) -> FAISS:
    docs = documents_from_parsed(parsed_records)
    if docs:
        store.add_documents(docs)
        if index_path:
            store.save_local(index_path)
    return store
