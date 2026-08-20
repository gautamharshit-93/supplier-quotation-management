"""
Turns parsed RFQ / supplier-quotation documents into a normalized schema so
different suppliers' quotes can be compared apples-to-apples.

Two extraction paths:
  1. LLM path (OPENAI_API_KEY set): GPT reads the raw text and returns
     structured JSON. Handles messy, inconsistent, Hindi/English-mixed text well.
  2. Heuristic path (no key): works DIRECTLY off the structured tables/sheets
     the parsers already extracted (column headers, docx tables, key/value
     pairs) rather than re-parsing flattened text with regex — this is far
     more reliable for well-formed Excel/Word documents. Free-text PDFs
     without a detected table fall back to line-pattern matching.
"""
import json
import re
from typing import Dict, List, Optional, Any

import config

NORMALIZED_SCHEMA_FIELDS = [
    "supplier_name", "quotation_ref", "rfq_ref", "deadline_date", "currency",
    "items", "delivery_terms", "delivery_lead_time_days", "payment_terms",
    "warranty", "notes",
]

EXTRACTION_SYSTEM_PROMPT = """You are a procurement data-extraction assistant.
You will be given raw text extracted from an RFQ (Request for Quotation) or a
supplier's quotation response (could be in English, Hindi, or a mix of both).

Extract the information into STRICT JSON matching this schema exactly:
{
  "supplier_name": string or null,
  "quotation_ref": string or null,
  "rfq_ref": string or null,
  "deadline_date": "YYYY-MM-DD" or null,
  "currency": string or null (e.g. "INR", "USD"),
  "items": [
    {
      "item_name": string,
      "quantity": number or null,
      "unit": string or null,
      "unit_price": number or null,
      "total_price": number or null,
      "portion": string or null,
      "packaging": string or null
    }
  ],
  "delivery_terms": string or null,
  "delivery_lead_time_days": number or null,
  "payment_terms": string or null,
  "warranty": string or null,
  "notes": string or null
}

Rules:
- Output ONLY valid JSON, no markdown fences, no commentary.
- If a field is not present in the text, use null (or empty list for items).
- Normalize numbers (strip currency symbols/commas) into plain numbers.
- If dates are in Indian format (DD/MM/YYYY) convert to YYYY-MM-DD.
"""


def _get_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=config.OPENAI_API_KEY)


def extract_with_llm(raw_text: str) -> Dict:
    client = _get_openai_client()
    truncated = raw_text[:12000]
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": truncated},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = _empty_schema()
        data["notes"] = "LLM returned non-JSON output; raw response saved."
        data["_raw_llm_output"] = content
    return _coerce_schema(data)


def _empty_schema() -> Dict:
    return {
        "supplier_name": None, "quotation_ref": None, "rfq_ref": None,
        "deadline_date": None, "currency": None, "items": [],
        "delivery_terms": None, "delivery_lead_time_days": None,
        "payment_terms": None, "warranty": None, "notes": None,
    }


def _coerce_schema(data: Dict) -> Dict:
    base = _empty_schema()
    base.update({k: v for k, v in data.items() if k in base})
    if not isinstance(base.get("items"), list):
        base["items"] = []
    return base


# ============================================================
# Heuristic / structured path (no OpenAI key needed)
# ============================================================

_HEADER_FIELD_ALIASES = {
    "supplier_name": ["supplier", "vendor", "company", "supplier name", "from"],
    "quotation_ref": ["quotation ref", "quote ref", "quotation no", "quotation number"],
    "rfq_ref": ["rfq ref", "rfq no", "rfq number", "rfq"],
    "deadline_date": ["deadline", "due date", "last date", "closing date"],
    "currency": ["currency"],
    "delivery_terms": ["delivery terms"],
    "delivery_lead_time_days": ["lead time", "delivery time", "delivery lead time"],
    "payment_terms": ["payment terms"],
    "warranty": ["warranty", "guarantee"],
}

