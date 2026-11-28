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
| W05 | In welchem Fach liegt der Siebeinsatz S-271, und für welche Pumpe ist er vorgesehen? | `wartungsanweisung-p71.md:11-13` | Fach B-07 und Pumpe P-71. Nicht mit S-217 für P-17 im Fach B-04 verwechseln. |

## Protokoll

### 25.11.2026 – Cosi-Lab, Browser

**Modell:** `gemini-3.5-flash-lite` · **Top-k:** 3

| Fall | Rang der erwarteten Belege | Lauf-ID | Antwortbefund |
| --- | --- | --- | --- |
| W01 | Wartungsanweisung: 1 | 25 | Bestanden: 120 Betriebsstunden für P-17 am Prüfstand West, korrekt belegt. |
| W02 | Störungsprotokoll: 1 | 26 | Bestanden: Kunststoffspäne im Ansaugsieb und 15 l/min nach der Reinigung, beides belegt. |
| W03 | Teileliste: 3; Wartungsanweisung: 2 | 27 | Teilweise bestanden: 120 Betriebsstunden korrekt belegt; S-217 trotz direktem Beleg als unbelegt markiert. |
| W04 | Teileliste: 1; kein Preisbeleg erwartet | 28 | Bestanden: Preis bleibt offen; S-217 korrekt belegt. |


### W03 unverändert gegengeprüft

