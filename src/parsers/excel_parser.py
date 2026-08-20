"""
Parses Excel RFQ / supplier-quotation workbooks into a normalized
list of row-dicts plus a raw-text blob (for the vector index / chatbot).
Works with .xlsx and .xls (via pandas/openpyxl).
"""
from pathlib import Path
from typing import List, Dict
import pandas as pd


def parse_excel(file_path: str) -> Dict:
    """
    Returns:
        {
          "sheets": {sheet_name: [row_dict, ...]},
          "raw_text": "flattened text of every sheet, for embeddings/search",
          "source": file_path,
        }
    """
    path = Path(file_path)
    xls = pd.ExcelFile(path)
    sheets = {}
    text_chunks = [f"Excel file: {path.name}"]

    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        # normalize column names
        df.columns = [str(c).strip() for c in df.columns]
        records = df.to_dict(orient="records")
        sheets[sheet_name] = records

        text_chunks.append(f"\n--- Sheet: {sheet_name} ---")
        text_chunks.append(df.to_string(index=False))

    return {
        "sheets": sheets,
        "raw_text": "\n".join(text_chunks),
        "source": str(path),
    }


def rows_to_dataframe(rows: List[Dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)
