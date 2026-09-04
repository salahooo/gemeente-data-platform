# CBS-datacontract: raw bevolkingsextractie

## Bron en scope

Bron: officiële CBS OData API, dataset `03759ned`.
`https://opendata.cbs.nl/ODataApi/OData/03759ned`

Fase 2B haalt alleen raw metadata, dimensies en gemeentelijke bevolkingsrecords op. Er vindt geen inhoudelijke transformatie plaats.

## Endpoints en dimensies

| Endpoint | Betekenis |
| --- | --- |
| `TableInfos` | Titel en metadata |
| `DataProperties` | Dimensies en meetvelden |
| `Geslacht`, `Leeftijd`, `BurgerlijkeStaat` | Selectiedimensies |
| `RegioS` | Officiële regio-indeling |
| `Perioden` | Jaarperioden |
| `TypedDataSet` | Ongetransformeerde records |

Totaalcodes worden uit CBS-titels ontdekt en daarna tegen de dimensietabel gevalideerd:

| Selectie | CBS-titel | Ontdekte code |
| --- | --- | --- |
| Geslacht | `Totaal mannen en vrouwen` | `T001038` |
| Leeftijd | `Totaal` | `10000` |
| Burgerlijke staat | `Totaal burgerlijke staat` | `T001019` |

`DataProperties` levert de meetvelden `BevolkingOp1Januari_1` voor `Bevolking op 1 januari` en `GemiddeldeBevolking_2` voor `Gemiddelde bevolking`.

## Gemeenten, perioden en query

Een gemeente heeft uitsluitend een officiële `RegioS.Key` met structuur `GMdddd`; daardoor zijn `NL`, `LD`, `PV` en `CR` uitgesloten. De OData-query gebruikt tevens `startswith(RegioS, 'GM')` en valideert elk record lokaal tegen `RegioS`.

Jaarperioden hebben de vorm `JJJJJJ00`, bijvoorbeeld `2020JJ00`. Alleen perioden met een gelijk jaar in code en titel, vanaf 2020, worden geselecteerd. De gerichte `TypedDataSet`-query bevat de ontdekte totaalcodes, deze perioden en gemeenten. `$select` beperkt de response tot dimensies en beide meetvelden.

De client ondersteunt `$filter`, `$select`, `$top` en `$skip`, volgt `odata.nextLink` en `@odata.nextLink`, detecteert herhaalde links en stopt bij de configureerbare paginalimiet. Bij meerdere pagina's worden ongewijzigde recordobjecten in één `value`-lijst samengevoegd; context staat in het manifest.

## Raw bestandsstructuur

```text
data/raw/cbs/03759ned/<utc-run-id>/
├── table_info.json
├── data_properties.json
├── gender.json
├── age.json
├── marital_status.json
├── regions.json
├── periods.json
├── population_records.json
├── quality_report.json
└── manifest.json
```

JSON wordt UTF-8 met inspringing atomair geschreven. De gegenereerde raw map wordt door `.gitignore` niet gecommit.

## Manifest en validaties

`manifest.json` versie 2.0 bevat schema-versie, datasetcode, titel, UTC-ophaaltijd, basis-URL, endpoints, queryparameters, ontdekte codes en titels, perioden, API-pagina's, records, bestandsnamen, SHA-256-checksums, validatiestatussen en kwaliteitsstatistieken per periode. Checksums gelden voor raw databestanden én `quality_report.json`; het manifest bevat geen zelf-referentiële checksum.

Meetvelden moeten numeriek zijn of een verklaarde CBS-ontbrekende waarde bevatten. In JSON is `null` de verwachte ontbrekende waarde; `.` wordt tevens als CBS-symbool geaccepteerd.

Een `gemeentecode` is iedere unieke GM-code in de raw extractie, inclusief historische codes. Een `actieve gemeentewaarneming` is projectspecifiek afgeleid: een gemeente-jaarrecord met een geldige niet-negatieve gehele bevolking op 1 januari. Een `actieve gemeente per periode` is een unieke GM-code met zo'n waarneming. Dit is geen claim dat alle raw GM-codes actieve gemeenten zijn.

`quality_report.json` is menselijk leesbare, afgeleide kwaliteitsinformatie zonder gewijzigde raw data. Het bevat definities, totalen en statistieken per periode, waarschuwingen, validatieresultaten en een toelichting dat historische GM-codes behouden blijven. Ontbrekende waarden zijn nooit nul. Volledig ontbrekende januariwaarden zijn een fout; volledig ontbrekende gemiddelde bevolking is zichtbaar als waarschuwing, bijvoorbeeld wanneer CBS de nieuwste gemiddelde jaarbevolking nog niet heeft gepubliceerd.

De run stopt bij een gebroken contract: collecties moeten `value`-lijsten bevatten; dimensiecodes bestaan; GM-codes zijn uniek en geldig; perioden zijn geldig en vanaf 2020; records hebben verplichte velden; gemeente-periodecombinaties zijn uniek; iedere periode heeft actieve waarnemingen; januariwaarden zijn voor actieve waarnemingen niet-negatieve gehele getallen; de extractie is niet leeg; checksums zijn opnieuw bevestigd.

## Grens met latere transformatie

Fase 2B bewaart CBS-records zonder hernoemen, aggregeren of inhoudelijk wijzigen. Indicatoren, opschonen, modelleren en laden in PostgreSQL behoren tot latere fasen.
