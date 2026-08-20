"""
Supplier Quotation Management — Streamlit dashboard.
Run with:  streamlit run app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd
import plotly.express as px

import config
from src.parsers import parse_document
from src.extraction.rfq_extractor import extract_structured_data
from src.analysis.cost_comparison import (
    build_item_wise_comparison,
    build_pivot_comparison,
    build_total_cost_summary,
    cheapest_supplier_per_item,
)
from src.analysis.investment_calc import build_investment_table
from src.analysis.gap_analysis import build_gap_analysis
from src.vectorstore.faiss_store import build_index, load_index, add_documents
from src.chatbot.query_bot import ask as ask_bot
from src.mailer.email_sender import render_comparison_email, render_award_email, send_email
from src.storage import save_uploaded_file, save_record, list_records
from src.utils.i18n import t

st.set_page_config(page_title="Supplier Quotation Management", layout="wide")

# ---------------- Session state ----------------
if "rfq_data" not in st.session_state:
    st.session_state.rfq_data = None
if "quotations" not in st.session_state:
    st.session_state.quotations = []  # list of normalized dicts
if "parsed_records" not in st.session_state:
    st.session_state.parsed_records = []  # raw parsed docs, for vector index
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------- Sidebar ----------------
with st.sidebar:
    lang = st.selectbox("🌐 " + t("language", "en") + " / भाषा", options=["en", "hi"],
                         format_func=lambda x: config.SUPPORTED_LANGUAGES[x])
    st.divider()
    st.subheader("⚙️ System status")
    st.markdown(f"- OpenAI LLM: {'✅ configured' if config.HAS_OPENAI else '⚪ not set (local fallback active)'}")
    st.markdown(f"- Embeddings: `{config.EMBEDDINGS_MODE}`")
    st.markdown(f"- SMTP email: {'✅ configured' if config.HAS_SMTP else '⚪ not set (draft mode only)'}")
    st.markdown(f"- Storage backend: `{config.STORAGE_BACKEND}`")
    st.markdown(f"- Doc parser: `{config.DOC_PARSER_MODE}`")
    st.caption("Edit the `.env` file to add API keys and unlock full AI features.")
    st.divider()
    if st.button("🗑️ Reset session"):
        for key in ["rfq_data", "quotations", "parsed_records", "vector_store", "chat_history"]:
            st.session_state[key] = None if key in ("rfq_data", "vector_store") else []
        st.rerun()

st.title("📊 " + t("app_title", lang))
st.caption(t("app_subtitle", lang))

# ---------------- Upload section ----------------
col1, col2 = st.columns(2)
with col1:
    st.subheader(t("upload_rfq", lang))
    rfq_file = st.file_uploader(
        "RFQ file", type=["xlsx", "xls", "pdf", "docx"], key="rfq_uploader"
    )
with col2:
    st.subheader(t("upload_quotes", lang))
    quote_files = st.file_uploader(
        "Supplier quotation files", type=["xlsx", "xls", "pdf", "docx"],
        accept_multiple_files=True, key="quote_uploader"
    )

if st.button("🚀 " + t("process_button", lang), type="primary", disabled=not (rfq_file and quote_files)):
    with st.spinner("Parsing and extracting structured data..."):
        parsed_records = []

        # --- RFQ ---
        rfq_bytes = rfq_file.getvalue()
        rfq_path = save_uploaded_file(rfq_bytes, f"RFQ_{rfq_file.name}")
        rfq_parsed = parse_document(rfq_path)
        rfq_extracted = extract_structured_data(rfq_parsed)
        rfq_extracted["record_type"] = "rfq"
        rfq_extracted["source_file"] = rfq_file.name
        save_record({**rfq_extracted, "record_type": "rfq", "raw_text": rfq_parsed["raw_text"][:5000]})
        st.session_state.rfq_data = rfq_extracted

        parsed_records.append({
            "raw_text": rfq_parsed["raw_text"], "source": rfq_file.name,
            "file_type": rfq_parsed["file_type"], "supplier_name": "RFQ (Buyer requirements)",
        })

        # --- Supplier quotations ---
        quotations = []
        for qf in quote_files:
            q_bytes = qf.getvalue()
            q_path = save_uploaded_file(q_bytes, f"QUOTE_{qf.name}")
            q_parsed = parse_document(q_path)
            q_extracted = extract_structured_data(q_parsed)
            if not q_extracted.get("supplier_name"):
                q_extracted["supplier_name"] = Path(qf.name).stem
            q_extracted["record_type"] = "quotation"
            q_extracted["source_file"] = qf.name
            save_record({**q_extracted, "record_type": "quotation", "raw_text": q_parsed["raw_text"][:5000]})
            quotations.append(q_extracted)

            parsed_records.append({
                "raw_text": q_parsed["raw_text"], "source": qf.name,
                "file_type": q_parsed["file_type"], "supplier_name": q_extracted.get("supplier_name"),
            })

        st.session_state.quotations = quotations
        st.session_state.parsed_records = parsed_records

        # --- Build vector index for the chatbot ---
        try:
            st.session_state.vector_store = build_index(
                parsed_records, index_path=str(config.VECTOR_INDEX_DIR)
            )
        except Exception as e:
            st.warning(f"Vector index build failed (chat/search will be limited): {e}")

    st.success(f"Processed 1 RFQ and {len(quote_files)} supplier quotation(s).")

st.divider()

# ---------------- Results ----------------
if not st.session_state.quotations:
    st.info(t("no_data", lang))
else:
    item_df = build_item_wise_comparison(st.session_state.quotations)
    total_summary = build_total_cost_summary(item_df)
    cheapest_df = cheapest_supplier_per_item(item_df)
    gap_df = build_gap_analysis(st.session_state.rfq_data or {}, st.session_state.quotations)

    tabs = st.tabs([
        f"💰 {t('cost_comparison', lang)}",
        f"🏦 {t('investment', lang)}",
        f"🔍 {t('gap_analysis', lang)}",
        f"💬 {t('query_bot', lang)}",
        f"✉️ {t('send_email', lang)}",
        "📋 Final Summary",
    ])

    # --- Cost comparison tab ---
    with tabs[0]:
        st.subheader(t("item_wise", lang))
        st.dataframe(item_df, use_container_width=True)

        pivot = build_pivot_comparison(item_df, value_col="unit_price")
        if not pivot.empty:
            st.subheader("Unit price by item × supplier")
            st.dataframe(pivot, use_container_width=True)

        st.subheader(t("total_cost", lang))
        if not total_summary.empty:
            st.dataframe(total_summary, use_container_width=True)
            fig = px.bar(total_summary, x="supplier_name", y="total_quoted_cost",
                         title="Total quoted cost per supplier", text_auto=".2s")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Not enough price data extracted yet to summarize totals.")

        st.subheader(t("cheapest_per_item", lang))
        st.dataframe(cheapest_df, use_container_width=True)

    # --- Investment tab ---
    with tabs[1]:
        inv_df = build_investment_table(st.session_state.quotations, total_summary)
        if not inv_df.empty:
            st.dataframe(inv_df, use_container_width=True)
            st.caption(
                "Advance payment % is auto-detected from payment terms text where possible. "
                "'Not specified' / blank means the source document didn't clearly state it — verify manually."
            )
        else:
            st.caption("No investment data available yet.")

    # --- Gap analysis tab ---
    with tabs[2]:
        st.dataframe(gap_df, use_container_width=True)
        st.caption("Lower gap_score = more complete, compliant quotation relative to the RFQ.")

    # --- Query bot tab ---
    with tabs[3]:
        st.caption(t("query_placeholder", lang))
        for role, msg in st.session_state.chat_history:
            with st.chat_message(role):
                st.markdown(msg)

        user_q = st.chat_input(t("query_placeholder", lang))
        if user_q:
            st.session_state.chat_history.append(("user", user_q))
            with st.chat_message("user"):
                st.markdown(user_q)
            with st.chat_message("assistant"):
                if st.session_state.vector_store is None:
                    reply = "Please process documents first so I have something to search."
                else:
                    with st.spinner("Searching indexed documents..."):
                        result = ask_bot(st.session_state.vector_store, user_q, language=lang)
                    reply = result["answer"]
                st.markdown(reply)
            st.session_state.chat_history.append(("assistant", reply))

    # --- Email tab ---
    with tabs[4]:
        supplier_names = [q.get("supplier_name") for q in st.session_state.quotations]
        chosen_supplier = st.selectbox("Supplier", supplier_names)
        chosen_q = next((q for q in st.session_state.quotations if q.get("supplier_name") == chosen_supplier), {})
        chosen_gap = gap_df[gap_df["supplier_name"] == chosen_supplier] if not gap_df.empty else pd.DataFrame()

        email_type = st.radio("Email type", ["Request missing info (gap follow-up)", "Award notification"], horizontal=True)
        to_address = st.text_input("Supplier email address", placeholder="supplier@example.com")

        if st.button("Generate email"):
            if email_type.startswith("Request"):
                missing_items = []
                missing_fields = []
                if not chosen_gap.empty:
                    row = chosen_gap.iloc[0]
                    if row["missing_items"] != "None":
                        missing_items = [x.strip() for x in row["missing_items"].split(",")]
                    if row["missing_fields"] != "None":
                        missing_fields = [x.strip() for x in row["missing_fields"].split(",")]
                draft = render_comparison_email(
                    supplier_name=chosen_supplier,
                    rfq_ref=(st.session_state.rfq_data or {}).get("rfq_ref"),
                    missing_items=missing_items,
                    missing_fields=missing_fields,
                    deadline=(st.session_state.rfq_data or {}).get("deadline_date"),
                    language=lang,
                )
            else:
                draft = render_award_email(
                    supplier_name=chosen_supplier,
                    rfq_ref=(st.session_state.rfq_data or {}).get("rfq_ref"),
                    language=lang,
                )
            st.session_state["_email_draft"] = draft

        draft = st.session_state.get("_email_draft")
        if draft:
            subject = st.text_input("Subject", value=draft["subject"])
            body = st.text_area("Body", value=draft["body"], height=220)
            if st.button("📤 Send / Save draft", type="primary"):
                if not to_address:
                    st.error("Enter a supplier email address first.")
                else:
                    result = send_email(to_address, subject, body)
                    if result["status"] == "sent":
                        st.success(f"Email sent to {to_address}.")
                    elif result["status"] == "draft_only":
                        st.warning(result["message"])
                        st.code(f"To: {to_address}\nSubject: {subject}\n\n{body}")
                    else:
                        st.error(f"Failed to send: {result.get('message')}")

    # --- Final summary tab ---
    with tabs[5]:
        st.subheader(t("final_recommendation", lang))
        if not total_summary.empty and not gap_df.empty:
            merged = total_summary.merge(gap_df[["supplier_name", "gap_score"]], on="supplier_name", how="left")
            merged["gap_score"] = merged["gap_score"].fillna(merged["gap_score"].max() or 0)
            # simple composite score: lower cost and lower gap_score is better (normalized 0-1 each, equal weight)
            if merged["total_quoted_cost"].notna().any():
                cost_norm = (merged["total_quoted_cost"] - merged["total_quoted_cost"].min()) / (
                    (merged["total_quoted_cost"].max() - merged["total_quoted_cost"].min()) or 1
                )
            else:
                cost_norm = 0
            gap_norm = (merged["gap_score"] - merged["gap_score"].min()) / (
                (merged["gap_score"].max() - merged["gap_score"].min()) or 1
            )
            merged["composite_score"] = 0.6 * cost_norm + 0.4 * gap_norm
            merged = merged.sort_values("composite_score")
            st.dataframe(merged, use_container_width=True)
            best = merged.iloc[0]
            st.success(
                f"**Recommended supplier: {best['supplier_name']}** — lowest combined score of "
                f"total cost (60% weight) and RFQ compliance/completeness (40% weight). "
                f"Review the Cost Comparison and Gap Analysis tabs before finalizing."
            )
            st.caption("This is a decision-support ranking, not an automatic award — always verify manually before formalizing an order.")
        else:
            st.caption("Process at least one RFQ and quotation with extractable prices to see a recommendation.")
