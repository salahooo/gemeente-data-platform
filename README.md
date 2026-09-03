# Gemeente Data Platform

Een portfolio-project voor functies rond data bij Nederlandse gemeenten en de overheid. Het project krijgt uiteindelijk een reproduceerbare dataketen voor gemeentelijke CBS-data.

## Huidige fase: CBS-metadata ophalen

De professionele Python-projectbasis is ingericht en kan metadata ophalen uit de
CBS Open Data API voor dataset `03759ned`. Het metadata-endpoint `TableInfos`
wordt opgehaald en als leesbare UTF-8-JSON opgeslagen in
`data/raw/03759ned_table_info.json`.

- Python 3.11+-project met een `src`-layout;
- centrale, omgevingsvariabele-gebaseerde configuratie;
- basisstructuur voor data, SQL, notebooks en documentatie;
- een minimale uitvoerbare applicatie, rooktest en codekwaliteitsconfiguratie;
- een kleine CBS-client voor uitsluitend datasetmetadata.

Er worden nog **geen** bevolkingsgegevens getransformeerd of geladen. PostgreSQL,
SQL-transformaties en Power BI zijn evenmin geïmplementeerd.

## Geplande vervolgfases

1. Gemeentelijke gegevens ophalen uit de CBS Open Data API.
2. Gegevens valideren en transformeren met Python en Pandas.
3. Verwerkte gegevens laden in PostgreSQL met SQLAlchemy en Psycopg.
4. Analyse- en rapportageviews opbouwen met SQL.
5. Dashboards ontwikkelen in Power BI.

## Architectuur

- [Architectuuroverzicht](docs/architecture.md)
- [TOGAF-light architectuurbeschrijving](docs/togaf-alignment.md)
- [ADR-register](docs/decisions/README.md)
- [ADR-001: afzonderlijke herbruikbare CBS OData-client](docs/decisions/ADR-001-cbs-odata-client.md)

## Lokaal starten

Minimale projectvereiste: Python 3.11 of nieuwer. Onderstaande opdrachten gebruiken
expliciet Python 3.14 op Windows PowerShell.

```powershell
py -3.14 -m pip install --user --upgrade pip
py -3.14 -m pip install --user -e ".[dev]"
py -3.14 -m gemeente_data_platform.main
py -3.14 -m gemeente_data_platform.fetch_metadata
py -3.14 -m pytest
py -3.14 -m ruff check .
```

De optie `--user` installeert pakketten voor het huidige Windows-gebruikersaccount,
zonder een virtual environment aan te maken.

Kopieer eventueel `.env.example` naar `.env` en vervang uitsluitend de voorbeeldwaarden door lokale instellingen. Het bestand `.env` wordt niet door Git gevolgd.
