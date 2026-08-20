"""
Sends automated procurement emails (e.g. comparison summaries, requests for
missing info flagged by gap analysis, final award notifications) via SMTP
(Gmail / Outlook / any standard SMTP provider using an app password).

Defaults to a safe "draft" mode: if SMTP credentials aren't configured,
emails are rendered and returned as text instead of being sent, so nothing
ever fails silently or gets sent by accident.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

import config


def render_comparison_email(
    supplier_name: str,
    rfq_ref: Optional[str],
    missing_items: List[str],
    missing_fields: List[str],
    deadline: Optional[str],
    language: str = "en",
) -> Dict[str, str]:
    """Builds a subject+body asking a supplier to fill gaps in their quotation."""
    if language == "hi":
        subject = f"RFQ {rfq_ref or ''} - कोटेशन में अतिरिक्त जानकारी आवश्यक"
        body = (
            f"प्रिय {supplier_name},\n\n"
            f"आपके कोटेशन की समीक्षा के दौरान, हमें निम्नलिखित जानकारी अधूरी मिली:\n"
        )
        if missing_items:
            body += f"- अनुपलब्ध आइटम: {', '.join(missing_items)}\n"
        if missing_fields:
            body += f"- अनुपलब्ध विवरण: {', '.join(missing_fields)}\n"
        if deadline:
            body += f"\nकृपया {deadline} से पहले अद्यतन कोटेशन भेजें।\n"
        body += "\nधन्यवाद,\nखरीद टीम"
    else:
        subject = f"RFQ {rfq_ref or ''} - Additional information needed on your quotation"
        body = (
            f"Dear {supplier_name},\n\n"
            f"While reviewing your quotation, we found the following was incomplete:\n"
        )
        if missing_items:
            body += f"- Missing items: {', '.join(missing_items)}\n"
        if missing_fields:
            body += f"- Missing details: {', '.join(missing_fields)}\n"
        if deadline:
            body += f"\nPlease send an updated quotation before {deadline}.\n"
        body += "\nThank you,\nProcurement Team"

    return {"subject": subject, "body": body}


def render_award_email(supplier_name: str, rfq_ref: Optional[str], language: str = "en") -> Dict[str, str]:
    if language == "hi":
        subject = f"RFQ {rfq_ref or ''} - कोटेशन स्वीकृत"
        body = (
            f"प्रिय {supplier_name},\n\n"
            f"हमें आपको सूचित करते हुए खुशी हो रही है कि आपका कोटेशन (RFQ {rfq_ref or ''}) स्वीकृत कर लिया गया है। "
            f"हम जल्द ही अंतिम आदेश और वितरण विवरण के साथ संपर्क करेंगे।\n\n"
            f"धन्यवाद,\nखरीद टीम"
        )
    else:
        subject = f"RFQ {rfq_ref or ''} - Quotation Accepted"
        body = (
            f"Dear {supplier_name},\n\n"
            f"We're pleased to inform you that your quotation for RFQ {rfq_ref or ''} has been accepted. "
            f"We will follow up shortly with the final purchase order and delivery details.\n\n"
            f"Best regards,\nProcurement Team"
        )
    return {"subject": subject, "body": body}


def send_email(to_address: str, subject: str, body: str) -> Dict:
    """
    Sends via SMTP if credentials are configured; otherwise returns the
    rendered email as a 'draft' without sending anything.
    """
    if not config.HAS_SMTP:
        return {
            "status": "draft_only",
            "message": "SMTP not configured in .env — email was NOT sent. Showing draft instead.",
            "to": to_address,
            "subject": subject,
            "body": body,
        }

    msg = MIMEMultipart()
    msg["From"] = f"{config.SMTP_FROM_NAME} <{config.SMTP_USERNAME}>"
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_USERNAME, [to_address], msg.as_string())
        return {"status": "sent", "to": to_address, "subject": subject}
    except Exception as e:
        return {"status": "error", "message": str(e), "to": to_address, "subject": subject}
