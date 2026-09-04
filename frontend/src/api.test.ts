import {describe, expect, it} from "vitest";

import {normalizeApiBase, publicApiUrl} from "./api";

describe("public API base", () => {
  it("normalises a public origin and removes a duplicate api suffix", () => {
    expect(normalizeApiBase("https://api.example.test/api/", true)).toBe("https://api.example.test");
  });

  it("rejects local or plaintext endpoints for a production build", () => {
    expect(() => normalizeApiBase("http://localhost:8000", true)).toThrow(/HTTPS/);
    expect(() => normalizeApiBase("http://api.example.test", true)).toThrow(/HTTPS/);
  });

  it("keeps same-origin requests working locally", () => {
    expect(normalizeApiBase(undefined, false)).toBe("");
    expect(publicApiUrl("/api/v1/years")).not.toContain("/api/api/");
  });
});
