import csv


def read_temperatures(path):
    # Jeder Aufruf sammelt seine eigenen Temperaturwerte.
    temperatures = []

    # Das CSV-Modul verarbeitet die Zeilenenden.
    # Der with-Block schließt die Datei auch bei einem Fehler.
    with open(path, encoding="utf-8", newline="") as file:
        # DictReader verwendet die Kopfzeile als Spaltennamen.
        reader = csv.DictReader(file)

        for row in reader:
            # Der Reader liefert den Feldinhalt als Text.
            raw_temperature = row["temperature_c"]

            if raw_temperature == "":
                # Ein leeres Feld steht für eine fehlende Messung.
                temperatures.append(None)
            else:
                try:
                    temperature = int(raw_temperature)
                except ValueError as error:
                    # Ergänze den ursprünglichen Fehler um die Stelle in der CSV.
                    # !r zeigt den problematischen Text mit Anführungszeichen an, etwa 'kaputt'
                    raise ValueError(
                        f"{path}, Zeile {reader.line_num}: "
                        f"ungültige Temperatur {raw_temperature!r}"
                    ) from error

                # Erst nach erfolgreicher Umwandlung zur Liste hinzufügen.
                temperatures.append(temperature)

    return temperatures