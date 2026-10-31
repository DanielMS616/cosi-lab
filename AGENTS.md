# AGENTS.md – Cosi-Lab

## Projekt und Umfang

Cosi ist ein Python-Versuchssystem für kontrollierte KI-Aufträge auf begrenzter Hardware. Wir entwickeln die Ablaufsteuerung selbst, um sie zu verstehen und Qualitäts- sowie Leistungsgrenzen zu messen. Zunächst entstehen ein fester Ablauf und eine Terminalbedienung; danach eine begrenzte Agentenschleife. Python berechnet verlässliche Kennzahlen, das Modell erklärt geprüfte Ergebnisse.

Bestehende Rechenleistung weiterverwenden, nachgewiesene Betriebsprobleme zuerst beheben und Erweiterungen anhand gemessenen Bedarfs entscheiden. Kursbeispiele und ältere Projekte sind keine verbindlichen Architekturvorgaben.

## Zusammenarbeit

- Lies zuerst `README.md`, den Git-Arbeitsstand und die für den Auftrag relevanten Dateien. Behaupte keinen Zugriff auf andere Rechner oder frühere Chats. Nutze ergänzende Lernunterlagen gezielt, sofern verfügbar.
- Setze den aktuellen Auftrag als kleines, vollständiges Arbeitspaket um. Erkläre vorher kurz Ziel, betroffene Bereiche und Prüfung. Innerhalb dieses Umfangs arbeite eigenständig; kläre grundlegende Architektur- oder Umfangsänderungen mit Daniel.
- Daniel muss den Code später erklären können. Besprich neue Konzepte am konkreten Beispiel und fasse zum Abschluss Änderung, Begründung, ausgeführte Prüfungen und verbleibende Grenzen zusammen.
- Kommuniziere auf Deutsch. Verwende englische Bezeichner, Kommentare und Docstrings; Python-Namen in `snake_case`, Klassen in `PascalCase`.

## Verständlicher Code und Lernkommentare

- Bevorzuge benannte Zwischenschritte, expliziten Kontrollfluss und überschaubare Funktionen. Trenne Bedienung, Fachlogik, Modellanbindung und Speicherung nach Verantwortung. Verwende Klassen, wenn sie Zustand oder Verantwortung sinnvoll bündeln.
- Kommentiere im Zweifel ausführlicher. Erkläre Zweck, Verarbeitungsschritte, wichtige Ein- und Ausgaben, Annahmen und Fehlerfälle. Kommentare dürfen auch beschreiben, was ein Schritt macht. Entferne hilfreiche Lernkommentare nicht allein zur Verkürzung; halte sie bei Änderungen aktuell.
- Gib Funktionen und Klassen hilfreiche Docstrings. Neue Sprachmittel und ungewöhnliche Entscheidungen benötigen eine kurze Erklärung.
- Führe Typannotationen schrittweise und konsistent ein. Grundverständnis ist vorhanden; komplexere Notation wird gemeinsam erarbeitet. Typannotationen ersetzen keine Laufzeitvalidierung.

## Architektur und Ressourcen

- Baue zuerst den kleinsten nachvollziehbaren Ablauf. Halte externe Modellzugänge durch kleine Schnittstellen austauschbar. Begründe zusätzliche Abhängigkeiten anhand eines konkreten Nutzens; vermeide vorsorgliche Dienste und Abstraktionen.
- Ein Agentenframework, Docker und eine externe Observability-Plattform sind keine Voraussetzungen. Setze Mehragentenbetrieb erst um, wenn Messungen einen Nutzen zeigen.
- Validiere Eingaben, trenne Lesen und Schreiben und erzwinge nötige Freigaben im Programm. Begrenze Modell- und Werkzeugaufrufe. Modelltext und Prompts ersetzen keine durchgesetzten Berechtigungen oder Abbruchregeln.
- Cosi führt nur registrierte Werkzeuge mit validierten Argumenten aus, keinen frei vom Modell generierten Shell- oder Python-Code.

## Tests und Nachweise

- Tests wurden bereits eingesetzt, sind aber weiterhin erklärungsbedürftig. Erläutere bei neuen Testarten Prüfabsicht, Eingabe, Erwartung, Assertion und Aussagegrenze.
- Prüfe neues oder geändertes Verhalten mit angemessenen Normal-, Grenz- und Fehlerfällen. Teste beobachtbares Verhalten statt Implementierungsdetails. Reine Kommentar- oder Formatänderungen brauchen keine neuen Verhaltenstests.
- Halte automatisierte Tests standardmäßig offline. Verwende Fakes oder Mocks an externen Grenzen und erkläre deren Einschränkungen. Trenne Komponentenprüfung, echte Integration und Modellqualität.
- Ermittle vorhandene Prüfkommandos aus dem Repository und nutze die Projektumgebung. Erfinde keine Testbefehle, installierten Werkzeuge oder Ergebnisse. Berichte ausgeführte Befehle und Resultate; kennzeichne nicht ausgeführte Prüfungen.

## Dokumentation und Git

- Dokumentiere kurz während der Arbeit und ausführlicher an wichtigen Meilensteinen. Halte Routinen am Sitzungsende normalerweise in fünf bis zehn Minuten fest; kleine Änderungen lösen kein großes Dokumentationspaket aus.
- Nutze Journale für Fortschritt und Beobachtungen, ADRs für wesentliche Entscheidungen mit Begründung und Runbooks für wiederkehrende Handgriffe. Pflege bestehende Quellen gezielt und vermeide doppelte Statusangaben.
- Halte beobachtete Ergebnisse, Annahmen und offene Fragen auseinander. Ändere oder erfinde keine historischen Nachweise.
- Bewahre vorhandene Änderungen. Führe Commits, Pushes und Deployments nur im beauftragten Umfang aus. Ins öffentliche Repository gehören keine Zugangsdaten, privaten Schlüssel, privaten Netzkonfigurationen oder personenbezogenen Rohdaten; Beispiele verwenden Platzhalter.
