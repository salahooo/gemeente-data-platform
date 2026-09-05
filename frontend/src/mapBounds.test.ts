import {describe, expect, it} from "vitest";
import {mapBounds, mapPath, type MapGeometry} from "./mapBounds";

const ring = [[0, 0], [10, 0], [10, 20], [0, 0]];

describe("map geometry", () => {
  it("supports Polygon and preserves inner rings in paths", () => {
    const geometry = {type: "Polygon", coordinates: [ring, ring]};
    const box = mapBounds([{geometry}]);
    expect(box).toEqual({minX: 0, maxX: 10, minY: 0, maxY: 20});
    expect(mapPath(geometry, box)).toBe("M0 820 L700 820 L700 0 L0 820 Z M0 820 L700 820 L700 0 L0 820 Z");
  });

  it("supports MultiPolygon across features and polygons", () => {
    const geometry = {type: "MultiPolygon", coordinates: [[ring], [[[-20, -30], [40, -30], [40, 50], [-20, -30]]]]};
    const box = mapBounds([{geometry: {type: "Polygon", coordinates: [ring]}}, {geometry}]);
    expect(box).toEqual({minX: -20, maxX: 40, minY: -30, maxY: 50});
    expect(mapPath(geometry, box).match(/M/g)).toHaveLength(2);
    expect(mapPath(geometry, box).match(/ Z/g)).toHaveLength(2);
  });

  it.each([null, {}, {type: "Point", coordinates: [1, 2]},
    {type: "Polygon", coordinates: []}, {type: "MultiPolygon", coordinates: [null, [null, []]]},
    {type: "Polygon", coordinates: [[null, null, null, null]]},
    {type: "Polygon", coordinates: [[[0, 0], [NaN, 1], [Infinity, 2], [0, 0]]]},
    {type: "Polygon", coordinates: [[[0, 0], [1, 1], [2, 2], [3, 3]]]},
  ])("safely skips empty or invalid geometry: %j", (geometry) => {
    expect(mapBounds([{geometry}])).toBeNull();
    expect(mapPath(geometry, null)).toBe("");
    expect(mapPath(geometry, {minX: 0, maxX: 1, minY: 0, maxY: 1})).toBe("");
  });

  it("keeps valid geometry beside invalid geometry and handles zero extents", () => {
    const geometry = {type: "Polygon", coordinates: [[[2, 2], [2, 2], [2, 2], [2, 2]]]};
    const box = mapBounds([{}, {geometry: null}, {geometry}]);
    expect(mapPath(geometry, box)).toBe("M0 0 L0 0 L0 0 L0 0 Z");
    expect(mapBounds([])).toBeNull();
  });

  it("reads two million coordinates from synthetic GeoJSON without a RangeError", async () => {
    const largeRing = Array.from({length: 1_000_000}, (_, i) => [i, -i]);
    largeRing[largeRing.length - 1] = [0, 0];
    const file = new File([JSON.stringify({type: "FeatureCollection", features: [
      {type: "Feature", geometry: {type: "MultiPolygon", coordinates: [[largeRing], [largeRing]]}},
    ]})], "large.geojson", {type: "application/geo+json"});
    const contents = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = () => reject(reader.error);
      reader.readAsText(file);
    });
    const data = JSON.parse(contents) as {features: MapGeometry[]};
    let box: ReturnType<typeof mapBounds> = null;
    expect(() => { box = mapBounds(data.features); }).not.toThrow();
    expect(box).toEqual({minX: 0, maxX: 999_998, minY: -999_998, maxY: 0});
    expect(() => mapPath(data.features[0].geometry, box)).not.toThrow();
  }, 20_000);
});
