# Prüfreihe für die RAG-Dokusuche

Die Prüfreihe verwendet nur die drei Markdown-Dateien aus `examples/rag/`.
Der Sollzustand stammt aus diesen Dateien. Er wird vor der Suche festgelegt.
Für jeden Fall verwenden wir dasselbe E5-Modell und `--top-k 3`. So lassen
sich sowohl Platz 1 als auch die ersten drei Treffer vergleichen.

| Fall | Frage | Erwartete Fundstelle | Erwartete Antwort |
| --- | --- | --- | --- |
| P01 · Direkte Frage | Zählt genau 60 °C bei der Fräse schon als Überschreitung? | `examples/rag/fraese-f07.md:3-5` | Im Dauerlauf zählen erst Werte über 60 °C als Überschreitung. Genau 60 °C bleiben im Protokoll. |
| P02 · Umschreibung | Muss ich die Breite von H-12 erneut messen, wenn ich das Messgerät austausche? | `examples/rag/masspruefung-h12.md:13-15` | Beim Wechsel des Messschiebers während der Prüfung wird die letzte Breitenmessung wiederholt. |
| P03 · Zwei Angaben aus einem Absatz | In welcher Reihenfolge werden die Kanäle beim Testton am Rack geprüft, und was wird bei einem Knacken notiert? | `examples/rag/nachtflug-rack.md:9-10` | Zuerst links, dann rechts. Bei Knacken werden Kanal und Zeitpunkt notiert. |
| P04 · Zwei Dokumente | Was passiert bei genau 60 °C im Dauerlauf der Fräse F-07 und beim Soundcheck am Rack? | `examples/rag/fraese-f07.md:3-5` und `examples/rag/nachtflug-rack.md:3-4` | Bei der Fräse keine Überschreitung; beim Rack leuchtet die gelbe Anzeige. Beide Aussagen brauchen ihre jeweilige Fundstelle. |
| P05 · Fehlende Angabe mit Hinweis | Wie breit soll die Halterung H-12 sein? | `examples/rag/masspruefung-h12.md:6-7` belegt nur den Verweis auf die Zeichnung. | Die konkrete Sollbreite ist nicht belegt. Die Antwort nennt keine Zahl und verweist mit Fundstelle auf die separate Zeichnung. |
| P06 · Außerhalb des Bestands | Wann öffnet die Bibliothek am Sonntag? | Kein Beleg im Dokumentbestand. | Die Öffnungszeit ist nicht belegt. Keine erfundene Uhrzeit und kein Verweis auf eine irrelevante Fundstelle. |
| P07 · Geltungsbereich einer Regel | Gilt die 60-°C-Regel vom Spindellager auch für das Kühlmittel der Fräse im Stillstand? | `examples/rag/fraese-f07.md:10-12` | Die Regel für das Spindellager im Dauerlauf gilt nicht für den Kühlmittelwert im Stillstand. Kein eigener Grenzwert für das Kühlmittel wird behauptet. |

## So prüfen wir

1. **Suche:** Frage aus der Tabelle unverändert mit `--top-k 3 --show-prompt`
   stellen. Für jeden erwarteten Beleg den Rang aufschreiben, sonst `fehlt`.
   Bei P04 braucht der Prompt beide Belege. Bei P06 gibt die Ähnlichkeitssuche
   trotzdem Treffer zurück; keiner davon belegt eine Öffnungszeit.
2. **Antwort:** Dieselbe Frage mit `--gpt` und `--gemini` ausführen und beide
   Lauf-IDs notieren. Mit `show_rag_run.py <ID>` lässt sich später genau der
   gesendete Prompt wieder öffnen. Die Antwort ist korrekt, wenn sie die
   Frage vollständig und anhand der gelieferten Absätze beantwortet, ihre
   Belege nennt und fehlende Angaben offen lässt.
3. **Fehler zuordnen:** Fehlt ein nötiger Absatz im Prompt, ist das ein
   Suchproblem. Ist der Absatz da und die Antwort trotzdem falsch oder
   unvollständig, ist das ein Antwortproblem. Wenn ein Beleg bei P04 fehlt,
   darf das Modell den fehlenden Teil ausdrücklich offenlassen.

Zum Beispiel zuerst den Fall P04 prüfen:

```bash
.venv/bin/python rag_cli.py \
  "Was passiert bei genau 60 °C im Dauerlauf der Fräse F-07 und beim Soundcheck am Rack?" \
  --top-k 3 --show-prompt
```

## Protokoll für einen Prüfdurchlauf

Erste Läufe auf dem Mac am 20.11.2026. Für P05 sind die bereits gespeicherten
Läufe mit derselben Frage, denselben Ausschnitten und `--top-k 3` übernommen.

