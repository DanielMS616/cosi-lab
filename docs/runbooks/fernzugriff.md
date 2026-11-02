# Cosi-Lab – Runbook Fernzugriff

## 1. Täglicher Ablauf

1. **Zu Hause:** Cosi-Lab einschalten, die derzeit erforderliche **F1-Bestätigung** durchführen und Ubuntu starten lassen. Eine Anmeldung am lokalen Ubuntu-Desktop ist für SSH nicht erforderlich.
2. **Am Mac:** Mit dem Bibliotheks-WLAN oder einem anderen Internetzugang verbinden. Eine gegebenenfalls angezeigte WLAN-Anmeldeseite zuerst abschließen.
3. In der **WireGuard-App** das Profil **`cosi-lab` aktivieren**.
4. Im **Mac-Terminal** verbinden:

   ```bash
   ssh cosi-vpn
   ```

   Falls abgefragt, die Passphrase des SSH-Schlüssels eingeben.
5. Bei Bedarf nach der Anmeldung prüfen:

   ```bash
   hostname
   echo "$SSH_CONNECTION"
   ```

   Erwartet: Hostname `cosi-lab`; die SSH-Verbindung verwendet die privaten VPN-Adressen von Client und Lab, Zielport `22`. Der Quellport wechselt. Die konkreten Adressen bleiben in der lokalen Betriebsdokumentation.
6. Zum Beenden der Arbeit:

   ```bash
   exit
   ```

   Anschließend den WireGuard-Tunnel am Mac deaktivieren, wenn er nicht mehr benötigt wird. `exit` beendet die SSH-Sitzung; der Rechner bleibt eingeschaltet. Langlaufende Programme sind dadurch nicht automatisch gegen einen Sitzungsabbruch abgesichert.

**Gezieltes Herunterfahren:** `sudo poweroff` auf Cosi-Lab beendet auch den Fernzugriff. Für den nächsten Start ist nach aktuellem Stand wieder eine F1-Bestätigung vor Ort nötig.

## 2. Zweck und dokumentierter Stand

Stand: **2. November 2026 – öffentliche Dokumentationsfassung**. Grundlage sind die gemeinsam durchgeführte Einrichtung und die vom Betreiber zurückgemeldeten Testergebnisse. Private Infrastrukturdetails sind durch Funktionsbeschreibungen ersetzt.

Der Mac erreicht Cosi-Lab über einen verschlüsselten WireGuard-Tunnel und meldet sich anschließend per SSH-Schlüssel an. Der Zugang ist zunächst auf **SSH zum Lab-Rechner** begrenzt. Andere Heimnetzgeräte und der allgemeine Internetverkehr des Macs werden damit nicht automatisch über das Heimnetz geleitet.

Der Zugriff ist über einen Handy-Hotspot geprüft. Ein erfolgreicher Test direkt im Bibliotheks-WLAN steht noch aus. Vor längerem unbeaufsichtigtem Betrieb bleiben feste Montage und ausreichende Kühlung gesondert zu prüfen.

## 3. Zusammenfassung der Einrichtung

| Baustein | Aktuelle Einrichtung |
|---|---|
| Router | Bestehender Heimrouter mit DHCP-Reservierung, DynDNS und IPv4-Portweiterleitung; Modell und Firmware werden privat dokumentiert |
| VPN-Endpunkt | WireGuard auf Cosi-Lab unter Ubuntu LTS; der Router leitet die VPN-Pakete weiter |
| Feste LAN-Zuordnung | Die aktuelle LAN-Adresse von Cosi-Lab ist im Router per DHCP reserviert |
| Öffentliche Erreichbarkeit | Eine IPv4-Portweiterleitung für den konfigurierten WireGuard-UDP-Port an Cosi-Lab |
| Fester DNS-Name | DuckDNS; ein IPv4-Eintrag, kein IPv6-Eintrag für diesen Namen; Aktualisierung im Router eingerichtet |
| VPN-Adressen | Eigenes privates VPN-Adresspaar für Client und Lab; konkrete Werte bleiben lokal |
| Gegenstellen | Jedes Gerät besitzt ein eigenes Schlüsselpaar; auf der Gegenstelle ist jeweils der öffentliche Schlüssel hinterlegt |
| Mac-Profil | WireGuard-Profil `cosi-lab`; Endpoint ist der gespeicherte DuckDNS-Name mit dem konfigurierten VPN-Port |
| Tunnel-Routing | `AllowedIPs` begrenzt jede Gegenstelle auf die einzelne VPN-Adresse der jeweils anderen Seite (`/32`) |
| Verbindungsaufrechterhaltung | Auf dem Mac: `PersistentKeepalive = 25` |
| SSH | Bestehender OpenSSH-Server mit Schlüsselanmeldung; Passwortanmeldung wurde zuvor erfolgreich als gesperrt geprüft |
| SSH-Kurzaufruf | Profil `cosi-vpn` in der **SSH-Konfiguration des Macs** (`~/.ssh/config`); Ziel ist die VPN-Adresse des Labs |
| Autostart | `wg-quick@wg0` aktiviert; automatischer Start nach einem Neustart praktisch bestätigt |

