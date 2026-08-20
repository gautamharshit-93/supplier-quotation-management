"""
Lightweight bilingual (English/Hindi) UI strings for the Streamlit app.
Not a full i18n framework — just enough to make the dashboard usable in
either language, since GPT-side multilingual reasoning is handled in
chatbot/query_bot.py and mailer/email_sender.py directly.
"""

STRINGS = {
    "en": {
        "app_title": "Supplier Quotation Management",
        "app_subtitle": "Upload RFQs and supplier quotations (Excel / PDF / Word) to compare, analyze, and decide.",
        "upload_rfq": "1. Upload the RFQ (what you asked for)",
        "upload_quotes": "2. Upload supplier quotations (responses)",
        "process_button": "Process documents",
        "cost_comparison": "Cost Comparison",
        "item_wise": "Item-wise price comparison",
        "total_cost": "Total quoted cost per supplier",
        "cheapest_per_item": "Cheapest supplier per item",
        "investment": "Investment / Cash Outlay",
        "gap_analysis": "Gap Analysis",
        "query_bot": "Ask a question",
        "query_placeholder": "e.g. Which supplier offers the earliest delivery for packaging material?",
        "send_email": "Send / Draft Email",
        "language": "Language",
        "no_data": "No documents processed yet. Upload files above to get started.",
        "final_recommendation": "Final Recommendation",
    },
    "hi": {
        "app_title": "आपूर्तिकर्ता कोटेशन प्रबंधन",
        "app_subtitle": "तुलना, विश्लेषण और निर्णय के लिए RFQ और आपूर्तिकर्ता कोटेशन (Excel / PDF / Word) अपलोड करें।",
        "upload_rfq": "1. RFQ अपलोड करें (आपने क्या माँगा था)",
        "upload_quotes": "2. आपूर्तिकर्ता कोटेशन अपलोड करें (प्रतिक्रियाएँ)",
        "process_button": "दस्तावेज़ प्रोसेस करें",
        "cost_comparison": "लागत तुलना",
        "item_wise": "आइटम-वार मूल्य तुलना",
        "total_cost": "प्रति आपूर्तिकर्ता कुल कोटेड लागत",
        "cheapest_per_item": "प्रत्येक आइटम के लिए सबसे सस्ता आपूर्तिकर्ता",
        "investment": "निवेश / नकद व्यय",
        "gap_analysis": "गैप विश्लेषण",
        "query_bot": "प्रश्न पूछें",
        "query_placeholder": "जैसे: पैकेजिंग सामग्री की सबसे जल्दी डिलीवरी कौन सा आपूर्तिकर्ता देता है?",
        "send_email": "ईमेल भेजें / ड्राफ्ट करें",
        "language": "भाषा",
        "no_data": "अभी तक कोई दस्तावेज़ प्रोसेस नहीं हुआ। शुरू करने के लिए ऊपर फ़ाइलें अपलोड करें।",
        "final_recommendation": "अंतिम सिफारिश",
    },
}


def t(key: str, lang: str = "en") -> str:
    return STRINGS.get(lang, STRINGS["en"]).get(key, key)
