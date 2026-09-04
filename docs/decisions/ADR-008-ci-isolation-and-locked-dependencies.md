# ADR-008: Geïsoleerde CI en gelockte dependencies

- Status: Accepted
- Datum: 2026-09-04

## Context

De repository ondersteunt Python 3.11 en nieuwer, terwijl lokale ontwikkeling
Python 3.14 zonder virtual environment gebruikt. Fase 5 heeft een strikte
ontwikkel- en testdatabase-scheiding die CI moet behouden. Losse dependency
resoluties maken CI-resultaten minder herhaalbaar.

## Besluit

GitHub Actions voert eerst een databasevrije quality-matrix uit voor Python 3.11
en 3.14. Een afhankelijke integratiejob start alleen de expliciete
`postgres_test`-service zonder Compose-dependencies, op 5434. Tijdelijke
wachtwoordbestanden bestaan uitsluitend gedurende die CI-job en worden altijd
verwijderd.

`pyproject.toml` blijft de functionele dependencybron. `uv.lock` is de
gegenereerde, universele resolutie die CI met `--frozen` installeert. `pip-audit`
scant die omgeving. Dependabot onderhoudt pip-, Action- en Docker-updates.

## Consequenties

- CI kan de ontwikkelservice op 5433, PostgreSQL op 5432 of projectvolumes niet
  raken via de integratiejob.
- Een lockwijziging wordt bewust samen met de bronconstraint beoordeeld.
- Lokale ontwikkeling kan de bestaande pip-opdrachten blijven gebruiken; de
  bevroren lock is verplicht voor CI.
