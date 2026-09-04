# ADR-003: Parquet als canonieke processed opslag

- Status: Accepted
- Datum: 2026-09-04

## Context

Fase 3 heeft een lokaal, reproduceerbaar formaat nodig voor getypeerde
processed tabellen. De uitvoer moet efficiënt herleesbaar zijn en tegelijk
controleerbaar blijven voor mensen.

## Beslissing

Parquet is de canonieke technische opslag voor de drie processed tabellen.
Iedere tabel krijgt daarnaast een UTF-8-CSV-export met dezelfde inhoud.

## Alternatieven

- Alleen CSV: eenvoudig leesbaar, maar zwakker in typebehoud en minder geschikt
  als technische bron.
- Alleen JSON: passend voor raw OData-responses, maar minder geschikt voor
  relationele analyse-tabellen.
- Directe raw-naar-PostgreSQL-load: buiten scope; PostgreSQL consumeert uitsluitend
  een gevalideerde processed run.

## Consequenties

De omgeving heeft `pyarrow` nodig. De transformatie herleest Parquet en
vergelijkt de CSV-export om type- en inhoudsproblemen vroeg te signaleren.
