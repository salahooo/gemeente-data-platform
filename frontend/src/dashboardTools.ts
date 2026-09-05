import type {Observation} from "./types";

export function csvCell(value: string | number | null): string {
  const raw = value === null ? "" : String(value);
  const safe = /^[=+\-@]/.test(raw) ? `'${raw}` : raw;
  return `"${safe.replaceAll('"', '""')}"`;
}

export function csvDocument(rows: Array<Record<string, string | number | null>>): string {
  const columns = Object.keys(rows[0] ?? {});
  return `\uFEFF${[columns, ...rows.map((row) => columns.map((column) => row[column]))].map((row) => row.map(csvCell).join(";")).join("\r\n")}\r\n`;
}

export function indexedSeries(first: Observation[], second: Observation[]) {
  const secondByYear = new Map(second.map((item) => [item.year, item.population_january_1]));
  const base = first.find((item) => item.population_january_1 > 0 && (secondByYear.get(item.year) ?? 0) > 0)?.year;
  if (base === undefined) return {baseYear: null, values: []};
  const firstBase = first.find((item) => item.year === base)?.population_january_1 ?? 0;
  const secondBase = secondByYear.get(base) ?? 0;
  return {baseYear: base, values: first.map((item) => {
    const other = secondByYear.get(item.year) ?? null;
    return {year: item.year, primary: item.population_january_1 && firstBase ? item.population_january_1 / firstBase * 100 : null, secondary: other && secondBase ? other / secondBase * 100 : null, primaryPopulation: item.population_january_1, secondaryPopulation: other};
  })};
}
