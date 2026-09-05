import {describe, expect, it} from "vitest";
import {csvDocument, indexedSeries} from "./dashboardTools";

describe("dashboard tools", () => {
  it("maakt Excel-veilige UTF-8 CSV met puntkomma's", () => {
    expect(csvDocument([{naam: "=formule", jaar: 2026, waarde: null}])).toBe('\uFEFF"naam";"jaar";"waarde"\r\n"\'=formule";"2026";""\r\n');
  });
  it("indexeert vanaf het eerste gezamenlijke geldige jaar", () => {
    const data = [{year: 2020, population_january_1: 10}, {year: 2021, population_january_1: 12}] as never;
    const result = indexedSeries(data, [{year: 2020, population_january_1: 20}, {year: 2021, population_january_1: 18}] as never);
    expect(result.baseYear).toBe(2020);
    expect(result.values[1]).toMatchObject({primary: 120, secondary: 90});
  });
});
