# Architectuur

## Doel en scope

Het Gemeente Data Platform haalt openbare CBS-data gecontroleerd op. Fase 3 bouwt
uit een gevalideerde raw run analyseklare bevolkingstabellen. De huidige keten
omvat dus raw extractie en lokale transformatie; PostgreSQL, SQL-views en Power
BI zijn toekomstig.

## 1. Systeemcontext

### C4 niveau 1 — Systeemcontext

```mermaid
flowchart LR
    gebruiker[Data-analist of gebruiker - extern] --> platform[Gemeente Data Platform - bestaand]
    platform --> cbs[CBS OData API - extern]
    platform -. toekomstig .-> powerbi[Power BI-dashboard - toekomstig en extern]
```

## 2. Containers

### C4 niveau 2 — Containerdiagram

```mermaid
flowchart LR
    etl[Python ETL-applicatie - bestaand] --> cbs[CBS OData API - extern]
    etl --> raw[Raw JSON landing zone - bestaand]
    etl --> processed[Processed Parquet en CSV - bestaand]
    processed -. toekomstig .-> postgres[PostgreSQL-database - toekomstig]
    postgres -. toekomstig .-> powerbi[Power BI - toekomstig en extern]
```

De raw landing zone bewaart een onveranderlijke bronrun per UTC-run-id. De
processed opslag bevat een afzonderlijke, atomair gepubliceerde run met Parquet,
CSV, kwaliteitsrapport en manifest.

## 3. Componenten van de Python-applicatie

### C4 niveau 3 — Componentdiagram

```mermaid
flowchart LR
    subgraph app[Python ETL-applicatie - bestaand]
        config[config.py - bestaand]
        extraction[extract_population.py en population_extraction.py - bestaand]
        client[cbs_client.py - bestaand]
        rawcontracts[data_contracts.py en quality.py - bestaand]
        rawstorage[raw_storage.py - bestaand]
        runner[transform_population.py - bestaand]
        pipeline[processed_pipeline.py - bestaand]
        transformation[population_transformation.py - bestaand]
        processedcontracts[processed_contracts.py - bestaand]
        processedstorage[processed_storage.py - bestaand]
        database[Databaselaag - toekomstig]
    end
    cbs[CBS OData API - extern]
    raw[Raw JSON - bestaand]
    processed[Processed Parquet en CSV - bestaand]
    postgres[PostgreSQL - toekomstig]

    config --> extraction
    extraction --> client
    client --> cbs
    extraction --> rawcontracts
    rawcontracts --> rawstorage
    rawstorage --> raw
    config --> runner
    runner --> pipeline
    pipeline --> raw
    pipeline --> transformation
    transformation --> processedcontracts
    pipeline --> processedstorage
    processedstorage --> processed
    processed -. toekomstig .-> database
    database -. toekomstig .-> postgres
```

## 4. Dynamisch gedrag

### Sequence diagram: raw naar processed

```mermaid
sequenceDiagram
    participant U as Gebruiker - extern
    participant R as transform_population - bestaand
    participant C as Configuratie - bestaand
    participant S as Processed opslag - bestaand
    participant W as Raw JSON - bestaand
    participant T as Transformatielaag - bestaand

    U->>R: Start transformatie met optionele raw run
    R->>C: Lees instellingen
    R->>S: Selecteer nieuwste volledige geldige raw run
    S->>W: Lees manifest en verifieer checksums
    W-->>S: Gevalideerde raw records, dimensies en kwaliteit
    S->>T: Bouw dimensies en facts
    T->>T: Valideer sleutels, waarden en reconciliatie
    T-->>S: Processed tabellen en kwaliteitsrapport
    S->>S: Schrijf tijdelijk Parquet en CSV
    S->>S: Herlees, valideer en checksum uitvoer
    S-->>R: Publiceer UTC-runmap atomair
```

Een ontbrekende, onvolledige of checksum-onjuiste raw run stopt de verwerking.
Ook contract-, opslag- en uitvoervalidatiefouten stoppen vóór publicatie. De
transformatie doet zelf geen HTTP-aanroep naar CBS.

### Lineage

```mermaid
flowchart LR
    cbs[CBS OData API - extern] --> raw[Gevalideerde raw run - bestaand]
    raw --> validation[Raw-validatie - bestaand]
    validation --> transform[Selectie en transformatie - bestaand]
    raw --> records[population_records.json]
    raw --> regions[regions.json]
    raw --> periods[periods.json]
    raw --> rawquality[quality_report.json]
    records --> transform
    regions --> transform
    periods --> transform
    rawquality --> transform
    transform --> municipality[dim_municipality]
    transform --> period[dim_period]
    transform --> population[fact_population]
    transform --> quality[Processed quality report en manifest]
    municipality --> postgres[PostgreSQL - toekomstig]
    period --> postgres
    population --> postgres
    postgres --> powerbi[Power BI - toekomstig]
```

Het relationele schema staat in het
[processed-datacontract](processed-data-contract.md).

### Legenda

- **Bestaand:** geïmplementeerd en getest.
- **Toekomstig:** gepland, nog niet geïmplementeerd.
- **Extern:** systeem buiten onze verantwoordelijkheid.

## Architectuurprincipes

- Verantwoordelijkheden zijn gescheiden tussen configuratie, extractie,
  transformatie, validatie en opslag.
- Configuratie staat buiten de bedrijfslogica.
- Een herbruikbare CBS-client bundelt transportafspraken voor externe API-calls.
- Tests kunnen zonder echte netwerkverbinding worden uitgevoerd.
- Raw data blijft onveranderd; processed data is herleidbaar naar een raw run.
- Secrets en gegenereerde data worden niet gecommit.
- Documentatie verandert mee met de implementatie.
- Een toekomstige component wordt nooit als bestaand gepresenteerd.

## Huidige versus doelarchitectuur

| Onderdeel | Huidig: fase 4 | Later: doelarchitectuur |
| --- | --- | --- |
| Databron | CBS OData API, dataset `03759ned` | Uitbreidbare CBS-bronnen |
| Ingestie | Gevalideerde raw extractie | Herhaalbare extracties voor meer datasets |
| Verwerking | Raw naar drie processed tabellen | Aanvullende transformaties en regels |
| Opslag | Lokale processed runs en PostgreSQL 17 (`core`, `mart`, `ops`) | Beheerde productieopslag en herstelproces |
| Presentatie | Niet aanwezig | Power BI-dashboard boven analysegegevens |
| Kwaliteitscontrole | Contracten, reconciliatie, checksums, pytest en Ruff | Aanvullende laad- en rapportagecontroles |

## Database-load en deployment

```mermaid
sequenceDiagram
    participant P as Python loader
    participant R as Processed Parquet
    participant D as PostgreSQL 17
    P->>R: valideer manifest en checksums
    P->>D: start ops.etl_run
    P->>D: laad core snapshot transactioneel
    P->>D: valideer mart views en markeer success
```

```mermaid
flowchart LR
    host[Windows-host: Python 3.14] --> docker[Docker Desktop]
    docker --> postgres[PostgreSQL 17 container: bestaand]
    postgres --> volume[Project named volume]
    postgres -. toekomstig .-> bi[Power BI]
```
