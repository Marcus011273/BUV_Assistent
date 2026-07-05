from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, Dict, List


KRITERIEN: List[str] = [
    "Strukturierung / roter Faden",
    "Zielorientierung",
    "Aktivierung",
    "Angemessenheit / Passung / Differenzierung",
    "Motivierung",
    "Unterrichtserfolg / Leistungssicherung",
    "Lehrersprache / Gesprächsführung",
    "Klassenführung / Atmosphäre",
    "Fachlichkeit / didaktische Reduktion",
    "Reflexion / Transfer",
]


SCHRIFTWESEN_ITEMS: List[str] = [
    "Jahrespläne",
    "Sequenzpläne",
    "Wochenpläne",
    "Unterrichtsvorbereitungen",
    "Material zum aktiven / handlungsorientierten Lernen",
    "Einsatz von Hörtexten, Film, PC",
    "Notenlisten, Notengebung",
    "Kriterien für mdl. Noten",
    "Deckblatt Proben",
    "Gestaltung Proben",
    "Korrektur der Hefte",
    "Anzahl/Gestaltung der Hefteinträge",
    "Schülerbeobachtungen",
    "Gesprächsprotokolle/Elternkontakte",
    "Individuelle Erziehungsmaßnahmen",
    "Bilder aus dem Kunstunterricht",
    "Kriterien zur Benotung",
    "Klassenzimmergestaltung",
]


def empty_observation_grid() -> Dict[str, Dict[str, str]]:
    return {
        kriterium: {
            "positive_feststellungen": "",
            "beratungspunkte": "",
            "memo": "",
        }
        for kriterium in KRITERIEN
    }


def empty_schriftwesen() -> Dict[str, Dict[str, str]]:
    return {
        item: {
            "status": "OK",
            "bemerkung": "",
        }
        for item in SCHRIFTWESEN_ITEMS
    }


def create_empty_protocol() -> Dict[str, Any]:
    today = date.today().isoformat()

    return {
        "schema_version": "0.3",
        "protokoll_typ": "Besondere Unterrichtsvorbereitung",
        "erstellt_am": today,
        "zuletzt_bearbeitet": today,
        "stammdaten": {
            "laa_name": "",
            "buv_nummer": "1",
            "seminarjahr": "",
            "schule": "",
            "bemerkungen": "",
        },
        "einzel_buv": {
            "datum": "",
            "fach": "",
            "klasse": "",
            "thema": "",
            "entwurf_analyse": [],
            "beobachtungen": empty_observation_grid(),
            "zusammenfassung_weiterarbeit": "",
            "zielvereinbarungen_laa": "",
        },
        "doppel_buv": {
            "datum": "",
            "stunde_1": {
                "fach": "",
                "klasse": "",
                "thema": "",
                "entwurf_analyse": [],
                "beobachtungen": empty_observation_grid(),
            },
            "stunde_2": {
                "fach": "",
                "klasse": "",
                "thema": "",
                "entwurf_analyse": [],
                "beobachtungen": empty_observation_grid(),
            },
            "zusammenfassung_weiterarbeit": "",
            "zielvereinbarungen_laa": "",
        },
        "kompetenzen": {
            "erzieherische_kompetenz": {
                "positive_feststellungen": "",
                "beratungspunkte": "",
            },
            "schriftwesen": empty_schriftwesen(),
            "handlungs_und_sachkompetenz": "",
            "einbringen_schule_und_seminar": "",
        },
    }


def ensure_protocol_shape(protocol: Dict[str, Any]) -> Dict[str, Any]:
    """Ergänzt fehlende Schlüssel, falls ein älterer JSON-Arbeitsstand geladen wird."""
    base = create_empty_protocol()
    merged = _deep_merge(base, protocol or {})

    for path in [
        ("einzel_buv", "beobachtungen"),
        ("doppel_buv", "stunde_1", "beobachtungen"),
        ("doppel_buv", "stunde_2", "beobachtungen"),
    ]:
        grid = merged
        for key in path:
            grid = grid[key]

        for kriterium in KRITERIEN:
            grid.setdefault(
                kriterium,
                {
                    "positive_feststellungen": "",
                    "beratungspunkte": "",
                    "memo": "",
                },
            )
            grid[kriterium].setdefault("positive_feststellungen", "")
            grid[kriterium].setdefault("beratungspunkte", "")
            grid[kriterium].setdefault("memo", "")

    merged["doppel_buv"]["stunde_1"].setdefault("entwurf_analyse", [])
    merged["doppel_buv"]["stunde_2"].setdefault("entwurf_analyse", [])

    kompetenzen = merged.setdefault("kompetenzen", {})
    schriftwesen = kompetenzen.setdefault("schriftwesen", {})

    for item in SCHRIFTWESEN_ITEMS:
        schriftwesen.setdefault(item, {"status": "OK", "bemerkung": ""})
        schriftwesen[item].setdefault("status", "OK")
        schriftwesen[item].setdefault("bemerkung", "")

    merged["zuletzt_bearbeitet"] = date.today().isoformat()

    return merged


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)

    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result
