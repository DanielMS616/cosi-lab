def build_temperature_prompt(
    total_count, valid_count, missing_count, threshold, exceedances
):
    """Erstellt einen Prompt aus den bereits berechneten Temperaturkennzahlen."""

    # Dieser Schreibauftrag bleibt bei jeder Auswertung gleich.
    instruction = (
        "Fasse die folgenden Temperaturkennzahlen in zwei verständlichen Sätzen "
        "auf Deutsch zusammen, gib die Zahlen unverändert wieder und bleib bei "
        "den angegebenen Fakten, ohne Ursachen oder Bewertungen hinzuzufügen."
    )

    # Die f-Strings setzen die übergebenen Werte ein.
    # \n beginnt jeweils eine neue Zeile.
    facts = (
        f"Messwerte insgesamt: {total_count}\n"
        f"Gültige Messwerte: {valid_count}\n"
        f"Fehlende Messwerte: {missing_count}\n"
        f"Schwelle: {threshold} °C\n"
        f"Messwerte strikt über der Schwelle: {exceedances}"
    )

    # Eine Leerzeile trennt den Schreibauftrag von den Fakten.
    return f"{instruction}\n\n{facts}"