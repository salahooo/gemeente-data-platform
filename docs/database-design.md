# Databaseontwerp

PostgreSQL 17 bevat de schemas `core`, `mart` en `ops`. Alleen Alembics
technische versietabel staat in `public`.

```mermaid
erDiagram
    DIM_MUNICIPALITY ||--o{ FACT_POPULATION : municipality_code
    DIM_PERIOD ||--o{ FACT_POPULATION : period_code
    DIM_MUNICIPALITY { string municipality_code PK string municipality_name int first_observed_year int last_observed_year boolean is_active_latest_period }
    DIM_PERIOD { string period_code PK int year string period_label boolean has_january_population boolean has_average_population }
    FACT_POPULATION { string municipality_code FK string period_code FK int population_january_1 numeric average_population }
    ETL_RUN { uuid run_id PK string processed_run_id string status }
```

`INTEGER` past bij gemeentelijke bevolkingswaarden; `NUMERIC(18,3)` bewaart
gemiddelde bevolking. Jaar-op-jaar blijft beperkt tot dezelfde code en is geen
geografische harmonisatie.
