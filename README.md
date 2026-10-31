# Cosi-Lab

Python-Versuchssystem für kontrollierte KI-Aufträge auf begrenzter Hardware mit öffentlicher Projektdokumentation.

**Aktueller Stand · 31. Oktober 2026:** Ubuntu und ein schlüsselbasierter Fernzugriff über WireGuard sind eingerichtet und in mehreren Schritten geprüft. Eine lokale Python-Entwicklungsumgebung, ein CSV-Importer, ein deterministischer Rechenbaustein und eine einfache Terminalbedienung zur Temperaturauswertung mit Offline-Tests sind vorhanden. Modellanbindung und Agentenschleife folgen. Dieses Repository macht den Fortschritt, die Entscheidungen und die Grenzen des Aufbaus nachvollziehbar.

## Leitfrage

> Wie lässt sich ein nachvollziehbares und kontrolliertes KI-System mit eigener Ablaufsteuerung auf begrenzter Hardware aufbauen, und wo liegen seine gemessenen Qualitäts- und Leistungsgrenzen?

## Leitgedanke

> Bestehende Rechenleistung weiterverwenden, nachgewiesene Betriebsprobleme zuerst beheben und Erweiterungen anhand gemessenen Bedarfs entscheiden. Begrenzte Ressourcen werden bewusst genutzt, um das Systemverhalten zu verstehen und Leistungsgrenzen nachvollziehbar zu bestimmen.

## Geplantes erstes Softwareziel

Eine synthetische Temperaturmessreihe wird als CSV eingelesen und mit Python deterministisch ausgewertet. Ein Sprachmodell formuliert auf Grundlage geprüfter Kennzahlen einen Bericht. Eine Datei wird erst nach menschlicher Freigabe abgelegt. Ablaufsteuerung, Modellanbindung, Werkzeugaufrufe und strukturierte Ereignisprotokolle werden im eigenen Python-Kern nachvollziehbar umgesetzt.

Der feste Ablauf aus CSV-Import und deterministischer Temperaturauswertung ist über eine einfache Terminalbedienung verfügbar. Darauf aufbauend soll eine begrenzte Agentenschleife mit demselben Werkzeugumfang verglichen werden. API-Modelle und ein kleines lokales Modell dienen dazu, Qualität, Ressourcenbedarf und Leistungsgrenzen zu untersuchen. Modellanbindung, freigegebene Speicherung und Agentenschleife bleiben Entwicklungsziele.

## Bisher erreicht

| Bereich | Stand |
|---|---|
| Rechnerbasis | Vorhandene Hardware mit Sechskern-CPU und 16 GB RAM; Ubuntu installiert |
| Administration | SSH-Schlüsselanmeldung eingerichtet und Passwortanmeldung als gesperrt geprüft |
| Fernzugriff | WireGuard mit dynamischem DNS; SSH im Heimnetz und über einen Mobilfunk-Hotspot erfolgreich getestet |
| Wiederanlauf | VPN-Autostart und SSH ohne vorherige Desktop-Anmeldung nach Neustart bestätigt |
| Dokumentation | Öffentlich bereinigtes Runbook, Strukturdiagramme und erstes Journal vorhanden |

## Offene Punkte

- Längerer Leerlauftest und Prüfung im tatsächlichen Bibliotheks-WLAN.
- DNS-Aktualisierung nach einem Wechsel der öffentlichen IP praktisch nachweisen.
- Montage, Kühlung und zuverlässige Bedienung weiter klären; F1-Bestätigung beim Start bleibt erforderlich.
- Speicherbasis weiter bewerten: Die vorhandene HDD hat keinen abgeschlossenen Langtest, die gefundene SSD auffällige Gesundheitswerte.
- Das ausführlichere Lern-/Codeprofil ergänzen; die Arbeitsregeln sind in [AGENTS.md](AGENTS.md) festgehalten.

## Lokale Entwicklungsumgebung

Für die erste Offline-Aufgabe zur Temperaturauswertung genügt die Python-Standardbibliothek; zusätzliche Pakete sind nicht erforderlich. Die lokale Umgebung verwendet Python 3.14. Die folgenden Befehle werden im Repository-Verzeichnis ausgeführt (macOS/Linux); zum Erstellen muss `python3.14` verfügbar sein.

Umgebung einmalig erstellen; eine vorhandene `.venv` vorher prüfen:

```bash
python3.14 -m venv .venv
```

Optional für die aktuelle Shell aktivieren (zsh/bash):

```bash
source .venv/bin/activate
python --version
deactivate
```

Ohne Aktivierung lässt sich der Interpreter direkt aufrufen:

```bash
.venv/bin/python --version
```

In PyCharm wird `.venv/bin/python` als vorhandener Projektinterpreter ausgewählt. Die `.venv` bleibt lokal und wird von Git ignoriert.

`temperature_analysis.py` enthält `analyze_temperatures(values, threshold=60.0)`: Der Baustein zählt gültige und fehlende Messwerte, berechnet Minimum, Maximum und arithmetisches Mittel ohne zusätzliche Rundung und zählt Werte strikt oberhalb des Schwellenwerts. `None` wird nur als fehlend gezählt; ungültige Eingaben, fehlende gültige Messwerte oder ein Überlauf bei der Mittelwertberechnung führen zu `ValueError`. Die Berechnung verwendet ausschließlich die Standardbibliothek und läuft offline.

