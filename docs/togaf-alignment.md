# TOGAF-light architectuurbeschrijving

Dit project gebruikt relevante TOGAF-denkprincipes voor structurering en
communicatie, maar voert geen volledig TOGAF ADM-traject uit. De beschrijving
is daarom proportioneel voor een portfolio-project en geen certificering of
claim van volledige TOGAF-implementatie.

## Architectuurweergaven en aanpak

De [C4-weergaven](architecture.md) maken de architectuur op drie afzonderlijke
niveaus zichtbaar: niveau 1 toont de systeemcontext, niveau 2 de containers en
niveau 3 de componenten van de Python-applicatie. C4 beschrijft daarmee de
technische structuur en relaties.

TOGAF-light helpt in dit project bij de architectuurvisie, stakeholders, eisen
en migratiestappen. Het is geen volledige TOGAF ADM-implementatie. Huidige en
doelarchitectuur blijven hieronder bewust gescheiden.

## Architectuurvisie

Een transparante, herhaalbare dataketen maken voor openbare CBS-data over
Nederlandse gemeenten. De keten begint klein met controleerbare metadata en
kan later uitgroeien naar een analyse- en rapportagevoorziening.

## Zakelijke aanleiding

Datafuncties bij gemeenten hebben baat bij herleidbare bronnen, voorspelbare
verwerking en toegankelijke rapportage. Dit project demonstreert die werkwijze
met een openbare CBS-dataset, zonder gemeentelijke persoonsgegevens te
verwerken.

## Stakeholders en belangen

| Stakeholder | Belang |
| --- | --- |
| Data-analist | Begrijpelijke bronmetadata en betrouwbare herhaalbaarheid |
| Beleidsmedewerker | Toekomstige, toegankelijke inzichten over gemeentelijke data |
| Technisch beheerder | Kleine, testbare componenten en heldere configuratie |
| CBS | Correct en respectvol gebruik van de openbare OData API |

## Functionele eisen

- De applicatie haalt metadata op voor CBS-dataset `03759ned`.
- De API-client gebruikt een sessie, User-Agent, timeout en HTTP-statuscontrole.
- De metadata wordt als leesbare UTF-8-JSON in `data/raw/` opgeslagen.
- Fouten door netwerk, HTTP of JSON worden niet stilzwijgend genegeerd.

## Niet-functionele eisen

- Configuratie via omgevingsvariabelen met veilige standaardwaarden.
- Offline testbaarheid door HTTP-responses te mocken.
- Python 3.11+ als minimale projectvereiste; validatie met Python 3.14.
- Broncodekwaliteit gecontroleerd met pytest en Ruff.

## Huidige architectuur: fase 2A

Fase 2A bestaat uit een configuratiemodule, metadata-runner en herbruikbare
CBS API-client. De runner haalt `TableInfos` op en schrijft het resultaat naar
een lokaal raw JSON-bestand. PostgreSQL, SQL-modellen en Power BI bestaan nog
niet in de implementatie. Dit is de bestaande situatie die in de C4-weergaven
met **bestaand** of **extern** is aangeduid.

## Doelarchitectuur: toekomstig

De beoogde keten is: CBS OData API naar Python-transformatie, vervolgens
PostgreSQL en SQL-views, met Power BI als presentatielaag. Deze onderdelen zijn
toekomstig en vallen buiten fase 2A. In de C4-weergaven zijn zij als
**toekomstig** gemarkeerd.

## Belangrijkste tussenstappen

1. Metadata-ophaling stabiel houden en bronstructuur begrijpen.
2. Een beperkte extractie en validatie van feitelijke brondata ontwerpen.
3. Een PostgreSQL-laag en herhaalbare laadstap toevoegen.
4. SQL-views en Power BI-rapportage ontwikkelen.

## Risico's en beheersmaatregelen

| Risico | Beheersmaatregel |
| --- | --- |
| CBS API is tijdelijk niet bereikbaar | Configureerbare timeout en expliciete netwerkfout |
| API retourneert een foutstatus | `raise_for_status()` en een duidelijke `CbsHttpError` |
| API-response is geen geldige JSON | Expliciete JSON-validatie en `CbsInvalidJsonError` |
| Bronstructuur wijzigt | Metadata lokaal vastleggen en toekomstige validatieregels toevoegen |
| Scope groeit te snel | Fasen scheiden; alleen metadata-ophaling is nu geïmplementeerd |
