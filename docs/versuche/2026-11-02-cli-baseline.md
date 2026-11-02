# CLI-Basismessung: optionale Protokollierung

**Datum:** 2. November 2026 · **Projekt:** Cosi-Lab · **Autor:** Daniel Glöde

## Fragestellung und Rahmen

Wie verändern sich gesamte Prozesslaufzeit und maximaler residenter Speicherbedarf der Temperaturauswertung durch die optionale JSONL-Protokollierung?

Ausführung und Terminalausgaben wurden vom Betreiber auf dem Ubuntu-Lab-Rechner zurückgemeldet. Diese Notiz wertet die mitgeteilten Rohmesswerte aus; sie behauptet keinen eigenen Zugriff auf den Rechner.

Versuchsumgebung laut den bisherigen Betriebsnachweisen: Intel Core i5-8500, 16 GB RAM, Ubuntu 26.04.1 LTS und bisherige HDD als Systemlaufwerk. Der geprüfte Code umfasst CSV-Import, deterministische Analyse, CLI und JSONL-Protokolle. Die vor den Läufen gesicherten und anschließend übermittelten Angaben aus `umgebung.txt` ordnen die Messung wie folgt zu:

| Metadatum | Erfasster Wert |
|---|---|
| Zeitpunkt der Metadatenerfassung | `2026-11-02T13:22:24+01:00` (CET) |
| Git-HEAD bei der Messung | `c86a761a7990864d0815c561523ec494970a5173` |
| Python | `3.14.4` |
| Linux-Kernel | `7.0.0-38-generic` |

## Durchführung

- Synthetische CSV mit 120.000 Datensätzen, Kopfzeile `time_s,temperature_c`, UTF-8 und LF. Zeitstempel: ganze Sekunden von 0 bis 119.999; Temperaturfolge `[40, 42, fehlend, 61, 65, 60]`, 20.000-mal wiederholt.
- Schwellenwert: 60 °C, Überschreitung strikt `>`. Der Referenzlauf lieferte die erwarteten 100.000 gültigen und 20.000 fehlenden Werte, Minimum 40 °C, Maximum 65 °C, Mittelwert 53,6 °C und 40.000 Überschreitungen.
- Ein ungemessener Lauf je Variante vorab. Die Messreihe beschreibt Betrieb mit bereits gelesenen Dateien im Dateisystemcache; sie ist kein Kaltstartversuch.
- Fünf Blöcke in der Reihenfolge **ohne / mit / mit / ohne** Protokollierung: zehn neue Programmprozesse je Variante.
- GNU `/usr/bin/time`: `%e` für gesamte Prozesslaufzeit in Sekunden, `%M` für maximalen residenten Speicherbedarf unter Linux in KiB und `%x` für den Prozess-Rückgabecode. Zahlenformat: `LC_ALL=C`.
- Gemessen wurde der vollständige CLI-Prozess einschließlich Python-Start, Verarbeitung und Ausgabeformatierung. stdout wurde nach `/dev/null` geleitet. Die internen JSONL-Schrittdauern wurden für diesen Vergleich nicht verwendet.
- Mit Protokollierung entstanden je Lauf eine neue Datei und sechs Ereignisse. Es gilt die vorhandene gepufferte Dateiausgabe ohne zusätzliche erzwungene Datenträgersynchronisation.

## Ergebnisse

| Messgröße | Ohne Protokollierung | Mit Protokollierung |
|---|---:|---:|
| Messläufe | 10 | 10 |
| Erfolgreiche Prozesse, Rückgabecode 0 | 10 | 10 |
| Laufzeit: Median | 0,34 s | 0,35 s |
| Laufzeit: Minimum–Maximum | 0,34–0,36 s | 0,34–0,35 s |
| Maximaler residenter Speicherbedarf: Median | 46.420 KiB | 46.526 KiB |
| Maximaler residenter Speicherbedarf: Median in MiB | 45,33 MiB | 45,44 MiB |
| Maximaler residenter Speicherbedarf: Minimum–Maximum | 46.340–46.528 KiB | 46.468–46.656 KiB |

Die Laufzeitmediane unterscheiden sich um 10 ms, die Speichermediane um 106 KiB. Die Reihe deutet auf einen kleinen zusätzlichen Zeitbedarf der Protokollierung hin. Die Zeitausgabe hat hier nur Hundertstelsekunden, und die beobachteten Bereiche überschneiden sich. Ein präziser allgemeiner Prozentwert für den Zusatzaufwand lässt sich daraus nicht ableiten. Die geringe Speicherdifferenz ist ebenfalls gegenüber den beobachteten Schwankungen vorsichtig zu bewerten.

