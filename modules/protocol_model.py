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


def empty_observation_grid() -> Dict[str, Dict[str, str]]:
    return {
        kriterium: {
            "positive_feststellungen": "",
            "beratungspunkte": "",
            "memo": "",
        }
        for kriterium in KRITERIEN
    }


def create_empty_protocol() -> Dict[str, Any]:
    today = date.today().isoformat()
    return {
        "schema_version": "0.1",
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
            "entwurf_analyse": [],
            "stunde_1": {
                "fach": "",
                "klasse": "",
                "thema": "",
                "beobachtungen": empty_observation_grid(),
            },
            "stunde_2": {
                "fach": "",
                "klasse": "",
                "thema": "",
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
            "handlungs_und_sachkompetenz": "",
            "einbringen_schule_und_seminar": "",
        },
    }


def ensure_protocol_shape(protocol: Dict[str, Any]) -> Dict[str, Any]:
    """Ergänzt fehlende Schlüssel, falls ein älterer JSON-Arbeitsstand geladen wird."""
    base = create_empty_protocol()
    merged = _deep_merge(base, protocol or {})

    # Beobachtungsraster absichern, falls Kriterien später ergänzt wurden.
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
                {"positive_feststellungen": "", "beratungspunkte": "", "memo": ""},
            )
            grid[kriterium].setdefault("positive_feststellungen", "")
            grid[kriterium].setdefault("beratungspunkte", "")
            grid[kriterium].setdefault("memo", "")

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
