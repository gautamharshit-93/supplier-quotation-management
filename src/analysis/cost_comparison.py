"""
Builds item-wise and total cost comparison tables across multiple
supplier quotations that have been normalized by rfq_extractor.
"""
from typing import Dict, List
import pandas as pd


def build_item_wise_comparison(quotations: List[Dict]) -> pd.DataFrame:
    """
    quotations: list of normalized quotation dicts (from rfq_extractor),
                each expected to have "supplier_name" and "items".
    Returns a long-format DataFrame: item_name, supplier_name, quantity,
    unit_price, total_price, portion, packaging.
    """
    rows = []
    for q in quotations:
        supplier = q.get("supplier_name") or "Unknown Supplier"
        for item in q.get("items", []):
            qty = item.get("quantity")
            unit_price = item.get("unit_price")
            total_price = item.get("total_price")
            if total_price is None and qty is not None and unit_price is not None:
                total_price = round(qty * unit_price, 2)
            rows.append({
                "item_name": item.get("item_name", "Unknown item"),
                "supplier_name": supplier,
                "quantity": qty,
                "unit": item.get("unit"),
                "unit_price": unit_price,
                "total_price": total_price,
                "portion": item.get("portion"),
                "packaging": item.get("packaging"),
            })
    return pd.DataFrame(rows)


def build_pivot_comparison(item_df: pd.DataFrame, value_col: str = "unit_price") -> pd.DataFrame:
    """Wide-format table: rows = items, columns = suppliers, values = price."""
    if item_df.empty:
        return pd.DataFrame()
    pivot = item_df.pivot_table(
        index="item_name", columns="supplier_name", values=value_col, aggfunc="first"
    )
    return pivot


def build_total_cost_summary(item_df: pd.DataFrame) -> pd.DataFrame:
    """Total quoted cost per supplier, plus cheapest/most expensive flags."""
    if item_df.empty:
        return pd.DataFrame()
    summary = (
        item_df.groupby("supplier_name")["total_price"]
        .sum(min_count=1)
        .reset_index()
        .rename(columns={"total_price": "total_quoted_cost"})
        .sort_values("total_quoted_cost")
    )
    if not summary.empty and summary["total_quoted_cost"].notna().any():
        min_cost = summary["total_quoted_cost"].min()
        summary["savings_vs_cheapest"] = summary["total_quoted_cost"] - min_cost
        summary["rank"] = summary["total_quoted_cost"].rank(method="min").astype("Int64")
    return summary


def cheapest_supplier_per_item(item_df: pd.DataFrame) -> pd.DataFrame:
    """For each item, which supplier offers the lowest unit price."""
    if item_df.empty:
        return pd.DataFrame()
    valid = item_df.dropna(subset=["unit_price"])
    if valid.empty:
        return pd.DataFrame()
    idx = valid.groupby("item_name")["unit_price"].idxmin()
    return valid.loc[idx].reset_index(drop=True)[
        ["item_name", "supplier_name", "unit_price", "quantity", "total_price"]
    ].rename(columns={"supplier_name": "best_price_supplier", "unit_price": "best_unit_price"})
