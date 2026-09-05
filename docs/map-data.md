# Gemeentekaart: bron en grenzen

De kaart gebruikt de gemeentelaag uit **CBS Wijken en Buurten 2026 versie 0**
via de PDOK OGC API. De asset is op 5 september 2026 opgehaald, vereenvoudigd
met behoud van vormen en beperkt tot `gm_code`, `gm_naam` en `jaar`.

- Bron: [PDOK / CBS Wijken en Buurten 2026](https://api.pdok.nl/cbs/wijken-en-buurten-2026/ogc/v1/collections/gemeenten?f=html)
- Grensjaar: 2026; gemeentecode is de enige join-key.
- Herkomst: gemeentegrenzen zijn gebaseerd op de BRK van het Kadaster; PDOK/CBS
  blijft als bronattributie zichtbaar in de interface.

De kaart harmoniseert geen historische codes. Een code zonder 2026-geometrie
blijft daarom onbekend op de kaart en is geen uitspraak over een juridische
herindeling.