Für den geprüften Offline-Ablauf mit diesem Datensatz ergibt sich kein Anlass, die Protokollierung aus Leistungsgründen zu vereinfachen. Die Messung macht keine Aussage über Modellinferenz, andere Datenmengen oder mehr Protokollereignisse. Sie ist auch kein Nachweis für Datenträgergesundheit, dauerhafte Speicherung von Ereignissen oder die Leistung nach einem SSD-Wechsel.

## Reproduktion

Voraussetzungen: Ubuntu/Linux mit GNU `/usr/bin/time`, passende Projektversion und vorhandene `.venv`. Im Repository-Verzeichnis in derselben Bash-Sitzung ausführen. Die Befehle legen einen neuen lokalen Versuchsordner außerhalb des Repositorys an; die Anwendung bleibt unverändert.

```bash
cosi_messung=$(mktemp -d "$HOME/cosi-messung-XXXXXX")
.venv/bin/python - "$cosi_messung/daten.csv" <<'PY'
import csv
import sys

pattern = [40, 42, None, 61, 65, 60]
with open(sys.argv[1], "x", encoding="utf-8", newline="") as target:
    writer = csv.writer(target, lineterminator="\n")
    writer.writerow(["time_s", "temperature_c"])
    for index in range(120_000):
        temperature = pattern[index % len(pattern)]
        writer.writerow([index, "" if temperature is None else temperature])
PY

{
    date -Is
    git rev-parse HEAD
    .venv/bin/python --version
    uname -r
} > "$cosi_messung/umgebung.txt"

.venv/bin/python cosi.py "$cosi_messung/daten.csv" --threshold 60
```

Nur bei den oben genannten erwarteten Kennzahlen und fehlerfreiem Referenzlauf fortfahren:

```bash
.venv/bin/python cosi.py "$cosi_messung/daten.csv" \
  --threshold 60 --log-dir "$cosi_messung/logs" > /dev/null

printf 'modus,laufzeit_s,max_ram_kib,exit\n' > "$cosi_messung/messwerte.csv"
for runde in 1 2 3 4 5; do
    for modus in ohne_log mit_log mit_log ohne_log; do
        if [ "$modus" = mit_log ]; then
            LC_ALL=C /usr/bin/time \
              -a -o "$cosi_messung/messwerte.csv" -f "$modus,%e,%M,%x" \
              .venv/bin/python cosi.py "$cosi_messung/daten.csv" \
              --threshold 60 --log-dir "$cosi_messung/logs" > /dev/null
        else
            LC_ALL=C /usr/bin/time \
              -a -o "$cosi_messung/messwerte.csv" -f "$modus,%e,%M,%x" \
              .venv/bin/python cosi.py "$cosi_messung/daten.csv" \
              --threshold 60 > /dev/null
        fi || break 2
    done
done
printf 'Versuchsordner: %s\n' "$cosi_messung"
cat "$cosi_messung/messwerte.csv"
```

Ein vollständiger erfolgreicher Versuch hat 20 Messzeilen und ausschließlich Rückgabecode 0. Bei Fehlern wird die Reihe als unvollständig behandelt; gescheiterte Läufe werden nicht stillschweigend aus der Auswertung entfernt. Originaldaten, Metadaten und Ereignisdateien bleiben lokal erhalten. Öffentlich werden nur bereinigte Messwerte und das Verfahren übernommen.

## Übermittelte Rohmesswerte

```csv
modus,laufzeit_s,max_ram_kib,exit
ohne_log,0.34,46524,0
mit_log,0.35,46608,0
mit_log,0.35,46528,0
ohne_log,0.36,46444,0
ohne_log,0.34,46368,0
mit_log,0.34,46524,0
mit_log,0.35,46524,0
ohne_log,0.34,46340,0
ohne_log,0.34,46476,0
mit_log,0.35,46644,0
mit_log,0.35,46496,0
ohne_log,0.34,46376,0
ohne_log,0.34,46524,0
mit_log,0.35,46656,0
mit_log,0.35,46564,0
ohne_log,0.35,46528,0
ohne_log,0.34,46396,0
mit_log,0.35,46468,0
mit_log,0.35,46504,0
ohne_log,0.34,46396,0
```