### Firewall auf Cosi-Lab

UFW ist aktiv: eingehende Verbindungen standardmäßig gesperrt, ausgehende erlaubt. Freigegeben sind:

- **TCP 22 aus dem Heimnetz:** bisheriger lokaler SSH-Zugang.
- **Konfigurierter VPN-Port über die LAN-Schnittstelle:** ausschließlich UDP für WireGuard zur LAN-Adresse von Cosi-Lab.
- **TCP 22 über `wg0`:** ausschließlich von der VPN-Adresse des Macs zur VPN-Adresse von Cosi-Lab.

Für SSH besteht keine öffentliche Portweiterleitung am Router. Eine Weiterleitung durch Cosi-Lab in weitere Netze wurde nicht eingerichtet.

### Ablage der Einstellungen

- **Lab:** `/etc/wireguard/wg0.conf`; privater VPN-Schlüssel in einer separaten, geschützten Datei unter `/etc/wireguard/`. `PostUp` lädt ihn beim Start.
- **Mac:** VPN-Konfiguration in der WireGuard-App; SSH-Verbindungsprofil in `~/.ssh/config`; privater SSH-Schlüssel bleibt auf dem Mac.
- **Router:** DHCP-Reservierung, IPv4-Portweiterleitung und benutzerdefinierte DynDNS-Einstellungen. Die Zugangsdaten für den DNS-Dienst bleiben ausschließlich in der privaten Konfiguration.

Diese öffentliche Fassung enthält keine realen IP-Adressen oder VPN-Domainnamen, keine privaten Benutzerkennungen, Schlüsselwerte, Token, Seriennummern oder Router-Firmwarestände. Die tatsächlichen Verbindungsdaten bleiben lokal. Die aufgeführten Rollen und Befehle beschreiben den eingerichteten Ablauf; sie sind keine vollständige Konfiguration zum direkten Neuaufsetzen.

## 4. Kurze Funktionsprüfung

**Auf Cosi-Lab**, nach einer erfolgreichen Anmeldung:

```bash
systemctl is-active wg-quick@wg0
systemctl is-enabled wg-quick@wg0
ip -4 -br address show wg0
echo "$SSH_CONNECTION"
```

Erwartet: `active`, `enabled`, die lokal konfigurierte VPN-Adresse des Labs und eine SSH-Verbindung über die beiden privaten VPN-Adressen.

Für eine weitergehende lokale Diagnose auf Cosi-Lab:

```bash
sudo wg show
sudo ufw status verbose
```

`latest handshake` zeigt den letzten erfolgreichen Schlüsselaustausch. Eine aktivierte Mac-App allein belegt noch keine erfolgreiche Verbindung. Diagnoseausgaben können öffentliche Adressen und öffentliche Schlüssel enthalten; vor einer Veröffentlichung prüfen.

**DNS auf dem Mac prüfen:** `DEIN_VPN_DNSNAME` lokal durch den eingerichteten vollständigen Namen ersetzen:

```bash
dig +short DEIN_VPN_DNSNAME A
dig +short DEIN_VPN_DNSNAME AAAA
```

Der erste Befehl soll die aktuelle öffentliche IPv4-Adresse aus dem Router-Online-Monitor liefern; der zweite soll leer bleiben.

## 5. Häufige Störungen

