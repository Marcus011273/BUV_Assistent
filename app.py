from __future__ import annotations

import streamlit as st

from modules.ai_client import (
    analyze_draft_short,
    extract_metadata_from_draft,
    extract_text_from_upload,
    has_api_key,
    summarize_observations,
)
from modules.protocol_model import KRITERIEN, create_empty_protocol, ensure_protocol_shape
from modules.storage import build_base_filename, load_protocol_from_bytes, protocol_to_json_bytes
from modules.word_export import create_word_document

st.set_page_config(page_title="BUV-Protokoll", page_icon="📝", layout="wide")


def init_state() -> None:
    if "protocol" not in st.session_state:
        st.session_state.protocol = create_empty_protocol()
    else:
        st.session_state.protocol = ensure_protocol_shape(st.session_state.protocol)


init_state()


def sync_widget_values_from_protocol() -> None:
    """Erzwingt, dass Widgets nach KI-/JSON-Änderungen neu aus dem Protokoll befüllt werden.

    Streamlit merkt sich Eingabefelder über den `key`. Wenn ein Feld einmal leer
    angezeigt wurde, überschreibt der gespeicherte Widget-Wert den neuen `value`.
    Deshalb löschen wir bei Bedarf die betroffenen Widget-Keys vor dem Zeichnen der
    Felder. Danach nimmt Streamlit wieder den Wert aus dem Protokollmodell.
    """
    if not st.session_state.pop("_sync_widgets_from_protocol", False):
        return

    keys_to_clear = [
        "stamm_laa",
        "stamm_schule",
        "stamm_seminarjahr",
        "stamm_bemerkungen",
        "stamm_buv_nummer",
        "einzel_datum",
        "einzel_fach",
        "einzel_klasse",
        "einzel_thema",
        "einzel_analyse_text",
        "einzel_zusammenfassung",
        "einzel_zv",
        "doppel_datum",
        "doppel_analyse_text",
        "doppel_zusammenfassung",
        "doppel_zv",
        "stunde_1_fach",
        "stunde_1_klasse",
        "stunde_1_thema",
        "stunde_2_fach",
        "stunde_2_klasse",
        "stunde_2_thema",
        "erz_pos",
        "erz_ber",
        "hand_sach",
        "einbringen",
    ]

    for key in keys_to_clear:
        st.session_state.pop(key, None)


sync_widget_values_from_protocol()

st.title("Besondere Unterrichtsvorbereitung")
st.caption("Internes Seminar-Tool: Arbeitsstand lokal als JSON speichern, Protokoll als Word-Dokument exportieren.")

notice = st.session_state.pop("_notice", None)
if notice:
    st.success(notice)

with st.sidebar:
    st.header("Arbeitsstand")

    if st.button("Neues Protokoll", use_container_width=True):
        st.session_state.protocol = create_empty_protocol()
        st.session_state["_sync_widgets_from_protocol"] = True
        st.session_state["_notice"] = "Neues Protokoll angelegt."
        st.rerun()

    uploaded_json = st.file_uploader("JSON-Arbeitsstand hochladen", type=["json"])
    if uploaded_json is not None:
        try:
            st.session_state.protocol = load_protocol_from_bytes(uploaded_json.getvalue())
            st.session_state["_sync_widgets_from_protocol"] = True
            st.session_state["_notice"] = "Arbeitsstand geladen."
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    protocol = st.session_state.protocol
    base_name = build_base_filename(protocol)

    st.download_button(
        "Arbeitsstand als JSON herunterladen",
        data=protocol_to_json_bytes(protocol),
        file_name=f"{base_name}_arbeitsstand.json",
        mime="application/json",
        use_container_width=True,
    )

    st.divider()
    if has_api_key():
        st.success("KI-Schlüssel gefunden")
    else:
        st.warning("Kein KI-Schlüssel gefunden. KI-Buttons funktionieren erst mit OPENAI_API_KEY.")

protocol = st.session_state.protocol


def persist_protocol() -> None:
    st.session_state.protocol = ensure_protocol_shape(protocol)


def save_back() -> None:
    st.session_state.protocol = ensure_protocol_shape(protocol)


def text_input(label: str, container: dict, field_key: str, **kwargs) -> None:
    container[field_key] = st.text_input(label, value=container.get(field_key, ""), **kwargs)


def text_area(label: str, container: dict, field_key: str, height: int = 120, **kwargs) -> None:
    container[field_key] = st.text_area(label, value=container.get(field_key, ""), height=height, **kwargs)


