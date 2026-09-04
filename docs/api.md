# Read-only analytics API

De FastAPI-service biedt openbare, alleen-lezen analyses uit `mart`-views. Zij
doet geen CBS-aanroepen, leest geen raw/processed bestanden en bevat geen
authenticatie: de gegevens zijn openbaar. Dashboard en Power BI kunnen deze
stabiele JSON-contracten later consumeren.

| Endpoint | Doel |
| --- | --- |
| `GET /health` | Processtatus, zonder databaseverbinding |
| `GET /ready` | Mart-bereikbaarheid en vereiste views |
| `GET /api/v1/years` | Jaren en beschikbaarheid gemiddelde bevolking |
| `GET /api/v1/municipalities` | Zoekbare, gepagineerde gemeentecatalogus |
| `GET /api/v1/municipalities/{code}` | Gemeentedetail |
| `GET /api/v1/municipalities/{code}/population` | Tijdreeks en jaar-op-jaar |
| `GET /api/v1/national/population` | Landelijke totalen |
| `GET /api/v1/rankings/population?year=2026` | Deterministische rangorde |

`page` begint bij 1 en `page_size` is 1–100. Rankings vereisen `year`; `limit`
is 1–100. Ongeldige invoer retourneert 422, onbekende gemeenten 404 en een
onbereikbare database 503. Elke response bevat `X-Request-ID`.

`average_population` is voor 2026 `null`; ontbrekend betekent nadrukkelijk niet
nul. De eerste jaar-op-jaarobservatie houdt alle vorige/veranderwaarden `null`.

## Starten

Maak lokaal uitsluitend `secrets/api_password.txt` op basis van het voorbeeld.
Nieuwe databases maken `gemeente_api` tijdens initialisatie. Bestaande volumes
krijgen de rol veilig opnieuw via de init-script en daarna `alembic upgrade head`.

```powershell
docker compose up -d postgres
docker compose exec -T postgres sh /docker-entrypoint-initdb.d/02-create-api-role.sh
py -3.14 -m alembic upgrade head
docker compose --profile api up -d api
Invoke-RestMethod http://localhost:8000/api/v1/years
docker compose --profile api stop api
```

Swagger staat op `/docs` en OpenAPI op `/openapi.json`. `API_ALLOWED_ORIGINS`
is optioneel, kommagescheiden en heeft standaard geen CORS-origin; wildcard en
credentials worden niet gecombineerd.

De API gebruikt alleen loginrol `gemeente_api`: CONNECT, USAGE op `mart` en
SELECT op mart-views. Zij heeft geen rechten op `core`, `ops` of DDL. Secret- en
URLwaarden worden centraal geredigeerd voordat zij gelogd kunnen worden.
