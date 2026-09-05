export type MapGeometry = {geometry?: unknown};
export type Bounds = {minX: number; maxX: number; minY: number; maxY: number};
type Visitor = (x: number, y: number, first: boolean, last: boolean) => void;

// Fixed-depth traversal shared by bounds and SVG paths. Invalid rings are skipped whole.
export function visitCoordinates(geometry: unknown, visit: Visitor) {
  if (!geometry || typeof geometry !== "object") return;
  const {type, coordinates} = geometry as {type?: unknown; coordinates?: unknown};
  if (!Array.isArray(coordinates)) return;
  const polygons = type === "Polygon" ? [coordinates] : type === "MultiPolygon" ? coordinates : [];
  for (const polygon of polygons) {
    if (!Array.isArray(polygon)) continue;
    for (const ring of polygon) {
      if (!Array.isArray(ring) || ring.length < 4) continue;
      let valid = true;
      for (const point of ring) {
        if (!Array.isArray(point) || point.length < 2 || !Number.isFinite(point[0]) || !Number.isFinite(point[1])) {
          valid = false;
          break;
        }
      }
      if (!valid) continue;
      const first = ring[0];
      const last = ring[ring.length - 1];
      if (first[0] !== last[0] || first[1] !== last[1]) continue;
      for (let i = 0; i < ring.length; i++) visit(ring[i][0], ring[i][1], i === 0, i === ring.length - 1);
    }
  }
}

export function mapBounds(features: MapGeometry[]): Bounds | null {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const feature of features) {
    visitCoordinates(feature?.geometry, (x, y) => {
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    });
  }
  return minX === Infinity ? null : {minX, maxX, minY, maxY};
}

export function mapPath(geometry: unknown, box: Bounds | null): string {
  if (!box) return "";
  const width = box.maxX - box.minX || 1;
  const height = box.maxY - box.minY || 1;
  if (!Number.isFinite(width) || !Number.isFinite(height)) return "";
  const commands: string[] = [];
  visitCoordinates(geometry, (x, y, first, last) => {
    commands.push(`${first ? "M" : "L"}${(x - box.minX) / width * 700} ${(box.maxY - y) / height * 820}${last ? " Z" : ""}`);
  });
  return commands.join(" ");
}
