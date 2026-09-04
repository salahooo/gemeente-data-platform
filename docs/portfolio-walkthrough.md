# Portfolio-walkthrough (vijf minuten)

| Stap | Toon | Zeg | Bewijst |
| --- | --- | --- | --- |
| 1 | `localhost:3000` KPI's | CBS-data is via een read-only keten beschikbaar. | Productdenken |
| 2 | Ranking 2026 | 342 actieve gemeenten is een momentopname. | Datainterpretatie |
| 3 | Zoek Alphen aan den Rijn | Selecteer `GM0484`. | API-gedreven UI |
| 4 | Tijdreeks en verandering | Historische codes worden niet kunstmatig geharmoniseerd. | Tijdreeksintegriteit |
| 5 | Null-melding 2026 | Ontbrekend is geen nul. | Datakwaliteit |
| 6 | `localhost:8000/docs` | FastAPI geeft typed, read-only endpoints. | API-ontwerp |
| 7 | `docs/database-design.md` | Mart-views scheiden consumptie van core. | SQL/modellering |
| 8 | `data/runs/` en `ops.etl_run` | Manifesten/checksums geven lineage. | Operability |
| 9 | GitHub Actions | Pythonmatrix en 5434-testdatabase zijn geïsoleerd. | Testautomatisering |
| 10 | `docs/architecture.md` en ADRs | Keuzes zijn navolgbaar vastgelegd. | Architectuurcommunicatie |

## Korte antwoorden op vragen

- **Waarom FastAPI?** Typed contracts, OpenAPI en een kleine read-only laag.
- **Waarom PostgreSQL?** Transactionele loads, views en rollen passen bij marts.
- **Waarom Parquet?** Efficiënte, reproduceerbare processed opslag naast leesbare CSV.
- **Waarom raw en processed scheiden?** Bronherkomst blijft immutable en transformatie reproduceerbaar.
- **Idempotentie?** Snapshot-loads valideren eerst en wisselen transactioneel; bij fout blijft de vorige snapshot zichtbaar.
- **Waarom null niet nul?** Nul zou een feitelijke bevolkingswaarde claimen die de bron niet levert.
- **Aparte API-rol?** De API leest alleen mart-views volgens least privilege.
- **Waarom geen React-DB-verbinding?** Credentials en SQL blijven server-side; de browser gebruikt alleen FastAPI.
- **Migrations?** Alembic versieert schemawijzigingen gecontroleerd.
- **Mislukte load?** De transactie rolt terug en lineage registreert de foutstatus.
- **Testisolatie?** Integratie gebruikt alleen `localhost:5434/gemeente_data_test` met safety guard.
- **Productie anders?** Beheerde secrets, scheduling, backups, observability en deployment volgen in latere fases.
- **Herindelingen?** Historische GM-codes blijven bewaard totdat een betrouwbare officiële mapping beschikbaar is.
