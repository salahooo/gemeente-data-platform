# Gemeente Data Platform

Een portfolio-project voor functies rond data bij Nederlandse gemeenten en de overheid. Het project krijgt uiteindelijk een reproduceerbare dataketen voor gemeentelijke CBS-data.

## Huidige fase: projectbasis

Op dit moment is alleen de professionele Python-projectbasis ingericht:

- Python 3.11+-project met een `src`-layout;
- centrale, omgevingsvariabele-gebaseerde configuratie;
- basisstructuur voor data, SQL, notebooks en documentatie;
- een minimale uitvoerbare applicatie, rooktest en codekwaliteitsconfiguratie.

Er is nog **geen** koppeling met de CBS Open Data API, PostgreSQL, SQL-transformaties of Power BI.

## Geplande vervolgfases

1. Gemeentelijke gegevens ophalen uit de CBS Open Data API.
2. Gegevens valideren en transformeren met Python en Pandas.
3. Verwerkte gegevens laden in PostgreSQL met SQLAlchemy en Psycopg.
4. Analyse- en rapportageviews opbouwen met SQL.
5. Dashboards ontwikkelen in Power BI.

De beoogde architectuur staat in [docs/architecture.md](docs/architecture.md).

## Lokaal starten

Minimale projectvereiste: Python 3.11 of nieuwer. Onderstaande opdrachten gebruiken
expliciet Python 3.14 op Windows PowerShell.

```powershell
py -3.14 -m pip install --user --upgrade pip
py -3.14 -m pip install --user -e ".[dev]"
py -3.14 -m gemeente_data_platform.main
py -3.14 -m pytest
py -3.14 -m ruff check .
```

De optie `--user` installeert pakketten voor het huidige Windows-gebruikersaccount,
zonder een virtual environment aan te maken.

Kopieer eventueel `.env.example` naar `.env` en vervang uitsluitend de voorbeeldwaarden door lokale instellingen. Het bestand `.env` wordt niet door Git gevolgd.
