# Cosi-Lab

Python-Versuchssystem für kontrollierte KI-Aufträge auf begrenzter Hardware mit öffentlicher Projektdokumentation.

**Aktueller Stand · 31. Oktober 2026:** Ubuntu und ein schlüsselbasierter Fernzugriff über WireGuard sind eingerichtet und in mehreren Schritten geprüft. Eine lokale Python-Entwicklungsumgebung und ein deterministischer Rechenbaustein zur Temperaturauswertung mit Offline-Tests sind vorhanden. CSV-Verarbeitung und Agentensoftware folgen. Dieses Repository macht den Fortschritt, die Entscheidungen und die Grenzen des Aufbaus nachvollziehbar.

## Leitfrage

> Wie lässt sich ein nachvollziehbares und kontrolliertes KI-System mit eigener Ablaufsteuerung auf begrenzter Hardware aufbauen, und wo liegen seine gemessenen Qualitäts- und Leistungsgrenzen?

## Leitgedanke

> Bestehende Rechenleistung weiterverwenden, nachgewiesene Betriebsprobleme zuerst beheben und Erweiterungen anhand gemessenen Bedarfs entscheiden. Begrenzte Ressourcen werden bewusst genutzt, um das Systemverhalten zu verstehen und Leistungsgrenzen nachvollziehbar zu bestimmen.

## Geplantes erstes Softwareziel

Eine synthetische Temperaturmessreihe wird als CSV eingelesen und mit Python deterministisch ausgewertet. Ein Sprachmodell formuliert auf Grundlage geprüfter Kennzahlen einen Bericht. Eine Datei wird erst nach menschlicher Freigabe abgelegt. Ablaufsteuerung, Modellanbindung, Werkzeugaufrufe und strukturierte Ereignisprotokolle werden im eigenen Python-Kern nachvollziehbar umgesetzt.

Zunächst entsteht ein fester Ablauf mit Terminal-Bedienung. Darauf aufbauend soll eine begrenzte Agentenschleife mit demselben Werkzeugumfang verglichen werden. API-Modelle und ein kleines lokales Modell dienen dazu, Qualität, Ressourcenbedarf und Leistungsgrenzen zu untersuchen. Die deterministische Auswertung einer Messwertliste ist bereits implementiert; CSV-Verarbeitung, Terminal-Bedienung, Modellanbindung, freigegebene Speicherung und Agentenschleife bleiben Entwicklungsziele.

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

## Dokumentation und Fortschritt

- [Aktueller Aufbau als Diagramme](docs/aufbau.md)
- [Runbook: täglicher Fernzugriff und Einrichtung](docs/runbooks/fernzugriff.md)
- [Journal: 31. Oktober 2026](docs/journal/2026-10-31.md)

Das Journal hält abgeschlossene Schritte und Beobachtungen kurz fest. Wesentliche Entscheidungen werden mit ihrer Begründung dokumentiert. Testergebnisse werden als geprüft, auffällig oder noch offen gekennzeichnet; geplante Funktionen werden nicht als bereits umgesetzt dargestellt.

## Öffentliche und private Unterlagen

Dieses Repository enthält ausgewählte, bereinigte Projektunterlagen. Echte Verbindungsadressen, Routermodell und Firmware, Zugangsdaten, Schlüssel, Seriennummern, reale VPN-Konfigurationen und unbereinigte Diagnoseberichte bleiben außerhalb dieses Repositorys. Die `.gitignore` unterstützt diese Trennung; vor jedem Commit werden die tatsächlich vorgemerkten Änderungen geprüft.
