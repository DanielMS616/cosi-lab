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

`--threshold` ist optional (Standard: `60.0`) und muss eine endliche Zahl sein. Kennzahlen erscheinen ohne zusätzliche Rundung auf stdout. Ohne Speicheroption erscheinen sie erst nach erfolgreicher Verarbeitung und gegebenenfalls erfolgreichem Logabschluss; ein angeforderter Modellbericht folgt gekennzeichnet danach. Fehler erscheinen auf stderr, ohne Erfolgsbericht. Rückgabecodes: `0` für Erfolg oder Hilfe, `1` für Datei-, Format-, Analyse-, Modell-, Speicher- oder Protokollierungsfehler, `2` für ungültige Kommandozeilenargumente. Ohne `--save-report` und `--database` werden keine Ergebnisdateien geschrieben; nur `--save-report` fragt eine Freigabe ab.

Mit `--database PATH` speichert die CLI einen erfolgreichen Import samt Analyse zusätzlich in SQLite. Ein neuer Pfad wird initialisiert; an eine bestehende kompatible Cosi-Datenbank wird je Aufruf ein neuer Lauf angehängt. Beispiel mit zwei Auswertungen in derselben Datenbank:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --database data/cli-runs.sqlite3
.venv/bin/python cosi.py examples/temperature_sample.csv --threshold 65 --database data/cli-runs.sqlite3
```

Ohne `--model-report` und `--save-report` enthält jeder Lauf einen `runs`-Datensatz sowie zwei verknüpfte Artefakte: den absoluten CSV-Dateiverweis mit SHA-256 und Bytezahl und das vollständige Analyseergebnis als JSON. Der Schwellenwert steht in `runs.settings_json`; `simulation` ist `false`, da die Auswertung real erfolgt. Es entstehen dabei weder Modellaufruf noch gespeicherter Bericht oder Export. `--database` kann auch mit `--model-report` und `--save-report` gemeinsam verwendet werden. Die bisherigen Aufrufe ohne Datenbank behalten ihr Verhalten.

Vor jedem Einfügen prüft der Speicherbaustein die Cosi-Kennung, Schemaversion und die Tabellen-, Index- und Triggerdefinitionen gegen `db/schema.sql`. Fremde Datenbanken, bestehende leere Dateien, unbekannte Versionen und abweichende Schemata werden ohne Einfügen abgelehnt; automatische Migrationen gibt es nicht. Der Vergleich akzeptiert bewusst nur das mitgelieferte Schema. Fremdschlüssel und rekursive Trigger sind auf jeder Verbindung aktiv. Analyseläufe ohne Exportentscheidung werden in einer Transaktion geschrieben: Fehler beim Einfügen oder Commit rollen sämtliche Datensätze dieses Laufs zurück, vorhandene Läufe bleiben erhalten. Bei einer neu angelegten Datenbank kann das initialisierte Schema zurückbleiben. Die CSV wird nur referenziert; ihre Verfügbarkeit nach dem Lauf ist nicht durch die Datenbank gesichert.

Ohne `--save-report` bleibt die Terminalausgabe auch mit `--database` die normale Kennzahlenausgabe, gegebenenfalls gefolgt vom Modellbericht, und erfolgt erst nach erfolgreicher Speicherung und Logabschluss. `--log-dir` ist kombinierbar und verwendet dieselbe Lauf-ID; bei reinen Analyseläufen wird zusätzlich der Schritt `database_save` protokolliert. Die Datenbank-Laufdauer umfasst die Verarbeitung vor dem abschließenden Speichern, mit `--save-report` auch Vorschau, Freigabewartezeit und gegebenenfalls Dateischreiben. Scheitert die getrennte JSONL-Protokollierung nach einem Datenbank-Commit, bleiben bereits bestätigte Daten gespeichert; die CLI meldet dies ausdrücklich und endet mit Code `1`. Ohne `--database` gibt es keinen SQLite-Zugriff. Datenbanken unter `/data/` bleiben lokal und werden von Git ignoriert.

Die Abfrage [db/analysis_query.sql](db/analysis_query.sql) zeigt die CSV-/Analyse-Verknüpfung für beide Läufe. Sie kann nach erneutem Öffnen mit derselben Python-Leseanleitung wie die Demo-Abfrage unten ausgeführt werden; dafür Datenbankpfad und SQL-Datei auf `data/cli-runs.sqlite3` und `db/analysis_query.sql` setzen.

`--database PATH` ist auch mit `--model-report` kombinierbar. Ein ausdrücklich angeforderter echter Modellaufruf benötigt wie bisher `OPENAI_API_KEY`:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --database data/model-runs.sqlite3 --model-report
```

