# Cosi-Lab

Python-Versuchssystem für kontrollierte KI-Aufträge auf begrenzter Hardware mit öffentlicher Projektdokumentation.

**Aktueller Stand · 2. November 2026:** CSV-Import, deterministische Temperaturauswertung, Terminalbedienung, optionale JSONL-Protokollierung und Speicherung nach Freigabe sind vorhanden. Ein optionaler Modellbericht ist über die CLI verfügbar und offline getestet. Zusätzlich hat der Betreiber einen erfolgreichen CLI-Live-Test auf Ubuntu mit `--model-report` und `--log-dir` zurückgemeldet: korrekte Beispielkennzahlen und Prozess-Rückgabecode `0`. Dieser Nachweis gilt für einen Einzelfall (siehe Journal). Commit `c86a761` wurde auf Ubuntu mit Python 3.14.4 erfolgreich geprüft: 51 Tests sowie die protokollierte Beispielauswertung mit Rückgabecode 0. Auch automatische DNS-Aktualisierung nach einem echten öffentlichen IPv4-Wechsel und anschließender VPN-/SSH-Zugriff über den Handy-Hotspot sind geprüft. Grundlage sind die im [Journal](docs/journal/2026-11-02.md) festgehaltenen Rückmeldungen. Die Agentenschleife folgt.

## Leitfrage

> Wie lässt sich ein nachvollziehbares und kontrolliertes KI-System mit eigener Ablaufsteuerung auf begrenzter Hardware aufbauen, und wo liegen seine gemessenen Qualitäts- und Leistungsgrenzen?

## Leitgedanke

> Bestehende Rechenleistung weiterverwenden, nachgewiesene Betriebsprobleme zuerst beheben und Erweiterungen anhand gemessenen Bedarfs entscheiden. Begrenzte Ressourcen werden bewusst genutzt, um das Systemverhalten zu verstehen und Leistungsgrenzen nachvollziehbar zu bestimmen.

## Geplantes erstes Softwareziel

Eine synthetische Temperaturmessreihe wird als CSV eingelesen und mit Python deterministisch ausgewertet. Ein Sprachmodell formuliert auf Grundlage geprüfter Kennzahlen einen Bericht. Eine Datei wird erst nach menschlicher Freigabe abgelegt. Ablaufsteuerung, Modellanbindung, Werkzeugaufrufe und strukturierte Ereignisprotokolle werden im eigenen Python-Kern nachvollziehbar umgesetzt.

Der feste Ablauf aus CSV-Import und deterministischer Temperaturauswertung ist über eine einfache Terminalbedienung verfügbar. Darauf aufbauend soll eine begrenzte Agentenschleife mit demselben Werkzeugumfang verglichen werden. API-Modelle und ein kleines lokales Modell dienen dazu, Qualität, Ressourcenbedarf und Leistungsgrenzen zu untersuchen. Modellbericht und Speicherung nach ausdrücklicher Freigabe sind zuschaltbar; die Agentenschleife bleibt ein Entwicklungsziel.

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

`--threshold` ist optional (Standard: `60.0`) und muss eine endliche Zahl sein. Kennzahlen erscheinen ohne zusätzliche Rundung auf stdout. Ohne Speicheroption erscheinen sie erst nach erfolgreicher Verarbeitung und gegebenenfalls erfolgreichem Logabschluss; ein angeforderter Modellbericht folgt gekennzeichnet danach. Fehler erscheinen auf stderr, ohne Erfolgsbericht. Rückgabecodes: `0` für Erfolg oder Hilfe, `1` für Datei-, Format-, Analyse-, Modell-, Speicher- oder Protokollierungsfehler, `2` für ungültige Kommandozeilenargumente. Ohne `--save-report` werden keine Ergebnisdateien geschrieben und keine Freigaben abgefragt.

Ohne `--model-report` bleibt der Aufruf vollständig offline. Nur diese Option aktiviert die OpenAI-Berichtserstellung und benötigt `OPENAI_API_KEY` in der Umgebung. Übermittelt werden ausschließlich Kennzahlen und derselbe validierte Schwellenwert wie bei der Analyse, keine Rohdaten oder Dateipfade. Beispiel für einen ausdrücklich angeforderten API-Aufruf:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --threshold 60 --model-report --model gpt-4.1-mini
```

`--model` ist bei `--model-report` optional (Standard: `gpt-4.1-mini`). Ohne `--model-report` sowie bei leerem oder nur aus Leerraum bestehendem Modellnamen endet die Argumentprüfung mit Code `2`, bevor Verarbeitung, Netzwerkzugriff oder Protokollierung beginnen.

Mit `--save-report` wird der vollständige Bericht zunächst ausdrücklich als **Vorschau** zusammen mit einem vom Programm bestimmten Ziel `reports/<UUID>.txt` gezeigt. Die Option funktioniert mit und ohne `--model-report`. Freigabe und Speicherung sind offline getestet.

Zum Commit `c74b996` bestätigt eine [Betreiber-Rückmeldung](docs/journal/2026-11-02.md) den Ubuntu-Praxistest ohne Modellbericht: 104 Tests erfolgreich, `nein` ohne Berichtsordner oder Datei, danach `ja` im selben Versuchsordner mit genau einer Datei entsprechend der Vorschau. Beide Aufrufe bestätigten den Protokollabschluss und endeten mit Code `0`. Die Versuchsdateien liegen außerhalb des Repositorys. Beispielaufruf:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --save-report --log-dir logs
```

