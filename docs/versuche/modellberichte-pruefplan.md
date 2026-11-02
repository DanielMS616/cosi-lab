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
