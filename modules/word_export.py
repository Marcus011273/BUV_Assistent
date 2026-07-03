from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Iterable

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt


def create_word_document(protocol: Dict[str, Any]) -> bytes:
    doc = Document()
    _set_styles(doc)

    title = doc.add_heading("Besondere Unterrichtsvorbereitung", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    stammdaten = protocol.get("stammdaten", {})
    _add_meta_table(
        doc,
        [
            ("Name LAA", stammdaten.get("laa_name", "")),
            ("Besondere Unterrichtsvorbereitung", f"{stammdaten.get('buv_nummer', '')}. Besondere Unterrichtsvorbereitung"),
            ("Seminarjahr", stammdaten.get("seminarjahr", "")),
            ("Schule", stammdaten.get("schule", "")),
            ("Bemerkungen", stammdaten.get("bemerkungen", "")),
        ],
    )

    _add_section_einzel_buv(doc, protocol.get("einzel_buv", {}))
    _add_section_doppel_buv(doc, protocol.get("doppel_buv", {}))
    _add_section_kompetenzen(doc, protocol.get("kompetenzen", {}))

    doc.add_heading("Zielvereinbarungen des LAA", level=1)
    doc.add_paragraph(
        "Bitte tragen Sie hier Ihre Zielvereinbarungen ein und senden Sie das Dokument anschließend zurück."
    )
    einzel_zv = protocol.get("einzel_buv", {}).get("zielvereinbarungen_laa", "")
    doppel_zv = protocol.get("doppel_buv", {}).get("zielvereinbarungen_laa", "")

    doc.add_heading("Zur Einzel-BUV", level=2)
    _add_multiline_or_blanks(doc, einzel_zv, blank_lines=4)
    doc.add_heading("Zur Doppel-BUV", level=2)
    _add_multiline_or_blanks(doc, doppel_zv, blank_lines=4)

    doc.add_paragraph()
    _add_signature_lines(doc)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _set_styles(doc: Document) -> None:
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10)
    for style_name in ["Heading 1", "Heading 2", "Heading 3"]:
        doc.styles[style_name].font.name = "Arial"


def _add_meta_table(doc: Document, rows: Iterable[tuple[str, str]]) -> None:
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = str(label)
        cells[1].text = str(value or "")
    doc.add_paragraph()


def _add_section_einzel_buv(doc: Document, einzel: Dict[str, Any]) -> None:
    doc.add_heading("Einzel-BUV", level=1)
    _add_meta_table(
        doc,
        [
            ("Datum", einzel.get("datum", "")),
            ("Fach", einzel.get("fach", "")),
            ("Klasse", einzel.get("klasse", "")),
            ("Thema", einzel.get("thema", "")),
        ],
    )
    _add_analysis(doc, "Kurzanalyse des Entwurfs", einzel.get("entwurf_analyse", []))
    _add_observations(doc, einzel.get("beobachtungen", {}))
    _add_text_block(doc, "Zusammenfassung zur Weiterarbeit – Besprechung der Einzel-BUV", einzel.get("zusammenfassung_weiterarbeit", ""))


def _add_section_doppel_buv(doc: Document, doppel: Dict[str, Any]) -> None:
    doc.add_heading("Doppel-BUV", level=1)
    _add_meta_table(doc, [("Datum", doppel.get("datum", ""))])
    _add_analysis(doc, "Kurzanalyse des Entwurfs", doppel.get("entwurf_analyse", []))

    for key, label in [("stunde_1", "Doppel-BUV – 1. Stunde"), ("stunde_2", "Doppel-BUV – 2. Stunde")]:
        stunde = doppel.get(key, {})
        doc.add_heading(label, level=2)
        _add_meta_table(
            doc,
            [
                ("Fach", stunde.get("fach", "")),
                ("Klasse", stunde.get("klasse", "")),
                ("Thema", stunde.get("thema", "")),
            ],
        )
        _add_observations(doc, stunde.get("beobachtungen", {}))

    _add_text_block(doc, "Zusammenfassung zur Weiterarbeit – Besprechung der Doppel-BUV", doppel.get("zusammenfassung_weiterarbeit", ""))


def _add_section_kompetenzen(doc: Document, kompetenzen: Dict[str, Any]) -> None:
    doc.add_heading("Erzieherische Kompetenz", level=1)
    erzieh = kompetenzen.get("erzieherische_kompetenz", {})
    _add_text_block(doc, "Positive Feststellungen", erzieh.get("positive_feststellungen", ""), heading_level=2)
    _add_text_block(doc, "Beratungspunkte", erzieh.get("beratungspunkte", ""), heading_level=2)

    _add_text_block(doc, "Handlungs- und Sachkompetenz", kompetenzen.get("handlungs_und_sachkompetenz", ""), heading_level=1)
    _add_text_block(doc, "Einbringen in Schule und Seminar", kompetenzen.get("einbringen_schule_und_seminar", ""), heading_level=1)


def _add_observations(doc: Document, observations: Dict[str, Dict[str, str]]) -> None:
    doc.add_heading("Unterrichtskompetenz – Beobachtungen", level=2)
    for kriterium, fields in observations.items():
        if not any((fields or {}).values()):
            continue
        doc.add_heading(kriterium, level=3)
        if fields.get("positive_feststellungen"):
            _add_text_block(doc, "Positive Feststellungen", fields.get("positive_feststellungen", ""), heading_level=None)
        if fields.get("beratungspunkte"):
            _add_text_block(doc, "Beratungspunkte", fields.get("beratungspunkte", ""), heading_level=None)
        if fields.get("memo"):
            _add_text_block(doc, "Memo / Rohnotizen", fields.get("memo", ""), heading_level=None)


def _add_analysis(doc: Document, title: str, points: Any) -> None:
    doc.add_heading(title, level=2)
    if isinstance(points, str):
        points = [line.strip("- ") for line in points.splitlines() if line.strip()]
    if not points:
        doc.add_paragraph("—")
        return
    for point in points:
        doc.add_paragraph(str(point), style="List Bullet")


def _add_text_block(doc: Document, title: str, text: str, heading_level: int | None = 2) -> None:
    if heading_level is not None:
        doc.add_heading(title, level=heading_level)
    else:
        p = doc.add_paragraph()
        run = p.add_run(f"{title}: ")
        run.bold = True
    if text:
        for line in str(text).splitlines():
            if line.strip():
                doc.add_paragraph(line.strip())
    else:
        doc.add_paragraph("—")


def _add_multiline_or_blanks(doc: Document, text: str, blank_lines: int = 3) -> None:
    if text and text.strip():
        for line in text.splitlines():
            doc.add_paragraph(line)
    else:
        for _ in range(blank_lines):
            doc.add_paragraph("- ")


def _add_signature_lines(doc: Document) -> None:
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "München, den ____________________"
    table.rows[0].cells[1].text = "München, den ____________________"
    table.rows[1].cells[0].text = "Marcus Müller, Seminarrektor"
    table.rows[1].cells[1].text = "Unterschrift LAA"
