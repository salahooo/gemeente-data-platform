import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {ApiError, api} from "./api";
import {startDashboard} from "./startup";

beforeEach(() => vi.useFakeTimers());
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });
const options = () => ({signal: new AbortController().signal, ready: vi.fn().mockResolvedValue({status: "ready"}), load: vi.fn().mockResolvedValue("snapshot"), onAttempt: vi.fn(), onReady: vi.fn()});

describe("bounded startup", () => {
  it("loads once after fast readiness without leftover timers", async () => {
    const input = options();
    expect(await startDashboard(input)).toBe("snapshot");
    expect(input.ready).toHaveBeenCalledTimes(1);
    expect(input.load).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
  it("retries readiness centrally and starts data only after recovery", async () => {
    const input = options(); input.ready.mockRejectedValueOnce(new ApiError(503));
    const result = startDashboard(input);
    await vi.advanceTimersByTimeAsync(5000);
    expect(input.load).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(7000);
    expect(await result).toBe("snapshot");
    expect(input.ready).toHaveBeenCalledTimes(2);
    expect(input.load).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
  it("stops after seven attempts and 84 seconds", async () => {
    const input = options(); input.ready.mockRejectedValue(new TypeError("offline"));
    const result = startDashboard(input).catch((error) => error);
    await vi.advanceTimersByTimeAsync(83_999);
    expect(input.ready).toHaveBeenCalledTimes(7);
    expect(input.load).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(await result).toBeInstanceOf(Error);
    expect(vi.getTimerCount()).toBe(0);
  });
  it.each([400, 401, 403, 404, 422])("never retries HTTP %i", async (status) => {
    const input = options(); input.ready.mockRejectedValue(new ApiError(status));
    await expect(startDashboard(input)).rejects.toHaveProperty("status", status);
    expect(input.ready).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
  it("cancels a retry wait on navigation/unmount", async () => {
    const input = options(); const controller = new AbortController(); input.signal = controller.signal;
    input.ready.mockRejectedValue(new ApiError(502));
    const result = startDashboard(input).catch((error) => error);
    await vi.advanceTimersByTimeAsync(1000);
    controller.abort();
    expect(await result).toHaveProperty("name", "AbortError");
    expect(vi.getTimerCount()).toBe(0);
    expect(input.ready).toHaveBeenCalledTimes(1);
  });
  it("aborts sibling data requests before a central recovery attempt", async () => {
    const input = options(); let firstSignal: AbortSignal | undefined;
    input.load.mockImplementationOnce(async (signal: AbortSignal) => { firstSignal = signal; throw new ApiError(504); });
    const result = startDashboard(input);
    await vi.advanceTimersByTimeAsync(12000);
    expect(await result).toBe("snapshot");
    expect(firstSignal?.aborted).toBe(true);
    expect(input.ready).toHaveBeenCalledTimes(2);
  });
});

describe("GET cancellation", () => {
  function pendingFetch() {
    const fetcher = vi.fn((_url: unknown, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), {once: true});
    }));
    vi.stubGlobal("fetch", fetcher);
    return fetcher;
  }
  it("keeps the eight-second timeout when an external signal is supplied", async () => {
    const fetcher = pendingFetch();
    const result = api.ready(new AbortController().signal).catch((error) => error);
    await vi.advanceTimersByTimeAsync(8000);
    expect(await result).toHaveProperty("name", "AbortError");
    expect(fetcher.mock.calls[0][1].signal?.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });
  it("aborts requests and removes timeout timers immediately", async () => {
    pendingFetch(); const controller = new AbortController();
    const result = api.ready(controller.signal).catch((error) => error);
    controller.abort();
    expect(await result).toHaveProperty("name", "AbortError");
    expect(vi.getTimerCount()).toBe(0);
  });
});
