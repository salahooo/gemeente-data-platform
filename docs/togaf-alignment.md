# TOGAF-light architectuurbeschrijving

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

## Niet-functionele eisen

- Configuratie via omgevingsvariabelen met veilige standaardwaarden.
- Offline testbaarheid door HTTP-responses en opslag te mocken.
- Raw data blijft onveranderd; publicatie gebeurt atomair na validatie.
- Python 3.11+ is de minimale projectvereiste; validatie gebruikt Python 3.14.
- Broncodekwaliteit wordt gecontroleerd met pytest en Ruff.

## Huidige architectuur: fase 3

De huidige implementatie bevat de bestaande onderdelen in alle drie C4-niveaus:
een Python-applicatie, de externe CBS OData API, raw JSON-runmappen en processed
Parquet-, CSV- en JSON-runmappen. Een transformatie selecteert de nieuwste
volledige geldige raw run of een expliciete run, valideert de inhoud en bouwt
`dim_municipality`, `dim_period` en `fact_population`. Historische GM-codes
worden niet geharmoniseerd. PostgreSQL, SQL-views en Power BI bestaan nog niet.

## Huidige architectuur: fase 4

PostgreSQL 17 is nu een gerealiseerde data-architectuurcomponent. De Python
loader zet gevalideerde processed Parquet-data transactioneel om naar `core`,
analytische views staan in `mart` en auditbare runs in `ops`. `gemeente_app`
heeft least-privilege rechten; secrets staan lokaal buiten Git. Power BI blijft
toekomstig.

## Doelarchitectuur: toekomstig

De beoogde keten is CBS OData API naar Python-verwerking, vervolgens PostgreSQL
en SQL-views, met Power BI als presentatielaag. Dit zijn toekomstig geplande
onderdelen en geen fase-3-functionaliteit.

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
| Scope groeit te snel | Fasen scheiden; database en Power BI blijven toekomstig |
