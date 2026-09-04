# Managed PostgreSQL bootstrap

Deze procedure maakt geen CBS-call en is niet gekoppeld aan API-start of
Render-deploy. Gebruik alleen met `APP_ENV=production`; configuratie weigert
localhost, ontbrekende SSL en onveilige CORS vóór een verbinding wordt geopend.

1. Controleer providerconnectiviteit met `DATABASE_URL`.
2. De preflight controleert eerst de benodigde rollen `gemeente_app`,
   `gemeente_reader` en `gemeente_api`, plus database-`CREATE` voor de
   migratie/loginrol. Bij ontbrekende rollen stopt zij vóór Alembic.
3. Gebruik alleen wanneer de provider `CREATEROLE` toestaat de expliciete
   `--create-roles` optie met `BOOTSTRAP_APP_PASSWORD` en
   `BOOTSTRAP_API_PASSWORD` als runtime secrets. Wanneer dat niet mag, maak de
   drie rollen en hun beperkte grants handmatig in de providerconsole.
4. Voer Alembic migrations uit met een beperkte migratie/loadrol.
5. Laad een bestaande, checksum-geldige processed run; commit nooit raw of
   processed data en haal geen CBS op voor een webdeploy.
6. Reconcileer core-tabellen en mart-views met het processed manifest.
7. Controleer `/ready` met de read-only API-rol.

```powershell
py -3.14 -m gemeente_data_platform.deploy_database --processed-run <id> --dry-run
py -3.14 -m gemeente_data_platform.deploy_database --processed-run <id>
py -3.14 -m gemeente_data_platform.deploy_database --processed-run <id> --create-roles
```

`--dry-run` doet geen netwerk-, migratie- of datamutatie. `--migrate-only` stopt
na migrations. Bestaande Alembic-revisies blijven immutable; prerequisites worden
expliciet vóór Alembic afgehandeld. Een single-role provider-login is alleen een
fallback wanneer die login de expliciete preflight en alle benodigde grants
aantoonbaar haalt; het is niet gelijkwaardig aan de lokale least-privilege-rollen.
Bewaar credentials uitsluitend in geheime variabelenopslag,
roteer ze periodiek en revokeer ze bij teardown.
