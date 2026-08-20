from pathlib import Path
from .excel_parser import parse_excel
from .pdf_parser import parse_pdf
from .docx_parser import parse_docx


def parse_document(file_path: str) -> dict:
    """Dispatches to the right parser based on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        result = parse_excel(file_path)
        result["file_type"] = "excel"
    elif ext == ".pdf":
        result = parse_pdf(file_path)
        result["file_type"] = "pdf"
    elif ext in (".docx", ".doc"):
        result = parse_docx(file_path)
        result["file_type"] = "docx"
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    return result
