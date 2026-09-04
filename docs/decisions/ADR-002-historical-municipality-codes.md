# ADR-002: historische gemeentecodes per waarnemingsjaar behouden

- Status: Accepted
- Datum: 2026-09-04

## Context

CBS-raw data bevat huidige en historische gemeentecodes. Een tijdreeks kan door
grenswijzigingen, samenvoegingen en opheffingen worden beïnvloed. Zonder een
officiële, brononderbouwde herindelingsbrug zou automatische harmonisatie een
oncontroleerbare afleiding zijn.

## Beslissing

Processed data behoudt iedere CBS-gemeentecode met ten minste één actieve
waarneming binnen het geselecteerde venster. Elke code houdt haar eigen
waarnemingsgeschiedenis. De toepassing voegt opgeheven codes niet automatisch
samen met opvolgers en leidt geen juridische begin- of einddata af.

## Alternatieven

- Automatisch naar actuele gemeenten harmoniseren: eenvoudiger voor sommige
  dashboards, maar zonder betrouwbare officiële mapping niet verantwoord.
- Alleen actuele gemeenten tonen: historische waarnemingen zouden verdwijnen.
- Een toekomstige officiële herindelingsbrug: mogelijk wanneer een passende,
  beheerde bron en expliciete analysemethode beschikbaar zijn.

## Consequenties

Vergelijkingen door de tijd kunnen door gemeentelijke herindelingen worden
beïnvloed. Verschijnende en verdwijnende codes zijn daarom kwaliteitssignalen,
geen automatische oprichting of opheffing.
