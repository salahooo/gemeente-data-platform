import type {AgeProfileData, DataQuality, Lineage, Municipality, National, Observation, Ranking, Year} from "./types";

const timeout = 8000;

/** Normalize an optional public API origin without ever appending /api twice. */
export function normalizeApiBase(value: string | undefined, production = import.meta.env.PROD): string {
  const base = (value ?? "").trim().replace(/\/+$/, "");
  if (!base) return "";
  const url = new URL(base);
  const localHost = ["local", "host"].join("");
  const loopback = [127, 0, 0, 1].join(".");
  if (production && (url.protocol !== "https:" || [localHost, loopback, "::1"].includes(url.hostname))) {
    throw new Error("VITE_API_BASE_URL must be a public HTTPS origin in production.");
  }
  return `${url.origin}${url.pathname.replace(/\/api$/, "").replace(/\/$/, "")}`;
}

export const apiBaseUrl = normalizeApiBase(import.meta.env.VITE_API_BASE_URL);

export function publicApiUrl(path: string): string {
  return `${apiBaseUrl}${path}`;
}

export class ApiError extends Error { constructor(public status: number) { super(status === 404 ? "Niet gevonden" : `API-fout (${status})`); } }

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, {once: true});
  if (signal?.aborted) abort();
  const timer = setTimeout(abort, timeout);
  try {
    const response = await fetch(publicApiUrl(path), {signal: controller.signal});
    if (!response.ok) {
      throw new ApiError(response.status);
    }
    return await response.json() as T;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

export const api = {
  profile: (code: string, year: number, signal?: AbortSignal) => get<AgeProfileData>(`/api/v1/municipalities/${code}/profile?year=${year}`, signal),
  dataQuality: (signal?: AbortSignal) => get<DataQuality[]>("/api/v1/data-quality", signal),
  ready: async (signal?: AbortSignal) => { const result = await get<{status: string}>("/ready", signal); if (result.status !== "ready") throw new ApiError(503); return result; },
  years: (signal?: AbortSignal) => get<Year[]>("/api/v1/years", signal),
  national: (signal?: AbortSignal) => get<National[]>("/api/v1/national/population", signal),
  ranking: (year: number, limit = 10, signal?: AbortSignal) => get<Ranking[]>(`/api/v1/rankings/population?year=${year}&limit=${limit}`, signal),
  municipalities: (search: string, signal?: AbortSignal) =>
    get<{items: Municipality[]}>(`/api/v1/municipalities?search=${encodeURIComponent(search)}&page_size=10`, signal),
  municipality: (code: string, signal?: AbortSignal) => get<Municipality>(`/api/v1/municipalities/${code}`, signal),
  population: (code: string, signal?: AbortSignal) => get<{observations: Observation[]}>(`/api/v1/municipalities/${code}/population`, signal),
  lineage: (signal?: AbortSignal) => get<Lineage | null>("/api/v1/lineage/latest", signal),
};
