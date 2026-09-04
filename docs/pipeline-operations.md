# Pipeline operations

## Standaardrun

Gebruik uitsluitend Python 3.14 zonder virtual environment:

```powershell
py -3.14 -m gemeente_data_platform.run_pipeline
```

De volgorde is: CBS-extractie en raw-validatie, processed-transformatie,
Alembic-upgrade, transactionele PostgreSQL-snapshot-load en database-/mart-view
reconciliatie. De manifestmap `data/runs/<pipeline-run-id>/` bevat
`pipeline_manifest.json`, `pipeline.log.jsonl` en na validatie
`database_validation.json`. Deze bestanden, raw en processed data zijn
gegenereerd en staan niet in Git.

## Besturing en herstel

```powershell
py -3.14 -m gemeente_data_platform.run_pipeline --dry-run
py -3.14 -m gemeente_data_platform.run_pipeline --start-at transform --raw-run <raw-run-id>
py -3.14 -m gemeente_data_platform.run_pipeline --start-at load --processed-run <processed-run-id>
py -3.14 -m gemeente_data_platform.run_pipeline --resume <pipeline-run-id>
```

`--stop-after` beperkt een run tot een fase. Een start na `transform` vereist
een expliciete processed run; starten op `transform` vereist een expliciete raw
run. Resume verifieert succesvolle artifacts en hun checksums, slaat ze over en
begint bij de eerste mislukte of onafgeronde fase. Exitcode 2 betekent ongeldige
bediening/configuratie, 3 lock-contentie en 4 een fasefout.

## Veilig operationeel gedrag

De pipeline redigeert passwords, database-URL's en secretpaden in manifesten en
logs. Start nooit twee schrijvende runs: de tweede stopt met exitcode 3. Een
dry-run doet geen externe CBS-call, migration of datamutatie. De loader vervangt
de `core` snapshot in één transactie; faalt de load, dan blijft de vorige
snapshot intact. `ops.etl_run` koppelt processed/raw checksums aan de
pipeline-run-id.

Gebruik development uitsluitend op `localhost:5433/gemeente_data`. De
integratietestdatabase is exclusief `localhost:5434/gemeente_data_test` en
vereist `RUN_DB_INTEGRATION=1`.
