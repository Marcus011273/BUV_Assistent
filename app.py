from __future__ import annotations

import streamlit as st

from modules.ai_client import (
    analyze_draft_short,
    convert_memos_to_beratungspunkte,
    extract_metadata_from_draft,
    extract_text_from_upload,
    has_api_key,
    summarize_observations,
)
from modules.protocol_model import (
    KRITERIEN,
    SCHRIFTWESEN_ITEMS,
    create_empty_protocol,
    ensure_protocol_shape,
)
from modules.storage import build_base_filename, load_protocol_from_bytes, protocol_to_json_bytes
from modules.word_export import create_word_document


st.set_page_config(page_title="BUV-Protokoll", page_icon="📝", layout="wide")


def init_state() -> None:
    if "protocol" not in st.session_state:
        st.session_state.protocol = create_empty_protocol()
    else:
        st.session_state.protocol = ensure_protocol_shape(st.session_state.protocol)

    if "_widget_version" not in st.session_state:
        st.session_state["_widget_version"] = 0


init_state()


def get_widget_version() -> int:
    """Version der Eingabefelder.

    Wenn die App Daten programmgesteuert verändert, z. B. durch KI oder JSON-Upload,
    erhöhen wir diese Version. Dadurch bekommen die Eingabefelder neue Keys und
    Streamlit liest die Werte frisch aus dem Protokollmodell.
    """
    return st.session_state.get("_widget_version", 0)


def widget_key(base_key: str) -> str:
    """Erzeugt einen versionsabhängigen Widget-Key."""
    return f"{base_key}_v{get_widget_version()}"


def rerun_with_fresh_widgets(notice: str) -> None:
    """Erhöht die Widget-Version und startet die App neu.

    Dadurch werden Textfelder, deren Werte durch KI oder JSON-Upload verändert wurden,
    zuverlässig neu aus dem Protokoll befüllt.
    """
    st.session_state["_widget_version"] = get_widget_version() + 1
    st.session_state["_notice"] = notice
    st.rerun()


st.title("Besondere Unterrichtsvorbereitung")
st.caption(
    "Internes Seminar-Tool: Arbeitsstand lokal als JSON speichern, "
    "Protokoll als Word-Dokument exportieren."
)

notice = st.session_state.pop("_notice", None)
if notice:
    st.success(notice)

if "_last_metadata" in st.session_state:
    with st.expander("Zuletzt erkannte Stammdaten der KI anzeigen"):
        st.json(st.session_state["_last_metadata"])


with st.sidebar:
    st.header("Arbeitsstand")

    if st.button("Neues Protokoll", use_container_width=True):
        st.session_state.protocol = create_empty_protocol()
        rerun_with_fresh_widgets("Neues Protokoll angelegt.")

    uploaded_json = st.file_uploader(
        "JSON-Arbeitsstand hochladen",
        type=["json"],
        key="json_upload",
    )

    if uploaded_json is not None:
        st.info(f"Ausgewählte Datei: {uploaded_json.name}")

        if st.button("Arbeitsstand aus JSON übernehmen", use_container_width=True):
            try:
                st.session_state.protocol = load_protocol_from_bytes(uploaded_json.getvalue())
                rerun_with_fresh_widgets("Arbeitsstand aus JSON übernommen.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Arbeitsstand konnte nicht geladen werden: {exc}")

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
    base_key = kwargs.pop("key", field_key)
    container[field_key] = st.text_input(
        label,
        value=container.get(field_key, ""),
        key=widget_key(base_key),
        **kwargs,
    )


def text_area(label: str, container: dict, field_key: str, height: int = 120, **kwargs) -> None:
    base_key = kwargs.pop("key", field_key)
    container[field_key] = st.text_area(
        label,
        value=container.get(field_key, ""),
        height=height,
        key=widget_key(base_key),
        **kwargs,
    )


