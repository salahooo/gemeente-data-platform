# Gemeente Data Platform

De read-only FastAPI analytics API is beschikbaar op `localhost:8000` via het
Compose-profiel `api`; zie [API-documentatie](docs/api.md). Zij leest uitsluitend
`mart`-views met de aparte loginrol `gemeente_api`.

[![CI](https://github.com/salahooo/gemeente-data-platform/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/salahooo/gemeente-data-platform/actions/workflows/ci.yml)

Een portfolio-project voor functies rond data bij Nederlandse gemeenten en de overheid. Het project krijgt uiteindelijk een reproduceerbare dataketen voor gemeentelijke CBS-data.

## Huidige fase: betrouwbare end-to-end bevolkingspipeline

De professionele Python-projectbasis ontdekt dimensies, haalt ongetransformeerde
bevolkingsrecords voor gemeentecodes op uit de CBS Open Data API voor dataset
`03759ned` en bouwt daaruit een reproduceerbare processed laag. De raw extractie
valideert dimensiecodes, perioden en records voordat CBS-responses in een unieke
UTC-runmap onder `data/raw/cbs/03759ned/` worden opgeslagen. De transformatie
gebruikt daarna uitsluitend zo'n lokaal gevalideerde raw run.

- Python 3.11+-project met een `src`-layout;
- centrale, omgevingsvariabele-gebaseerde configuratie;
- basisstructuur voor data, SQL, notebooks en documentatie;
- een minimale uitvoerbare applicatie, rooktest en codekwaliteitsconfiguratie;
- een CBS-client met timeout, retries en begrensde paginering;
- dimensieontdekking en gerichte, raw extractie voor perioden vanaf 2020;
- atomaire JSON-opslag, checksums en een manifest per extractierun.
- drie gevalideerde processed tabellen: `dim_municipality`, `dim_period` en
  `fact_population`;
- Parquet als technische bron en UTF-8-CSV als leesbare export, met een manifest,
  checksums, kwaliteitsrapport en atomaire publicatie per processed run.

Historische gemeentecodes worden niet geharmoniseerd of samengevoegd. Een actieve
gemeentewaarneming is in dit project een gemeente-jaarrecord
met een geldige numerieke bevolking op 1 januari; ontbrekend is niet nul.
Fase 5 orkestreert CBS-extractie, raw-validatie, processed-transformatie,
Alembic, transactionele PostgreSQL-snapshot-load en databasevalidatie als één
herstelbare run. Elke pipeline-run heeft een getypeerd manifest, JSONL-log en
lineage naar `ops.etl_run`. Power BI blijft toekomstig.

## Geplande vervolgfases

1. Productie-geschikte scheduling, backup en herstel ontwerpen.
2. Dashboards ontwikkelen in Power BI.

## Architectuur

- [Architectuuroverzicht](docs/architecture.md)
- [TOGAF-light architectuurbeschrijving](docs/togaf-alignment.md)
- [CBS-datacontract](docs/data-contract.md)
- [Processed-datacontract](docs/processed-data-contract.md)
- [ADR-register](docs/decisions/README.md)
- [ADR-001: afzonderlijke herbruikbare CBS OData-client](docs/decisions/ADR-001-cbs-odata-client.md)
- [ADR-002: historische gemeentecodes behouden](docs/decisions/ADR-002-historical-municipality-codes.md)
- [ADR-003: Parquet als canonieke processed opslag](docs/decisions/ADR-003-parquet-as-canonical-processed-storage.md)
- [ADR-007: pipeline-orchestratie en lineage](docs/decisions/ADR-007-pipeline-orchestration-and-lineage.md)
- [Pipeline-operations](docs/pipeline-operations.md)
- [CI/CD en repositorykwaliteit](docs/ci-cd.md)

## Lokaal starten

Minimale projectvereiste: Python 3.11 of nieuwer. Onderstaande opdrachten gebruiken
expliciet Python 3.14 op Windows PowerShell.

```powershell
py -3.14 -m pip install --user --upgrade pip
py -3.14 -m pip install --user -e ".[dev]"
py -3.14 -m gemeente_data_platform.main
py -3.14 -m gemeente_data_platform.fetch_metadata
py -3.14 -m gemeente_data_platform.extract_population
py -3.14 -m gemeente_data_platform.transform_population
py -3.14 -m gemeente_data_platform.run_pipeline --dry-run
py -3.14 -m gemeente_data_platform.run_pipeline
py -3.14 -m pytest
py -3.14 -m ruff check .
git diff --check
```

De optie `--user` installeert pakketten voor het huidige Windows-gebruikersaccount,
zonder een virtual environment aan te maken.

Kopieer eventueel `.env.example` naar `.env` en vervang uitsluitend de voorbeeldwaarden door lokale instellingen. Het bestand `.env` wordt niet door Git gevolgd.

## Raw landing zone

Elke metadata- of extractierun schrijft naar een unieke UTC-runmap:
`data/raw/cbs/03759ned/<utc-run-id>/`. De volledige bevolkingsrun bevat de
opgehaalde metadata, dimensies, `population_records.json`, `quality_report.json`
en `manifest.json`.
Zie het [CBS-datacontract](docs/data-contract.md) voor de bestandsstructuur,
validaties en de grens tussen raw extractie en transformatie. De processed-laag
modelleert alleen bruikbare gemeente-jaarwaarnemingen.

## Processed laag

De transformatie selecteert standaard de nieuwste volledig geldige raw run. Kies
eventueel reproduceerbaar een specifieke run met `--raw-run`:

```powershell
py -3.14 -m gemeente_data_platform.transform_population --raw-run 20260904T004750415349Z
```

Elke processed run komt onder `data/processed/cbs/03759ned/<utc-run-id>/` terecht.
De map bevat Parquet- en CSV-versies van de drie tabellen, `quality_report.json`
en `manifest.json`. Generated data wordt niet door Git gevolgd. Zie het
[processed-datacontract](docs/processed-data-contract.md) voor schema's,
selectieregels en validaties.

## PostgreSQL en end-to-end pipeline

De standaardopdracht `py -3.14 -m gemeente_data_platform.run_pipeline` voert
alle vijf fasen uit tegen de lokale PostgreSQL 17 Docker-container op poort 5433.
Zie het [runbook](docs/runbook.md), [pipeline-operations](docs/pipeline-operations.md)
en het [databaseontwerp](docs/database-design.md). PostgreSQL is bestaand;
Power BI blijft toekomstig.

## CI en tests

GitHub Actions draait op pull requests, pushes naar `main` en handmatige starts.
De quality-matrix gebruikt Python 3.11 en 3.14 en voert uitsluitend databasevrije
tests uit. Pas daarna start de afzonderlijke PostgreSQL-integratiejob alleen
`postgres_test` op `localhost:5434/gemeente_data_test`. CI start of wijzigt nooit
de ontwikkelservice op 5433. Zie [CI/CD en repositorykwaliteit](docs/ci-cd.md)
voor lokale reproductie, dependency-updates en probleemoplossing.