| Beobachtung | Nächster sinnvoller Schritt |
|---|---|
| Internet im öffentlichen WLAN funktioniert nicht | WLAN-Anmeldeseite abschließen und eine gewöhnliche Internetseite öffnen |
| WireGuard ist aktiviert, aber SSH erreicht das Lab nicht | Auf Cosi-Lab nach aktuellem Handshake prüfen; wenn nötig vor Ort oder über den lokalen LAN-Zugang diagnostizieren |
| Öffentliche IP hat sich geändert | DNS-Zuordnung prüfen; danach WireGuard am Mac deaktivieren und erneut aktivieren, damit der Endpoint neu aufgelöst wird |
| Kein Zugang nur im Bibliotheks-WLAN | Mit dem Handy-Hotspot vergleichen; eine Einschränkung von UDP durch das Bibliotheksnetz ist möglich und muss geprüft werden |
| Rechner steht vor dem Ubuntu-Start | F1 vor Ort bestätigen; der VPN-Dienst ist erst nach dem Ubuntu-Start verfügbar |
| Warnung über einen geänderten SSH-Hostschlüssel | Identität des Labs unabhängig prüfen; gespeicherte Hostschlüssel nicht ungeprüft entfernen |

### Veralteten DNS-Eintrag diagnostizieren

1. Die aktuelle öffentliche IPv4-Adresse im Router-Online-Monitor mit dem Ergebnis von `dig +short DEIN_VPN_DNSNAME A` vergleichen. Den Platzhalter nur lokal ersetzen.
2. Bei Abweichung den letzten DynDNS-Updateversuch und dessen Ergebnis im Router prüfen. Die Update-URL anhand der [DuckDNS-Schnittstelle](https://www.duckdns.org/spec.jsp) kontrollieren: Stimmen Zielname, Zugangsdaten und die vom Router eingesetzten Parameter? Wird die aktuelle statt einer fest eingetragenen alten IPv4-Adresse übermittelt? DuckDNS meldet `OK` bei Erfolg und `KO` bei einem Fehler.
3. Nach Korrektur einen Updateversuch auslösen und die DNS-Antwort erneut prüfen. Ist das Update erfolgreich, aber die Antwort noch alt, die Cache-Laufzeit (TTL, sichtbar mit `dig DEIN_VPN_DNSNAME A`) berücksichtigen und später erneut abfragen.
4. Sobald DNS die aktuelle IPv4-Adresse liefert, WireGuard am Mac deaktivieren und erneut aktivieren. Über den Handy-Hotspot einen aktuellen Handshake und anschließend `ssh cosi-vpn` prüfen. Bleibt der Zugriff gestört, VPN-Dienst und Portweiterleitung getrennt prüfen.

Update-URLs können Tokens enthalten. Konkrete Adressen, Tokens, Schlüssel, Router-Sitzungslinks und unbereinigte Diagnoseausgaben bleiben in der privaten Betriebsdokumentation.

## 6. Nachgewiesene Funktionen und offene Tests

| Prüfung | Ergebnis / Stand |
|---|---|
| WireGuard und SSH im Heimnetz | Erfolgreich |
| Fernzugriff über Mobilfunk mit öffentlicher IPv4 | Erfolgreich |
| DNS-Abgleich und Fernzugriff mit DuckDNS-Endpoint | Erfolgreich zurückgemeldet |
| Neustart: automatischer VPN-Start und SSH ohne Desktop-Anmeldung | Erfolgreich; F1 weiterhin erforderlich |
| Energieeinstellung des Benutzers im Netzbetrieb | `sleep-inactive-ac-type = 'nothing'`; gespeicherter Timeout `3600` Sekunden löst dabei keine Schlafaktion aus |
| Längerer Leerlauf ohne Desktop-Anmeldung | Noch offen; vorgeschlagener Test: etwa 70 Minuten, danach erneut verbinden |
| Zugriff aus dem tatsächlichen Bibliotheks-WLAN | Noch offen |
| Automatische DNS-Aktualisierung nach Wechsel der öffentlichen IP | Am 02.11.2026 nach Anpassung der Update-URL mit echtem öffentlichen IPv4-Wechsel erfolgreich geprüft; VPN/SSH anschließend über Handy-Hotspot erfolgreich (siehe [Journal](../journal/2026-11-02.md)) |
| Montage und Kühlung für längeren unbeaufsichtigten Betrieb | Noch gesondert zu prüfen |

## 7. Technische Referenzen

- [WireGuard: Quick Start](https://www.wireguard.com/quickstart/)
- [Ubuntu: WireGuard mit systemd verwalten](https://ubuntu.com/server/docs/how-to/wireguard-vpn/common-tasks/)
- [DuckDNS: Update-Schnittstelle](https://www.duckdns.org/spec.jsp)
- [OpenSSH: Client-Konfiguration](https://man.openbsd.org/ssh_config)