Nur `ja` (äußeren Leerraum entfernen, Groß-/Kleinschreibung ignorieren) erlaubt Speichern. Andere Antworten, EOF und Strg+C bei der Eingabe verweigern die Freigabe und enden regulär mit Code `0` und „Nicht gespeichert“. Erst nach Freigabe werden Berichtsordner und Datei angelegt. `report_storage.py` schreibt den bereits angezeigten Bericht exakt als UTF-8, einschließlich abschließendem Zeilenumbruch, ohne Vorschau-Markierungen oder Zielpfad. Es gibt keinen weiteren Modellaufruf. Modelltext bestimmt weder Ziel noch Freigabe; exklusive Dateierstellung verhindert Überschreiben auch bei einer UUID-Kollision. `/reports/` wird von Git ignoriert.

Die Vorschau bestätigt weder Speicherung noch Logabschluss. „Bericht gespeichert“ erscheint erst nach erfolgreichem Schreiben und Schließen der Berichtdatei sowie gegebenenfalls erfolgreichem Logabschluss. Scheitert nach dem Schreibabschluss die Protokollierung, meldet die CLI mit Code `1`, dass die Berichtdatei bereits vollständig geschrieben und geschlossen wurde. Sie wird nicht zurückgerollt. Bei Schreib- oder Schließfehlern der Berichtdatei ist der Schreibabschluss unbestätigt; eine unvollständige Datei kann verbleiben. Exklusive Erstellung ist keine Garantie gegen Datenverlust bei einem Systemabsturz.

Mit `--log-dir logs` wird optional eine neue UTF-8-Datei `logs/<run_id>.jsonl` exklusiv angelegt; das Verzeichnis wird bei Bedarf erstellt. Beispiel:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --threshold 60 --log-dir logs
```

Jede JSON-Zeile enthält ausschließlich technische Metadaten zu Lauf und Schritten (`csv_import`, `temperature_analysis` und bei angefordertem Bericht `model_report`): Schema-Version, Lauf-ID, UTC-Zeitpunkt, Ereignis, Schritt, Status, Abschlussdauer und gegebenenfalls Exception-Klassenname. Laufzeiten werden mit `time.perf_counter` unabhängig von der Systemuhr gemessen. Messwerte, Dateipfade, Prompts, Modellantworten und Fehlertexte werden nicht protokolliert. Modellfehler werden mit ihrem ursprünglichen Exception-Klassennamen als fehlgeschlagener Schritt und Lauf erfasst; das Ereignisschema bleibt unverändert. Protokollierungsfehler führen zu Rückgabecode `1` ohne abschließende Erfolgsmeldung; ohne Speicheroption erfolgt auch die Berichtsausgabe erst nach vollständiger Protokollierung und Schließen der Datei. Bei `--save-report` wurde gegebenenfalls bereits die ausdrücklich gekennzeichnete Vorschau angezeigt. Bei Schreibfehlern kann eine unvollständige Protokolldatei zurückbleiben. Ohne Option sowie bei Hilfe oder ungültigen Argumenten entstehen keine Protokolle. `/logs/` wird von Git ignoriert.

Mit `--save-report` erfassen die zusätzlichen Ereignisse `save_approved` beziehungsweise `save_declined` die Freigabeentscheidung (`step: report_save`, `status: success`, Dauer und Fehlertyp `null`). Eine Ablehnung ist kein Verarbeitungsfehler. Nur nach Freigabe folgt der Schritt `report_save` mit den bestehenden Start-/Abschlussereignissen. Eingabetext, Bericht und Zielpfad stehen nicht im Log; die gemeinsamen Felder bleiben unverändert.

Die Laufdauer umfasst die Verarbeitung und Teile der Protokollierung: Sie beginnt nach der Logdateierstellung vor `run_started` und endet vor dem Schreiben von `run_finished`. Python-Start, Argumentprüfung, Logdateierstellung, abschließendes Schließen der Logdatei und die abschließende Terminalausgabe sind nicht enthalten. Bei `--save-report` umfasst `run_finished.duration_ms` zusätzlich Vorschau, Wartezeit auf die Freigabe und gegebenenfalls Speicherung einschließlich Schließen der Berichtdatei. Diese Laufzeit ist keine reine Verarbeitungszeit.

`run_finished` mit `status: success` beschreibt erfolgreiche Verarbeitung vor dem Schließen der Protokolldatei. Ein anschließender Schließfehler führt dennoch zu CLI-Rückgabecode `1`. Versuchsreihen müssen deshalb zusätzlich den Prozess-Rückgabecode erfassen.

## Textschnittstelle für Temperaturberichte

`temperature_report.generate_temperature_report(analysis_result, threshold, text_generator)` erstellt aus den sieben vorhandenen Kennzahlen und dem zugehörigen Schwellenwert einen Auftrag für einen kurzen deutschen Bericht. Rohdaten, Dateipfade und zusätzliche Wörterbucheinträge werden nicht übergeben; die Kennzahlen werden nicht neu berechnet. Der Auftrag verlangt, fehlende Werte und Werte strikt oberhalb des Schwellenwerts korrekt zu beschreiben und keine Ursachen zu erfinden.

Der übergebene Textgenerator ist eine Funktion, die einen Auftragstext erhält und eine Textantwort liefert. Sie wird genau einmal aufgerufen. Nicht-textuelle oder leere Antworten (auch reiner Leerraum) führen zu `ValueError`; Generatorausnahmen werden unverändert weitergereicht. Die Schnittstelle ist mit festen Testantworten offline geprüft; diese Tests bewerten keine Modellqualität oder Faktentreue. Die Antwort wird inhaltlich nicht geprüft. Die CLI verbindet diese Schnittstelle ausschließlich bei `--model-report` mit dem OpenAI-Adapter. Die berechneten Kennzahlen bleiben die verlässliche Grundlage; der Modellbericht ist nicht automatisch auf Faktentreue geprüft.

## OpenAI-Textadapter

`openai_text.generate_text(prompt, model="gpt-4.1-mini")` liefert Text über die Responses API; `model` ist ein optionales Schlüsselwortargument. Der Adapter verwendet nur die Standardbibliothek und liest `OPENAI_API_KEY` ausschließlich beim Funktionsaufruf. Ohne Schlüssel erfolgt kein HTTP-Aufruf. Ein Aufruf sendet genau einen POST an `https://api.openai.com/v1/responses`, mit normaler TLS-Zertifikatsprüfung, `max_output_tokens=600` und `store=false`. Es gibt keine automatischen Wiederholungen oder Weiterleitungen. Der Netzwerk-Timeout von 30 Sekunden begrenzt blockierende Socket-Operationen, garantiert aber keine Gesamtlaufzeit, etwa einschließlich DNS-Auflösung und mehrerer Netzwerkoperationen.

