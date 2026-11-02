# 2026-11-02 – Erste Qualitätsprüfung der Modellberichte

## Grundlage und Durchführung

Grundlage ist eine **Betreiber-Rückmeldung vom 02.11.2026** zur Ausführung auf Ubuntu. Die Aufrufe wurden hier nicht erneut ausgeführt.

- Geprüfter Commit: `5e5037129eeeb116ec54c5df511873fbe5533586`.
- Modellbezeichnung: `gpt-4.1-mini`.
- Vier Fälle aus dem [Manifest](../../examples/report_eval/cases.json), jeweils ein CLI-Aufruf mit Modellbericht.
- Alle vier Aufrufe lieferten Prozess-Rückgabecode **0**.
- Die inhaltliche Bewertung erfolgte manuell anhand der zurückgemeldeten Modellberichte und der festgelegten Referenzdaten nach dem [Prüfplan](modellberichte-pruefplan.md).

## Festgelegte Sollwerte

Die Werte sind aus dem Manifest übernommen, nicht aus den Modellantworten abgeleitet. Minimum, Maximum, Mittelwert und Schwellenwert sind in °C angegeben. Überschreitungen zählen strikt mit `Wert > Schwellenwert`; fehlende Temperaturen gehen nicht in die Berechnung ein.

| Fall | `total_count` | `valid_count` | `missing_count` | `minimum` | `maximum` | `mean` | `exceedance_count` | Schwellenwert |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `threshold_equal` | 3 | 3 | 0 | 40 | 60 | 50 | 0 | 60 |
| `mostly_missing` | 8 | 3 | 5 | 40 | 65 | 55 | 1 | 60 |
| `single_valid` | 3 | 1 | 2 | 42 | 42 | 42 | 0 | 60 |
| `negative_temperatures` | 5 | 4 | 1 | −15 | 0 | −7,5 | 1 | −5 |

## Manuelle Ergebnisse

Die Wiedergabe der Kennzahlen und zusätzliche Aussagen werden getrennt bewertet. In allen vier Berichten wurden sämtliche sieben Kennzahlen und der jeweilige Schwellenwert korrekt wiedergegeben; insoweit wurden weder Auslassungen noch falsche Angaben festgestellt.

| Fall | Rückgabecode | Kennzahlen und Vollständigkeit | Zusätzlicher inhaltlicher Befund |
|---|---:|---|---|
| `threshold_equal` | 0 | Alle sieben Kennzahlen und Schwellenwert korrekt und vollständig. | Keine zusätzliche falsche Aussage festgestellt. |
| `mostly_missing` | 0 | Alle sieben Kennzahlen und Schwellenwert korrekt und vollständig. | **Falsche Zusatzbehauptung:** „Werte am Schwellenwert selbst sind nicht vorhanden.“ Begründung siehe unten. |
| `single_valid` | 0 | Alle sieben Kennzahlen und Schwellenwert korrekt und vollständig; Minimum, Maximum und Mittelwert jeweils 42 °C. | Keine zusätzliche falsche Aussage festgestellt. |
| `negative_temperatures` | 0 | Alle sieben Kennzahlen und Schwellenwert korrekt und vollständig; negative Zahlen und strikte Überschreitung korrekt erklärt. | Keine zusätzliche falsche Aussage festgestellt. |

### Fehler im Fall `mostly_missing`

Der Bericht enthält laut Rückmeldung den Satz:

> Werte am Schwellenwert selbst sind nicht vorhanden.

Die gültigen Temperaturen der [Referenzdatei](../../examples/report_eval/mostly_missing.csv) sind **40, 60 und 65 °C**, der Schwellenwert beträgt **60 °C**. Damit existiert ein Wert genau am Schwellenwert. Er zählt aufgrund der strikten Regel nicht als Überschreitung; nur 65 °C liegt darüber. Die Behauptung über das Fehlen eines Werts am Schwellenwert ist daher falsch. Dieser zusätzliche Faktenfehler besteht neben der korrekten Wiedergabe aller Kennzahlen und ist keine Auslassung.

## Einordnung und nächster Versuch

Rückgabecode `0` belegt den technischen Abschluss des jeweiligen Aufrufs. Er bestätigt keine automatisch geprüfte inhaltliche Richtigkeit des Modellberichts. Diese Prüfreihe ergab **drei Berichte ohne festgestellten inhaltlichen Fehler und einen Bericht mit einer falschen Zusatzbehauptung**.

Es handelt sich um vier Einzelantworten, jeweils eine pro Fall. Daraus lassen sich keine allgemeine Fehlerquote und keine Aussage über dauerhafte Zuverlässigkeit ableiten. Die Rückmeldung ersetzt keine wiederholte Prüfreihe.

Der Befund spricht dafür, als nächsten Versuch den Berichtsauftrag präziser auf die bereitgestellten Fakten zu begrenzen und zusätzliche, daraus nicht belegbare Behauptungen ausdrücklich auszuschließen. Eine solche Präzisierung ist eine **zu prüfende Verbesserungshypothese**, keine garantierte Lösung. Der Prompt wurde für diese Dokumentation nicht verändert.
