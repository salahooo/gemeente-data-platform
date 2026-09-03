# Architectuur

## Doel en scope

Het Gemeente Data Platform automatiseert het ophalen van openbare CBS-data. In
latere fasen worden gegevens getransformeerd, in PostgreSQL opgeslagen en voor
analyse beschikbaar gemaakt in Power BI.

De huidige implementatie is **fase 2A: metadata-ophaling**. De applicatie haalt
alleen `TableInfos`-metadata op uit CBS-dataset `03759ned` en schrijft die als
UTF-8-JSON naar `data/raw/03759ned_table_info.json`. Er worden nog geen
feitelijke bevolkingsgegevens verwerkt of opgeslagen.

## 1. Systeemcontext

### C4 niveau 1 — Systeemcontext

Het Gemeente Data Platform is hier één systeem. CBS en Power BI zijn externe
systemen; Power BI is bovendien toekomstig.

```mermaid
flowchart LR
    gebruiker[Data-analist of gebruiker - extern] --> platform[Gemeente Data Platform - bestaand]
    platform --> cbs[CBS OData API - extern]
    platform -. toekomstig .-> powerbi[Power BI-dashboard - toekomstig en extern]
```

## 2. Containers

### C4 niveau 2 — Containerdiagram

Dit niveau toont alleen zelfstandig uitvoerbare applicaties of opslaglocaties,
niet de interne Python-modules.

```mermaid
flowchart LR
    etl[Python ETL-applicatie - bestaand] --> cbs[CBS OData API - extern]
    etl --> raw[Lokaal raw JSON-bestand - bestaand en tijdelijke opslag]
    raw -. toekomstig .-> postgres[PostgreSQL-database - toekomstig]
    postgres -. toekomstig .-> powerbi[Power BI - toekomstig]
```

De bestaande Python ETL-applicatie voert in fase 2A alleen metadata-ophaling
uit. Het lokale raw JSON-bestand is tijdelijke opslag; PostgreSQL en Power BI
zijn nog niet geïmplementeerd.

## 3. Componenten van de Python-applicatie

### C4 niveau 3 — Componentdiagram

Dit niveau toont uitsluitend de interne componenten van de Python-applicatie.
De CBS OData API en het lokale raw JSON-bestand staan visueel buiten de
applicatie.

```mermaid
flowchart LR
    subgraph app[Python ETL-applicatie - bestaand]
        config[config.py - bestaand]
        runner[fetch_metadata.py - bestaand]
        client[cbs_client.py - bestaand]
        extract[Extractielaag - toekomstig]
        transform[Transformatielaag - toekomstig]
        database[Databaselaag - toekomstig]
    end

    cbs[CBS OData API - extern]
    raw[Lokaal raw JSON-bestand - bestaand en tijdelijke opslag]
    postgres[PostgreSQL-database - toekomstig]

    config --> runner
    runner --> client
    client --> cbs
    runner --> raw
    raw -. toekomstig .-> extract
    extract -. toekomstig .-> transform
    transform -. toekomstig .-> database
    database -. toekomstig .-> postgres
```

## 4. Dynamisch gedrag

### Sequence diagram: metadata-ophaling

```mermaid
sequenceDiagram
    participant U as Gebruiker - extern
    participant R as Metadata-runner - bestaand
    participant S as Configuratiemodule - bestaand
    participant C as CBS API-client - bestaand
    participant A as CBS OData API - extern
    participant F as Raw JSON-bestand - bestaand

    U->>R: Start fetch_metadata
    R->>S: Lees basis-URL, datasetcode en timeout
    S-->>R: Instellingen
    R->>C: get_table_info()
    C->>A: HTTP GET /03759ned/TableInfos
    A-->>C: JSON-response
    C->>C: Valideer HTTP-status en JSON
    C-->>R: Metadata-object
    R->>F: Schrijf UTF-8 JSON met inspringing
```

### Legenda

- **Bestaand:** geïmplementeerd en getest.
- **Toekomstig:** gepland, nog niet geïmplementeerd.
- **Extern:** systeem buiten onze verantwoordelijkheid.

Bij een netwerkprobleem, HTTP-fout of ongeldige JSON gooit de CBS API-client
respectievelijk een `CbsNetworkError`, `CbsHttpError` of `CbsInvalidJsonError`.
De runner onderdrukt deze fouten niet; er wordt dan geen geslaagde metadata-run
gemeld.

## Architectuurprincipes

- Verantwoordelijkheden zijn gescheiden tussen configuratie, ophalen en opslag.
- Configuratie staat buiten de bedrijfslogica.
- Een herbruikbare externe API-client bundelt HTTP-afspraken.
- Tests kunnen zonder echte netwerkverbinding worden uitgevoerd.
- Raw data blijft inhoudelijk onveranderd; metadata wordt alleen als JSON
  opgeslagen.
- Secrets en gegenereerde data worden niet gecommit.
- Documentatie verandert mee met de implementatie.
- Een toekomstige component wordt nooit als bestaand gepresenteerd.

## Huidige versus doelarchitectuur

| Onderdeel | Huidig: fase 2A | Later: doelarchitectuur |
| --- | --- | --- |
| Databron | CBS OData API, dataset `03759ned`, endpoint `TableInfos` | CBS-data voor geselecteerde bevolkingsgegevens |
| Ingestie | Python metadata-runner met `requests.Session` | Herhaalbare extractieruns voor brongegevens |
| Verwerking | Geen datatransformatie | Python-transformatielaag en validatieregels |
| Opslag | Lokaal JSON-bestand in `data/raw/` | PostgreSQL met beheerde tabellen |
| Presentatie | Niet aanwezig | Power BI-dashboard boven op analysegegevens |
| Kwaliteitscontrole | HTTP-status, JSON-validatie, pytest en Ruff | Aanvullende data-, laad- en rapportagecontroles |