def edit_observation_grid(grid: dict, prefix: str) -> None:
    for kriterium in KRITERIEN:
        fields = grid.setdefault(kriterium, {"positive_feststellungen": "", "beratungspunkte": "", "memo": ""})
        with st.expander(kriterium, expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                text_area("Positive Feststellungen", fields, "positive_feststellungen", key=f"{prefix}_{kriterium}_pos")
            with c2:
                text_area("Beratungspunkte", fields, "beratungspunkte", key=f"{prefix}_{kriterium}_ber")
            with c3:
                text_area("Memo / Rohnotizen", fields, "memo", key=f"{prefix}_{kriterium}_memo")


def draft_upload_section(target: dict, label: str, metadata_target: str) -> None:
    st.subheader(label)
    uploaded = st.file_uploader(
        "Unterrichtsentwurf hochladen (PDF, DOCX oder TXT)",
        type=["pdf", "docx", "txt"],
        key=f"upload_{metadata_target}",
    )
    if uploaded:
        draft_text = extract_text_from_upload(uploaded)
        with st.expander("Ausgelesener Text anzeigen"):
            st.text_area("Text", draft_text[:20000], height=250, key=f"draft_text_{metadata_target}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Stammdaten aus Entwurf erkennen", key=f"meta_{metadata_target}"):
                try:
                    meta = extract_metadata_from_draft(draft_text)
                    apply_metadata(meta, metadata_target)
                    persist_protocol()
                    st.session_state["_sync_widgets_from_protocol"] = True
                    st.session_state["_notice"] = "Stammdaten übernommen. Bitte prüfen und ggf. korrigieren."
                    st.rerun()
                except Exception as exc:
                    st.error(f"KI-Fehler: {exc}")
        with c2:
            if st.button("Entwurf kurz analysieren", key=f"analyse_{metadata_target}"):
                try:
                    target["entwurf_analyse"] = analyze_draft_short(draft_text)
                    persist_protocol()
                    st.session_state["_sync_widgets_from_protocol"] = True
                    st.session_state["_notice"] = "Kurzanalyse erstellt."
                    st.rerun()
                except Exception as exc:
                    st.error(f"KI-Fehler: {exc}")


def apply_metadata(meta: dict, target: str) -> None:
    stammdaten = protocol["stammdaten"]
    if meta.get("laa_name"):
        stammdaten["laa_name"] = meta["laa_name"]
    if meta.get("schule"):
        stammdaten["schule"] = meta["schule"]

    if target == "einzel":
        einzel = protocol["einzel_buv"]
        for source, dest in [("datum", "datum"), ("fach", "fach"), ("klasse", "klasse"), ("thema", "thema")]:
            if meta.get(source):
                einzel[dest] = meta[source]
    elif target == "doppel":
        doppel = protocol["doppel_buv"]
        if meta.get("datum"):
            doppel["datum"] = meta["datum"]
        # Fach/Klasse/Thema zunächst in Stunde 1 eintragen; du kannst es danach ändern.
        stunde_1 = doppel["stunde_1"]
        for source, dest in [("fach", "fach"), ("klasse", "klasse"), ("thema", "thema")]:
            if meta.get(source):
                stunde_1[dest] = meta[source]


tabs = st.tabs([
    "Stammdaten",
    "Einzel-BUV",
    "Doppel-BUV",
    "Kompetenzen",
    "Export",
])

with tabs[0]:
    st.header("Stammdaten")
    stammdaten = protocol["stammdaten"]
    c1, c2 = st.columns(2)
    with c1:
        text_input("Name LAA", stammdaten, "laa_name", key="stamm_laa")
        stammdaten["buv_nummer"] = st.selectbox(
            "Nummer der Besonderen Unterrichtsvorbereitung",
            ["1", "2", "3", "4"],
            index=max(0, ["1", "2", "3", "4"].index(str(stammdaten.get("buv_nummer", "1"))) if str(stammdaten.get("buv_nummer", "1")) in ["1", "2", "3", "4"] else 0),
            key="stamm_buv_nummer",
        )
    with c2:
        text_input("Seminarjahr", stammdaten, "seminarjahr", key="stamm_seminarjahr")
        text_input("Schule", stammdaten, "schule", key="stamm_schule")
    text_area("Bemerkungen", stammdaten, "bemerkungen", height=100, key="stamm_bemerkungen")
    save_back()

with tabs[1]:
    st.header("Einzel-BUV")
    einzel = protocol["einzel_buv"]
    draft_upload_section(einzel, "Vor dem Unterrichtsbesuch", "einzel")

    st.subheader("Stammdaten der Einzel-BUV")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        text_input("Datum", einzel, "datum", key="einzel_datum")
    with c2:
        text_input("Fach", einzel, "fach", key="einzel_fach")
    with c3:
        text_input("Klasse", einzel, "klasse", key="einzel_klasse")
    with c4:
        text_input("Thema", einzel, "thema", key="einzel_thema")

    st.subheader("Kurzanalyse des Entwurfs")
    einzel["entwurf_analyse"] = st.text_area(
        "Maximal 5 Stichpunkte, je Zeile ein Punkt",
        value="\n".join(einzel.get("entwurf_analyse", [])) if isinstance(einzel.get("entwurf_analyse"), list) else str(einzel.get("entwurf_analyse", "")),
        height=140,
        key="einzel_analyse_text",
    ).splitlines()

    st.subheader("Beobachtungen zur Unterrichtsdurchführung")
    edit_observation_grid(einzel["beobachtungen"], "einzel")

    if st.button("Notizen zur Einzel-BUV verdichten", key="summarize_einzel"):
        try:
            einzel["zusammenfassung_weiterarbeit"] = summarize_observations(protocol, "Einzel-BUV")
            persist_protocol()
            st.session_state["_sync_widgets_from_protocol"] = True
            st.session_state["_notice"] = "Zusammenfassung zur Einzel-BUV erstellt."
            st.rerun()
        except Exception as exc:
            st.error(f"KI-Fehler: {exc}")

    text_area("Zusammenfassung zur Weiterarbeit – Besprechung der Einzel-BUV", einzel, "zusammenfassung_weiterarbeit", height=180, key="einzel_zusammenfassung")
    text_area("Zielvereinbarungen des LAA zur Einzel-BUV", einzel, "zielvereinbarungen_laa", height=120, key="einzel_zv")
    save_back()

with tabs[2]:
    st.header("Doppel-BUV")
    doppel = protocol["doppel_buv"]
    draft_upload_section(doppel, "Vor dem Unterrichtsbesuch", "doppel")
    text_input("Datum der Doppel-BUV", doppel, "datum", key="doppel_datum")

    st.subheader("Kurzanalyse des Entwurfs")
    doppel["entwurf_analyse"] = st.text_area(
        "Maximal 5 Stichpunkte, je Zeile ein Punkt",
        value="\n".join(doppel.get("entwurf_analyse", [])) if isinstance(doppel.get("entwurf_analyse"), list) else str(doppel.get("entwurf_analyse", "")),
        height=140,
        key="doppel_analyse_text",
    ).splitlines()

    for stunde_key, label in [("stunde_1", "Doppel-BUV – 1. Stunde"), ("stunde_2", "Doppel-BUV – 2. Stunde")]:
        st.subheader(label)
        stunde = doppel[stunde_key]
        c1, c2, c3 = st.columns(3)
        with c1:
            text_input("Fach", stunde, "fach", key=f"{stunde_key}_fach")
        with c2:
            text_input("Klasse", stunde, "klasse", key=f"{stunde_key}_klasse")
        with c3:
            text_input("Thema", stunde, "thema", key=f"{stunde_key}_thema")
        edit_observation_grid(stunde["beobachtungen"], stunde_key)

    if st.button("Notizen zur Doppel-BUV verdichten", key="summarize_doppel"):
        try:
            doppel["zusammenfassung_weiterarbeit"] = summarize_observations(protocol, "Doppel-BUV")
            persist_protocol()
            st.session_state["_sync_widgets_from_protocol"] = True
            st.session_state["_notice"] = "Zusammenfassung zur Doppel-BUV erstellt."
            st.rerun()
        except Exception as exc:
            st.error(f"KI-Fehler: {exc}")

    text_area("Zusammenfassung zur Weiterarbeit – Besprechung der Doppel-BUV", doppel, "zusammenfassung_weiterarbeit", height=180, key="doppel_zusammenfassung")
    text_area("Zielvereinbarungen des LAA zur Doppel-BUV", doppel, "zielvereinbarungen_laa", height=120, key="doppel_zv")
    save_back()

with tabs[3]:
    st.header("Kompetenzen")
    kompetenzen = protocol["kompetenzen"]
    erzieh = kompetenzen["erzieherische_kompetenz"]
    st.subheader("Erzieherische Kompetenz")
    c1, c2 = st.columns(2)
    with c1:
        text_area("Positive Feststellungen", erzieh, "positive_feststellungen", height=160, key="erz_pos")
    with c2:
        text_area("Beratungspunkte", erzieh, "beratungspunkte", height=160, key="erz_ber")

    text_area("Handlungs- und Sachkompetenz", kompetenzen, "handlungs_und_sachkompetenz", height=160, key="hand_sach")
    text_area("Einbringen in Schule und Seminar", kompetenzen, "einbringen_schule_und_seminar", height=160, key="einbringen")
    save_back()

with tabs[4]:
    st.header("Export")
    base_name = build_base_filename(protocol)
    st.write("Lade hier deinen lokalen Arbeitsstand oder das Word-Protokoll herunter.")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "JSON-Arbeitsstand herunterladen",
            data=protocol_to_json_bytes(protocol),
            file_name=f"{base_name}_arbeitsstand.json",
            mime="application/json",
            use_container_width=True,
        )
    with c2:
        try:
            docx_bytes = create_word_document(protocol)
            st.download_button(
                "Word-Protokoll herunterladen",
                data=docx_bytes,
                file_name=f"{base_name}_protokoll.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"Word-Export fehlgeschlagen: {exc}")

    st.info("Hinweis: Das Word-Dokument enthält offene Felder für die Zielvereinbarungen des LAA.")
