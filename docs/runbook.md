# Runbook lokale PostgreSQL

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
