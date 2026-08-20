"""
Estimates upfront investment / cash outflow required per supplier,
based on quoted total cost and payment terms (advance %, milestones, etc.)
"""
import re
from typing import Dict, List, Optional
import pandas as pd


def _guess_advance_percent(payment_terms: Optional[str]) -> Optional[float]:
    """Tries to pull an advance-payment percentage out of free text payment terms."""
    if not payment_terms:
        return None
    m = re.search(r"(\d{1,3})\s*%\s*(?:advance|upfront|in advance)", payment_terms, re.IGNORECASE)
    if m:
        return min(float(m.group(1)), 100.0)
    if re.search(r"100\s*%\s*advance", payment_terms, re.IGNORECASE):
        return 100.0
    if re.search(r"advance", payment_terms, re.IGNORECASE) and not m:
        return None  # advance mentioned but % unclear
    return None


def build_investment_table(quotations: List[Dict], total_cost_by_supplier: pd.DataFrame) -> pd.DataFrame:
    """
    Combines total quoted cost with payment-terms parsing to estimate:
      - advance_payment_pct (best guess, may be None if unclear)
      - upfront_cash_required
      - balance_on_delivery
      - delivery_lead_time_days (cash tied up duration proxy)
    """
    terms_by_supplier = {
        (q.get("supplier_name") or "Unknown Supplier"): {
            "payment_terms": q.get("payment_terms"),
            "delivery_lead_time_days": q.get("delivery_lead_time_days"),
        }
        for q in quotations
    }

    if total_cost_by_supplier.empty:
        return pd.DataFrame()

    rows = []
    for _, r in total_cost_by_supplier.iterrows():
        supplier = r["supplier_name"]
        total_cost = r.get("total_quoted_cost")
        terms = terms_by_supplier.get(supplier, {})
        payment_terms = terms.get("payment_terms")
        advance_pct = _guess_advance_percent(payment_terms)

        upfront = None
        balance = None
        if total_cost is not None and advance_pct is not None:
            upfront = round(total_cost * advance_pct / 100.0, 2)
            balance = round(total_cost - upfront, 2)

        rows.append({
            "supplier_name": supplier,
            "total_quoted_cost": total_cost,
            "payment_terms": payment_terms or "Not specified",
            "advance_payment_pct": advance_pct,
            "upfront_cash_required": upfront,
            "balance_on_delivery": balance,
            "delivery_lead_time_days": terms.get("delivery_lead_time_days"),
        })

    return pd.DataFrame(rows)
