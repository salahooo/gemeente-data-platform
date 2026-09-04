# ADR-004: PostgreSQL via Docker Compose

- Status: Accepted
- Datum: 2026-09-04

PostgreSQL draait als `postgres:17.11-bookworm` in een projectgebonden Compose
service op hostpoort 5433 met named volume. Dit is reproduceerbaar en raakt de
bestaande lokale server op 5432 niet. Lokale PostgreSQL en een cloud-database
waren alternatieven. Image-updates worden bewust getest; volumes worden niet
automatisch verwijderd.