Die Berichtsfunktion erzeugt den tatsächlichen Prompt. Vor dem Aufruf von `generate_text_result(...)` prüft der Speicherbaustein die Datenbank und schreibt Lauf (`running`), CSV-Verweis, Analyse und Modellaufruf (`started`) einschließlich Prompt, Prompt-Hash und Anfrageparametern in einer gemeinsamen Transaktion. Diese wird vollständig abgeschlossen und die Verbindung geschlossen, bevor der Adapter aufgerufen wird. Ein Fehler bei der Vorbereitung verhindert die Anfrage. Während des Modellaufrufs bleibt keine SQLite-Transaktion offen.

Bei Erfolg werden Antwort und verfügbare typisierte Metadaten gespeichert und der vollständige angezeigte Bericht als Artefakt mit Analyse und Modellaufruf verknüpft. Ohne `--save-report` werden beide Status auf `succeeded` gesetzt; mit `--save-report` wird nur der Modellaufruf abgeschlossen, während der Gesamtlauf auf die Exportentscheidung wartet. Diese Schritte bilden eine zweite gemeinsame Transaktion. HTTP-Status, API-Rohantwort, Antwortstatus und weitere vom Adapter nicht gelieferte optionale Metadaten bleiben `NULL`; Antwort-Header bleiben schema-gemäß `{}`. Response-ID und Request-ID bleiben getrennt. Die Modelldauer stammt aus dem Adapterergebnis.

Bei `OpenAITextError` schließen eine gemeinsame Transaktion und der feste Fehlercode Modellaufruf sowie Lauf als `failed` ab. Ein bekannter HTTP-Status wird übernommen; ohne bekannten Status bleibt er `NULL`. Es entsteht kein Bericht. Fehlertexte und rohe Serverfehler werden nicht gespeichert. Die Fehlerdauer wird lokal gemessen, da der Adapter kein Ergebnisobjekt zurückgibt. Bei einem Fehler während des abschließenden Speicherns meldet die CLI den Speicherfehler mit Code `1`; sie wiederholt die Modellanfrage nicht. Der Rollback erhält die bereits bestätigten Startdaten als `running`/`started`, ohne einen erfolgreichen oder fehlgeschlagenen Abschluss zu behaupten. Auch ein unerwarteter Abbruch kann solche offenen Startdaten hinterlassen; eine automatische Wiederaufnahme gibt es nicht.

[db/model_calls_query.sql](db/model_calls_query.sql) zeigt erfolgreiche, fehlgeschlagene und noch offene Modellaufrufe. Ein `LEFT JOIN` erhält auch Datensätze ohne Bericht. Offline-Tests ersetzen den Modelladapter durch feste Ergebnisse oder Fehler. Eine zweite SQLite-Verbindung prüft schon innerhalb des simulierten Aufrufs die sichtbaren Startdaten und die freigegebene Schreibsperre. Weitere Assertions prüfen Erfolg, HTTP 429 ohne Bericht, unbekannten HTTP-Status, fehlende Metadaten, abgelehnte Datenbanken und Rollbacks beider Abschlusswege ohne Wiederholungsanfrage. Diese Tests prüfen Speicherung und Ablauf, keine echte API-Integration oder Modellqualität.

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

