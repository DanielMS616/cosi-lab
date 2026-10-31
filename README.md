# Cosi-Lab

Öffentliche Projektdokumentation zum Aufbau eines lokal betriebenen Python-Versuchssystems für kontrollierte KI-Aufträge auf begrenzter Hardware.

**Aktueller Stand · 31. Oktober 2026:** Ubuntu und ein schlüsselbasierter Fernzugriff über WireGuard sind eingerichtet und in mehreren Schritten geprüft. Die eigentliche Agentensoftware ist noch nicht implementiert. Dieses Repository macht den Fortschritt, die Entscheidungen und die Grenzen des Aufbaus nachvollziehbar.

## Leitfrage

> Wie lässt sich ein nachvollziehbares und kontrolliertes KI-System mit eigener Ablaufsteuerung auf begrenzter Hardware aufbauen, und wo liegen seine gemessenen Qualitäts- und Leistungsgrenzen?

## Leitgedanke

> Bestehende Rechenleistung weiterverwenden, nachgewiesene Betriebsprobleme zuerst beheben und Erweiterungen anhand gemessenen Bedarfs entscheiden. Begrenzte Ressourcen werden bewusst genutzt, um das Systemverhalten zu verstehen und Leistungsgrenzen nachvollziehbar zu bestimmen.

## Geplantes erstes Softwareziel

Eine synthetische Temperaturmessreihe wird als CSV eingelesen und mit Python deterministisch ausgewertet. Ein Sprachmodell formuliert auf Grundlage geprüfter Kennzahlen einen Bericht. Eine Datei wird erst nach menschlicher Freigabe abgelegt. Ablaufsteuerung, Modellanbindung, Werkzeugaufrufe und strukturierte Ereignisprotokolle werden im eigenen Python-Kern nachvollziehbar umgesetzt.

Zunächst entsteht ein fester Ablauf mit Terminal-Bedienung. Darauf aufbauend soll eine begrenzte Agentenschleife mit demselben Werkzeugumfang verglichen werden. API-Modelle und ein kleines lokales Modell dienen dazu, Qualität, Ressourcenbedarf und Leistungsgrenzen zu untersuchen. Die genannten Funktionen sind Entwicklungsziele und noch keine verfügbaren Funktionen dieses Repositorys.

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
- Lern-/Codeprofil und Arbeitsregeln für die Entwicklung festhalten; anschließend den ersten kleinen Softwareablauf implementieren.

## Dokumentation und Fortschritt

- [Aktueller Aufbau als Diagramme](docs/aufbau.md)
- [Runbook: täglicher Fernzugriff und Einrichtung](docs/runbooks/fernzugriff.md)
- [Journal: 31. Oktober 2026](docs/journal/2026-10-31.md)

Das Journal hält abgeschlossene Schritte und Beobachtungen kurz fest. Wesentliche Entscheidungen werden mit ihrer Begründung dokumentiert. Testergebnisse werden als geprüft, auffällig oder noch offen gekennzeichnet; geplante Funktionen werden nicht als bereits umgesetzt dargestellt.

## Öffentliche und private Unterlagen

Dieses Repository enthält ausgewählte, bereinigte Projektunterlagen. Echte Verbindungsadressen, Routermodell und Firmware, Zugangsdaten, Schlüssel, Seriennummern, reale VPN-Konfigurationen und unbereinigte Diagnoseberichte bleiben außerhalb dieses Repositorys. Die `.gitignore` unterstützt diese Trennung; vor jedem Commit werden die tatsächlich vorgemerkten Änderungen geprüft.
