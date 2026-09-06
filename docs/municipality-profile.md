# Gemeenteprofiel en publieke datakwaliteit

Exact één aanvullende bron: [CBS 70072ned, Regionale kerncijfers Nederland](https://www.cbs.nl/nl-nl/cijfers/detail/70072ned).
De officiële OData API levert gemeentecodes (`GMdddd`), jaarlijkse `YYYYJJ00`
perioden en aantallen naar leeftijd op 1 januari. De bestaande 03759ned-bron
blijft ongewijzigd. Dit is leeftijdsopbouw, geen voorspelling of afgeleide claim.

De vijf groepen zijn 0–14, 15–24, 25–44, 45–64 en 65+. De laatste is uitsluitend
de som van CBS 65–79 en 80+; ontbreekt een deel, dan blijft de som NULL.
De eerste vier CBS-velden en beide 65+-velden worden expliciet gecontroleerd.
CBS publiceert ook historische gemeentecodes met uitsluitend NULL-waarden in
latere jaren. Alleen zulke volledig lege observaties worden overgeslagen;
gedeeltelijk ontbrekende categorieën blijven expliciet NULL, nooit nul.
CBS wijzigde de leeftijdsgroepen in juli 2026: een toekomstige schemawijziging
laat extractie bewust falen. Er wordt niet automatisch op andere indicatoren
teruggevallen. De CBS-metadatabeschrijving bepaalt voorlopigheid en revisies.

Nederland gebruikt de expliciete `NL01`-rij uit dezelfde tabel, dezelfde
peildatum en dezelfde categoriedefinitie. Percentages zijn het groepsaantal
gedeeld door het brontotaal, afgerond op één decimaal. Het is geen ongewogen
gemiddelde van gemeentelijke percentages. Historische gemeentecodes worden
niet omgerekend naar actuele grenzen. Het bestaande inwoners-KPI komt uit
03759ned; revisietiming kan afwijken van 70072ned.

## Expliciete verwerking

Geen CBS-call of migration vindt plaats bij API-start. Extractie maakt een
checksum-geadresseerde run in bestaande genegeerde raw/processed-opslag.
Herhaald ophalen van dezelfde waarden geeft dezelfde run. Raw bronrecords en
kolommetadata blijven lokaal reproduceerbaar bewaard; processed data heeft
een SHA256-controle en wordt ook bij laden opnieuw gevalideerd.

```powershell
py -m gemeente_data_platform.profile_pipeline --first-year 2025 --last-year 2026 --dry-run
py -m gemeente_data_platform.profile_pipeline --first-year 2025 --last-year 2026
# Na groene merge, met bestaande productie-secretconfiguratie:
py -m gemeente_data_platform.deploy_database --profile-run <run-id> --dry-run
py -m gemeente_data_platform.deploy_database --profile-run <run-id>
```

De bestaande deployment-CLI voert de minimale voorwaartse migration uit en
laadt uitsluitend het nieuwe profiel. Geen bestaande bevolking wordt vervangen.
Geen nieuwe rollen of cloudresources zijn nodig. `--dry-run` valideert het lokale
bestand maar opent geen databaseverbinding. Ontbrekende providerrechten stoppen
de deployment veilig; laat de bestaande migratierol de nieuwe revision uitvoeren
en herhaal daarna dezelfde CLI-opdracht. Secrets blijven in de bestaande
geheime runtimeconfiguratie en worden nooit uitgeprint.

Per aangevraagd jaar worden 250–1000 gemeenten plus precies één Nederlandse
rij verwacht (brede veiligheidsmarges, geen fragiele exacte aantallen).
Unieke regio/jaar/categorie, toegestane categorieën, jaren, niet-negatieve gehele
waarden, verwachte kolommen en sommen worden gecontroleerd. De gemeentecode én
het jaar moeten voorkomen in de bestaande bevolkingssnapshot. Staging, de
controle, vervanging van alleen aangevraagde profieljaren en succesvolle lineage
vinden in één transactie plaats. Een fout bewaart de vorige snapshot. Een
advisory lock serialiseert profielloads. De uitgestelde FK laat de bestaande
transactionele bevolkingsloader dezelfde gemeentecodes veilig herplaatsen.

## Publieke contracten

- `GET /api/v1/municipalities/GM0363/profile?year=2026`: maximaal vijf categorieën.
- `GET /api/v1/data-quality`: maximaal twee vaste publieke datasets.

De API krijgt alleen SELECT op de twee nieuwe mart-views; geen rechten op
staging, core of operationele tabellen. Repository en Pydantic-modellen
projecteren uitsluitend vooraf bepaalde publieke velden. Geen SQL, interne
namen, paden, hostnamen of ETL-logs verlaten deze endpoints. Nieuwe views zijn
niet vereist voor `/ready`; ontbrekende migrations, optionele data of metadata
geven een lege veilige respons. Het bestaande dashboard blijft beschikbaar.

De monitor telt voor bevolking gemeente/jaar-records en ontbrekende gemiddelde
bevolking. Voor leeftijd telt hij gemeente/jaar/categorie-records, exclusief NL,
en ontbrekende aantallen plus ontbrekende totalen per categorierij. De status
verwijst naar de laatst succesvol geladen snapshot, niet naar een live CBS-check.
De oorspronkelijke lineage-interface blijft intact; nieuwe verwerkingsmetadata
staat los daarvan. Ontbrekende data is nooit nul en krijgt een rustige melding.

Kaart en profiel staan op desktop naast elkaar; mobiele selectie biedt een
expliciete profiel-link, zonder automatisch scrollen. Enter en Space blijven
werken. De infolaag toont groei wanneer de geselecteerde reeks beschikbaar is.
