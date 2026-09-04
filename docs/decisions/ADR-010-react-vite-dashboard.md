# ADR-010: React/Vite-dashboard achter same-origin API-proxy

## Status

Accepted, 2026-09-04.

## Besluit

Gebruik React met TypeScript en Vite voor het dashboard. Bouw het als statische
assets in een non-root Nginx-container. De container proxy't dezelfde-origin
`/api/`, health en API-documentatie uitsluitend naar FastAPI. De browser praat
nooit rechtstreeks met PostgreSQL; ontwikkeling gebruikt de Vite-proxy of de
expliciete `VITE_API_BASE_URL`.

## Consequenties

De UI blijft los van opslag en credentials, terwijl de API haar bestaande
least-privilege mart-toegang bewaakt. Het dashboardimage is reproduceerbaar met
gelockte npm-dependencies en de Node 24 Debian-slim buildstage.