Prompt und Reihenfolge der Fundstellen waren in #27, #29 und #30 gleich.
Die Zuordnung P-17 → S-217 stand jeweils auf Rang 3. GPT (#29)
beantwortete beide Teilfragen korrekt. Gemini (#27 und #30) nannte das
Wartungsintervall richtig, stufte die belegte Teilenummer aber als
unbelegt ein und verwies stattdessen auf den Absatz zur Lagerausgabe.


### W03: Reihenfolgeprobe mit Gemini

Aus Lauf #30 wurden dieselbe Frage, dieselben Antwortregeln und dieselben
drei Ausschnitte übernommen. Nur Position 1 und 3 wurden getauscht.
Der direkte Beleg für S-217 (`teileliste-p17.md:3-4`) stand damit zuerst.

Gemini stufte die Teilenummer weiterhin als unbelegt ein. Das Intervall
von 120 Betriebsstunden wurde korrekt belegt. Der zuvor ausgegebene
Hinweis zur Lagerausgabe entfiel. Die Probe lief ohne neue Suche und
wurde nicht als eigener SQLite-Lauf gespeichert.


### Modellvergleich über alle vier Praxisfälle

Je Frage erhielten beide Modelle denselben Prompt mit denselben drei
Fundstellen in derselben Reihenfolge.

| Fall | Gemini | GPT | Befund |
| --- | --- | --- | --- |
| W01 | #25: bestanden | #31: bestanden | Beide nennen 120 Betriebsstunden für Prüfstand West mit passendem Beleg. |
| W02 | #26: bestanden | #32: bestanden | Beide nennen Kunststoffspäne und 15 l/min nach der Reinigung, jeweils belegt. |
| W03 | #27 und #30: teilweise bestanden | #29 und #33: bestanden | GPT belegt beide Angaben; Gemini stuft S-217 trotz direktem Beleg als unbelegt ein. |
| W04 | #28: bestanden | #34: teilweise bestanden | GPT lässt den Preis offen und nennt S-217, vertauscht aber die Teilfragen und zitiert den nicht gelieferten Bereich `:3-7`. |


### Suchvergleich mit drei und vier Treffern

28.11.2026 · Cosi-Lab · erweiterter Praxisbestand mit P-71-Unterlagen.
Ein Fall besteht, wenn alle erwarteten Belege in der Trefferliste stehen.
GPT und Gemini wurden nicht aufgerufen.

| Fall | Top-k 3 | Top-k 4 |
| --- | --- | --- |
| W01 | Wartungsanweisung: Rang 1 | Wartungsanweisung: Rang 1 |
| W02 | Störungsprotokoll: Rang 1 | Störungsprotokoll: Rang 1 |
| W03 | Teileliste fehlt; Wartungsanweisung: Rang 2 | Teileliste: Rang 4; Wartungsanweisung: Rang 2 |
| W04 | Teileliste: Rang 2 | Teileliste: Rang 2 |
| **Bestanden** | **3 von 4** | **4 von 4** |


### GPT-Antworten mit vier Treffern im erweiterten Praxisbestand

28.11.2026 · Cosi-Lab · Browser · `gpt-4o-mini` · Top-k 4.

| Fall | Lauf-ID | Fundstellen im Prompt | Antwortbefund |
| --- | --- | --- | --- |
| W03 | #35 | Teileliste P-17: Rang 4; Wartungsanweisung P-17: Rang 2 | Bestanden: S-217 und 120 Betriebsstunden in der richtigen Reihenfolge genannt und einzeln belegt. |
| W04 | #36 | P-71-Preis: Rang 1; Teileliste P-17: Rang 2 | Fachlich bestanden: Preis für P-17 bleibt offen, S-217 exakt belegt. Reihenfolge der Teilfragen vertauscht. |

Die Zitatprüfung meldete in beiden Läufen keine unbekannten Fundstellen.


### GPT und Gemini mit vier Treffern verglichen

28.11.2026 · Cosi-Lab · erweiterter Praxisbestand · Top-k 4.
Pro Frage waren Prompt und Reihenfolge der Fundstellen identisch.

| Fall | GPT | Gemini |
| --- | --- | --- |
| W03 | #35: bestanden. S-217 von Rang 4 und 120 Betriebsstunden von Rang 2 korrekt belegt. | #37: teilweise bestanden. Wartungsintervall korrekt belegt; S-217 trotz Beleg auf Rang 4 als unbelegt gemeldet. |
| W04 | #36: fachlich bestanden. Preis bleibt offen; S-217 korrekt belegt. Reihenfolge vertauscht. | #38: vollständig bestanden. Preis zuerst als unbelegt markiert, danach S-217 korrekt belegt. |

Bei W04 stand der Preis von 38 Euro für P-71 auf Rang 1. Kein Modell
übertrug ihn auf P-17. Die Zitatprüfung meldete in keinem der vier
Läufe eine unbekannte Fundstelle.


### W03 auf die Teilenummer eingegrenzt

Basis: Gemini-Lauf #37 mit vier Treffern. Nur die Frage wurde ersetzt:
„Welche Teilenummer hat der Siebeinsatz für P-17?“
Die Ausschnitte, ihre Reihenfolge und das Modell blieben gleich.

Gemini nannte S-217 und zitierte `teileliste-p17.md:3-4` von Rang 4.
In der ursprünglichen zweiteiligen Frage hatte es die Teilenummer
trotz desselben Belegs als unbelegt gemeldet. Für diese Probe wurde
keine neue Suche gestartet und kein neuer SQLite-Lauf gespeichert.


### W03: Gemeinsame Suche und getrennte Teilfragen

28.11.2026 · Cosi-Lab · erweiterter Praxisbestand.
Die beiden Teilfragen wurden mit je drei Treffern gesucht.

| Erwarteter Beleg | Gemeinsame Frage | Eigene Teilfrage |
| --- | --- | --- |
| Teilenummer: `teileliste-p17.md:3-4` | Rang 4 | Rang 1 |
| Wartungsintervall: `wartungsanweisung-p17.md:3-5` | Rang 2 | Rang 1 |

Beide Belege sind bereits über den jeweils ersten Treffer verfügbar.
Ein Antwortmodell wurde nicht aufgerufen.

teilfragen = (
    "Welche Teilenummer hat der Siebeinsatz für P-17?",
    "Nach wie vielen Betriebsstunden ist die Siebkontrolle für P-17 fällig?",
)


### W03 mit zwei direkten Belegen erneut beantwortet

Basis: Gemini-Lauf #37. Die zweiteilige Frage und die Antwortregeln
blieben gleich. Im Prompt standen nur `wartungsanweisung-p17.md:3-5`
und `teileliste-p17.md:3-4` in ihrer ursprünglichen Reihenfolge.

Gemini belegte das Intervall von 120 Betriebsstunden, meldete S-217
aber weiterhin fälschlich als unbelegt. Die Antwort sprach vom
Siebeinsatz, während die Wartungsanweisung das Ansaugsieb nennt.
Die Probe wurde nicht als neuer SQLite-Lauf gespeichert.


### W03: Teilfragen separat gesucht und beantwortet

28.11.2026 · Cosi-Lab · `gemini-3.5-flash-lite` · Top-k 1 je Teilfrage.

| Teilfrage | Lauf | Suchbefund | Antwortbefund |
| --- | --- | --- | --- |
| Teilenummer | #39 | `teileliste-p17.md:3-4` auf Rang 1 | Nicht bestanden: S-217 trotz direktem Beleg als unbelegt gemeldet. |
| Wartungsintervall | #40 | `wartungsanweisung-p17.md:3-5` auf Rang 1 | Bestanden: 120 Betriebsstunden, korrekt belegt. |


### W05: Lagerfach und Pumpe aus der Teilenummer bestimmen

28.11.2026 · Cosi-Lab · erweiterter Praxisbestand · Top-k 4.
Beide Modelle erhielten denselben Prompt und dieselben Fundstellen.
Der erwartete Beleg stand auf Rang 2; der Absatz zu S-217 und B-04 auf Rang 3.

| Modell | Lauf | Antwortbefund |
| --- | --- | --- |
| GPT | #41 | Bestanden: B-07, danach P-71. Beide Angaben korrekt belegt. |
| Gemini | #42 | Bestanden: B-07, danach P-71. Beide Angaben korrekt belegt. |

In beiden Läufen meldete die Zitatprüfung keine unbekannten Fundstellen.


### Suchvergleich um W05 erweitert

28.11.2026 · Cosi-Lab · unveränderter erweiterter Praxisbestand.
Die Ränge von W01–W04 blieben gleich.

| Ergebnis | Top-k 3 | Top-k 4 |
| --- | --- | --- |
| W05 · `wartungsanweisung-p71.md:11-13` | Rang 2 | Rang 2 |
| **Suchchecks bestanden** | **4 von 5** | **5 von 5** |

Bei Top-k 3 fehlt weiterhin nur der Beleg für S-217 in W03.


### Suchcheck mit Top-k 4

| Fall | Erwartete Belege und Trefferpositionen | Ergebnis |
| --- | --- | --- |
| W01 | OK: Rang 1 von 4 · examples/rag-praxis/wartungsanweisung-p17.md:3-5 | bestanden |
| W02 | OK: Rang 1 von 4 · examples/rag-praxis/stoerungsprotokoll-p17.md:3-5 | bestanden |
| W03 | OK: Rang 4 von 4 · examples/rag-praxis/teileliste-p17.md:3-4; OK: Rang 2 von 4 · examples/rag-praxis/wartungsanweisung-p17.md:3-5 | bestanden |
| W04 | OK: Rang 2 von 4 · examples/rag-praxis/teileliste-p17.md:3-4 | bestanden |
| W05 | OK: Rang 2 von 4 · examples/rag-praxis/wartungsanweisung-p71.md:11-13 | bestanden |
| **Gesamt** | | **5 von 5 Suchchecks bestanden.** |


### Kennungen bei drei ausgegebenen Treffern vorgezogen

28.11.2026 · Cosi-Lab · erweiterter Praxisbestand · Top-k 3.
Die Variante sortiert bei einer einzelnen Kennung zunächst fünf
Suchkandidaten um und gibt danach die ersten drei Treffer aus.

| Fall | E5-Reihenfolge | Mit `--kennung-vorziehen` |
| --- | --- | --- |
| W01 | Wartungsanweisung: Rang 1 | Rang 1 |
| W02 | Störungsprotokoll: Rang 1 | Rang 1 |
| W03 | Teileliste fehlt; Wartungsanweisung: Rang 2 | Teileliste: Rang 2; Wartungsanweisung: Rang 1 |
| W04 | Teileliste: Rang 2 | Rang 1 |
| W05 | Wartungsanweisung P-71: Rang 2 | Rang 2 |
| **Bestanden** | **4 von 5** | **5 von 5** |

Geprüft wurde die Suche. GPT und Gemini wurden nicht aufgerufen.

> ssh cosi-vpn 'cd ~/cosi-lab-e5-neustart && RAG_BESTAND=praxis .venv/bin/python - --top-k 3 --markdown --kennung-vorziehen' \
  < rag_pruefe_suche.py


### W03 mit nach Kennung umsortierten Treffern beantwortet

28.11.2026 · Cosi-Lab · `gemini-3.5-flash-lite` · Top-k 3.
Frage und Antwortregeln stammen aus Lauf #37.

| Rang | Fundstelle |
| --- | --- |
| 1 | `wartungsanweisung-p17.md:3-5` |
| 2 | `teileliste-p17.md:3-4` |
| 3 | `teileliste-p17.md:6-7` |

Bestanden: Gemini nannte S-217 und 120 Betriebsstunden in der
Reihenfolge der Frage und belegte beide Angaben korrekt. Die
Zitatprüfung meldete keine unbekannten Zitate. Der Versuch
wurde nicht als neuer SQLite-Lauf gespeichert.