_ITEM_COLUMN_ALIASES = {
    "item_name": ["item name", "item", "description", "product", "material"],
    "quantity": ["quantity", "required quantity", "qty"],
    "unit": ["unit"],
    "unit_price": ["unit price", "price", "rate"],
    "total_price": ["total price", "total", "amount", "total cost"],
    "portion": ["portion", "portion spec"],
    "packaging": ["packaging", "packaging spec"],
}

_DATE_RE = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")


def _normalize_key(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _match_alias(key: str, alias_map: Dict[str, List[str]]) -> Optional[str]:
    nk = _normalize_key(key)
    # exact match first, then "starts with" (handles "Lead Time (days)" etc.)
    for field, aliases in alias_map.items():
        if nk in aliases:
            return field
    for field, aliases in alias_map.items():
        if any(nk.startswith(a) for a in aliases):
            return field
    return None


_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _clean_number(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = re.sub(r"[₹$]|rs\.?|inr|usd", "", str(val), flags=re.IGNORECASE)
    m = _NUMBER_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _normalize_date(val: Any) -> Optional[str]:
    if not val:
        return None
    s = str(val)
    m = _DATE_RE.search(s)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        y = y if len(y) == 4 else f"20{y}"
        try:
            return f"{y}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    return None


def _extract_header_fields_from_kv_rows(rows: List[Dict], data: Dict) -> None:
    """rows like [{"Field": "Supplier", "Value": "Acme Corp"}, ...]"""
    for row in rows:
        keys = list(row.keys())
        if len(keys) < 2:
            continue
        field_key, value_key = keys[0], keys[1]
        field_name = row.get(field_key)
        value = row.get(value_key)
        if field_name is None or value is None:
            continue
        matched = _match_alias(field_name, _HEADER_FIELD_ALIASES)
        if not matched:
            continue
        if matched == "deadline_date":
            data["deadline_date"] = _normalize_date(value) or data["deadline_date"]
        elif matched == "delivery_lead_time_days":
            n = _clean_number(value)
            data["delivery_lead_time_days"] = int(n) if n is not None else data["delivery_lead_time_days"]
        else:
            data[matched] = str(value).strip()


def _extract_items_from_rows(rows: List[Dict]) -> List[Dict]:
    """rows: list of dicts with column headers as keys (from Excel sheet or docx/pdf table)."""
    if not rows:
        return []
    sample_keys = list(rows[0].keys())
    col_map = {}
    for key in sample_keys:
        matched = _match_alias(key, _ITEM_COLUMN_ALIASES)
        if matched:
            col_map[key] = matched

    if "item_name" not in col_map.values():
        return []

    items = []
    for row in rows:
        item: Dict[str, Any] = {
            "item_name": None, "quantity": None, "unit": None,
            "unit_price": None, "total_price": None, "portion": None, "packaging": None,
        }
        for col_key, field in col_map.items():
            val = row.get(col_key)
            if val is None or str(val).strip() == "" or str(val).lower() == "nan":
                continue
            if field in ("quantity", "unit_price", "total_price"):
                item[field] = _clean_number(val)
            else:
                item[field] = str(val).strip()
        if item["item_name"]:
            items.append(item)
    return items


def _extract_from_excel(parsed: Dict, data: Dict) -> None:
    sheets = parsed.get("sheets", {})
    for sheet_name, rows in sheets.items():
        if not rows:
            continue
        keys = [_normalize_key(k) for k in rows[0].keys()]
        if "field" in keys and "value" in keys:
            _extract_header_fields_from_kv_rows(rows, data)
        else:
            items = _extract_items_from_rows(rows)
            if items:
                data["items"].extend(items)


def _extract_from_docx(parsed: Dict, data: Dict) -> None:
    for line in parsed.get("raw_text", "").splitlines():
        if ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        matched = _match_alias(field_name, _HEADER_FIELD_ALIASES)
        if not matched or not value.strip():
            continue
        if matched == "deadline_date":
            data["deadline_date"] = _normalize_date(value) or data["deadline_date"]
        elif matched == "delivery_lead_time_days":
            n = _clean_number(value)
            data["delivery_lead_time_days"] = int(n) if n is not None else data["delivery_lead_time_days"]
        else:
            data[matched] = value.strip()

    for table_rows in parsed.get("tables", []):
        if len(table_rows) < 2:
            continue
        headers = table_rows[0]
        row_dicts = [dict(zip(headers, r)) for r in table_rows[1:]]
        items = _extract_items_from_rows(row_dicts)
        if items:
            data["items"].extend(items)


_PDF_LINE_ITEM_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 /\-\.\(\)]{2,50}?)\s+"
    r"Qty\s*(?P<qty>[\d,]+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)?\s+"
    r"Unit Price\s*(?:Rs\.?|₹|\$)?\s*(?P<price>[\d,]+(?:\.\d+)?)"
    r"(?:\s+Portion:\s*(?P<portion>[^:]+?))?"
    r"(?:\s+Packaging:\s*(?P<packaging>.+))?$",
    re.IGNORECASE,
)


