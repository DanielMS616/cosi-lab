import csv

# Sammelt die Temperaturen in derselben Reihenfolge wie in der Datei.
temperatures = []

def read_temperatures(path):
    # newline="" überlässt die Zeilenenden dem CSV-Modul.
    # Der with-Block schließt die Datei automatisch.
    with open(path, encoding="utf-8", newline="") as file:
        # DictReader verwendet die erste Zeile als Spaltenüberschrift.
        for row in csv.DictReader(file):
            # CSV-Felder werden als Text eingelesen, auch wenn darin Zahlen stehen.
            raw_temperature = row["temperature_c"]

            if raw_temperature == "":
                # Ein leeres Feld steht für einen fehlenden Messwert.
                temperatures.append(None)
            else:
                # Den Text in eine Ganzzahl umwandeln und zur Liste hinzufügen.
                temperatures.append(int(raw_temperature))

    return temperatures