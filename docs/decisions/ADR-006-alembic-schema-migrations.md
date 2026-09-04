# ADR-006: Alembic voor schema migrations

- Status: Accepted
- Datum: 2026-09-04

Alembic versieert handmatig gecontroleerde upgrade- en downgrade-stappen. De
applicatieconfiguratie levert de verbinding; `alembic.ini` bevat geen wachtwoord.
Losse SQL-scripts en automatisch tabellen maken geven minder reproduceerbare
schema-evolutie.
