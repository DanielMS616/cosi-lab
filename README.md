# Cosi-Lab – Lernversion

Cosi-Lab ist ein Python-Lernprojekt für die Auswertung von Temperaturdaten. Das Programm liest eine CSV-Datei und zählt die Messwerte insgesamt, die gültigen und fehlenden Werte sowie die Werte, die strikt über einer wählbaren Schwelle liegen. Auf Wunsch formuliert GPT oder Gemini aus diesen Kennzahlen einen kurzen Bericht; das Programm speichert dann Prompt, Antwort und verfügbare API-Metadaten in einer lokalen SQLite-Datenbank.

Python berechnet die Kennzahlen. Das Modell bekommt den daraus erzeugten Prompt und formuliert den Text. Der frühere Prototyp ist unter [`prototyp-2026-11-07`](https://github.com/DanielMS616/cosi-lab/tree/prototyp-2026-11-07) archiviert. In der Lernversion dokumentiere ich die einzelnen Schritte und ihre Prüfung im Journal.

## Schnellstart

Führe die Befehle im Projektordner aus. Falls noch keine virtuelle Umgebung existiert, lege sie einmal mit `python3 -m venv .venv` an. Verwende danach `.venv/bin/python` für alle Beispiele. So verwendest du auch bei einem späteren Modellaufruf den Interpreter, in dessen Umgebung die Projektpakete installiert sind.

```bash
.venv/bin/python main.py examples/temperature_sample.csv
.venv/bin/python main.py examples/temperature_sample.csv --threshold 65 --show-temperatures --show-prompt
```

Die Beispieldatei enthält vier Einträge: drei gültige Werte und eine fehlende Messung. Bei der Standardschwelle von 60 °C liegt ein Wert darüber; bei 65 °C sind es null, weil Gleichheit nicht als Überschreitung zählt. `--show-temperatures` zeigt die eingelesene Liste, `--show-prompt` den fertigen Auftrag an das Modell. Beide Schalter funktionieren ohne API-Aufruf und zusätzliche Python-Pakete.

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

Wähle pro Aufruf höchstens ein Modell. Ein erfolgreicher Modelllauf wird in `data/model_runs.sqlite3` gespeichert. `requested_at_utc` hält fest, wann das Programm die Modellfunktion aufgerufen hat. Dieser UTC-Zeitstempel stammt von der Uhr des Rechners; bei älteren Läufen bleibt er `NULL`.

GPT übernimmt die von OpenAI gemeldete Verarbeitungszeit, falls der Header `openai-processing-ms` vorhanden und lesbar ist. Bei Gemini bleibt `duration_ms` auf `NULL`. Fehlende Tokenzahlen bleiben ebenfalls `NULL`; eine lokal gemessene Laufzeit gibt es bisher nicht.

Nach einem Modelllauf kannst du den jüngsten Eintrag mit der `sqlite3`-Kommandozeile ansehen:

```bash
sqlite3 -readonly -header -column -nullvalue NULL data/model_runs.sqlite3 \
  'SELECT id, model, requested_at_utc, duration_ms, input_tokens, output_tokens
   FROM model_runs ORDER BY id DESC LIMIT 1;'
```

## Alle versionierten Dateien

### Programm und Konfiguration

| Datei | Inhalt und Aufgabe |
| --- | --- |
| [`README.md`](README.md) | Erklärt das Projekt, seine Benutzung und die Aufgaben aller versionierten Dateien. |
| [`.gitignore`](.gitignore) | Hält lokale Entwicklungsdateien, Zugangsdaten und erzeugte Datenbanken aus dem Repository. Dazu gehören unter anderem `.venv/`, `.env` und `data/`. |
| [`requirements.txt`](requirements.txt) | Listet die zusätzlichen Python-Pakete `openai`, `google-genai` und `python-dotenv`. Sie werden für die optionalen Modellaufrufe gebraucht. |
| [`main.py`](main.py) | Ist der Einstieg im Terminal und liest den CSV-Pfad sowie die Optionen ein. Die Datei verbindet CSV-Import, Auswertung und Ausgabe; bei gewähltem Modell ruft sie den passenden Anbieter auf und speichert den Lauf. |
| [`temperature_csv.py`](temperature_csv.py) | Liest die Spalte `temperature_c` aus einer CSV-Datei. Leere Felder werden zu `None`, Zahlen zu Ganzzahlen; bei einem ungültigen Temperaturwert enthält die Fehlermeldung Datei, Zeile und Feldinhalt. |
| [`temperature.py`](temperature.py) | Enthält die Funktionen für die Auswertung. Eine zählt fehlende Werte, die andere zählt gültige Werte strikt oberhalb der Schwelle. |
| [`temperature_prompt.py`](temperature_prompt.py) | Verbindet einen festen deutschen Schreibauftrag mit den berechneten Kennzahlen. So können beide Anbieter denselben Prompt erhalten, und mit `--show-prompt` lässt er sich vorher ansehen. |
| [`model_gpt.py`](model_gpt.py) | Sendet den Prompt mit dem OpenAI-SDK an `gpt-4o-mini`. Gibt den Bericht, verfügbare Eingabe- und Ausgabetoken sowie die gemeldete Verarbeitungszeit zurück. |
| [`model_gemini.py`](model_gemini.py) | Sendet den Prompt mit dem Google-SDK an `gemini-3.5-flash-lite`. Gibt Bericht und verfügbare Tokenzahlen zurück; separat gemeldete Denk-Token werden dabei nicht zu den Ausgabetoken addiert. |
| [`model_storage.py`](model_storage.py) | Legt die SQLite-Tabelle `model_runs` an und ergänzt in vorhandenen Datenbanken bei Bedarf die Spalte für den Aufrufzeitpunkt. Speichert Modellname, CSV-Pfad, Schwelle, Prompt, Antwort, UTC-Zeitstempel und verfügbare API-Metadaten und gibt die Lauf-ID zurück. |

### Beispieldaten

| Datei | Inhalt und Aufgabe |
| --- | --- |
| [`examples/temperature_sample.csv`](examples/temperature_sample.csv) | Enthält die Messwerte 40, 60 und 65 °C sowie ein leeres Temperaturfeld. Dient zum Prüfen der Zählung und der fehlenden Werte. |
| [`examples/temperature_invalid.csv`](examples/temperature_invalid.csv) | Enthält in Zeile 3 den Wert `kaputt` statt einer Temperatur. Damit lässt sich prüfen, ob das Programm eine verständliche Fehlermeldung ausgibt und den Prozess mit Code `1` beendet. |

### Dokumentation und Lernjournal

| Datei | Inhalt und Aufgabe |
| --- | --- |
| [`docs/aufbau-fernzugriff.md`](docs/aufbau-fernzugriff.md) | Zeigt als Mermaid-Diagramm, wie der Zugriff vom Mac auf Cosi-Lab über DuckDNS, den Heimrouter, WireGuard und SSH funktioniert. Die geprüften Zugänge über Handy-Hotspot und Bibliotheks-WLAN sind eingezeichnet. |
| [`docs/aufbau-hardware.md`](docs/aufbau-hardware.md) | Zeigt im Mermaid-Diagramm den dokumentierten Hardwarestand vom 31.10.2026. Enthält die Komponenten, Laufwerke und die damals offenen Punkte bei Kühlung und Start. |
| [`docs/journal/2026-11-09.md`](docs/journal/2026-11-09.md) | Hält die ersten Schritte fest: Zählen, CSV-Import, Fehlermeldungen, Terminaloptionen und die Ausgabe der Kennzahlen. Dokumentiert außerdem den Prompt und den ersten erfolgreichen GPT-Aufruf. |
| [`docs/journal/2026-11-10.md`](docs/journal/2026-11-10.md) | Dokumentiert die Gemini-Anbindung und den ersten Vergleich der Modellberichte. Hält die Tests zur SQLite-Speicherung und die ausgelesenen Metadaten für GPT und Gemini fest. |

## Lokale Dateien und Ordner

| Pfad | Inhalt und Aufgabe |
| --- | --- |
| `.env` | Enthält die eigenen API-Schlüssel, sofern Modellaufrufe genutzt werden. Wird nicht mit Git geteilt. |
| `.venv/` | Enthält die lokale Python-Umgebung und die dort installierten Pakete. Kann mit `requirements.txt` neu eingerichtet werden. |
| `data/model_runs.sqlite3` | Enthält gespeicherte Modellläufe einschließlich Prompt und Antwort. Die Datei entsteht beim ersten erfolgreichen Modelllauf und wird von Git ignoriert. |
