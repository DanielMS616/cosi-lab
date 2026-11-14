# Cosi-Lab – Lernversion

Cosi-Lab ist ein Python-Lernprojekt mit zwei Abläufen. Die **Temperaturauswertung** liest eine CSV-Datei und berechnet die Anzahl der gesamten, gültigen und fehlenden Messwerte sowie die Anzahl der Werte strikt über einer wählbaren Schwelle. Auf Wunsch formuliert GPT oder Gemini daraus einen Bericht. Prompt, Antwort und Metadaten landen in SQLite; den gespeicherten Bericht kannst du später ansehen und nach Freigabe exportieren.

Die **Dokusuche** findet Ausschnitte mit Dateipfad und Zeilennummern. Bei einer Frage kann GPT die gefundenen Ausschnitte als Kontext verwenden. Dieser Ablauf heißt RAG (*Retrieval-Augmented Generation*): Erst sucht Python die Quellen, dann formuliert das Modell anhand dieser Quellen eine Antwort. Die Lernversion verwendet dafür eine Wortsuche in lokalen Dateien.

Der frühere Prototyp ist unter [`prototyp-2026-11-07`](https://github.com/DanielMS616/cosi-lab/tree/prototyp-2026-11-07) archiviert. Wie die Lernversion Schritt für Schritt entstanden ist und wie ich sie geprüft habe, steht im [Journal](docs/journal/).

## Schnellstart

Führe die Befehle im Projektordner aus. Falls noch keine virtuelle Umgebung existiert, lege sie einmal mit `python3 -m venv .venv` an. Verwende danach `.venv/bin/python`, damit auch Modellaufrufe den Interpreter mit den installierten Projektpaketen verwenden.

```bash
.venv/bin/python main.py examples/temperature_sample.csv
.venv/bin/python main.py examples/temperature_sample.csv --threshold 65 --show-temperatures --show-prompt
```

Die Beispieldatei enthält vier Einträge: drei gültige Werte und eine fehlende Messung. Bei der Standardschwelle von 60 °C liegt ein Wert darüber; bei 65 °C sind es null, weil Gleichheit nicht als Überschreitung zählt. Die Option `--threshold` erwartet eine Ganzzahl. `--show-temperatures` zeigt die eingelesene Liste, `--show-prompt` den fertigen Auftrag an das Modell. Ohne Modellschalter bleiben diese Aufrufe offline und brauchen keine zusätzlichen Pakete.

### Modellberichte und SQLite

Für die Modellaufrufe installiere die Abhängigkeiten in der virtuellen Umgebung:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Trage in die lokale Datei `.env` neben `main.py` den Schlüssel für den gewünschten Anbieter ein: `OPENAI_API_KEY` für GPT oder `GEMINI_API_KEY` für Gemini. Die `.env` bleibt lokal und gehört nicht in Git.

```bash
.venv/bin/python main.py examples/temperature_sample.csv --gpt
.venv/bin/python main.py examples/temperature_sample.csv --gemini
```

Wähle pro Aufruf höchstens ein Modell. Python berechnet die Kennzahlen, GPT oder Gemini formuliert den Bericht. Beide Anbieter verwenden denselben Speicherblock in `main.py`. Ein erfolgreicher Modelllauf landet mit Modellname, CSV-Pfad, Schwelle, Prompt und Antwort in `data/model_runs.sqlite3` und erhält eine Lauf-ID. Dazu kommen diese Metadaten:

| Feld | Bedeutung |
| --- | --- |
| `requested_at_utc` | Zeitpunkt auf dem eigenen Rechner unmittelbar vor dem Modellaufruf, in UTC. Er sagt nichts darüber aus, wann die Temperatur gemessen wurde. |
| `duration_ms` | Von OpenAI im HTTP-Header `openai-processing-ms` gemeldete Verarbeitungszeit, sofern vorhanden und lesbar. Bei Gemini bleibt dieses Feld `NULL`. |
| `client_duration_ms` | Lokal mit `perf_counter()` gemessene Dauer vom Aufruf der Modellfunktion bis zu ihrer Rückkehr, einschließlich SDK und Netzwerk. CSV-Auswertung, SQLite-Speicherung und Terminalausgabe liegen außerhalb der Messung. |
| `input_tokens`, `output_tokens` | Die vom Anbieter gemeldeten Tokenzahlen. Gemini zählt für `output_tokens` die Antworttokens; getrennt gemeldete Denk-Token werden nicht hinzugerechnet. |

Fehlende oder in älteren Läufen noch nicht erfasste Werte bleiben `NULL`. Die Differenz zwischen lokaler Dauer und Anbieterzeit ist keine Messung der reinen Netzwerkzeit.

Nach einem Modelllauf kannst du den jüngsten Eintrag mit der `sqlite3`-Kommandozeile ansehen:

```bash
sqlite3 -readonly -header -column -nullvalue NULL data/model_runs.sqlite3 \
  'SELECT id, model, requested_at_utc, duration_ms, client_duration_ms,
          input_tokens, output_tokens
   FROM model_runs ORDER BY id DESC LIMIT 1;'
```

Die [drei Temperatur-Vergleichsfälle](docs/journal/2026-11-14.md#gpt-und-gemini-mit-drei-temperaturfällen-vergleichen) prüfen Werte genau an der Schwelle, überwiegend fehlende Werte und negative Temperaturen. In je einem Lauf pro Modell und Fall gaben alle sechs Antworten die fünf Sollangaben korrekt und vollständig in zwei Sätzen wieder, ohne unbelegte Zusätze. Daraus lässt sich noch keine allgemeine Rangfolge ableiten.

### Gespeicherten Lauf ansehen und exportieren

Setze statt `12` die ID ein, die beim Speichern ausgegeben wurde:

```bash
.venv/bin/python show_model_run.py 12
```

Die Ansicht öffnet die Datenbank nur zum Lesen und zeigt den ursprünglichen Prompt, die Antwort und die Metadaten. Fehlende Werte erscheinen als „nicht erfasst“. Mit `--database PFAD` kannst du eine andere SQLite-Datei wählen. Für Ansicht und Export ist kein erneuter Modellaufruf nötig.

```bash
.venv/bin/python show_model_run.py 12 --export
```

`--export` zeigt den Zielpfad und den vollständigen Bericht vor der Freigabe. Der Kopf enthält Lauf-ID, Modell, nur den CSV-Dateinamen, Schwelle und den Modellaufruf in UTC. Darunter steht die gespeicherte Antwort. Nach `ja` landet genau der angezeigte Bericht als UTF-8-Text in `reports/model-run-12.txt`. Ohne Zustimmung entsteht keine Datei; ein vorhandener Export wird nicht überschrieben. Prompt, Tokenzahlen und Laufzeiten bleiben in der Laufansicht.

### Projektdokumente durchsuchen und Fragen beantworten

In einer angegebenen Datei findet die Phrasensuche die erste Zeile mit dem zusammenhängenden Wortlaut. Mit `--question` zerlegt die Suche eine Frage in Wörter und bewertet Ausschnitte von bis zu drei Zeilen nach der Anzahl verschiedener passender Wörter. Bei Gleichstand bleibt der frühere Treffer; bei mehreren Dateien entscheidet dann die Reihenfolge der Dateien. Bei der Fragensuche wird `Prozessor` zu `cpu`, und die Bestandteile des Projektnamens `Cosi-Lab` lösen keinen Treffer aus. Die Originalfrage im Prompt bleibt unverändert.

```bash
.venv/bin/python doc_search.py docs/aufbau-fernzugriff.md "ssh im tunnel"
.venv/bin/python doc_search.py docs/aufbau-hardware.md \
  "Wie funktioniert SSH im WireGuard-Tunnel?" \
  --question --also-search docs/aufbau-fernzugriff.md --show-prompt
```

`--also-search DATEI` lässt sich für mehrere zusätzliche Dateien wiederholen. Mit `--project-docs` lässt du die Dateipfade weg; das Programm durchsucht dann die festgelegte Hardware- und Fernzugriffsdoku als Fragensuche. Standardmäßig wird nur der beste Ausschnitt ausgegeben. `--multi-source` nimmt bis zu zwei Fundstellen auf, jeweils den besten Ausschnitt pro angegebener Datei. Im folgenden Beispiel liefert die Fernzugriffsdoku den SSH-Beleg und die Hardware-Doku den CPU-Beleg:

```bash
.venv/bin/python doc_search.py \
  "Welche CPU ist verbaut und wie läuft SSH im WireGuard-Tunnel?" \
  --project-docs --multi-source --show-prompt
```

`--show-prompt` zeigt die Originalfrage, die Fundstellen und die Ausschnitte offline. Ergänze bei Bedarf `--gpt`, um genau diesen Kontext an `gpt-4o-mini` zu senden. Ohne Treffer wird kein Modell aufgerufen. Die Antworten auf Dokufragen erscheinen im Terminal und werden nicht in SQLite gespeichert.

Für Dokufragen sind bis zu **240 Ausgabetoken** vorgesehen; für die GPT-Temperaturberichte bleibt der Standard bei **120**. Im Test endete eine Antwort mit zwei Quellen bei 120 Token mit `incomplete` und dem Grund `max_output_tokens`; der Kontrolllauf mit 240 Token meldete `completed`. Das Programm zeigt den API-Status und, falls vorhanden, den Grund für eine unvollständige Ausgabe.

Die Zitatprüfung erkennt Angaben wie `docs/aufbau-hardware.md:3-5` und prüft, ob genau dieser Dateipfad und Zeilenbereich im Prompt standen. Sie meldet abweichende Angaben oder dass kein Zitat erkannt wurde. Eine bekannte Fundstelle allein zeigt weder, dass sie die jeweilige Aussage stützt, noch dass die Antwort vollständig ist. In einem Live-Lauf waren zum Beispiel beide Zitate korrekt, aber die Schlüsselanmeldung wurde nicht ausdrücklich erwähnt. Die [RAG-Prüfreihe](docs/versuche/rag-pruefreihe.md) trennt deshalb Quellenauswahl und Antwortqualität und hält vier Fälle fest: eine Quelle, zwei Quellen, eine teilweise belegte Frage und keine Fundstelle.

### Offline-Tests ausführen

Die Tests prüfen SQLite, den Export, die Rangfolge bei der Suche, die Promptvorschau und den Umgang mit abweichenden Zitaten. Sie brauchen keine API-Schlüssel: Sie verwenden lokale Dateien, temporäre Datenbanken und bei Bedarf feste Testantworten.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Alle versionierten Dateien

### Programm und Konfiguration

| Datei | Inhalt und Aufgabe |
| --- | --- |
| [`README.md`](README.md) | Erklärt das Projekt, seine Benutzung und die Aufgaben aller versionierten Dateien. |
| [`.gitignore`](.gitignore) | Hält lokale Entwicklungsdateien, Zugangsdaten, Datenbanken und Exporte aus dem Repository. Dazu gehören `.venv/`, `.env`, `data/` und `reports/`. |
| [`requirements.txt`](requirements.txt) | Listet die zusätzlichen Python-Pakete `openai`, `google-genai` und `python-dotenv`. Sie werden für die optionalen Modellaufrufe gebraucht. |
| [`main.py`](main.py) | Ist der Einstieg im Terminal und liest den CSV-Pfad sowie die Optionen ein. Die Datei verbindet CSV-Import, Auswertung und Ausgabe; bei gewähltem Modell ruft sie den passenden Anbieter auf und speichert den Lauf. |
| [`temperature_csv.py`](temperature_csv.py) | Liest die Spalte `temperature_c` aus einer CSV-Datei. Leere Felder werden zu `None`, Zahlen zu Ganzzahlen; bei einem ungültigen Temperaturwert enthält die Fehlermeldung Datei, Zeile und Feldinhalt. |
| [`temperature.py`](temperature.py) | Enthält die Funktionen für die Auswertung. Eine zählt fehlende Werte, die andere zählt gültige Werte strikt oberhalb der Schwelle. |
| [`temperature_prompt.py`](temperature_prompt.py) | Verbindet einen festen deutschen Schreibauftrag mit den berechneten Kennzahlen. So können beide Anbieter denselben Prompt erhalten, und mit `--show-prompt` lässt er sich vorher ansehen. |
| [`model_gpt.py`](model_gpt.py) | Sendet Temperatur- und Dokuprompts mit dem OpenAI-SDK an `gpt-4o-mini`. Gibt Text, verfügbare Tokenzahlen, Anbieterzeit, API-Status und den Grund einer unvollständigen Antwort zurück; das Ausgabelimit lässt sich pro Aufruf setzen. |
| [`model_gemini.py`](model_gemini.py) | Sendet den Prompt mit dem Google-SDK an `gemini-3.5-flash-lite`. Gibt Bericht und verfügbare Tokenzahlen zurück; separat gemeldete Denk-Token werden dabei nicht zu den Ausgabetoken addiert. |
| [`model_storage.py`](model_storage.py) | Legt die SQLite-Tabelle `model_runs` an und ergänzt fehlende Spalten bei Bedarf. Speichert Modellläufe und kann sie anhand ihrer ID wieder auslesen. |
| [`show_model_run.py`](show_model_run.py) | Zeigt Prompt, Antwort und Metadaten eines gespeicherten Laufs per ID. Baut für `--export` einen Berichtskopf und schreibt nach Bestätigung genau den Text aus der Vorschau in eine neue Datei. |
| [`doc_search.py`](doc_search.py) | Durchsucht eine oder mehrere lokale Dateien und wählt bis zu zwei Ausschnitte mit Fundstellen aus. Zeigt sie direkt oder als Prompt an, kann die Dokufrage an GPT senden und meldet das Ergebnis der Zitatprüfung. |
| [`doc_prompt.py`](doc_prompt.py) | Baut Prompts aus der Originalfrage und einer oder zwei Fundstellen. Gleicht erkannte Zitate mit den angebotenen Pfaden und Zeilenbereichen ab. |

### Tests

| Datei | Inhalt und Aufgabe |
| --- | --- |
| [`tests/test_model_storage.py`](tests/test_model_storage.py) | Prüft mit temporären SQLite-Dateien das Speichern und Auslesen nach ID. Prüft auch, dass fehlende Datenbanken beim Lesen nicht angelegt werden. |
| [`tests/test_report_export.py`](tests/test_report_export.py) | Prüft, dass die Exportvorschau dem Dateiinhalt entspricht, eine Ablehnung keinen Ordner anlegt und ein belegtes Ziel nicht überschrieben wird. |
| [`tests/test_doc_search.py`](tests/test_doc_search.py) | Prüft die Rangfolge von Ausschnitten innerhalb einer Datei und zwischen Dateien. Sichert die Zuordnung `Prozessor` → `CPU` und den Ausschluss des Projektnamens ab. |
| [`tests/test_doc_prompt.py`](tests/test_doc_prompt.py) | Prüft die Promptvorschau mit Dateiargumenten und mit der festen Projektdoku, einschließlich einer zweiten Quelle auf Wunsch. Sichert ab, dass ohne Treffer kein Modell aufgerufen und ein abweichendes Zitat gemeldet wird. |

### Beispieldaten

| Datei | Inhalt und Aufgabe |
| --- | --- |
| [`examples/temperature_sample.csv`](examples/temperature_sample.csv) | Enthält die Messwerte 40, 60 und 65 °C sowie ein leeres Temperaturfeld. Dient zum Prüfen der Zählung und der fehlenden Werte. |
| [`examples/temperature_invalid.csv`](examples/temperature_invalid.csv) | Enthält in Zeile 3 den Wert `kaputt` statt einer Temperatur. Damit lässt sich prüfen, ob das Programm eine verständliche Fehlermeldung ausgibt und den Prozess mit Code `1` beendet. |
| [`examples/eval_threshold_equal.csv`](examples/eval_threshold_equal.csv) | Prüft Werte genau an der Schwelle: 3 Messwerte, alle gültig, keiner strikt über 60 °C. |
| [`examples/eval_mostly_missing.csv`](examples/eval_mostly_missing.csv) | Prüft überwiegend fehlende Werte: 5 Einträge, 2 gültig, 3 fehlend und einer strikt über 60 °C. |
| [`examples/eval_negative_temperatures.csv`](examples/eval_negative_temperatures.csv) | Prüft negative Temperaturen: 5 Einträge, 4 gültig, einer fehlend und zwei strikt über −5 °C. |

### Dokumentation und Lernjournal

| Datei | Inhalt und Aufgabe |
| --- | --- |
| [`docs/aufbau-fernzugriff.md`](docs/aufbau-fernzugriff.md) | Zeigt als Mermaid-Diagramm, wie der Zugriff vom Mac auf Cosi-Lab über DuckDNS, den Heimrouter, WireGuard und SSH funktioniert. Die geprüften Zugänge über Handy-Hotspot und Bibliotheks-WLAN sind eingezeichnet. |
| [`docs/aufbau-hardware.md`](docs/aufbau-hardware.md) | Zeigt im Mermaid-Diagramm den dokumentierten Hardwarestand vom 31.10.2026. Enthält die Komponenten, Laufwerke und die damals offenen Punkte bei Kühlung und Start. |
| [`docs/journal/2026-11-09.md`](docs/journal/2026-11-09.md) | Hält die ersten Schritte fest: Zählen, CSV-Import, Fehlermeldungen, Terminaloptionen und die Ausgabe der Kennzahlen. Dokumentiert außerdem den Prompt und den ersten erfolgreichen GPT-Aufruf. |
| [`docs/journal/2026-11-10.md`](docs/journal/2026-11-10.md) | Dokumentiert die Gemini-Anbindung und den ersten Vergleich der Modellberichte. Hält die Tests zur SQLite-Speicherung und die ausgelesenen Metadaten für GPT und Gemini fest. |
| [`docs/journal/2026-11-11.md`](docs/journal/2026-11-11.md) | Dokumentiert den gemeinsamen Speicherblock, die lokale Laufzeitmessung und die Testläufe mit GPT und Gemini. Beschreibt das Auslesen eines gespeicherten Laufs anhand seiner ID und die ersten Offline-Tests. |
| [`docs/journal/2026-11-14.md`](docs/journal/2026-11-14.md) | Dokumentiert Exportfreigabe und Berichtskopf, den Temperaturvergleich sowie den Aufbau der Dokusuche bis zu mehreren Fundstellen und der Zitatprüfung. |
| [`docs/versuche/rag-pruefreihe.md`](docs/versuche/rag-pruefreihe.md) | Hält vier wiederholbare Fälle mit Soll-Ergebnissen und den beobachteten Ausgangsstand fest. Trennt die Auswahl der Quelle von der Frage, ob GPT seine Antwort darauf stützt. |

## Lokale Dateien und Ordner

| Pfad | Inhalt und Aufgabe |
| --- | --- |
| `.env` | Enthält die eigenen API-Schlüssel, sofern Modellaufrufe genutzt werden. Wird nicht mit Git geteilt. |
| `.venv/` | Enthält die lokale Python-Umgebung und die dort installierten Pakete. Kann mit `requirements.txt` neu eingerichtet werden. |
| `data/model_runs.sqlite3` | Enthält gespeicherte Temperatur-Modellläufe einschließlich Prompt, Antwort und Metadaten. Das Programm legt die Datei beim Speichern bei Bedarf an; Git ignoriert sie. |
| `reports/` | Enthält bestätigte Exporte als UTF-8-Textdateien, beispielsweise `model-run-12.txt`. Der Ordner wird bei Bedarf angelegt und von Git ignoriert. |