| Fall | Rang der erwarteten Belege | GPT: Lauf-ID und Ergebnis | Gemini: Lauf-ID und Ergebnis | Auffälligkeit |
| --- | --- | --- | --- | --- |
| P01 | Fräse: 1 | 8 · bestanden | 7 · bestanden | Beide beantworten die Frage direkt und belegen, dass genau 60 °C nicht als Überschreitung zählen. Die Protokollierung war nicht gefragt. |
| P02 | Breitenmessung: 1 | 9 · bestanden | 10 · bestanden | Beide erkennen in der Umschreibung den Wechsel des Messschiebers und nennen die Wiederholung der letzten Breitenmessung. |
| P03 | Kanaltest: 1 | 12 · bestanden | 11 · bestanden | Beide nennen die Reihenfolge links–rechts sowie Kanal und Zeitpunkt bei Knacken. |
| P04 | Fräse: 2; Rack: 1 | 3 · bestanden | 5 · bestanden | Beide Antworten unterscheiden die Regeln bei 60 °C und belegen beide Aussagen. |
| P05 | Zeichnungshinweis: 1 | 1 · bestanden | 2 · bestanden | Beide benennen die fehlende Sollbreite und verweisen mit der passenden Fundstelle auf die Zeichnung. |
| P06 | Kein Beleg; drei themenfremde Treffer | 4 · bestanden | 6 · teilweise: keine Uhrzeit, aber unbelegte Fundstellen | Die Ausschnitte enthalten keinen Hinweis auf Öffnungszeiten. Gemini nennt zusätzlich `nachtflug-rack.md:6-10`, obwohl dieser zusammenhängende Bereich nicht im Prompt stand. |
| P07 | Kühlmittel: 1 | 13 · bestanden | 14 · bestanden | Beide grenzen den Kühlmittelwert im Stillstand vom Spindellager im Dauerlauf ab und nennen keinen unbelegten Grenzwert. |

Bei allen sechs Fällen mit erwartetem Beleg standen sämtliche benötigten
Fundstellen unter den ersten drei Treffern. Für P06 gab es wie erwartet keinen
Beleg zur Frage. GPT bestand 7 von 7 Fällen, Gemini 6 von 7. Gemini ließ bei P06
die Uhrzeit offen, nannte aber themenfremde Fundstellen.


## Protokoll 2026-11-25

Testläufe über Cosi-lab per SSH. Vier Fälle: P01 → P04 → P05 → P06. Trefferzahl k = 3 und Modell = gemini-3.5-flash-lite.
Commit: 70d9a8c

### 25.11.2026 – Browser auf Cosi-Lab

**Commit:** 70d9a8c · **Modell:** `gemini-3.5-flash-lite` · **Top-k:** 3

| Fall | Rang im gespeicherten Prompt | Lauf-ID | Antwortbefund |
| --- | --- | --- | --- |
| P01 | Fräse: 1 | 9 | Bestanden: Genau 60 °C zählen nicht als Überschreitung; passender Beleg zitiert. |
| P04 | Rack: 1; Fräse: 2 | 10 | Nicht bestanden: Fräse fälschlich als unbelegt markiert, Rack nicht beantwortet. Beide Belege lagen vor. |
| P05 | Zeichnungshinweis: 1 | 11 | Bestanden: Keine Sollbreite genannt; separate Zeichnung mit passender Fundstelle angegeben. |
| P06 | Kein Beleg erwartet; drei themenfremde Treffer | 12 | Bestanden: Öffnungszeit als unbelegt markiert, ohne Uhrzeit, Hinweis oder Zitat. |

| Fall | Rang der erwarteten Belege | GPT: Lauf-ID und Ergebnis | Gemini: Lauf-ID und Ergebnis | Auffälligkeit |
| --- |----------------------------|---------------------------|------------------------------|---------------|
| P01 | x                          | x                         | x                            | x             |
| P02 | x                          | x                         | x                            | x             |
| P03 | x                          | x                         | x                            | x             |
| P04 | x                          | x                         | x                            | x             |
| P05 | x                          | x                         | x                            | x             |
| P06 | x                          | x                         | x                            | x             |
| P07 | x                          | x                         | x                            | x             |


## Leere Tabelle zum Kopieren

| Fall | Rang der erwarteten Belege | GPT: Lauf-ID und Ergebnis | Gemini: Lauf-ID und Ergebnis | Auffälligkeit |
| --- |----------------------------|---------------------------|------------------------------|---------------|
| P01 | x                          | x                         | x                            | x             |
| P02 | x                          | x                         | x                            | x             |
| P03 | x                          | x                         | x                            | x             |
| P04 | x                          | x                         | x                            | x             |
| P05 | x                          | x                         | x                            | x             |
| P06 | x                          | x                         | x                            | x             |
| P07 | x                          | x                         | x                            | x             |