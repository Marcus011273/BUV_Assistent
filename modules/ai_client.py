from __future__ import annotations

import json
from typing import Any, Dict, List

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


def has_api_key() -> bool:
    return bool(_get_api_key())


def _get_api_key() -> str | None:
    # Lokal kann zusätzlich OPENAI_API_KEY als Umgebungsvariable genutzt werden.
    try:
        key = st.secrets.get("OPENAI_API_KEY")
        if key:
            return str(key)
    except Exception:
        pass
    import os

    return os.getenv("OPENAI_API_KEY")


def get_client() -> OpenAI:
    key = _get_api_key()
    if not key:
        raise RuntimeError("Kein OPENAI_API_KEY gefunden. In Streamlit Cloud unter Secrets hinterlegen.")
    return OpenAI(api_key=key)


def extract_text_from_upload(uploaded_file: Any) -> str:
    """Liest PDF/TXT grob aus. DOCX-Unterstützung kann später ergänzt werden."""
    if uploaded_file is None:
        return ""
    name = (uploaded_file.name or "").lower()
    data = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        parts: List[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()

    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")

    if name.endswith(".docx"):
        from io import BytesIO
        from docx import Document

        doc = Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()

    return data.decode("utf-8", errors="ignore")


def analyze_draft_short(draft_text: str) -> List[str]:
    prompt = f"""
Du bist ein erfahrener Seminarrektor für das Lehramt Mittelschule in Bayern.
Analysiere den folgenden Unterrichtsentwurf knapp in höchstens 5 Stichpunkten.
Beziehe dich nur auf diese Bereiche:
- Vorüberlegungen
- Anbindung an den Lehrplan
- Sequenz
- Formulierung der Kompetenzerwartungen
- Artikulation

Formuliere sachlich, knapp und beratungsorientiert. Keine langen Absätze.

UNTERRICHTSENTWURF:
{draft_text[:30000]}
"""
    text = _chat(prompt)
    return _split_bullets(text, max_items=5)


def summarize_observations(protocol: Dict[str, Any], buv_type: str) -> str:
    context = json.dumps(protocol, ensure_ascii=False, indent=2)
    prompt = f"""
Du bist ein erfahrener Seminarrektor für das Lehramt Mittelschule in Bayern.
Formuliere aus den folgenden Rohnotizen aussagekräftige Beratungsschwerpunkte zur Weiterarbeit.

BUV-Art: {buv_type}

Regeln:
- maximal 8 Stichpunkte
- sachlich, professionell und klar
- keine unnötigen Wiederholungen
- keine Übertreibungen
- entwicklungsorientiert formulieren
- bei Doppel-BUV Entwicklung seit der Einzel-BUV berücksichtigen, falls Daten vorhanden sind
- Ergebnis nur als Stichpunkte ausgeben

DATEN:
{context[:50000]}
"""
    return _chat(prompt)


def extract_metadata_from_draft(draft_text: str) -> Dict[str, str]:
    prompt = f"""
Extrahiere aus dem folgenden Unterrichtsentwurf, soweit vorhanden, diese Felder.
Gib ausschließlich valides JSON zurück. Keine Erklärungen.

Felder:
laa_name, datum, schule, fach, klasse, thema, buv_art

buv_art soll einer dieser Werte sein: Einzel-BUV, Doppel-BUV, unbekannt.
Wenn ein Feld nicht erkennbar ist, nutze einen leeren String.

UNTERRICHTSENTWURF:
{draft_text[:25000]}
"""
    raw = _chat(prompt)
    cleaned = _strip_json_fences(raw)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        # Fallback: ersten JSON-Block zwischen { und } versuchen
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
            except json.JSONDecodeError:
                pass
    return {}


def _strip_json_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return text


def _chat(prompt: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Du formulierst präzise, sachlich und auf Deutsch."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def _split_bullets(text: str, max_items: int = 5) -> List[str]:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.lstrip("-•0123456789. )\t")
        if line:
            lines.append(line)
    return lines[:max_items]