def _extract_from_pdf(parsed: Dict, data: Dict) -> None:
    for line in parsed.get("raw_text", "").splitlines():
        if ":" not in line:
            continue
        field_name, _, value = line.partition(":")
        matched = _match_alias(field_name, _HEADER_FIELD_ALIASES)
        if matched and value.strip() and "Qty" not in value:
            if matched == "deadline_date":
                data["deadline_date"] = _normalize_date(value) or data["deadline_date"]
            elif matched == "delivery_lead_time_days":
                n = _clean_number(value)
                data["delivery_lead_time_days"] = int(n) if n is not None else data["delivery_lead_time_days"]
            else:
                data[matched] = value.strip()

    for table_rows in parsed.get("tables", []):
        if len(table_rows) < 2:
            continue
        headers = table_rows[0]
        row_dicts = [dict(zip(headers, r)) for r in table_rows[1:]]
        items = _extract_items_from_rows(row_dicts)
        if items:
            data["items"].extend(items)

    if not data["items"]:
        for line in parsed.get("raw_text", "").splitlines():
            m = _PDF_LINE_ITEM_RE.match(line.strip())
            if m:
                data["items"].append({
                    "item_name": m.group("name").strip(),
                    "quantity": _clean_number(m.group("qty")),
                    "unit": m.group("unit"),
                    "unit_price": _clean_number(m.group("price")),
                    "total_price": None,
                    "portion": m.group("portion").strip() if m.group("portion") else None,
                    "packaging": m.group("packaging").strip() if m.group("packaging") else None,
                })


def extract_with_heuristics(parsed: Dict) -> Dict:
    data = _empty_schema()
    file_type = parsed.get("file_type")

    if file_type == "excel":
        _extract_from_excel(parsed, data)
    elif file_type == "docx":
        _extract_from_docx(parsed, data)
    elif file_type == "pdf":
        _extract_from_pdf(parsed, data)

    if not data["currency"]:
        raw = parsed.get("raw_text", "")
        if "₹" in raw or re.search(r"\bINR\b|\bRs\.?\b", raw, re.IGNORECASE):
            data["currency"] = "INR"
        elif "$" in raw or re.search(r"\bUSD\b", raw, re.IGNORECASE):
            data["currency"] = "USD"

    data["notes"] = (
        "Extracted with local heuristics from document structure "
        "(no OpenAI key configured) — spot-check before finalizing."
    )
    return data


def extract_structured_data(parsed: Dict) -> Dict:
    """
    Main entry point. `parsed` is the dict returned by src.parsers.parse_document
    (has raw_text, file_type, and sheets/tables depending on type).
    Uses the LLM if OPENAI_API_KEY is configured, else structured heuristics.
    """
    if config.HAS_OPENAI:
        try:
            return extract_with_llm(parsed.get("raw_text", ""))
        except Exception as e:
            fallback = extract_with_heuristics(parsed)
            fallback["notes"] = f"LLM extraction failed ({e}); used local fallback instead."
            return fallback
    return extract_with_heuristics(parsed)
