import {render, screen} from "@testing-library/react";
import type {ReactElement} from "react";
import {describe, expect, it, vi} from "vitest";
import {ErrorBoundary} from "./ErrorBoundary";
function Broken(): ReactElement { throw new Error("expected test error"); }
describe("ErrorBoundary", () => { it("toont een veilige herstelmelding", () => { vi.spyOn(console, "error").mockImplementation(() => undefined); render(<ErrorBoundary><Broken /></ErrorBoundary>); expect(screen.getByRole("alert")).toHaveTextContent("kon niet veilig worden weergegeven"); }); });
