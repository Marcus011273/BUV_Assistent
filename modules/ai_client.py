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
        # Auch Tabellen auslesen: BUV-Artikulationsschemata stehen oft darin.
        # In der Dokumentreihenfolge (python-docx mit iter_inner_content).
        parts: List[str] = []
        if hasattr(doc, "iter_inner_content"):
            for element in doc.iter_inner_content():
                if hasattr(element, "rows"):
                    for row in element.rows:
                        parts.append(" | ".join(cell.text.strip() for cell in row.cells))
                else:
                    parts.append(element.text)
        else:
            parts.extend(p.text for p in doc.paragraphs)
            for table in doc.tables:
                for row in table.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(part for part in parts if part.strip()).strip()

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


# Gemeinsamer Bewertungsmaßstab für Einzel- und Doppel-BUV.
# Die Prüfung bezieht sich auf die PLANUNG, nicht auf beobachteten Unterricht.
BUV_ANALYSE_KRITERIEN = """
Analysiere kritisch, fachlich präzise und beratungsorientiert anhand dieser fünf Bereiche:

1. Vorüberlegungen: Prüfe fachliche Richtigkeit und Tiefe der Sachanalyse,
   zentrale Fachbegriffe und Zusammenhänge, didaktische Reduktion,
   Lernvoraussetzungen und daraus tatsächlich abgeleitete Planungsentscheidungen.
   Benenne Lücken oder Widersprüche zwischen Sachanalyse und Stundenplanung.

2. Lehrplanbezug: Unterscheide eine formal richtige Zuordnung vom tatsächlichen
   Einlösen der fachlichen Anforderungen. Prüfe, ob die im Entwurf genannten
   Lehrplan-Kompetenzen und -Inhalte in ihrer Bedeutung und Tiefe aufgegriffen
   werden und die geforderten Handlungen und Denkprozesse stattfinden.
   Nur bei vorliegendem Lehrplanwortlaut ist ein inhaltlicher Wortlautabgleich
   möglich; ohne ihn Unsicherheit offen benennen, nichts erfinden.

3. Sequenz: Prüfe die logische Abfolge, den roten Faden, die kumulative
   Kompetenzentwicklung, mögliche Sprünge, Redundanzen, notwendige
   Zwischenschritte sowie die fachlich begründete Rolle der BUV-Stunde.

4. Kompetenzerwartungen: Prüfe die Präzision und Beobachtbarkeit der Ziele,
   passende Operatoren, fachliche Substanz, Alterspassung, Realisierbarkeit
   und kognitive Tiefe. Unterscheide reine Reproduktion von Erklären,
   Anwenden, Begründen, Beurteilen oder Transfer, soweit fachlich sinnvoll.
   Kompetenzen sollen Lernleistungen statt bloßer Unterrichtsaktivitäten
   beschreiben. Keine künstlich höheren Anforderungen verlangen.

5. Artikulation: Prüfe, ob Einstieg/Problemstellung, Erarbeitung, Auswertung,
   Sicherung und gegebenenfalls Anwendung die angestrebten Kompetenzen
   tatsächlich fördern. Beurteile konkrete Schülerhandlungen, Medien,
   Materialien, Sozialformen, Impulse, Arbeitsaufträge, Übergänge,
   Differenzierung, Zeitansätze und Überprüfung der Lernergebnisse.
   Unterscheide äußere Aktivierung von fachlich gehaltvollem Lernen.

Prüfe bereichsübergreifend die Kohärenz:
Lehrplan -> Sequenz -> Kompetenzerwartungen -> Schülerhandlungen -> Sicherung.
Decke besonders auf, wenn anspruchsvolle Ziele behauptet werden, die
Aufgaben und die Sicherung aber nur oberflächliche Leistungen ermöglichen.

Regeln:
- Nenne konkrete Stärken UND wichtige Schwächen, keine Gefälligkeitsanalyse.
- Begründe Kritik an erkennbaren Elementen der Planung; formuliere nach
  Möglichkeit einen konkreten, umsetzbaren Beratungsimpuls.
- Fehlende Angaben nicht automatisch als feststehende Planungsmängel werten.
- Erfinde weder Lehrplanformulierungen noch Unterrichtsdetails.
- Beurteile nur den Entwurf, nicht eine noch nicht beobachtete Durchführung.
- Berücksichtige Fach, Jahrgangsstufe, Lernvoraussetzungen und Zeitrahmen.
- Keine Note, keine pauschalen Qualitätsurteile.
"""


