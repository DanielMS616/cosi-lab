# RAG-Prüfreihe für Cosi-Lab

Die Prüfreihe bewertet zwei Dinge getrennt: Findet die Suche den richtigen Ausschnitt? 
Und beantwortet GPT die Frage anhand dieses Ausschnitts?

| Fall | Frage | Erwartung |
| --- | --- | --- |
| Eine Quelle reicht | Welche CPU hat Cosi-Lab? | Die Hardware-Doku nennt den Intel Core i5-8500 mit 6 Kernen. Die Antwort nennt die passende Fundstelle. |
| Zwei Quellen sind nötig | Welche CPU ist verbaut und wie läuft SSH im WireGuard-Tunnel? | Mit `--multi-source` enthält der Prompt Hardware- und Fernzugriffsdoku. Die Antwort ordnet die CPU der Hardware-Doku und SSH über WireGuard der Fernzugriffsdoku zu. |
| Nur ein Teil ist belegt | Welche CPU ist verbaut, wie erfolgt die SSH-Anmeldung im WireGuard-Tunnel und welche SSH-Portnummer ist konfiguriert? | Mit `--multi-source` nennt die Antwort CPU und Schlüsselanmeldung mit den jeweiligen Fundstellen. Die Portnummer geht aus den Ausschnitten nicht hervor. |
| Keine Fundstelle | Welche Seriennummer hat Cosi-Lab? | Die Suche meldet „Keine passende Fundstelle gefunden.“ Ohne Treffer wird kein Modell aufgerufen. |

Zuerst prüfe ich mit `--show-prompt`, welche Quelle und welcher Ausschnitt ausgewählt werden. 
Falls ich die Modellantwort erneut prüfen möchte, füge ich `--gpt` hinzu. 
Dann kontrolliere ich den API-Status, die Vollständigkeit der Antwort und die Belege für die einzelnen Aussagen. 
Die automatische Zitatprüfung gleicht nur Pfade und Zeilennummern ab.

```bash
.venv/bin/python doc_search.py \
  "Welche CPU ist verbaut und wie läuft SSH im WireGuard-Tunnel?" \
  --project-docs --multi-source --show-prompt
```

**Ausgangsstand vom 14.11.2026:** Die CPU-Frage und die kombinierte Frage wurden mit den passenden Fundstellen beantwortet. 
Bei der Frage mit drei Teilen fehlte die Portnummer in der Quelle; 
GPT hat keine Nummer geraten. Die Seriennummer-Frage lieferte nach dem Ausschluss des Projektnamens keinen Treffer. 
In einem weiteren Lauf zur kombinierten Frage wurden beide Quellen korrekt zitiert, 
die Schlüsselanmeldung aber nicht ausdrücklich erwähnt. Das zeigt, warum ich Zitate und Vollständigkeit getrennt prüfe.