def edit_observation_grid(grid: dict, prefix: str) -> None:
    for kriterium in KRITERIEN:
        fields = grid.setdefault(
            kriterium,
            {
                "positive_feststellungen": "",
                "beratungspunkte": "",
                "memo": "",
            },
        )

        with st.expander(kriterium, expanded=False):
            c1, c2, c3 = st.columns(3)

            with c1:
                text_area(
                    "Positive Feststellungen",
                    fields,
                    "positive_feststellungen",
                    key=f"{prefix}_{kriterium}_pos",
                )

            with c2:
                text_area(
                    "Beratungspunkte",
                    fields,
                    "beratungspunkte",
                    key=f"{prefix}_{kriterium}_ber",
                )

            with c3:
                text_area(
                    "Memo / Rohnotizen",
                    fields,
                    "memo",
                    key=f"{prefix}_{kriterium}_memo",
                )


def apply_ai_beratungspunkte_to_grid(grid: dict, context_label: str) -> None:
    result = convert_memos_to_beratungspunkte(grid, context_label)

    for kriterium, text in result.items():
        if kriterium in grid and text.strip():
            grid[kriterium]["beratungspunkte"] = text.strip()

def edit_schriftwesen_table(kompetenzen: dict) -> None:
    schriftwesen = kompetenzen.setdefault("schriftwesen", {})

    st.subheader("Handlungs- und Sachkompetenz – Schriftwesen")
    st.caption("Das Datum wird im Word-Dokument automatisch aus dem Datum der Doppel-BUV übernommen.")

    header_cols = st.columns([3.5, 1.2, 3.5])
    header_cols[0].markdown("**Bereich**")
    header_cols[1].markdown("**Status**")
    header_cols[2].markdown("**Bemerkung**")

    status_options = ["OK", "fehlt", "--"]

    for index, item in enumerate(SCHRIFTWESEN_ITEMS):
        row = schriftwesen.setdefault(item, {"status": "OK", "bemerkung": ""})
        current_status = row.get("status", "OK")

        if current_status not in status_options:
            current_status = "OK"

        cols = st.columns([3.5, 1.2, 3.5])

        with cols[0]:
            st.write(item)

        with cols[1]:
            row["status"] = st.selectbox(
                "Status",
                status_options,
                index=status_options.index(current_status),
                key=widget_key(f"schriftwesen_status_{index}"),
                label_visibility="collapsed",
            )

        with cols[2]:
            row["bemerkung"] = st.text_input(
                "Bemerkung",
                value=row.get("bemerkung", ""),
                key=widget_key(f"schriftwesen_bemerkung_{index}"),
                label_visibility="collapsed",
            )

def apply_metadata(meta: dict, target: str) -> None:
    """Übernimmt erkannte Stammdaten aus der KI-Antwort ins Protokoll."""
    stammdaten = protocol["stammdaten"]

    if meta.get("laa_name"):
        stammdaten["laa_name"] = meta["laa_name"]

    if meta.get("schule"):
        stammdaten["schule"] = meta["schule"]

    if target == "einzel":
        einzel = protocol["einzel_buv"]

        for source, dest in [
            ("datum", "datum"),
            ("fach", "fach"),
            ("klasse", "klasse"),
            ("thema", "thema"),
        ]:
            if meta.get(source):
                einzel[dest] = meta[source]

    elif target in ["doppel_1", "doppel_2"]:
        doppel = protocol["doppel_buv"]

        if meta.get("datum"):
            doppel["datum"] = meta["datum"]

        stunde_key = "stunde_1" if target == "doppel_1" else "stunde_2"
        stunde = doppel[stunde_key]

        for source, dest in [
            ("fach", "fach"),
            ("klasse", "klasse"),
            ("thema", "thema"),
        ]:
            if meta.get(source):
                stunde[dest] = meta[source]


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
            st.text_area(
                "Text",
                draft_text[:20000],
                height=250,
                key=f"draft_text_{metadata_target}",
            )

        c1, c2 = st.columns(2)

        with c1:
            if st.button("Stammdaten aus Entwurf erkennen", key=f"meta_{metadata_target}"):
                try:
                    meta = extract_metadata_from_draft(draft_text)
                    apply_metadata(meta, metadata_target)
                    persist_protocol()
                    st.session_state["_last_metadata"] = meta
                    rerun_with_fresh_widgets(
                        "Stammdaten übernommen. Bitte prüfen und ggf. korrigieren."
                    )
                except Exception as exc:
                    st.error(f"KI-Fehler: {exc}")

        with c2:
            if st.button("Entwurf kurz analysieren", key=f"analyse_{metadata_target}"):
                try:
                    target["entwurf_analyse"] = analyze_draft_short(draft_text)
                    persist_protocol()
                    rerun_with_fresh_widgets("Kurzanalyse erstellt.")
                except Exception as exc:
                    st.error(f"KI-Fehler: {exc}")


