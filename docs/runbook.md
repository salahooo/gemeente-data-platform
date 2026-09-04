# Runbook lokale PostgreSQL

## Read-only API

Start met `docker compose --profile api up -d api`; verifieer `/health` en
`/ready` en stop alleen die service met `docker compose --profile api stop api`.

## Dashboard

Start met `docker compose --profile dashboard up -d dashboard` en controleer
`docker compose ps`, `/ready`, `/api/v1/years`, een directe dashboardroute en
`/docs` op poort 3000. Stop alleen de dashboardservice; PostgreSQL op 5433
blijft draaien. Het dashboard voert uitsluitend read-only API-aanvragen uit.

Start de projectdatabase: `docker compose up -d postgres`. Stop zonder het
volume te verwijderen: `docker compose stop postgres`. Gebruik nooit `down -v`.
Controleer met `docker compose ps` en
`py -3.14 -m gemeente_data_platform.check_database`.

Gebruik normaal één gecontroleerde run:
`py -3.14 -m gemeente_data_platform.run_pipeline`. Deze voert extract,
transformatie, migration, snapshot-load en databasevalidatie uit en legt het
run-id vast in `data/runs/` en `ops.etl_run`. Gebruik eerst
`py -3.14 -m gemeente_data_platform.run_pipeline --dry-run` om uitsluitend het
plan/manifest te maken. Zie [pipeline operations](pipeline-operations.md) voor
resume en starten bij een latere fase.

pgAdmin: host `localhost`, poort `5433`, database `gemeente_data`, gebruiker
`gemeente_app`; lees het wachtwoord uit het genegeerde lokale secretbestand.
Deze containerdatabase staat los van de bestaande PostgreSQL op poort 5432.
Init-scripts werken alleen bij een nieuw projectvolume. Backup/herstel is een
toekomstige productiestap.

## Integratietests

Gewone `py -3.14 -m pytest`-tests zijn databasevrij. Start voor integratietests
alleen `docker compose --profile test up -d postgres_test`, zet
`$env:RUN_DB_INTEGRATION='1'` en voer `py -3.14 -m pytest -m integration` uit.
De testdatabase is `gemeente_data_test` op poort 5434 met tijdelijke opslag.
Stop uitsluitend haar met `docker compose --profile test stop postgres_test`.
De guards weigeren ieder ander doel, waaronder de lokale 5432-server en de
ontwikkeldatabase op 5433.

De integratiesuite test ook rollback: bij een fout blijft de vorige core-snapshot
zichtbaar en wordt een beperkte `failed`-registratie in `ops.etl_run` bewaard.

## CI en troubleshooting

CI draait de databasevrije tests op Python 3.11 en 3.14, gevolgd door dezelfde
integratiesuite tegen uitsluitend `localhost:5434/gemeente_data_test`. De CI-job
start expliciet alleen `postgres_test`; development op 5433 blijft buiten scope.
Zie [CI/CD en repositorykwaliteit](ci-cd.md) voor de workflowvolgorde,
dependency-lock, lokaal reproduceren en foutdiagnose. Gebruik bij een lokale
integratiefout uitsluitend `docker compose logs postgres_test` en stop daarna
alleen `postgres_test`.
