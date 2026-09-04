# TOGAF-light architectuurbeschrijving

## Fase 7: read-only API

De FastAPI-container is een bestaande applicatielaag tussen afnemers en mart.
Een eigen least-privilege rol ondersteunt het securityprincipe; dashboard en
Power BI zijn nog doelarchitectuur.

Dit project gebruikt relevante TOGAF-denkprincipes voor structurering en
communicatie, maar voert geen volledig TOGAF ADM-traject uit. De beschrijving is
proportioneel voor een portfolio-project en is geen certificering of claim van
volledige TOGAF-implementatie.

## Architectuurweergaven en aanpak

De [C4-weergaven](architecture.md) visualiseren de technische architectuur op
drie afzonderlijke niveaus: niveau 1 systeemcontext, niveau 2 containers en
niveau 3 componenten. Dezelfde documentatie toont ook dynamisch gedrag en
lineage. TOGAF-light ondersteunt hier de visie, stakeholders, eisen, risico's en
migratiestappen rond die technische weergaven.

## Architectuurvisie

Een transparante, herhaalbare dataketen maken voor openbare CBS-data over
Nederlandse gemeenten. De keten bouwt van gecontroleerde raw brondata naar
analyseklare tabellen, en kan later naar database- en rapportagelagen groeien.

## Zakelijke aanleiding

Datafuncties bij gemeenten hebben baat bij herleidbare bronnen, voorspelbare
verwerking en toegankelijke rapportage. Dit project demonstreert die werkwijze
met een openbare CBS-dataset, zonder gemeentelijke persoonsgegevens.

## Stakeholders en belangen

| Stakeholder | Belang |
| --- | --- |
| Data-analist | Begrijpelijke bron, reproduceerbare tabellen en kwaliteitsinformatie |
| Beleidsmedewerker | Toekomstige, toegankelijke inzichten over gemeentelijke data |
| Technisch beheerder | Kleine, testbare componenten en heldere configuratie |
| CBS | Correct en respectvol gebruik van de openbare OData API |

## Functionele eisen

- Metadata, dimensies en geselecteerde raw bevolkingsrecords voor `03759ned`
  worden gecontroleerd opgehaald.
- Een gevalideerde raw run wordt lokaal naar drie processed tabellen omgezet.
- De processed run bevat Parquet, CSV, kwaliteitsinformatie, checksums en een
  manifest met herkomst.
- Een specifieke raw run is selecteerbaar voor reproduceerbare verwerking.
- Eén pipeline-run orkestreert extract, transformatie, schema, snapshot-load en
  database-/mart-reconciliatie met persistente state, checksums en lineage.

## Niet-functionele eisen

- Configuratie via omgevingsvariabelen met veilige standaardwaarden.
- Offline testbaarheid door HTTP-responses en opslag te mocken.
- Raw data blijft onveranderd; publicatie gebeurt atomair na validatie.
- Python 3.11+ is de minimale projectvereiste; operationele validatie gebruikt Python 3.14.
- Broncodekwaliteit wordt gecontroleerd met pytest en Ruff.
- CI toetst de ondersteunde Python-versies, dependency-integriteit en een
  geïsoleerde PostgreSQL-integratie zonder de ontwikkelomgeving te raken.

## Huidige architectuur: fase 5

De huidige implementatie omvat een Python-orchestrator, CBS OData, immutable raw
JSON-runmappen, processed Parquet/CSV-runs en PostgreSQL 17 op localhost:5433.
De orchestrator bewaart een manifest/state machine, JSONL-logging, locking en
pipeline-to-ETL-lineage. De loader zet gevalideerde processed data transactioneel
om naar `core`; `mart`-views worden dynamisch met het processed manifest
gereconcilieerd. Historische GM-codes worden niet geharmoniseerd. Power BI blijft
toekomstig.

GitHub Actions is een gerealiseerde kwaliteitscomponent: een databasevrije
Python-matrix gaat vooraf aan een strikt geïsoleerde `postgres_test`-job. De
dependency-resolutie is gelockt voor CI, terwijl `pyproject.toml` de bron blijft.

## Doelarchitectuur: toekomstig

De beoogde keten breidt de gerealiseerde CBS OData-, Python-, PostgreSQL- en
SQL-viewlagen uit met scheduling, beheerde opslag, backup/herstel en Power BI als
presentatielaag. Deze uitbreidingen zijn toekomstig.

## Belangrijkste tussenstappen

1. Processed-datacontract en raw-herleidbaarheid stabiel houden.
2. Beschikbaarheid, backup en herstel voor productie ontwerpen.
3. Power BI-rapportage boven de analysegegevens ontwikkelen.

## Risico's en beheersmaatregelen

| Risico | Beheersmaatregel |
| --- | --- |
| CBS-bron wijzigt | Metadata, raw manifesten en contractvalidaties vastleggen |
| Onvolledige raw run | Manifest- en checksumcontrole vóór transformatie |
| Niet-herleidbare verwerking | Raw run-id en raw-manifestchecksum in processed manifest |
| Fout bij wegschrijven | Tijdelijke map, herlezing, validatie en atomaire publicatie |
| Onderbroken end-to-end run | Atomaire pipeline-state, artifactchecksums en resume |
| Parallelle writer | Cross-platform projectlock |
| CI raakt ontwikkeldata | Alleen expliciete `postgres_test` zonder dependencies |
| Onverwachte dependencyversie | `uv.lock`, frozen installatie en pip-audit |
| Scope groeit te snel | Fasen scheiden; Power BI en productiebeheer blijven toekomstig |
