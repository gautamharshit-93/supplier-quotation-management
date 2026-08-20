"""
Parses PDF RFQs / supplier quotations.
Default mode: local extraction via pdfplumber (text + tables), no API key.
Optional mode: LlamaParse (cloud, higher-quality layout parsing) if
DOC_PARSER_MODE=llamaparse and LLAMA_CLOUD_API_KEY is set in .env.
"""
from pathlib import Path
from typing import Dict, List
import pdfplumber

import config


def _parse_local(file_path: str) -> Dict:
    path = Path(file_path)
    text_chunks = [f"PDF file: {path.name}"]
    tables: List[List[List[str]]] = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            text_chunks.append(f"\n--- Page {i + 1} ---\n{page_text}")

            for table in page.extract_tables():
                tables.append(table)
                # also append a readable version of the table to raw text
                table_text = "\n".join(
                    " | ".join(str(cell) if cell is not None else "" for cell in row)
                    for row in table
                )
                text_chunks.append(f"\n[Table on page {i + 1}]\n{table_text}")

    return {
        "raw_text": "\n".join(text_chunks),
        "tables": tables,
        "source": str(path),
    }


def _parse_llamaparse(file_path: str) -> Dict:
    """Optional cloud parsing path. Requires `llama-parse` installed and a key."""
    try:
        from llama_parse import LlamaParse
    except ImportError as e:
        raise RuntimeError(
            "llama-parse is not installed. Run: pip install llama-parse, "
            "or set DOC_PARSER_MODE=local in .env to use the built-in parser."
        ) from e

    parser = LlamaParse(api_key=config.LLAMA_CLOUD_API_KEY, result_type="markdown")
    documents = parser.load_data(file_path)
    raw_text = "\n\n".join(d.text for d in documents)
    return {"raw_text": raw_text, "tables": [], "source": file_path}


def parse_pdf(file_path: str) -> Dict:
    if config.DOC_PARSER_MODE == "llamaparse" and config.LLAMA_CLOUD_API_KEY:
        try:
            return _parse_llamaparse(file_path)
        except Exception:
            # graceful fallback to local parsing if cloud parsing fails
            return _parse_local(file_path)
    return _parse_local(file_path)
