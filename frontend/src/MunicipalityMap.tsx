import {useEffect, useMemo, useState} from "react";
import type {Ranking} from "./types";
import {number} from "./format";

type Feature = {properties: {gm_code: string; gm_naam: string; jaar: string}; geometry: {coordinates: number[][][][]}};
type Collection = {features: Feature[]};

function rings(feature: Feature) { return feature.geometry.coordinates.flat(2) as number[][]; }
function bounds(features: Feature[]) { const points = features.flatMap(rings); return {minX: Math.min(...points.map((p) => p[0])), maxX: Math.max(...points.map((p) => p[0])), minY: Math.min(...points.map((p) => p[1])), maxY: Math.max(...points.map((p) => p[1]))}; }

export function MunicipalityMap({year, ranking, selectedCode, onSelect}: {year: number; ranking: Ranking[]; selectedCode?: string; onSelect: (item: Ranking) => void}) {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [failed, setFailed] = useState(false);
  useEffect(() => { void fetch("/data/cbs-gemeenten-2026-simplified.geojson").then((response) => response.json()).then((data: Collection) => setFeatures(data.features)).catch(() => setFailed(true)); }, []);
  const values = useMemo(() => new Map(ranking.map((item) => [item.municipality_code, item])), [ranking]);
  const box = useMemo(() => features.length ? bounds(features) : null, [features]);
  if (failed) return <article className="card map" id="kaart"><h2>Gemeentekaart</h2><p className="empty compact">Kaartgeometrie is tijdelijk niet beschikbaar; selecteer een gemeente via zoeken.</p></article>;
  const path = (feature: Feature) => !box ? "" : feature.geometry.coordinates.map((polygon) => polygon.map((ring) => ring.map(([x, y], index) => `${index ? "L" : "M"}${(x - box.minX) / (box.maxX - box.minX) * 700} ${(box.maxY - y) / (box.maxY - box.minY) * 820}`).join(" ") + " Z").join(" ")).join(" ");
  const max = Math.max(...ranking.map((item) => item.population_january_1), 1);
  return <article className="card map" id="kaart"><div className="comparison-heading"><div><h2>Gemeentekaart</h2><p className="caption">Inwonertal op 1 januari {year}; klik of gebruik Enter om te selecteren.</p></div><span className="map-legend">Licht: lager · donker: hoger</span></div>{features.length ? <svg viewBox="0 0 700 820" role="img" aria-label={`Kaart met inwonertal per gemeente in ${year}`}>{features.map((feature) => { const item = values.get(feature.properties.gm_code); const missing = !item; const shade = missing ? "#dce6e7" : `rgba(11, 110, 105, ${.2 + .8 * item.population_january_1 / max})`; return <path key={feature.properties.gm_code} d={path(feature)} fill={shade} className={selectedCode === feature.properties.gm_code ? "map-selected" : ""} tabIndex={0} role="button" aria-label={`${feature.properties.gm_naam} (${feature.properties.gm_code}), ${missing ? "waarde onbekend" : number(item.population_january_1)}`} onClick={() => item && onSelect(item)} onKeyDown={(event) => { if (item && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onSelect(item); } }}><title>{`${feature.properties.gm_naam}: ${missing ? "onbekend" : number(item.population_january_1)}`}</title></path>; })}</svg> : <p className="empty compact">Kaart laden…</p>}<p className="caption">Grenzen: CBS Wijken en Buurten 2026 versie 0 via PDOK, gemeentecode als join-key. Historische codes zonder 2026-geometrie blijven onbekend; dit duidt geen juridische herindeling.</p></article>;
}
