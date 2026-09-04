# ADR-011: Render frontend/API en externe managed PostgreSQL

- Status: Accepted
- Datum: 2026-09-04

## Besluit

React/Vite wordt een gratis Render Static Site en FastAPI een gratis Render Web
Service vanaf `main` via `render.yaml`. PostgreSQL blijft een externe managed
provider met verplichte SSL; geen Render Postgres wegens de gratis vervaltermijn.
Credentials zijn uitsluitend runtime secrets. Migrations en pipeline blijven
expliciete operatoracties.

## Consequenties

Gratis diensten kunnen cold starts en limieten hebben en vormen geen
productie-SLA. De browser verbindt alleen met de publieke API. Provideraccount,
prijscheck, backup/restore en credentialrotatie zijn handmatige prerequisites.
