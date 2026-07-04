from __future__ import annotations

import json
import os
from io import BytesIO
from typing import Any, Dict, List

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


def has_api_key() -> bool:
    return bool(_get_api_key())


def _get_api_key() -> str | None:
    try:
        key = st.secrets.get("OPENAI_API_KEY")
        if key:
            return str(key)
    except Exception:
        pass

    return os.getenv("OPENAI_API_KEY")


def get_client() -> OpenAI:
    key = _get_api_key()

    if not key:
        raise RuntimeError(
            "Kein OPENAI_API_KEY gefunden. In Streamlit Cloud unter Secrets hinterlegen."
        )

    return OpenAI(api_key=key)


def extract_text_from_upload(uploaded_file: Any) -> str:
    if uploaded_file is None:
        return ""

    name = (uploaded_file.name or "").lower()
    data = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        parts: List[str] = []

        for page in reader.pages:
            parts.append(page.extract_text() or "")

        return "\n".join(parts).strip()

    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")

    if name.endswith(".docx"):
        from docx import Document

        doc = Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()

    return data.decode("utf-8", errors="ignore")


def extract_metadata_from_draft(draft_text: str) -> Dict[str, str]:
    prompt = f"""
Extrahiere aus dem folgenden Unterrichtsentwurf, soweit vorhanden, diese Felder.
Gib ausschließlich valides JSON zurück. Keine Erklärungen.

Felder:
laa_name, datum, schule, fach, klasse, thema, buv_art

buv_art soll einer dieser Werte sein:
Einzel-BUV, Doppel-BUV, unbekannt.

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

Formuliere sachlich, knapp und beratungsorientiert.
Keine langen Absätze.

UNTERRICHTSENTWURF:
{draft_text[:30000]}
"""

    text = _chat(prompt)
    return _split_bullets(text, max_items=5)


def convert_memos_to_beratungspunkte(
    observation_grid: Dict[str, Dict[str, str]],
    context_label: str,
) -> Dict[str, str]:
    """Formuliert Rohnotizen/Memos kriterienbezogen zu Beratungspunkten um.

    Die App nutzt diese Funktion, um deine Rohnotizen aus dem Memo-Feld in
    prägnante Beratungspunkte zu übertragen. Die Rohnotizen selbst bleiben in
    der App erhalten, erscheinen aber nicht im Word-Export.
    """

    prompt = f"""
Du bist ein erfahrener Seminarrektor für das Lehramt Mittelschule in Bayern.

Formuliere aus den folgenden Rohnotizen und ggf. bereits vorhandenen Beratungspunkten
prägnante Beratungspunkte für ein Protokoll zur Besonderen Unterrichtsvorbereitung.

Kontext:
{context_label}

Regeln:
- Formuliere sachlich, klar und entwicklungsorientiert.
- Formuliere stichpunktartig.
- Maximal 2 Stichpunkte pro Kriterium.
- Keine langen Absätze.
- Keine Rohnotizen übernehmen.
- Keine Dopplungen.
- Wenn zu einem Kriterium keine sinnvollen Rohnotizen oder Beratungshinweise vorliegen,
  gib für dieses Kriterium einen leeren String zurück.
- Gib ausschließlich valides JSON zurück.
- Die JSON-Schlüssel müssen exakt den Kriterien entsprechen.

DATEN:
{json.dumps(observation_grid, ensure_ascii=False, indent=2)}
"""

    raw = _chat(prompt)
    cleaned = _strip_json_fences(raw)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
            except json.JSONDecodeError:
                pass

    raise RuntimeError(
        "Die KI konnte keine gültigen Beratungspunkte im JSON-Format zurückgeben."
    )


def summarize_observations(protocol: Dict[str, Any], buv_type: str) -> str:
    context = json.dumps(protocol, ensure_ascii=False, indent=2)

    prompt = f"""
Du bist ein erfahrener Seminarrektor für das Lehramt Mittelschule in Bayern.

Erstelle aus den folgenden Beobachtungen, positiven Feststellungen, Beratungspunkten
und Rohnotizen eine "Zusammenfassung zur Weiterarbeit" für ein Protokoll zur
Besonderen Unterrichtsvorbereitung.

BUV-Art:
{buv_type}

Wichtige Aufgabe:
Die Zusammenfassung soll NICHT die einzelnen Beobachtungen wiederholen.
Sie soll aus den Beobachtungen übergeordnete Entwicklungsschwerpunkte ableiten
und dem LAA konkrete Hinweise für die weitere Unterrichtsplanung und
Unterrichtsdurchführung geben.

Berücksichtige:
- Strukturierung / roter Faden
- Zielorientierung
- Aktivierung
- Angemessenheit / Passung / Differenzierung
- Motivierung
- Unterrichtserfolg / Leistungssicherung
- Lehrersprache / Gesprächsführung
- Klassenführung / Atmosphäre
- Fachlichkeit / didaktische Reduktion
- Reflexion / Transfer
- Erzieherische Kompetenz
- Handlungs- und Sachkompetenz
- Einbringen in Schule und Seminar

Regeln für die Ausgabe:
- Formuliere maximal 8 Stichpunkte.
- Jeder Stichpunkt soll ein klarer Tipp bzw. Entwicklungsschwerpunkt für die Weiterarbeit sein.
- Keine bloße Wiederholung einzelner Beobachtungen.
- Keine Aufzählung nach dem Muster "Bei Strukturierung..., bei Aktivierung...".
- Ähnliche Punkte sollen zusammengeführt werden.
- Formuliere sachlich, professionell, konkret und entwicklungsorientiert.
- Schreibe in einem Stil, der direkt in ein offizielles Beratungsprotokoll übernommen werden kann.
- Verwende keine Ich-Form.
- Verwende keine Überschrift.
- Gib ausschließlich Stichpunkte aus.

Bei Einzel-BUV:
- Leite aus den Beobachtungen die wichtigsten Schwerpunkte für die Weiterarbeit bis zur Doppel-BUV ab.

Bei Doppel-BUV:
- Berücksichtige auch die bereits vorhandenen Punkte aus der Einzel-BUV.
- Zeige, welche Entwicklungsschwerpunkte weiterhin bedeutsam sind.
- Benenne Schwerpunkte für die weitere Ausbildung.
- Wiederhole die Einzel-BUV nicht, sondern leite daraus eine Entwicklungsperspektive ab.

Beispiele für den gewünschten Stil:
- Hinführungsphasen künftig stärker auf eine zentrale Problemstellung ausrichten, sodass sich Thema und Stundenfrage für die Schülerinnen und Schüler nachvollziehbar ergeben.
- Sicherungsphasen konsequenter als Antwort auf die leitende Fragestellung planen und zentrale Ergebnisse sichtbar festhalten.
- Unterrichtsgespräche durch Denkzeiten, Austauschphasen und gezielte Impulse breiter aktivierend anlegen.
- Fachliche Inhalte stärker reduzieren und zentrale Begriffe wiederholt aufgreifen, damit der Lernweg für die Lerngruppe klarer nachvollziehbar bleibt.

DATEN:
{context[:50000]}
"""

    return _chat(prompt)


def _chat(prompt: str) -> str:
    client = get_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Du formulierst präzise, sachlich und auf Deutsch.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content or ""


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
