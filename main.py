import argparse

from temperature import count_above_threshold
from temperature_csv import read_temperatures

# Der Parser beschreibt, welche Angaben das Programm beim Start erwartet.
parser = argparse.ArgumentParser(description="Zählt Temperaturüberschreitungen.")

# Der Dateipfad ist eine Pflichtangabe und steht direkt hinter main.py.
parser.add_argument("path", help="Pfad zur CSV-Datei")

# Die Schwelle ist optional. argparse wandelt die Eingabe in eine Ganzzahl um.
parser.add_argument("--threshold", type=int, default=60, help="Temperaturschwelle (Standard: 60)")

# Lies die Terminalargumente ein und übernimm den angegebenen Dateipfad.
args = parser.parse_args()
path = args.path

# Die Schwelle kann durch ein Argument vorgegeben werden. Default = 60
threshold = args.threshold

try:
    temperatures = read_temperatures(path)
except ValueError as error:
    # Bei einem ungültigen Messwert zeigen wir nur die Meldung des CSV-Imports.
    print(error)
else:
    # Zähle erst, wenn die gesamte Datei erfolgreich eingelesen wurde.
    print(count_above_threshold(temperatures, threshold))