"""
General query bot: retrieval-augmented Q&A over all indexed RFQ/quotation
documents. Supports English and Hindi (both for the question and the answer).

If OPENAI_API_KEY is set -> generates a natural-language answer grounded in
retrieved chunks, in the requested language.
If not set -> returns the raw retrieved chunks so the tool is still useful
in local/demo mode (no free-text generation without an LLM).
"""
from typing import Dict, List, Optional

from langchain_community.vectorstores import FAISS

import config

_SYSTEM_PROMPT_TEMPLATE = """You are a procurement assistant answering questions about
supplier RFQs and quotations for a company. Answer ONLY using the provided context
snippets below. If the answer isn't in the context, say so honestly rather than guessing.

Respond in {language_name}. Be concise, use bullet points or a short table when comparing
suppliers or prices. Always mention which supplier / document a fact came from when relevant.

Context snippets:
---
{context}
---
"""

_LANGUAGE_NAMES = {"en": "English", "hi": "Hindi (हिन्दी)"}


def retrieve(store: FAISS, query: str, k: int = 6) -> List[Dict]:
    results = store.similarity_search_with_score(query, k=k)
    return [
        {
            "text": doc.page_content,
            "source": doc.metadata.get("source"),
            "supplier_name": doc.metadata.get("supplier_name"),
            "score": float(score),
        }
        for doc, score in results
    ]


def _format_context(snippets: List[Dict]) -> str:
    parts = []
    for s in snippets:
        label = s.get("supplier_name") or s.get("source") or "Unknown source"
        parts.append(f"[{label}]\n{s['text']}")
    return "\n\n".join(parts)


def answer_with_llm(query: str, snippets: List[Dict], language: str = "en") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)

    language_name = _LANGUAGE_NAMES.get(language, "English")
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        language_name=language_name, context=_format_context(snippets)
    )
    response = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content


def answer_without_llm(snippets: List[Dict]) -> str:
    if not snippets:
        return "No relevant information found in the indexed documents."
    lines = ["No OpenAI key configured — showing the most relevant raw excerpts instead:\n"]
    for s in snippets:
        label = s.get("supplier_name") or s.get("source") or "Unknown source"
        preview = s["text"][:400].strip()
        lines.append(f"**{label}**\n> {preview}\n")
    return "\n".join(lines)


def ask(store: FAISS, query: str, language: str = "en", k: int = 6) -> Dict:
    snippets = retrieve(store, query, k=k)
    if config.HAS_OPENAI:
        try:
            answer = answer_with_llm(query, snippets, language=language)
        except Exception as e:
            answer = f"(LLM call failed: {e})\n\n" + answer_without_llm(snippets)
    else:
        answer = answer_without_llm(snippets)
    return {"answer": answer, "sources": snippets}
