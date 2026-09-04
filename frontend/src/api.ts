import type {Municipality, National, Observation, Ranking, Year} from "./types";

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

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(publicApiUrl(path), {signal: signal ?? controller.signal});
    if (!response.ok) {
      throw new Error(response.status === 404 ? "Niet gevonden" : `API-fout (${response.status})`);
    }
    return await response.json() as T;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  ready: () => get<{status: string}>("/ready"),
  years: () => get<Year[]>("/api/v1/years"),
  national: () => get<National[]>("/api/v1/national/population"),
  ranking: (year: number) => get<Ranking[]>(`/api/v1/rankings/population?year=${year}&limit=10`),
  municipalities: (search: string, signal?: AbortSignal) =>
    get<{items: Municipality[]}>(`/api/v1/municipalities?search=${encodeURIComponent(search)}&page_size=10`, signal),
  municipality: (code: string) => get<Municipality>(`/api/v1/municipalities/${code}`),
  population: (code: string) => get<{observations: Observation[]}>(`/api/v1/municipalities/${code}/population`),
};
