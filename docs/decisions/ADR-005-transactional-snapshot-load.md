# ADR-005: transactionele snapshot-load

- Status: Accepted
- Datum: 2026-09-04

Een gevalideerde processed snapshot vervangt `core` transactioneel. Een eerder
succesvolle processed run is een no-op; `ops.etl_run` bewaart historie. Row-level
upserts en append-only historie zijn alternatieven. Lezers zien alleen een oude
of een volledige nieuwe snapshot.

Bij een laadfout rolt de core-transactie volledig terug. Daarna registreert de
loader in een afzonderlijke, beperkte transactie één `failed`-run met categorie
en ingekorte fouttekst; wachtwoorden en database-URL's worden niet opgeslagen.
