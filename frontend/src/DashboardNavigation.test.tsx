import {cleanup, fireEvent, render, screen} from "@testing-library/react";
import {afterEach, expect, it, vi} from "vitest";
import {CollapsibleSection, NavigationProvider, SectionNavigation} from "./DashboardNavigation";

afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); history.replaceState(null, "", "/");});

it("opens an anchored mobile section, preserves query state and keeps desktop content open", () => {
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({matches: query.includes("640px"), addEventListener: vi.fn(), removeEventListener: vi.fn()})));
  const scroll = vi.fn();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {configurable: true, value: scroll});
  history.replaceState(null, "", "/?year=2026&municipality=GM0363&compare=GM0599&compare_mode=index");
  render(<NavigationProvider><SectionNavigation ready /><CollapsibleSection id="kaart" title="Gemeentekaart"><p>Kaartinhoud</p></CollapsibleSection></NavigationProvider>);
  const toggle = screen.getByRole("button", {name: "Gemeentekaart"});
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByText("Kaartinhoud")).not.toBeVisible();
  fireEvent.click(screen.getByRole("link", {name: "Kaart"}));
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("Kaartinhoud")).toBeVisible();
  expect(scroll).toHaveBeenCalled();
  expect(location.search).toBe("?year=2026&municipality=GM0363&compare=GM0599&compare_mode=index");
  fireEvent.click(toggle);
  expect(screen.getByText("Kaartinhoud")).not.toBeVisible();
  cleanup();
  render(<CollapsibleSection id="kaart" title="Gemeentekaart"><p>Kaartinhoud</p></CollapsibleSection>);
  expect(screen.getByText("Kaartinhoud")).toBeVisible();
  expect(screen.queryByRole("button", {name: "Gemeentekaart"})).not.toBeInTheDocument();
});
