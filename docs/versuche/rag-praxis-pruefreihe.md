# RAG-Praxisprüfreihe: Pumpenwartung

Die drei Dateien in `examples/rag-praxis/` sind fiktive Übungsdokumente.
Die erwarteten Belege und Antworten stehen vor dem ersten Suchlauf fest.
Beim Test notieren wir Belegränge, Lauf-ID und Antwortbefund getrennt.

| Fall | Frage | Erwartete Fundstelle | Erwartete Antwort |
| --- | --- | --- | --- |
| W01 | Nach wie vielen Betriebsstunden soll das Ansaugsieb am Prüfstand West kontrolliert werden? | `wartungsanweisung-p17.md:3-5` | 120 Betriebsstunden für P-17. Die 80 Stunden gelten für P-71. |
| W02 | Woran lag der geringe Durchfluss bei P-17 am 18. November, und wie hoch war er nach der Reinigung? | `stoerungsprotokoll-p17.md:3-5` | Kunststoffspäne im Ansaugsieb; nach der Reinigung 15 l/min. |
| W03 | Welche Teilenummer hat der Siebeinsatz für P-17, und nach wie vielen Betriebsstunden ist die Siebkontrolle fällig? | `teileliste-p17.md:3-4` und `wartungsanweisung-p17.md:3-5` | S-217 und 120 Betriebsstunden. Beide Angaben einzeln belegen. |
| W04 | Was kostet der Siebeinsatz für P-17, und welche Teilenummer hat er? | Kein Preisbeleg; `teileliste-p17.md:3-4` für die Teilenummer. | Preis als unbelegt benennen. Danach S-217 mit Fundstelle angeben. |

## Protokoll

### 25.11.2026 – Cosi-Lab, Browser

**Modell:** `gemini-3.5-flash-lite` · **Top-k:** 3

| Fall | Rang der erwarteten Belege | Lauf-ID | Antwortbefund |
| --- | --- | --- | --- |
| W01 | Wartungsanweisung: 1 | 25 | Bestanden: 120 Betriebsstunden für P-17 am Prüfstand West, korrekt belegt. |
| W02 | Störungsprotokoll: 1 | 26 | Bestanden: Kunststoffspäne im Ansaugsieb und 15 l/min nach der Reinigung, beides belegt. |
| W03 | Teileliste: 3; Wartungsanweisung: 2 | 27 | Teilweise bestanden: 120 Betriebsstunden korrekt belegt; S-217 trotz direktem Beleg als unbelegt markiert. |
| W04 | Teileliste: 1; kein Preisbeleg erwartet | 28 | Bestanden: Preis bleibt offen; S-217 korrekt belegt. |