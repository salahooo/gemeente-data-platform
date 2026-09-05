import {cleanup, render, screen} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {MunicipalityMap} from "./MunicipalityMap";
import {ErrorBoundary} from "./ErrorBoundary";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it.each([null, {}, {features: []}, {features: [null, {}]},
  {features: [{properties: {gm_code: "GM0001", gm_naam: "Test"}, geometry: null}]},
])("isolates unavailable geometry from the dashboard: %j", async (data) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ok: true, json: async () => data}));
  render(<ErrorBoundary><h1>Dashboard</h1><MunicipalityMap year={2026} ranking={[]} onSelect={() => {}} /></ErrorBoundary>);
  expect(await screen.findByText(/Kaartgeometrie is tijdelijk niet beschikbaar/)).toBeInTheDocument();
  expect(screen.getByRole("heading", {name: "Dashboard"})).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