Mit zusätzlichem `--database` wird der exakte Bericht vor der Freigabe bereits in SQLite archiviert, einschließlich SHA-256 und Bytezahl seiner UTF-8-Darstellung. Beispiel ohne Modellaufruf:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --database data/exports.sqlite3 --save-report
```

Zusätzliches `--model-report` verwendet denselben Ablauf mit einem Modellbericht und benötigt den API-Schlüssel. In beiden Fällen zeigt die Vorschau denselben archivierten Text und den konkret aufgelösten Zielpfad. Während der Eingabe bleibt der Gesamtlauf `running`; es ist keine Schreibtransaktion und keine Datenbankverbindung der Ablaufsteuerung offen.

Die Entscheidung wird in `approvals` für genau Bericht-ID, Inhaltshash und Zielpfad gespeichert. `actor` ist der technische Wert `terminal_user`; Rohtexteingaben werden nicht gespeichert. Nur das normalisierte `ja` ergibt `approved` mit `explicit_yes`. Andere Eingaben, EOF und Strg+C ergeben `declined` mit `not_approved`, `eof` beziehungsweise `interrupted`. Bei Ablehnung wird der Lauf in derselben Transaktion erfolgreich abgeschlossen. Bericht und Entscheidung bleiben in SQLite; es gibt weder Datei noch `exports`-Datensatz.

Bei Zustimmung werden Freigabe und `exports.status = 'started'` gemeinsam gespeichert und bestätigt. Erst nach dem Schließen dieser Transaktion ruft die CLI den bestehenden exklusiven Datei-Export auf. Nach erfolgreichem Schreiben und Schließen werden Export (`succeeded`, `file_state = 'complete'`, erwartete Bytezahl) und Gesamtlauf gemeinsam abgeschlossen. Bei einem Dateifehler bleiben Bericht und Freigabe erhalten; Export und Lauf werden gemeinsam `failed`, mit `file_exists` bei belegtem Ziel oder `file_error` bei anderen Schreib-/Schließfehlern. Ein vorhandenes Ziel wird nicht überschrieben. Da ein Dateifehler den tatsächlichen Dateizustand nicht sicher belegt, bleibt dieser `unknown` und die bestätigte Bytezahl `NULL`.

Dateisystem und SQLite bilden keine gemeinsame Transaktion. Scheitert der Datenbankabschluss nach erfolgreichem Dateischreiben, bleibt die vollständige Datei erhalten. Die CLI endet mit Code `1` und meldet ausdrücklich, dass die Datei bereits geschrieben und geschlossen wurde und nur die Bestätigung in der Datenbank fehlt. Der Rollback erhält den Export als `started` und den Gesamtlauf als `running`. Es gibt keinen automatischen Export-Wiederholungsversuch. Auch ein Abbruch oder ein Protokollfehler zwischen diesen Schritten kann offene Zustände hinterlassen. [db/exports_query.sql](db/exports_query.sql) verbindet archivierten Bericht, Entscheidung und Exportstatus einschließlich noch unbestätigter oder abgelehnter Vorgänge.

Die Offline-Tests verwenden temporäre echte Datenbanken und Dateien. Sie prüfen die sichtbare Archivierung samt Hash/Bytezahl und freier Schreibsperre während der Eingabe, den bestätigten Exportstart vor dem Dateischreiben, Zustimmung/Ablehnung mit und ohne simuliertes Modell, EOF/Abbruch, belegte Ziele, Schreibfehler und den Rollback bei einem späten Datenbankfehler. Die Assertions vergleichen Vorschau, Archiv und exportierte Bytes und verlangen genau einen Schreibversuch. Ein absichtlich veränderter Bericht-Hash muss die Freigabe verhindern. Die Prüfung belegt Ablauf und Speicherung, keine Modellqualität oder Stromausfallsicherheit.

Die Vorschau bestätigt weder Speicherung noch Logabschluss. „Bericht gespeichert“ erscheint erst nach erfolgreichem Schreiben und Schließen der Berichtdatei sowie gegebenenfalls erfolgreichem Logabschluss. Scheitert nach dem Schreibabschluss die Protokollierung, meldet die CLI mit Code `1`, dass die Berichtdatei bereits vollständig geschrieben und geschlossen wurde. Sie wird nicht zurückgerollt. Bei Schreib- oder Schließfehlern der Berichtdatei ist der Schreibabschluss unbestätigt; eine unvollständige Datei kann verbleiben. Exklusive Erstellung ist keine Garantie gegen Datenverlust bei einem Systemabsturz.

Mit `--log-dir logs` wird optional eine neue UTF-8-Datei `logs/<run_id>.jsonl` exklusiv angelegt; das Verzeichnis wird bei Bedarf erstellt. Beispiel:

```bash
.venv/bin/python cosi.py examples/temperature_sample.csv --threshold 60 --log-dir logs
```

Jede JSON-Zeile enthält ausschließlich technische Metadaten zu Lauf und Schritten (`csv_import`, `temperature_analysis` und bei angefordertem Bericht `model_report`): Schema-Version, Lauf-ID, UTC-Zeitpunkt, Ereignis, Schritt, Status, Abschlussdauer und gegebenenfalls Exception-Klassenname. Laufzeiten werden mit `time.perf_counter` unabhängig von der Systemuhr gemessen. Messwerte, Dateipfade, Prompts, Modellantworten und Fehlertexte werden nicht protokolliert. Modellfehler werden mit ihrem ursprünglichen Exception-Klassennamen als fehlgeschlagener Schritt und Lauf erfasst; das Ereignisschema bleibt unverändert. Protokollierungsfehler führen zu Rückgabecode `1` ohne abschließende Erfolgsmeldung; ohne Speicheroption erfolgt auch die Berichtsausgabe erst nach vollständiger Protokollierung und Schließen der Datei. Bei `--save-report` wurde gegebenenfalls bereits die ausdrücklich gekennzeichnete Vorschau angezeigt. Bei Schreibfehlern kann eine unvollständige Protokolldatei zurückbleiben. Ohne Option sowie bei Hilfe oder ungültigen Argumenten entstehen keine Protokolle. `/logs/` wird von Git ignoriert.

Mit `--save-report` erfassen die zusätzlichen Ereignisse `save_approved` beziehungsweise `save_declined` die Freigabeentscheidung (`step: report_save`, `status: success`, Dauer und Fehlertyp `null`). Eine Ablehnung ist kein Verarbeitungsfehler. Nur nach Freigabe folgt der Schritt `report_save` mit den bestehenden Start-/Abschlussereignissen. Eingabetext, Bericht und Zielpfad stehen nicht im Log; die gemeinsamen Felder bleiben unverändert.

Die Laufdauer umfasst die Verarbeitung und Teile der Protokollierung: Sie beginnt nach der Logdateierstellung vor `run_started` und endet vor dem Schreiben von `run_finished`. Python-Start, Argumentprüfung, Logdateierstellung, abschließendes Schließen der Logdatei und die abschließende Terminalausgabe sind nicht enthalten. Bei `--save-report` umfasst `run_finished.duration_ms` zusätzlich Vorschau, Wartezeit auf die Freigabe und gegebenenfalls Speicherung einschließlich Schließen der Berichtdatei. Diese Laufzeit ist keine reine Verarbeitungszeit.

`run_finished` mit `status: success` beschreibt erfolgreiche Verarbeitung vor dem Schließen der Protokolldatei. Ein anschließender Schließfehler führt dennoch zu CLI-Rückgabecode `1`. Versuchsreihen müssen deshalb zusätzlich den Prozess-Rückgabecode erfassen.

Das separate Skript `cosi_runs.py` zeigt eine schreibgeschützte Übersicht der neuesten gespeicherten Läufe, einen pro Zeile:

```bash
.venv/bin/python cosi_runs.py --database data/exports.sqlite3 --limit 20
```

Jede Zeile enthält Lauf-ID, UTC-Startzeit, Aufgabentyp und Laufstatus. Wenn vorhanden, folgen Modellstatus, zurückgemeldetes Modell, Fehlercodes, HTTP-Status, Freigabe- und Exportstatus. Fehlercodes sind nach Lauf, Modellaufruf und Export gekennzeichnet. Modellaufruf und Entscheidung werden jeweils nach dem neuesten Start- beziehungsweise Entscheidungszeitpunkt ausgewählt. Bei gleichem Zeitpunkt entscheiden Aufrufnummer und IDs stabil; die neuesten Läufe werden nach Startzeit und danach Lauf-ID absteigend sortiert. Der Export gehört immer zur angezeigten Entscheidung, auch wenn eine ältere Freigabe bereits einen Export hatte. `running` und `started` werden ausdrücklich mit „kein Abschluss gespeichert“ gekennzeichnet. Prompt, Modellantwort und Berichtstext werden weder für die Übersicht abgefragt noch angezeigt; Steuerzeichen in Metadaten werden maskiert, damit ein Lauf genau eine Ausgabezeile behält.

Die Datenbank wird mit SQLite-URI `mode=ro` geöffnet und mit der bestehenden Cosi-Schemaprüfung validiert. Eine Lesetransaktion hält Prüfung und Abfrage im selben Datenstand; vor der Ausgabe ist die Verbindung wieder geschlossen. Fehlende Pfade werden nicht angelegt, fremde oder unbekannte Schemata werden abgelehnt. `--database` ist erforderlich; `--limit` ist optional, standardmäßig `20`, und muss eine positive Ganzzahl im SQLite-Zahlenbereich sein. Eine gültige leere Datenbank liefert keine Ausgabezeilen. Rückgabecodes: `0` für erfolgreiche Übersicht oder Hilfe, `1` für Lese-/Kompatibilitätsfehler, `2` für ungültige Argumente. Es gibt keinen Modellaufruf oder Export. Offline-Tests prüfen Darstellung, Sortierung und Limit mit echten temporären Datenbanken, mehrere Einträge ohne vervielfachte Laufzeilen, die Zuordnung zum neuesten Freigabeentscheid sowie den tatsächlich durchgesetzten Schreibschutz.

## Textschnittstelle für Temperaturberichte

`temperature_report.generate_temperature_report(analysis_result, threshold, text_generator)` erstellt aus den sieben vorhandenen Kennzahlen und dem zugehörigen Schwellenwert einen Auftrag für einen kurzen deutschen Bericht. Rohdaten, Dateipfade und zusätzliche Wörterbucheinträge werden nicht übergeben; die Kennzahlen werden nicht neu berechnet. Der Auftrag verlangt, fehlende Werte und Werte strikt oberhalb des Schwellenwerts korrekt zu beschreiben und keine Ursachen zu erfinden.

Aufgrund der [ersten Qualitätsprüfung](docs/versuche/2026-11-02-modellberichte-erste-pruefung.md) wurde der Berichtsauftrag präzisiert: alle sieben Kennzahlen und den Schwellenwert wiedergeben und keine zusätzlichen Aussagen über einzelne Temperaturen, deren Häufigkeit oder das Vorkommen von Werten genau am Schwellenwert ableiten. Der [erste A/B-Vergleich](docs/versuche/2026-11-02-promptvergleich-ab.md) ist laut Betreiber-Rückmeldung ausgeführt, wegen neun Adapterfehlern jedoch nur eingeschränkt auswertbar; ein belastbarer Qualitätsvorteil bleibt offen.

Der übergebene Textgenerator ist eine Funktion, die einen Auftragstext erhält und eine Textantwort liefert. Sie wird genau einmal aufgerufen. Nicht-textuelle oder leere Antworten (auch reiner Leerraum) führen zu `ValueError`; Generatorausnahmen werden unverändert weitergereicht. Die Schnittstelle ist mit festen Testantworten offline geprüft; diese Tests bewerten keine Modellqualität oder Faktentreue. Die Antwort wird inhaltlich nicht geprüft. Die CLI verbindet diese Schnittstelle ausschließlich bei `--model-report` mit dem OpenAI-Adapter. Die berechneten Kennzahlen bleiben die verlässliche Grundlage; der Modellbericht ist nicht automatisch auf Faktentreue geprüft.

## OpenAI-Textadapter

`openai_text.generate_text_result(prompt, model="gpt-4.1-mini")` liefert ein typisiertes `OpenAITextResult` (Dataclass) mit `text`, `requested_model`, `returned_model`, `response_id`, `request_id`, `input_tokens`, `output_tokens`, `total_tokens` und `duration_ms`. Die Response-ID stammt aus dem JSON-Feld `id`, die getrennte Request-ID ausschließlich aus dem HTTP-Header `x-request-id`. Fehlende oder ungültige optionale Metadaten bleiben einzeln `None`, ohne gültigen Antworttext zu verwerfen. Modellname und IDs müssen nichtleere Strings sein; Tokenzahlen müssen nichtnegative Ganzzahlen ohne boolesche Werte sein. Fehlende Tokenzahlen werden nicht berechnet. Die lokal mit `time.perf_counter()` gemessene Dauer in Millisekunden umfasst HTTP-Verbindungsaufbau, Anfrage, Lesen und Schließen der Ressourcen; Eingabeprüfung und JSON-/Textauswertung sind nicht enthalten. Sie ist keine serverseitige Modellrechenzeit. `generate_text(...) -> str` behält seine Signatur als Wrapper bei und gibt nur `.text` zurück. Beide Wege verwenden denselben Anfragepfad und dieselbe Fehlerdiagnose.

`openai_text.generate_text(prompt, model="gpt-4.1-mini")` liefert Text über die Responses API; `model` ist ein optionales Schlüsselwortargument. Der Adapter verwendet nur die Standardbibliothek und liest `OPENAI_API_KEY` ausschließlich beim Funktionsaufruf. Ohne Schlüssel erfolgt kein HTTP-Aufruf. Ein Aufruf sendet genau einen POST an `https://api.openai.com/v1/responses`, mit normaler TLS-Zertifikatsprüfung, `max_output_tokens=600` und `store=false`. Es gibt keine automatischen Wiederholungen oder Weiterleitungen. Der Netzwerk-Timeout von 30 Sekunden begrenzt blockierende Socket-Operationen, garantiert aber keine Gesamtlaufzeit, etwa einschließlich DNS-Auflösung und mehrerer Netzwerkoperationen.

