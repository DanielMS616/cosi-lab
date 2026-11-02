# Prüfplan: Qualität der Temperaturberichte

Diese kleine Prüfreihe bereitet die spätere manuelle Bewertung echter deutscher Modellberichte vor. Die vier CSV-Dateien und ihre unabhängig festgelegten Sollwerte stehen in [examples/report_eval/cases.json](../../examples/report_eval/cases.json). Die CSV-Pfade im Manifest beziehen sich auf dessen Verzeichnis. Die Sollwerte wurden ausdrücklich hinterlegt und nicht mit dem zu prüfenden Analysemodul erzeugt.

## Fälle

| Fall | Zweck und Besonderheit |
|---|---|
| `threshold_equal` | Ohne fehlende Werte; Maximum 60 °C genau am Schwellenwert 60 °C. Keine Überschreitung, Mittelwert 50 °C. |
| `mostly_missing` | Fünf von acht Temperaturen fehlen. Nur drei gültige Werte ergeben den Mittelwert 55 °C; nur 65 °C überschreitet 60 °C. |
| `single_valid` | Nur ein gültiger Wert von drei: Minimum, Maximum und Mittelwert sind jeweils 42 °C. Keine Überschreitung bei 60 °C. |
| `negative_temperatures` | Negative Temperaturen und Schwellenwert −5 °C: Nur 0 °C liegt strikt darüber; −5 °C selbst zählt nicht. Ein Wert fehlt, Mittelwert −7,5 °C. |

## Kriterien für spätere echte Antworten

- **Faktenrichtigkeit:** Jede genannte Kennzahl und der verwendete Schwellenwert müssen den Sollwerten entsprechen. Temperaturen und Mittelwert beziehen sich auf die gültigen Messwerte; die Einheit ist °C.
- **Vollständigkeit:** Prüfen, ob alle sieben Kennzahlen und der Schwellenwert verständlich wiedergegeben sind. Fehlende Angaben getrennt von falschen Angaben bewerten: Ein nicht genannter Mittelwert ist eine Auslassung, ein abweichender Mittelwert ein Faktenfehler.
- **Fehlende Werte:** Fehlende Temperaturen ausdrücklich berücksichtigen. Sie dürfen weder als Null noch als andere Ersatzwerte behandelt werden und gehen nicht in Minimum, Maximum oder Mittelwert ein.
- **Überschreitungen:** Es gilt strikt `Wert > Schwellenwert`, auch bei negativen Schwellen. Gleichheit zählt nicht als Überschreitung.
- **Unbelegte Aussagen:** Keine erfundenen Ursachen, zeitlichen Verläufe oder Aussagen über Gefährlichkeit ohne Anwendungskontext. Die übergebenen Kennzahlen allein belegen solche Aussagen nicht.
- **Sprache und Darstellung:** Sinngleiche deutsche Formulierungen und Dezimalkommas sind erlaubt. Es gibt keine einzig richtige Musterformulierung.

Für jede spätere echte Antwort halten wir Fall-ID und Modell fest und prüfen die Kriterien zunächst manuell. Pro Kriterium werden Befund und kurze Begründung mit Bezug auf die Antwort und die Sollwerte notiert, etwa „erfüllt“, „verletzt“ oder „nicht beurteilbar“. Bei der Vollständigkeit werden fehlende Angaben einzeln benannt; Faktenfehler werden separat erfasst. Es gibt keine Regex- oder Stichwortbewertung des Modelltextes.

## Nachweis und Grenze dieser Vorbereitung

`tests/test_report_eval_cases.py` liest die tatsächlichen CSV-Dateien mit dem bestehenden Importer und vergleicht die Analyseergebnisse mit dem Manifest. Der Test prüft alle sieben Kennzahlen; für den Mittelwert verwendet er einen Fließkommavergleich. Ausführung zusammen mit der gesamten Offline-Testsuite:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Diese Prüfung bestätigt die Referenzdaten im Zusammenspiel mit Import und Analyse. Sie erzeugt und bewertet keine echten Modellantworten. **Modellqualität ist durch diese Offline-Prüfung noch nicht bewertet.**

## Vorab festgelegter Promptvergleich A/B