Die zugehörigen Tests werden im Repository-Verzeichnis ausgeführt:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## CSV-Import

`temperature_csv.read_temperature_csv(path)` akzeptiert einen Pfad als `str` oder `pathlib.Path`. Die Beispieldatei [examples/temperature_sample.csv](examples/temperature_sample.csv) zeigt das unterstützte Format: UTF-8, Komma als Trennzeichen, feste Kopfzeile `time_s,temperature_c`, ein Datensatz je physischer Zeile mit genau zwei Feldern und Zeilenenden LF oder CRLF.

Zeitstempel müssen vorhanden, endlich und strikt aufsteigend sein. Temperaturen müssen endliche Zahlen sein; leere oder nur aus Leerraum bestehende Temperaturfelder werden als `None` erhalten. Der Importer liefert eine Liste von Wörterbüchern mit `time_s` und `temperature_c`, Zahlen jeweils als `float`. Fehlerhafte Zeilen werden mit `ValueError` samt Zeile und gegebenenfalls Feld gemeldet; Dateisystemfehler bleiben erhalten. Leere Dateien und Dateien nur mit Kopfzeile werden abgelehnt.

Import und Analyse bleiben getrennt: Auch ausschließlich fehlende Temperaturen sind importierbar. Erst `analyze_temperatures` lehnt die Auswertung ohne gültige Temperaturen ab. Die Tests prüfen beide Bausteine auch gemeinsam anhand der Beispieldatei.

## Terminalbedienung

Aus dem Projektverzeichnis lassen sich die Beispieldaten direkt auswerten und die deutschsprachige Hilfe anzeigen:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --threshold 60
.venv/bin/python cosi.py --help
```

`--threshold` ist optional (Standard: `60.0`) und muss eine endliche Zahl sein. Kennzahlen erscheinen erst nach vollständiger Berechnung auf stdout, ohne zusätzliche Rundung. Fehler erscheinen auf stderr. Rückgabecodes: `0` für Erfolg oder Hilfe, `1` für Datei-, Format- oder Analysefehler, `2` für ungültige Kommandozeilenargumente. Es werden keine Ergebnisdateien geschrieben.

Mit `--log-dir logs` wird optional eine neue UTF-8-Datei `logs/<run_id>.jsonl` exklusiv angelegt; das Verzeichnis wird bei Bedarf erstellt. Beispiel:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --threshold 60 --log-dir logs
```

Jede JSON-Zeile enthält ausschließlich technische Metadaten zu Lauf und Schritten (`csv_import`, `temperature_analysis`): Schema-Version, Lauf-ID, UTC-Zeitpunkt, Ereignis, Schritt, Status, Abschlussdauer und gegebenenfalls Exception-Klassenname. Laufzeiten werden mit `time.perf_counter` unabhängig von der Systemuhr gemessen. Messwerte, Dateipfade und Fehlertexte werden nicht protokolliert. Protokollierungsfehler führen zu Rückgabecode `1` ohne Erfolgsbericht; die Ausgabe erfolgt erst nach vollständiger Protokollierung und Schließen der Datei. Bei Schreibfehlern kann eine unvollständige Protokolldatei zurückbleiben. Ohne Option sowie bei Hilfe oder ungültigen Argumenten entstehen keine Protokolle. `/logs/` wird von Git ignoriert.

Die Laufdauer umfasst die Verarbeitung und Teile der Protokollierung: Sie beginnt nach der Logdateierstellung vor `run_started` und endet vor dem Schreiben von `run_finished`. Python-Start, Argumentprüfung, Logdateierstellung, abschließendes Schließen und Terminalausgabe sind nicht enthalten.

`run_finished` mit `status: success` beschreibt erfolgreiche Verarbeitung vor dem Schließen der Protokolldatei. Ein anschließender Schließfehler führt dennoch zu CLI-Rückgabecode `1`. Versuchsreihen müssen deshalb zusätzlich den Prozess-Rückgabecode erfassen.

## Dokumentation und Fortschritt

- [Aktueller Aufbau als Diagramme](docs/aufbau.md)
- [Runbook: täglicher Fernzugriff und Einrichtung](docs/runbooks/fernzugriff.md)
- [Journal: 31. Oktober 2026](docs/journal/2026-10-31.md)

Das Journal hält abgeschlossene Schritte und Beobachtungen kurz fest. Wesentliche Entscheidungen werden mit ihrer Begründung dokumentiert. Testergebnisse werden als geprüft, auffällig oder noch offen gekennzeichnet; geplante Funktionen werden nicht als bereits umgesetzt dargestellt.

## Öffentliche und private Unterlagen

Dieses Repository enthält ausgewählte, bereinigte Projektunterlagen. Echte Verbindungsadressen, Routermodell und Firmware, Zugangsdaten, Schlüssel, Seriennummern, reale VPN-Konfigurationen und unbereinigte Diagnoseberichte bleiben außerhalb dieses Repositorys. Die `.gitignore` unterstützt diese Trennung; vor jedem Commit werden die tatsächlich vorgemerkten Änderungen geprüft.
