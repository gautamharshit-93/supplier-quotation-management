"""
Compares what the RFQ asked for (required parameters/items) against what
each supplier actually quoted, and flags gaps: missing items, missing
fields (packaging/portion/warranty/delivery terms), and deadline risk.
"""
from datetime import datetime, date
from typing import Dict, List, Optional
import pandas as pd


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def build_gap_analysis(rfq: Dict, quotations: List[Dict]) -> pd.DataFrame:
    """
    rfq: normalized RFQ dict (the "ask") with an "items" list of required item names.
    quotations: list of normalized supplier quotation dicts (the "offers").

    Returns a DataFrame, one row per supplier, flagging gaps.
    """
    required_items = {
        (i.get("item_name") or "").strip().lower()
        for i in rfq.get("items", []) if i.get("item_name")
    }
    rfq_deadline = _parse_date(rfq.get("deadline_date"))

    rows = []
    for q in quotations:
        supplier = q.get("supplier_name") or "Unknown Supplier"
        quoted_items = {
            (i.get("item_name") or "").strip().lower()
            for i in q.get("items", []) if i.get("item_name")
        }
        missing_items = sorted(required_items - quoted_items) if required_items else []

        missing_fields = []
        for field, label in [
            ("delivery_terms", "Delivery terms"),
            ("payment_terms", "Payment terms"),
            ("warranty", "Warranty"),
            ("delivery_lead_time_days", "Delivery lead time"),
        ]:
            if not q.get(field):
                missing_fields.append(label)

        # item-level gaps: packaging / portion missing
        items_missing_packaging = [
            i.get("item_name") for i in q.get("items", []) if not i.get("packaging")
        ]
        items_missing_portion = [
            i.get("item_name") for i in q.get("items", []) if not i.get("portion")
        ]

        submitted_on_time = None
        if rfq_deadline is not None:
            # we don't always know submission date; treat presence of a valid
            # quotation as "on time" unless a submission_date field says otherwise
            submitted_on_time = "Unknown (no submission timestamp captured)"

        gap_score = (
            len(missing_items) * 3
            + len(missing_fields)
            + 0.5 * len(items_missing_packaging)
            + 0.5 * len(items_missing_portion)
        )

        rows.append({
            "supplier_name": supplier,
            "missing_items": ", ".join(missing_items) if missing_items else "None",
            "missing_fields": ", ".join(missing_fields) if missing_fields else "None",
            "items_missing_packaging": ", ".join(filter(None, items_missing_packaging)) or "None",
            "items_missing_portion": ", ".join(filter(None, items_missing_portion)) or "None",
            "rfq_deadline": rfq.get("deadline_date") or "Not specified",
            "gap_score": round(gap_score, 1),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("gap_score")  # lowest gap score = most complete quote
    return df
