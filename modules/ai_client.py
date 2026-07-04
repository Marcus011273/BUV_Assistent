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