tabs = st.tabs(
    [
        "Stammdaten",
        "Einzel-BUV",
        "Doppel-BUV",
        "Kompetenzen",
        "Export",
    ]
)


with tabs[3]:
    st.header("Kompetenzen")

    kompetenzen = protocol["kompetenzen"]
    erzieh = kompetenzen["erzieherische_kompetenz"]

    st.subheader("Erzieherische Kompetenz")

    c1, c2 = st.columns(2)

    with c1:
        text_area(
            "Positive Feststellungen",
            erzieh,
            "positive_feststellungen",
            height=160,
            key="erz_pos",
        )

    with c2:
        text_area(
            "Beratungspunkte",
            erzieh,
            "beratungspunkte",
            height=160,
            key="erz_ber",
        )

    st.divider()

    edit_schriftwesen_table(kompetenzen)

    text_area(
        "Weitere Hinweise zur Handlungs- und Sachkompetenz",
        kompetenzen,
        "handlungs_und_sachkompetenz",
        height=120,
        key="hand_sach",
    )

    st.divider()

    text_area(
        "Einbringen in Schule und Seminar",
        kompetenzen,
        "einbringen_schule_und_seminar",
        height=160,
        key="einbringen",
    )

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

    analyse_value = (
        "\n".join(einzel.get("entwurf_analyse", []))
        if isinstance(einzel.get("entwurf_analyse"), list)
        else str(einzel.get("entwurf_analyse", ""))
    )

    einzel["entwurf_analyse"] = st.text_area(
        "Maximal 5 Stichpunkte, je Zeile ein Punkt",
        value=analyse_value,
        height=140,
        key=widget_key("einzel_analyse_text"),
    ).splitlines()

    st.subheader("Beobachtungen zur Unterrichtsdurchführung")

    edit_observation_grid(einzel["beobachtungen"], "einzel")

    if st.button("Rohnotizen der Einzel-BUV in Beratungspunkte umwandeln", key="convert_einzel_memos"):
        try:
            apply_ai_beratungspunkte_to_grid(
                einzel["beobachtungen"],
                "Einzel-BUV",
            )
            persist_protocol()
            rerun_with_fresh_widgets("Rohnotizen wurden in Beratungspunkte umgewandelt.")
        except Exception as exc:
            st.error(f"KI-Fehler: {exc}")

    if st.button("Notizen zur Einzel-BUV verdichten", key="summarize_einzel"):
        try:
            einzel["zusammenfassung_weiterarbeit"] = summarize_observations(
                protocol,
                "Einzel-BUV",
            )
            persist_protocol()
            rerun_with_fresh_widgets("Zusammenfassung zur Einzel-BUV erstellt.")
        except Exception as exc:
            st.error(f"KI-Fehler: {exc}")

    text_area(
        "Zusammenfassung zur Weiterarbeit – Besprechung der Einzel-BUV",
        einzel,
        "zusammenfassung_weiterarbeit",
        height=180,
        key="einzel_zusammenfassung",
    )

    text_area(
        "Zielvereinbarungen des LAA zur Einzel-BUV",
        einzel,
        "zielvereinbarungen_laa",
        height=120,
        key="einzel_zv",
    )

    save_back()


