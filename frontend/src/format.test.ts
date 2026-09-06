import {describe,expect,it} from "vitest";import {number,percent,municipalityDisplayName} from "./format";describe("formatters",()=>{it("formats Dutch values and null",()=>{expect(number(1234567)).toBe("1.234.567");expect(number(null)).toBe("Niet beschikbaar");expect(percent(null)).toBe("Niet beschikbaar")})});

it("removes only the exact terminal municipality suffix", () => {
  for (const name of ["Utrecht", "Groningen", "’s-Gravenhage"]) expect(municipalityDisplayName(`${name} (gemeente)`)).toBe(name);
  for (const name of ["Utrecht", "X (gemeente) Y", "X (Gemeente)", "X (gemeente) ", ""]) expect(municipalityDisplayName(name)).toBe(name);
});