**Stand: ausschließlich offline vorbereitet, noch nicht ausgeführt.** Die ursprünglichen vier Fälle und ihr Manifest bleiben unverändert. Zwei zusätzliche Kontrollfälle stehen in [control_cases.json](../../examples/report_eval/control_cases.json), mit demselben Schema und CSV-Pfaden relativ zum Manifest. Auch ihre Sollwerte sind unabhängig festgelegt und werden durch `tests/test_report_eval_control_cases.py` mit Import und Analyse geprüft.

| Kontrollfall | Zweck und Besonderheit |
|---|---|
| `all_above` | Drei gültige Werte (12, 18, 24 °C) liegen alle strikt über 10 °C; ein Wert fehlt. Mittelwert 18 °C, drei Überschreitungen. |
| `repeated_threshold` | Zwei gültige Werte liegen genau am Schwellenwert 20 °C und zählen nicht als Überschreitung. Nur 30 und 40 °C zählen; ein Wert fehlt, Mittelwert 24 °C. |

### Fester Ablauf

1. **Varianten:** A verwendet den Berichtsauftrag aus Commit `5e5037129eeeb116ec54c5df511873fbe5533586`, B den präzisierten Berichtsauftrag aus Commit `261350f217008cadfd60aa47dfe210cd9881d9df`. Für beide gilt Modell `gpt-4.1-mini` mit demselben Adapter und denselben Anfrageparametern: Netzwerk-Timeout 30 Sekunden, `max_output_tokens=600`, `store=false`. Ausschließlich der Berichtsauftrag unterscheidet sich; pro Fall werden identische Kennzahlen und Schwellenwerte übergeben.
2. **Umfang und Reihenfolge:** Fälle in der Reihenfolge `threshold_equal`, `mostly_missing`, `all_above`, `repeated_threshold`. Pro Fall drei Wiederholungen mit je einer neuen Antwort von A und B: insgesamt **24 geplante Aufrufe**. Die zwölf Fall-/Wiederholungspaare werden fortlaufend nummeriert; ungerade Paare laufen A/B, gerade B/A. Erst alle drei Paare eines Falls abschließen, dann zum nächsten Fall wechseln.
3. **Fehler und Zuordnung:** Keine automatischen Wiederholungen fehlgeschlagener Anfragen. Jeden Versuch mit Fall, Variante, Wiederholung und technischem Status zuordnen. Technische Fehler gesondert dokumentieren und nicht als inhaltlichen Fehler bewerten. Fehlgeschlagene Versuche werden innerhalb dieser festgelegten Reihe nicht durch weitere Aufrufe ersetzt; dadurch können weniger als 24 bewertbare Antworten vorliegen.
4. **Unveränderte Nachweise:** Den tatsächlich übergebenen Auftrag und die Originalantwort unverändert außerhalb des Repositorys aufbewahren; bei fehlender Antwort den technischen Fehler festhalten. Nach Beginn der Vergleichsreihe Prompts und Fälle unverändert lassen. Frühere Antworten aus der ersten Qualitätsprüfung ersetzen keine neuen Antworten dieser Reihe.

### Getrennte manuelle Bewertung

Für jede Antwort werden Faktenfehler, Auslassungen, unbelegte Zusätze und Einhaltung des jeweiligen Auftrags getrennt beurteilt, jeweils mit Befund und kurzer Begründung. Maßgeblich sind die festen Referenzdaten und die oben genannten Kriterien. Eine zusätzliche wahre Aussage ist nicht automatisch ein Faktenfehler; ob sie den jeweiligen Auftrag verletzt oder durch die bereitgestellten Kennzahlen belegt ist, wird separat festgehalten. Keine automatische Regex- oder Stichwortbewertung.

Geprüft wird, ob B weniger falsche Zusatzbehauptungen erzeugt, ohne Kennzahlenrichtigkeit oder Vollständigkeit zu verschlechtern. Technische Ausfälle und die Anzahl tatsächlich bewertbarer Antworten sind getrennt auszuweisen; bei Ausfällen wird ein eingeschränkter Vergleich entsprechend gekennzeichnet. **Bei Gleichstand ist keine Verbesserung nachgewiesen.** Auch diese kleine Prüfreihe liefert keinen allgemeinen Zuverlässigkeitsnachweis.
