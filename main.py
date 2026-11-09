from temperature import count_above_threshold
from temperature_csv import read_temperatures

path = "examples/temperature_sample.csv"
threshold = 60

try:
    temperatures = read_temperatures(path)
except ValueError as error:
    print(error)
else:
    # Zähle die Überschreitungen und gib das Ergebnis aus.
    print(count_above_threshold(temperatures, threshold))