def analyze_draft_short(draft_text: str) -> List[str]:
    prompt = f"""
Du bist ein erfahrener Seminarrektor für das Lehramt Mittelschule in Bayern.

{BUV_ANALYSE_KRITERIEN}

AUSGABEFORMAT (verbindlich):
Gib GENAU fünf nummerierte EINZEILIGE Punkte zurück, in dieser Reihenfolge:
1. Vorüberlegungen: ...
2. Lehrplanbezug: ...
3. Sequenz: ...
4. Kompetenzerwartungen: ...
5. Artikulation: ...
Jeder Punkt besteht aus 2 bis 4 prägnanten Sätzen und enthält die
wichtigsten fachlichen Feststellungen einschließlich konkreter Kritik,
wo die Planung sie rechtfertigt. Keine zusätzlichen Überschriften,
Unterpunkte oder Zeilenumbrüche innerhalb eines Punktes.

UNTERRICHTSENTWURF:
{draft_text[:50000]}
"""
    text = _chat(prompt)
    return _split_bullets(text, max_items=5)


def split_doppel_buv_draft(draft_text: str) -> Dict[str, Any]:
    """Erkennt zwei Stunden und erstellt je eine fachlich vertiefte Kurzanalyse."""
    prompt = f"""
Du bist ein erfahrener Seminarrektor für das Lehramt Mittelschule in Bayern.

Analysiere einen Unterrichtsentwurf zu einer möglichen Doppel-BUV.
Prüfe, ob eine oder zwei Unterrichtsstunden enthalten sind, und ordne sie
anhand von Zeiten, Überschriften, Reihenfolge, Fächern, Klassen, Themen,
Kompetenzerwartungen und Artikulationsplänen eindeutig zu.

{BUV_ANALYSE_KRITERIEN}

WICHTIGE REGELN:
- Bei zwei erkennbaren Stunden: contains_two_lessons = true.
- Bei nur einer erkennbaren Stunde: contains_two_lessons = false.
- Wenn Uhrzeiten eindeutig sind, ordne die frühere als stunde_1 ein,
  sonst anhand der Reihenfolge im Dokument.
- Beurteile jede Stunde anhand ihrer eigenen Kompetenzerwartungen,
  Schülerhandlungen und Sicherung; ordne gemeinsame Vorüberlegungen
  bzw. die Sequenz sachgerecht zu.
- Erfinde keine Metadaten; lasse unbekannte Felder leer.
- Für jede vorhandene Stunde: kurzanalyse besteht aus GENAU fünf
  Strings, je ein String in der Reihenfolge Vorüberlegungen,
  Lehrplanbezug, Sequenz, Kompetenzerwartungen, Artikulation.
  Jeder String startet mit dem jeweiligen Bereichsnamen und Doppelpunkt,
  enthält 2 bis 4 prägnante Sätze und benennt nachvollziehbare Stärken,
  Schwächen und möglichst einen konkreten Beratungsimpuls.
- Wenn es nur eine Stunde gibt, bleiben die Felder von stunde_2 leer
  und kurzanalyse von stunde_2 ist eine leere Liste.
- Gib ausschließlich syntaktisch gültiges JSON zurück.

JSON-SCHEMA (Inhalt nur als Strukturbeispiel):
{{
  "contains_two_lessons": true,
  "confidence": "hoch",
  "reasoning_short": "",
  "metadata": {{"laa_name": "", "schule": "", "datum": ""}},
  "stunde_1": {{
    "fach": "", "klasse": "", "thema": "", "zeit": "",
    "kurzanalyse": [
      "Vorüberlegungen: ...", "Lehrplanbezug: ...", "Sequenz: ...",
      "Kompetenzerwartungen: ...", "Artikulation: ..."
    ]
  }},
  "stunde_2": {{
    "fach": "", "klasse": "", "thema": "", "zeit": "",
    "kurzanalyse": [
      "Vorüberlegungen: ...", "Lehrplanbezug: ...", "Sequenz: ...",
      "Kompetenzerwartungen: ...", "Artikulation: ..."
    ]
  }}
}}

UNTERRICHTSENTWURF:
{draft_text[:50000]}
"""

    raw = _chat(prompt)
    cleaned = _strip_json_fences(raw)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass

    raise RuntimeError(
        "Die KI konnte keine gültige Aufteilung der Doppel-BUV im JSON-Format zurückgeben."
    )