Nur abgeschlossene Antworten mit nichtleerem Text gelten als Erfolg. Textteile aus den `output/content`-Einträgen werden in ihrer Reihenfolge zusammengesetzt. HTTP-, Verbindungs-, JSON- und unvollständige Antwortfehler werden als `OpenAITextError` ohne Schlüssel, Anfrage-Header oder vollständige Serverfehlertexte gemeldet. Grundlage sind die offizielle [Textanleitung](https://developers.openai.com/api/docs/guides/text) und [API-Übersicht](https://developers.openai.com/api/reference/overview).

Die Adaptertests ersetzen ausschließlich die HTTP-Grenze durch Testobjekte und prüfen Anfrage, Antwortauswertung und Fehlerbehandlung offline. Die CLI-Integration wird mit einem festen Testgenerator geprüft. Zusätzlich liegen Betreiber-Rückmeldungen zu einem erfolgreichen manuellen Modellaufruf mit `gpt-4.1-mini` und einem erfolgreichen CLI-Live-Test mit Modellbericht und Protokollierung auf Ubuntu vor. Die Beispielkennzahlen waren korrekt; der CLI-Prozess endete mit Code `0`, alle Verarbeitungsschritte waren erfolgreich. Das ist ein erfolgreicher Einzelfall, kein allgemeiner Modellqualitäts- oder Zuverlässigkeitsnachweis. Lauf-ID und gemessene Modellschrittdauer einschließlich API-Kommunikation stehen im [Journal](docs/journal/2026-11-02.md).

## Dokumentation und Fortschritt

- [Aktueller Aufbau als Diagramme](docs/aufbau.md)
- [Runbook: täglicher Fernzugriff und Einrichtung](docs/runbooks/fernzugriff.md)
- [Journal: 31. Oktober 2026](docs/journal/2026-10-31.md)
- [Journal: 2. November 2026](docs/journal/2026-11-02.md)
- [Versuch: CLI-Basismessung mit und ohne Protokollierung](docs/versuche/2026-11-02-cli-baseline.md)
- [Prüfplan für Modellberichte](docs/versuche/modellberichte-pruefplan.md): vier CSV-Referenzfälle mit festen Sollwerten und Kriterien für die spätere manuelle Bewertung; die Offline-Prüfung bewertet noch keine Modellqualität.

Das Journal hält abgeschlossene Schritte und Beobachtungen kurz fest. Wesentliche Entscheidungen werden mit ihrer Begründung dokumentiert. Testergebnisse werden als geprüft, auffällig oder noch offen gekennzeichnet; geplante Funktionen werden nicht als bereits umgesetzt dargestellt.

## Öffentliche und private Unterlagen

Dieses Repository enthält ausgewählte, bereinigte Projektunterlagen. Echte Verbindungsadressen, Routermodell und Firmware, Zugangsdaten, Schlüssel, Seriennummern, reale VPN-Konfigurationen und unbereinigte Diagnoseberichte bleiben außerhalb dieses Repositorys. Die `.gitignore` unterstützt diese Trennung; vor jedem Commit werden die tatsächlich vorgemerkten Änderungen geprüft.
