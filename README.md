# LEIS – Luft-Eisspeicher-Simulation

Interaktive Streamlit-Anwendung für eine stündliche Systembetrachtung.
Startdatei: `app.py`. Python: **3.12**. Abhängigkeiten: `requirements.txt`.

## Daten und Modellgrenzen

- Temperatur: DWD, Station 03668 Nürnberg, TT_TU; stündliche UTC-Zeitstempel.
  Quelle: https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/historical/
- Börsenstrompreis: Bundesnetzagentur/SMARD, Deutschland/Luxemburg, Kalenderjahr 2025.
  Quelle: https://www.smard.de/home/downloadcenter/download-marktdaten/
- Datei `leis_inputs_2025.csv`: lokales Kalenderjahr 2025, in UTC umgerechnet.
- Gebäudelast und COP sind Modellannahmen. Speicherkapazität 1500 kWh latent je Modul,
  Quellenlimit 40 kW je Modul. Kein validierter Echtzeit-Digitalzwilling.
- Startseitenanimation: ausdrücklich Demo-Werte, keine Messdaten.
- Archivtabellen: eigene MATLAB-Simulationen mit den beschriebenen Annahmen;
  keine vertraulichen Hersteller-Messdaten. Nachlaufwerte sind separat gekennzeichnet.
- CSV-/Excel-Uploads werden durch den Cloud-Server verarbeitet, nicht automatisch
  im Repository gespeichert. Keine vertraulichen Daten in eine öffentliche Demo hochladen.

## Bereitstellung

In Streamlit Community Cloud dieses Repository, Branch `main`, Datei `app.py`
und unter Advanced settings Python 3.12 auswählen.

Dieses Paket enthält keine Projekt-PDFs, Literatur, MATLAB-Binärdateien,
Zugangsdaten, lokalen Protokolle oder aus Broschüren extrahierten Fotos.
