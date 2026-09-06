import {cleanup, render, screen, waitFor} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {api} from "./api";
import {AgeProfile, QualityMonitor} from "./MunicipalityProfile";

vi.mock("./api", () => ({api: {profile: vi.fn(), dataQuality: vi.fn()}}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("keeps optional missing data quiet and never treats it as zero", async () => {
  vi.mocked(api.profile).mockResolvedValue({municipality_code: "GM0363", year: 2026, dataset_code: "70072ned", categories: []});
  render(<AgeProfile code="GM0363" year={2026} revision={1} />);
  expect(screen.getByText("Aanvullende profielgegevens zijn nog niet beschikbaar.")).toBeInTheDocument();
  await waitFor(() => expect(api.profile).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("alert")).toBeNull();
});

it("renders an accessible chart with exact counts, nulls and national reference", async () => {
  vi.mocked(api.profile).mockResolvedValue({municipality_code: "GM0363", year: 2026, dataset_code: "70072ned", categories: [
    {category: "0-14", population: 0, share_percent: "0", national_share_percent: "15.2"},
    {category: "65+", population: null, share_percent: null, national_share_percent: null},
  ]});
  render(<AgeProfile code="GM0363" year={2026} revision={1} />);
  expect(await screen.findByRole("table")).toHaveAccessibleName(/Leeftijdsopbouw/);
  expect(screen.getByText("0% / 15,2%")).toBeInTheDocument();
  expect(screen.getByText("Onbekend / Onbekend")).toBeInTheDocument();
  expect(screen.getByText("Niet beschikbaar")).toBeInTheDocument();
  expect(screen.getByRole("link", {name: /CBS Regionale/})).toHaveAttribute("href", "https://www.cbs.nl/nl-nl/cijfers/detail/70072ned");
});

it("cancels obsolete profile requests when selection changes", () => {
  vi.mocked(api.profile).mockImplementation(() => new Promise(() => {}));
  const view = render(<AgeProfile code="GM0363" year={2026} revision={1} />);
  const signal = vi.mocked(api.profile).mock.calls[0][2];
  view.rerender(<AgeProfile code="GM0484" year={2026} revision={1} />);
  expect(signal?.aborted).toBe(true);
  view.unmount();
  expect(vi.mocked(api.profile).mock.calls[1][2]?.aborted).toBe(true);
});

it("shows only the public quality summary and handles unavailable metadata", async () => {
  vi.mocked(api.dataQuality).mockResolvedValue([{dataset_code: "70072ned", dataset_name: "Leeftijdsopbouw", source: "CBS Open Data", first_year: 2025, last_year: 2026, completed_at: null, record_count: 3420, validation_status: "validated", missing_values: 1, warning: "Ontbrekende waarden zijn geen nul."}]);
  render(<QualityMonitor revision={1} />);
  expect(await screen.findByText("Leeftijdsopbouw")).toBeInTheDocument();
  expect(screen.getByText("✓ Gevalideerd")).toBeInTheDocument();
  expect(screen.getByText("3.420")).toBeInTheDocument();
  expect(screen.getByText("2025–2026")).toBeInTheDocument();
});
