# ADR-007: Georkestreerde pipeline-run en operationele lineage

- Status: Accepted
- Datum: 2026-09-04

## Context

Losse extractie-, transformatie-, migration- en loader-CLI's maken de dataflow
inhoudelijk reproduceerbaar, maar bieden geen één run-id, hervatting of centraal
operationeel log. Dat maakt storingherstel en audit van een volledige run lastig.

## Besluit

`gemeente_data_platform.run_pipeline` is de end-to-end orchestrator. Elke run
krijgt een UTC-sorteerbare pipeline-run-id en een atomair bijgewerkt, getypeerd
manifest onder `data/runs/<pipeline-run-id>/`. Het manifest bevat de state
machine `extract`, `transform`, `migrate`, `load`, `validate`, artifacts,
checksums en eventuele foutinformatie. JSONL-events en consoleberichten worden
voor opslag centraal geredigeerd.

Een cross-platform filelock staat in `data/runtime/` en verhindert gelijktijdige
schrijvende runs. Hervatting valideert eerder geslaagde raw-, processed- en
validatie-artifacts; alleen een volgende onvolledige of mislukte fase wordt
opnieuw gestart. De loader legt de pipeline-run-id vast in
`ops.etl_run.pipeline_run_id` (Alembic `20260904_03`).

## Consequenties

- De immutable raw- en processed-runs blijven de technische bron; de pipeline
  dupliceert geen extractie-, transformatie- of laadlogica.
- Een dry-run maakt uitsluitend het operationele manifest/log en doet geen
  CBS-call, Alembic-upgrade of database-mutatie.
- De snapshot-load blijft transactioneel: bij een fout blijft de vorige
  `core`-snapshot zichtbaar en de mislukte ETL-registratie is auditeerbaar.
- Operators gebruiken een specifieke `--raw-run` of `--processed-run` wanneer
  zij later in de keten starten.
