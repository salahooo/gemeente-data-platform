# Geplande architectuur

## Datastroom

```text
CBS Open Data API → Python ETL → PostgreSQL → SQL views → Power BI
```

## Rollen in de pipeline

- **CBS Open Data API:** bron voor Nederlandse gemeentelijke gegevens.
- **Python ETL:** haalt gegevens op, valideert en transformeert ze; deze fase is nog niet geïmplementeerd.
- **PostgreSQL:** opslaglaag voor verwerkte gegevens; nog niet geconfigureerd.
- **SQL views:** herbruikbare analyse- en rapportagelaag boven op de database; nog niet aanwezig.
- **Power BI:** visualisatie- en dashboardlaag; nog niet ingericht.

Deze documentatie beschrijft de beoogde situatie, niet de huidige functionaliteit.
