import {ApiError} from "./api";

export const STARTUP_ATTEMPTS = 7;
export const STARTUP_LIMIT = 84_000;
export const COLD_START_MESSAGE = "De gratis API wordt momenteel opgestart. Dit kan ongeveer één minuut duren. Het dashboard probeert automatisch opnieuw verbinding te maken.";

export function temporaryFailure(error: unknown) {
  return error instanceof TypeError || error instanceof SyntaxError ||
    (error instanceof Error && error.name === "AbortError") ||
    (error instanceof ApiError && [502, 503, 504].includes(error.status));
}

function pause(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); signal.removeEventListener("abort", abort); reject(new DOMException("Cancelled", "AbortError")); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, ms);
    signal.addEventListener("abort", abort, {once: true});
    if (signal.aborted) abort();
  });
}

// One bounded coordinator; endpoints never have their own retry loops.
export async function startDashboard<T>({signal, ready, load, onAttempt, onReady, onDataFailure}: {
  signal: AbortSignal; ready: (signal: AbortSignal) => Promise<unknown>;
  load: (signal: AbortSignal) => Promise<T>; onAttempt: (attempt: number) => void; onReady: () => void;
  onDataFailure?: () => void;
}): Promise<T> {
  const deadline = Date.now() + STARTUP_LIMIT;
  for (let attempt = 1; attempt <= STARTUP_ATTEMPTS; attempt++) {
    signal.throwIfAborted();
    const started = Date.now();
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal.addEventListener("abort", abort, {once: true});
    const timer = setTimeout(abort, Math.max(0, deadline - Date.now()));
    onAttempt(attempt);
    let readySucceeded = false;
    try {
      await ready(controller.signal);
      controller.signal.throwIfAborted();
      onReady();
      readySucceeded = true;
      const data = await load(controller.signal);
      controller.signal.throwIfAborted();
      return data;
    } catch (error) {
      if (signal.aborted || !temporaryFailure(error)) throw error;
      if (readySucceeded) onDataFailure?.();
    } finally {
      controller.abort();
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
    }
    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    await pause(attempt === STARTUP_ATTEMPTS ? remaining : Math.min(remaining, Math.max(0, 12_000 - (Date.now() - started))), signal);
  }
  throw new Error("De gegevens zijn tijdelijk niet beschikbaar. Probeer het later opnieuw.");
}