with tabs[2]:
    st.header("Doppel-BUV")

    doppel = protocol["doppel_buv"]

    text_input("Datum der Doppel-BUV", doppel, "datum", key="doppel_datum")

    for stunde_key, label, metadata_target in [
        ("stunde_1", "Doppel-BUV – 1. Stunde", "doppel_1"),
        ("stunde_2", "Doppel-BUV – 2. Stunde", "doppel_2"),
    ]:
        st.divider()
        st.subheader(label)

        stunde = doppel[stunde_key]

        draft_upload_section(
            stunde,
            f"Entwurf hochladen – {label}",
            metadata_target,
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            text_input("Fach", stunde, "fach", key=f"{stunde_key}_fach")

        with c2:
            text_input("Klasse", stunde, "klasse", key=f"{stunde_key}_klasse")

        with c3:
            text_input("Thema", stunde, "thema", key=f"{stunde_key}_thema")

        st.subheader(f"Kurzanalyse des Entwurfs – {label}")

        analyse_value = (
            "\n".join(stunde.get("entwurf_analyse", []))
            if isinstance(stunde.get("entwurf_analyse"), list)
            else str(stunde.get("entwurf_analyse", ""))
        )

        stunde["entwurf_analyse"] = st.text_area(
            "Maximal 5 Stichpunkte, je Zeile ein Punkt",
            value=analyse_value,
            height=140,
            key=widget_key(f"{stunde_key}_analyse_text"),
        ).splitlines()

        st.subheader(f"Beobachtungen – {label}")

        edit_observation_grid(stunde["beobachtungen"], stunde_key)

        if st.button(
            f"Rohnotizen {label} in Beratungspunkte umwandeln",
            key=f"convert_{stunde_key}_memos",
        ):
            try:
                apply_ai_beratungspunkte_to_grid(
                    stunde["beobachtungen"],
                    label,
                )
                persist_protocol()
                rerun_with_fresh_widgets(
                    f"Rohnotizen aus {label} wurden in Beratungspunkte umgewandelt."
                )
            except Exception as exc:
                st.error(f"KI-Fehler: {exc}")

    st.divider()

    if st.button("Notizen zur Doppel-BUV verdichten", key="summarize_doppel"):
        try:
            doppel["zusammenfassung_weiterarbeit"] = summarize_observations(
                protocol,
                "Doppel-BUV",
            )
            persist_protocol()
            rerun_with_fresh_widgets("Zusammenfassung zur Doppel-BUV erstellt.")
        except Exception as exc:
            st.error(f"KI-Fehler: {exc}")

    text_area(
        "Zusammenfassung zur Weiterarbeit – Besprechung der Doppel-BUV",
        doppel,
        "zusammenfassung_weiterarbeit",
        height=180,
        key="doppel_zusammenfassung",
    )

    text_area(
        "Zielvereinbarungen des LAA zur Doppel-BUV",
        doppel,
        "zielvereinbarungen_laa",
        height=120,
        key="doppel_zv",
    )

    save_back()


with tabs[3]:
    st.header("Kompetenzen")

    kompetenzen = protocol["kompetenzen"]
    erzieh = kompetenzen["erzieherische_kompetenz"]

    st.subheader("Erzieherische Kompetenz")

    c1, c2 = st.columns(2)

    with c1:
        text_area(
            "Positive Feststellungen",
            erzieh,
            "positive_feststellungen",
            height=160,
            key="erz_pos",
        )

    with c2:
        text_area(
            "Beratungspunkte",
            erzieh,
            "beratungspunkte",
            height=160,
            key="erz_ber",
        )

    text_area(
        "Handlungs- und Sachkompetenz",
        kompetenzen,
        "handlungs_und_sachkompetenz",
        height=160,
        key="hand_sach",
    )

    text_area(
        "Einbringen in Schule und Seminar",
        kompetenzen,
        "einbringen_schule_und_seminar",
        height=160,
        key="einbringen",
    )

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

    st.info(
        "Hinweis: Das Word-Dokument enthält offene Felder für die Zielvereinbarungen des LAA."
    )
