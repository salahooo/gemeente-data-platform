import {act, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {beforeEach, describe, expect, it, vi} from "vitest";

import {App} from "./App";
import {api} from "./api";

vi.mock("./api", () => ({api: {
  ready: vi.fn(), years: vi.fn(), national: vi.fn(), ranking: vi.fn(),
  municipalities: vi.fn(), municipality: vi.fn(), population: vi.fn(),
}, publicApiUrl: (path: string) => path}));

const mockedApi = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
  mockedApi.ready.mockResolvedValue({status: "ready"});
  mockedApi.years.mockResolvedValue([{year: 2025, has_average_population: true}, {year: 2026, has_average_population: false}]);
  mockedApi.national.mockResolvedValue([
    {year: 2025, municipality_count: 342, population_january_1: 18_000_000, average_population: "50000", missing_average_population_count: 0},
    {year: 2026, municipality_count: 342, population_january_1: 18_100_000, average_population: null, missing_average_population_count: 4},
  ]);
  mockedApi.ranking.mockResolvedValue([{rank: 1, municipality_code: "GM0001", municipality_name: "Voorbeeldstad", population_january_1: 100_000}]);
  mockedApi.municipalities.mockResolvedValue({items: [{municipality_code: "GM0001", municipality_name: "Voorbeeldstad"}]});
  mockedApi.population.mockResolvedValue({observations: [{year: 2025, population_january_1: 99_000, average_population: "99500", population_change_absolute: 1_000, population_change_percent: "1.0"}]});
});

describe("App", () => {
  it("toont kerncijfers, null-waarschuwing en ranking uit de API", async () => {
    render(<App />);
    expect(await screen.findByText("API: Beschikbaar")).toBeInTheDocument();
    expect(screen.getByText("Gemiddelde bevolking voor 2026 ontbreekt; dit is geen nulwaarde.")).toBeInTheDocument();
    expect(screen.getByText("Voorbeeldstad")).toBeInTheDocument();
    expect(mockedApi.ranking).toHaveBeenCalledWith(2026);
  });

  it("zoekt en selecteert een gemeente zonder databaseverbinding", async () => {
    render(<App />);
    await screen.findByText("API: Beschikbaar");
    fireEvent.change(screen.getByLabelText("Gemeente"), {target: {value: "Vo"}});
    expect(await screen.findByRole("button", {name: /Voorbeeldstad/})).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: /Voorbeeldstad/}));
    await waitFor(() => expect(mockedApi.population).toHaveBeenCalledWith("GM0001"));
    expect(screen.getByText("Tijdreeks Voorbeeldstad")).toBeInTheDocument();
    expect(location.search).toContain("municipality=GM0001");
  });

  it("kiest standaard het nieuwste beschikbare jaar en werkt de URL bij", async () => {
    render(<App />);
    const selector = await screen.findByLabelText("Jaar");
    expect(selector).toHaveValue("2026");
    fireEvent.change(selector, {target: {value: "2025"}});
    await waitFor(() => expect(mockedApi.ranking).toHaveBeenCalledWith(2025));
    expect(location.search).toBe("?year=2025");
  });

  it("maakt filters en een geselecteerde tijdreeks weer leeg", async () => {
    render(<App />);
    await screen.findByText("API: Beschikbaar");
    fireEvent.change(screen.getByLabelText("Gemeente"), {target: {value: "Vo"}});
    fireEvent.click(await screen.findByRole("button", {name: /Voorbeeldstad/}));
    await act(async () => { await mockedApi.population.mock.results[0]?.value; });
    await screen.findByText("Tijdreeks Voorbeeldstad");
    await waitFor(() => expect(document.querySelectorAll(".recharts-responsive-container")).toHaveLength(3));
    const rankingCalls = mockedApi.ranking.mock.calls.length;
    fireEvent.click(screen.getByRole("button", {name: "Wis filters"}));
    await waitFor(() => expect(mockedApi.ranking.mock.calls.length).toBeGreaterThan(rankingCalls));
    expect(screen.getByText("Selecteer een gemeente")).toBeInTheDocument();
    expect(screen.getByLabelText("Gemeente")).toHaveValue("");
  });

  it("toont een veilige foutmelding als de API niet beschikbaar is", async () => {
    mockedApi.ready.mockRejectedValueOnce(new Error("offline"));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("tijdelijk niet beschikbaar");
    expect(screen.getByText("API: Niet beschikbaar")).toBeInTheDocument();
  });

  it("ververst de API-gegevens op expliciet gebruikersverzoek", async () => {
    render(<App />);
    await screen.findByText("API: Beschikbaar");
    const before = mockedApi.ready.mock.calls.length;
    fireEvent.click(screen.getByRole("button", {name: "Vernieuwen"}));
    await waitFor(() => expect(mockedApi.ready.mock.calls.length).toBeGreaterThan(before));
  });
});
