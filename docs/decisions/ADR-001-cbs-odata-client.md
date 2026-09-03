# ADR-001: afzonderlijke herbruikbare CBS OData-client

- Status: Accepted
- Datum: 2026-09-03

## Context

Fase 2A haalt alleen metadata op uit het `TableInfos`-endpoint van CBS-dataset
`03759ned`. De applicatie heeft een consistente manier nodig om HTTP-sessies,
timeouts, headers, statuscontrole en JSON-fouten te behandelen.

## Beslissing

Het project gebruikt een afzonderlijke, herbruikbare `CbsClient`. Deze client
maakt gebruik van `requests.Session`, verstuurt een duidelijke User-Agent,
gebruikt een configureerbare timeout, roept `raise_for_status()` aan en vertaalt
netwerk-, HTTP- en JSON-fouten naar duidelijke domeinfouten.

## Alternatieven

### Losse `requests.get()`-aanroepen

De runner kan rechtstreeks `requests.get()` aanroepen. Dit is eenvoudiger voor
één call, maar leidt bij volgende endpoints snel tot duplicatie van headers,
timeouts en foutafhandeling.

### Direct ophalen vanuit Power BI

Power BI kan in een toekomstige fase rechtstreeks de bron benaderen. Dit maakt
bronlogica en controle minder herbruikbaar en is nu niet passend: Power BI is
nog niet geïmplementeerd en fase 2A richt zich op Python-metadata-ophaling.

## Voordelen

- Eén testbare plek voor CBS-specifieke HTTP-afspraken.
- Herbruikbaar voor toekomstige metadata- of data-endpoints.
- Consistente en expliciete foutafhandeling.
- Scheiding tussen transportlogica en bestandsopslag.

## Nadelen en consequenties

- Een extra module en fouttypen vragen beperkte onderhoudsaandacht.
- Toekomstige endpoints kunnen aanvullende parameters of paginering vereisen.
- De client is bewust klein gehouden; transformatie, database-opslag en
  rapportage horen niet in deze component.