def convert_memos_to_beratungspunkte(
    observation_grid: Dict[str, Dict[str, str]],
    context_label: str,
) -> Dict[str, str]:
    """Formuliert ausschließlich Rohnotizen/Memos kriterienbezogen zu Beratungspunkten um.

    Wichtig:
    Positive Feststellungen werden bewusst NICHT an die KI übergeben,
    damit sie nicht im Feld Beratungspunkte erscheinen.
    """

    cleaned_grid: Dict[str, Dict[str, str]] = {}

    for kriterium, fields in observation_grid.items():
        if not isinstance(fields, dict):
            continue

        memo = str(fields.get("memo", "") or "").strip()
        vorhandene_beratungspunkte = str(fields.get("beratungspunkte", "") or "").strip()

        # Alte fehlerhafte KI-Ausgaben nicht erneut als Grundlage verwenden.
        if vorhandene_beratungspunkte.startswith("{") or vorhandene_beratungspunkte.startswith("["):
            vorhandene_beratungspunkte = ""

        cleaned_grid[str(kriterium)] = {
            "memo": memo,
            "vorhandene_beratungspunkte": vorhandene_beratungspunkte,
        }

    prompt = f"""
Du bist ein erfahrener Seminarrektor für das Lehramt Mittelschule in Bayern.

Formuliere aus den folgenden Rohnotizen und ggf. bereits vorhandenen Beratungspunkten
prägnante Beratungspunkte für ein Protokoll zur Besonderen Unterrichtsvorbereitung.

Kontext:
{context_label}

Sehr wichtig:
- Nutze ausschließlich die Felder "memo" und "vorhandene_beratungspunkte".
- Positive Feststellungen sind nicht Teil der Daten und dürfen nicht ergänzt, rekonstruiert oder wiederholt werden.
- Formuliere keine positiven Feststellungen.
- Schreibe im Feld Beratungspunkte nur Entwicklungs-, Beratungs- oder Weiterarbeitspunkte.
- Gib pro Kriterium ausschließlich einen String zurück.
- Gib keine Objekte, keine Listen und keine verschachtelten JSON-Strukturen zurück.
- Verwende keine Schlüssel wie "positive_feststellung", "positive_feststellungen", "memo" oder "beratungspunkte" innerhalb eines Rückgabewerts.

Regeln:
- Formuliere sachlich, klar und entwicklungsorientiert.
- Formuliere stichpunktartig.
- Maximal 2 Stichpunkte pro Kriterium.
- Keine langen Absätze.
- Keine Rohnotizen wortgleich übernehmen.
- Keine Dopplungen.
- Wenn zu einem Kriterium keine sinnvollen Rohnotizen oder Beratungshinweise vorliegen,
  gib für dieses Kriterium einen leeren String zurück.
- Gib ausschließlich valides JSON zurück.
- Die JSON-Schlüssel müssen exakt den Kriterien entsprechen.
- Die JSON-Werte müssen einfache Strings sein.

Beispiel für die gewünschte Ausgabe:
{{
  "Strukturierung / roter Faden": "- Material gezielter auswählen, um den fachlichen Fokus klarer sichtbar zu machen.",
  "Zielorientierung": "- Das Unterrichtsziel für die Schülerinnen und Schüler durchgängig transparenter machen."
}}

DATEN:
{json.dumps(cleaned_grid, ensure_ascii=False, indent=2)}
"""

    raw = _chat(prompt)
    cleaned = _strip_json_fences(raw)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return {
                str(k): _normalize_beratungspunkt_value(v)
                for k, v in data.items()
            }
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(cleaned[start : end + 1])
                if isinstance(data, dict):
                    return {
                        str(k): _normalize_beratungspunkt_value(v)
                        for k, v in data.items()
                    }
            except json.JSONDecodeError:
                pass

    raise RuntimeError(
        "Die KI konnte keine gültigen Beratungspunkte im JSON-Format zurückgeben."
    )

def _normalize_beratungspunkt_value(value: Any) -> str:
    """
    Macht KI-Rückgaben robust:
    - String bleibt String
    - Liste wird zu Stichpunkten
    - Dict wird bereinigt, sodass positive Feststellungen nicht übernommen werden
    """

    if value is None:
        return ""

    if isinstance(value, str):
        text = value.strip()

        # Falls die KI doch JSON als String zurückgibt, versuchen wir es zu bereinigen.
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = json.loads(text)
                return _normalize_beratungspunkt_value(parsed)
            except Exception:
                return ""

        return text

    if isinstance(value, list):
        lines = []

        for item in value:
            item_text = _normalize_beratungspunkt_value(item)

            if item_text:
                lines.append(item_text)

        return "\n".join(lines).strip()

    if isinstance(value, dict):
        # Positive Feststellungen ausdrücklich ignorieren.
        for forbidden_key in [
            "positive_feststellung",
            "positive_feststellungen",
            "positive",
            "positiv",
        ]:
            value.pop(forbidden_key, None)

        for preferred_key in [
            "beratungspunkte",
            "beratungspunkt",
            "hinweise",
            "entwicklungspunkte",
            "weiterarbeit",
        ]:
            if preferred_key in value:
                return _normalize_beratungspunkt_value(value.get(preferred_key))

        # Keine sichere Beratungspunkt-Struktur erkannt.
        return ""

    return str(value).strip()

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
