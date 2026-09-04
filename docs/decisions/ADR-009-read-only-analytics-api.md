# ADR-009: Read-only analytics API met afzonderlijke database-rol

- Status: Accepted
- Datum: 2026-09-04

## Besluit

Exposeer FastAPI onder `/api/v1` boven uitsluitend expliciete `mart`-views. De
service gebruikt de loginrol `gemeente_api`, niet `gemeente_app` of bootstrap.
De rol krijgt alleen CONNECT, schema-USAGE en SELECT op mart-views.

## Gevolgen

Endpoints kunnen niet muteren en zien geen `core`-tabellen of `ops.etl_run`.
Een migration beheert de view en grants; het Docker-init-script provisiont de
rol voor nieuwe databases en kan veilig voor bestaande volumes worden herhaald.
Openbare data krijgen nog geen gebruikersauthenticatie. CORS blijft opt-in.
