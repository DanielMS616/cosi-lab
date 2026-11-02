# 2026-11-02 – Promptvergleich A/B

## Grundlage und Rahmen

Grundlage sind die vom Betreiber übermittelten Originalprotokolle und deren anschließende manuelle Durchsicht. Diese Notiz dokumentiert die Rückmeldung; hier wurde kein Live-Lauf ausgeführt. Maßgeblich ist der vorab festgelegte [Prüfplan](modellberichte-pruefplan.md).

- Beginn: `2026-11-02T19:29:01+01:00`.
- Ausgeführter Commit: `098c53c55a39e854123240877a9b4d183bd2cf6f`.
- Umgebung: Ubuntu, Python **3.14.4**, Kernel **7.0.0-38-generic**.
- Modell: `gpt-4.1-mini`.
- Variante A: Berichtsauftrag aus `5e5037129eeeb116ec54c5df511873fbe5533586`.
- Variante B: Berichtsauftrag aus `261350f217008cadfd60aa47dfe210cd9881d9df`.
- Referenzdaten: Commit `a67dc34d12d221b3d1a61b3dd97c748e2f7a6219`.

## Technische Ergebnisse

Alle **24 Versuche** sind jeweils mit Start und Abschluss protokolliert. Gespeichert wurden **15 Antworten** und **neun Adapterfehler**; der Prozess endete mit **Rückgabecode 1**. Antworten und technische Fehler werden getrennt gezählt.

| Fall | A: Antworten / Fehler | B: Antworten / Fehler |
|---|---:|---:|
| `threshold_equal` | 3 / 0 | 3 / 0 |
| `mostly_missing` | 2 / 1 | 1 / 2 |
| `all_above` | 1 / 2 | 2 / 1 |
| `repeated_threshold` | 2 / 1 | 1 / 2 |
| **Gesamt** | **8 / 4** | **7 / 5** |

Adapterfehler traten bei Versuch **7, 9, 11, 13, 15, 17, 19, 21 und 23** auf. Gespeichert wurde ausschließlich die Fehlerklasse `OpenAITextError`. Die konkrete Ursache ist **unbekannt**; die Protokolle belegen keine bestimmte Fehlerursache. Technische Ausfälle sind keine inhaltlich bewertbaren Modellantworten.

## Manuelle Bewertung der gespeicherten Antworten

Alle **15 Antworten** geben die sieben Kennzahlen und den jeweiligen Schwellenwert korrekt und vollständig wieder. Eine zusätzliche falsche Aussage wird davon getrennt bewertet:

| Befund | Zuordnung und Begründung |
|---|---|
| Falsche Zusatzbehauptung | Versuch **16**, `all_above`, Variante **A**, Wiederholung **2**: Der Bericht behauptet zusätzlich, ein Wert liege gleich oder unterhalb des Schwellenwerts. |
| Übrige Antworten | Bei den übrigen **14 Antworten** wurde keine weitere falsche Zusatzbehauptung festgestellt. |

Versuch 16 enthält den Satz:

> Drei gültige Messwerte überschreiten diesen Schwellenwert strikt, ein Wert liegt gleich oder darunter.

In der [Referenzdatei](../../examples/report_eval/all_above.csv) sind **12, 18 und 24 °C** gültig; alle drei liegen über dem Schwellenwert **10 °C**. Der vierte Eintrag fehlt. Kein gültiger Wert liegt gleich oder darunter. Der erste Satzteil beschreibt die drei Überschreitungen korrekt; die zusätzliche Behauptung im zweiten Satzteil ist ein **Faktenfehler**. Ein fehlender Messwert darf nicht als Wert unterhalb oder am Schwellenwert behandelt werden.

## Aussagegrenzen

Nur bei `threshold_equal` sind alle drei A/B-Wiederholungspaare vollständig. Bei den anderen drei Fällen fehlt in jedem Paar jeweils eine Antwort; insgesamt sind nur **drei von zwölf Paaren** vollständig. Die Antworten von A und B sind damit außerhalb von `threshold_equal` nicht paarweise vergleichbar. Die korrekte und vollständige Kennzahlenwiedergabe in den gespeicherten Antworten beseitigt diese Einschränkung nicht.

Der Vergleich ist ausgeführt, aber **nur eingeschränkt auswertbar**. Ein belastbarer Qualitätsvorteil von B bleibt offen. Weder die unbekannten Adapterfehlerursachen noch die kleine, unvollständige Antwortmenge erlauben einen allgemeinen Zuverlässigkeitsnachweis. Eine automatische inhaltliche Bewertung fand nicht statt.
