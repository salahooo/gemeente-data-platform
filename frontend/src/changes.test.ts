import {expect, it} from "vitest";
import {annualChanges} from "./changes";

it("berekent opeenvolgende januariwaarden, inclusief krimp en nul", () => {
  expect(annualChanges([{year: 2023, population_january_1: 100}, {year: 2024, population_january_1: 90}, {year: 2025, population_january_1: 90}]).map((item) => item.change)).toEqual([null, -10, 0]);
});
it("houdt ontbrekende waarden en jaren onbekend en muteert de bron niet", () => {
  const data = [{year: 2026, population_january_1: 200}, {year: 2023, population_january_1: null}, {year: 2024, population_january_1: 100}];
  expect(annualChanges(data).map((item) => item.change)).toEqual([null, null, null]);
  expect(data[0].year).toBe(2026);
});