Nur abgeschlossene Antworten mit nichtleerem Text gelten als Erfolg. Textteile aus den `output/content`-Einträgen werden in ihrer Reihenfolge zusammengesetzt. HTTP-, Verbindungs-, JSON- und unvollständige Antwortfehler werden als `OpenAITextError` ohne Schlüssel, Anfrage-Header oder vollständige Serverfehlertexte gemeldet. Grundlage sind die offizielle [Textanleitung](https://developers.openai.com/api/docs/guides/text) und [API-Übersicht](https://developers.openai.com/api/reference/overview).

`OpenAITextError` ergänzt die unveränderte Meldung um `error_code` und `http_status`. Alte Aufrufe wie `OpenAITextError("Meldung")` liefern `unknown` und `None`. Die Codes sind vom Programm festgelegt:

| Code | Bedeutung |
|---|---|
| `invalid_input` | Ungültiger Auftrag oder Modellname |
| `configuration_error` | Fehlender oder ungültiger API-Schlüssel |
| `http_error` | Empfangener HTTP-Status außerhalb von 200–299 |
| `timeout` | Netzwerk-Timeout |
| `connection_error` | Sonstiger Verbindungs-, TLS- oder HTTP-Protokollfehler |
| `invalid_json` | Ungültiges UTF-8 oder JSON |
| `invalid_response` | Ungültige Antwortstruktur oder gemeldeter Antwortfehler |
| `incomplete_response` | Antwort oder Nachricht nicht abgeschlossen beziehungsweise unvollständig |
| `empty_response` | Kein nichtleerer Ausgabetext |
| `refusal` | Ausdrückliche Modellablehnung |
| `unknown` | Keine festgelegte Zuordnung; auch Rückfallwert für unbekannte Codewerte |

`http_status` enthält ausschließlich einen tatsächlich empfangenen numerischen HTTP-Status; ohne verfügbaren Status bleibt er `None`. Auch ein JSON-Fehler oder ein Timeout beim Lesen kann daher beispielsweise den empfangenen Status `200` tragen. Der Status allein belegt keinen erfolgreichen Textabruf.

Die Adaptertests ersetzen ausschließlich die HTTP-Grenze durch Testobjekte und prüfen Anfrage, Antwortauswertung und Fehlerbehandlung offline. Die CLI-Integration wird mit einem festen Testgenerator geprüft. Zusätzlich liegen Betreiber-Rückmeldungen zu einem erfolgreichen manuellen Modellaufruf mit `gpt-4.1-mini` und einem erfolgreichen CLI-Live-Test mit Modellbericht und Protokollierung auf Ubuntu vor. Die Beispielkennzahlen waren korrekt; der CLI-Prozess endete mit Code `0`, alle Verarbeitungsschritte waren erfolgreich. Das ist ein erfolgreicher Einzelfall, kein allgemeiner Modellqualitäts- oder Zuverlässigkeitsnachweis. Lauf-ID und gemessene Modellschrittdauer einschließlich API-Kommunikation stehen im [Journal](docs/journal/2026-11-02.md).

## Vergleichslauf der Berichtsaufträge

`compare_report_prompts.py` setzt den [festgelegten Prüfplan](docs/versuche/modellberichte-pruefplan.md) um: vier Fälle, drei Wiederholungen pro Variante, insgesamt höchstens 24 Anfragen in wechselnder Reihenfolge A/B und B/A. Standardmäßig werden ausschließlich die Aufträge und der Ablauf vorbereitet, auch bei gesetztem `OPENAI_API_KEY`:

```bash
.venv/bin/python compare_report_prompts.py --output-dir ../cosi-promptvergleich-vorbereitung
```

Der Zielordner muss neu sein und außerhalb des Repositorys liegen. Für eine ausdrücklich angeforderte Live-Reihe ist ein anderer neuer Ordner und `--live` erforderlich:

```bash
.venv/bin/python compare_report_prompts.py --output-dir ../cosi-promptvergleich-live --live
```

Nur `--live` aktiviert den bestehenden Adapter mit `gpt-4.1-mini`, dessen unveränderten Parametern und Schlüsselzugang über `OPENAI_API_KEY`. Erwartete Adapterfehler werden technisch erfasst; die übrigen Versuche laufen ohne Ersatzaufrufe weiter. Speicherfehler stoppen den Lauf mit Code `1`, Strg+C mit `130`. Code `0` bedeutet erfolgreiche Vorbereitung beziehungsweise Live-Abschluss ohne Adapterfehler; inhaltliche Richtigkeit wird nicht automatisch bewertet.

Der Lauf liest die A-/B-Fassungen von `temperature_report.py` mit `git show` aus den im Prüfplan benannten Commits. `ModuleType` stellt je Variante einen getrennten Namensraum bereit; `compile` und `exec` laden darin ausschließlich den festgelegten historischen Projektcode. Es erfolgen keine Checkouts und keine Änderungen an Produktionsmodulen. Referenzmanifeste und CSV-Dateien werden ebenfalls mit `git show` aus Commit `a67dc34d12d221b3d1a61b3dd97c748e2f7a6219` gelesen und über temporäre Dateien mit Importer und Analyse gegen alle Sollwerte geprüft, bevor Anfragen beginnen.

Ein aufzeichnender Testgenerator erhält den Auftrag von der jeweiligen historischen Berichtsfunktion und hält ihn unverändert fest. Seine interne Platzhalterantwort wird verworfen und niemals als Modellergebnis gespeichert. Beide Varianten bekommen dieselben berechneten Fakten und denselben Schwellenwert.

Im Versuchsordner enthält `plan.jsonl` 24 UTF-8-JSONL-Datensätze mit Varianten-Commits, Referenzdaten-Commit, Modell, Modus, Reihenfolge, Fall, Variante, Wiederholung und tatsächlichem Auftrag. Alle Planeinträge sind ausdrücklich `not_executed`; sie zeigen nur den vorbereiteten Ablauf. Im Live-Modus kommt `results.jsonl` hinzu: je Versuch ein `attempt_started` vor dem Aufruf und ein `attempt_finished` mit technischem Status und gegebenenfalls unveränderter Antwort danach. Jede Zeile wird sofort geschrieben und mit `flush` geleert. Schlüssel, Umgebungsvariablen, Anfrage-Header, Exception-Meldungen und Serverfehlertexte werden nicht gespeichert; die Fehlerdiagnose besteht aus Fehlertyp und den festgelegten Diagnosefeldern.

Neu erzeugte Vergleichsprotokolle verwenden `schema_version: 2` und ergänzen `error_code` sowie `http_status`. Bei Vorbereitung, Beginn und Erfolg sind beide Felder `null`; bei Adapterfehlern werden sie aus `OpenAITextError` übernommen. Vorhandene Protokolle werden nicht verändert. Die Ursachen der neun früheren Ausfälle bleiben ausdrücklich unbekannt: Die neuen Diagnosefelder liefern keinen nachträglichen Ursachennachweis.

Bereits geschriebene Nachweise bleiben bei Abbruch erhalten; ein Start ohne Abschluss belegt kein erfolgreich empfangenes Ergebnis. Beschädigte oder unvollständige letzte Zeilen sind bei einem Schreibfehler möglich; `flush` garantiert keine Haltbarkeit bei Systemausfall. Vorhandene Versuchsordner werden nicht wiederverwendet. Die automatisierten Tests ersetzen historische Quellen und Modellgenerator durch Fakes. Der Betreiber hat den Live-Vergleich ausgeführt; die anschließende manuelle Durchsicht ergab bei 15 gespeicherten Antworten korrekte und vollständige Kennzahlen sowie eine falsche Zusatzbehauptung. Neun Adapterfehler schränken die Auswertung ein; Details stehen in der [Ergebnisnotiz](docs/versuche/2026-11-02-promptvergleich-ab.md).

## Offline-Demolauf mit SQLite

Der separate Demolauf verwendet die Beispiel-CSV, den bestehenden Import, die Temperaturauswertung mit Schwellenwert `60.0` und die bestehende Berichtsfunktion. Er benötigt weder API-Schlüssel noch Netzwerk. Der simulierte Generator erfasst den tatsächlich erzeugten Prompt und liefert ein festes `OpenAITextResult`; ein Text-Wrapper verbindet ihn mit der unveränderten Berichtsschnittstelle. Der separate Einstieg `sqlite_demo.py` besteht weiterhin neben der CLI-Speicheroption `--database`.

Ein Datenbankpfad muss ausdrücklich angegeben werden und darf noch nicht existieren. Beispiel aus dem Projektverzeichnis:

```bash
env -u OPENAI_API_KEY .venv/bin/python sqlite_demo.py --database data/demo.sqlite3
```

`sqlite_storage.py` legt die Datenbank exklusiv an und führt `db/schema.sql` unverändert aus. Verwendet wird nur `sqlite3` aus der Standardbibliothek; das Schema benötigt SQLite ab 3.38 mit JSON-Unterstützung. `open_database(path)` öffnet ausschließlich bestehende Datenbanken und aktiviert Fremdschlüssel sowie rekursive Trigger auf jeder Verbindung. `run_record.CompletedRun` transportiert die fertigen Laufdaten ohne SQL oder Verbindungen zwischen Ablaufsteuerung und Speicherbaustein.

Ein erfolgreicher Lauf schreibt gemeinsam in einer Transaktion einen Datensatz in `runs`, drei in `artifacts` und einen in `model_calls`. Die Verknüpfung lautet CSV → Analyse → Modellaufruf; der Bericht verweist auf Analyse und Modellaufruf. Schema-gemäß wird die CSV als absoluter Dateiverweis mit SHA-256 und Bytezahl gespeichert, nicht als eingebetteter Dateiinhalt. Analyse und Bericht stehen vollständig in der Datenbank. Prompt und Antwort bleiben unverändert erhalten. Lauf und Anfrage tragen `simulation: true`; Provider, Modellnamen, Response-ID und Request-ID sind als Simulation gekennzeichnet. Tokenzahlen und Modelldauer sind feste synthetische Werte, keine Messungen oder Abrechnungsdaten. HTTP-Status, API-Rohantwort und serverseitige Metadaten bleiben `NULL`, Antwort-Header `{}`. Nicht erhobene Git-Provenienzfelder bleiben ebenfalls `NULL`. Die lokal gemessene Laufdauer umfasst die Verarbeitung vor der Speicherung, nicht den Datenbankschreibvorgang.

Nach Schließen und erneutem Öffnen verbindet [db/demo_query.sql](db/demo_query.sql) die vier Bereiche. Die Abfrage lässt sich ohne zusätzliches SQLite-Kommandozeilenprogramm ausführen:

```bash
.venv/bin/python - <<'PY'
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from sqlite_storage import open_database

with closing(open_database("data/demo.sqlite3")) as connection:
    connection.row_factory = sqlite3.Row
    query = Path("db/demo_query.sql").read_text(encoding="utf-8")
    rows = [dict(row) for row in connection.execute(query)]
print(json.dumps(rows, ensure_ascii=False, indent=2))
PY
```

Die Demo exportiert keine Berichtsdatei; `approvals` und `exports` bleiben leer. `/data/` wird von Git ignoriert. Bei Fehlern während der Speicherung werden sämtliche Laufdaten zurückgerollt; die zuvor angelegte Datenbank kann leer beziehungsweise mit Schema bestehen bleiben. Sie wird nicht automatisch gelöscht oder bei erneutem Aufruf überschrieben. Vor einer Wiederholung muss deshalb ein anderer neuer Pfad gewählt werden. Die Tests verwenden echte temporäre SQLite-Dateien und blockieren API-/Netzwerkzugriffe. Sie prüfen Persistenz nach erneutem Öffnen, Inhalte und Verknüpfungen, Metadaten, Hashes, Fremdschlüssel, rekursive Trigger, Überschreibschutz und Transaktions-Rollback; sie bewerten keine Modellqualität.

## Dokumentation und Fortschritt

- [Aktueller Aufbau als Diagramme](docs/aufbau.md)
- [Runbook: täglicher Fernzugriff und Einrichtung](docs/runbooks/fernzugriff.md)
- [Journal: 31. Oktober 2026](docs/journal/2026-10-31.md)
- [Journal: 2. November 2026](docs/journal/2026-11-02.md)
- [Journal: 7. November 2026](docs/journal/2026-11-07.md)
- [Versuch: CLI-Basismessung mit und ohne Protokollierung](docs/versuche/2026-11-02-cli-baseline.md)
- [Prüfplan für Modellberichte](docs/versuche/modellberichte-pruefplan.md): vier ursprüngliche CSV-Referenzfälle und zwei Kontrollfälle mit festen Sollwerten; der Promptvergleich mit 24 Versuchen ist ausgeführt und eingeschränkt auswertbar (siehe Ergebnisnotiz). Die Offline-Prüfung bewertet keine Modellqualität.
- [Erste echte Qualitätsprüfung der Modellberichte](docs/versuche/2026-11-02-modellberichte-erste-pruefung.md): Betreiber-Rückmeldung zu vier Einzelantworten; korrekte Kennzahlen in allen Fällen, eine falsche Zusatzbehauptung.
- [Ergebnis: Promptvergleich A/B](docs/versuche/2026-11-02-promptvergleich-ab.md): Betreiber-Rückmeldung, 15 Antworten und neun Adapterfehler; Qualitätsvorteil von B offen.

Das Journal hält abgeschlossene Schritte und Beobachtungen kurz fest. Wesentliche Entscheidungen werden mit ihrer Begründung dokumentiert. Testergebnisse werden als geprüft, auffällig oder noch offen gekennzeichnet; geplante Funktionen werden nicht als bereits umgesetzt dargestellt.

## Öffentliche und private Unterlagen

Dieses Repository enthält ausgewählte, bereinigte Projektunterlagen. Echte Verbindungsadressen, Routermodell und Firmware, Zugangsdaten, Schlüssel, Seriennummern, reale VPN-Konfigurationen und unbereinigte Diagnoseberichte bleiben außerhalb dieses Repositorys. Die `.gitignore` unterstützt diese Trennung; vor jedem Commit werden die tatsächlich vorgemerkten Änderungen geprüft.
