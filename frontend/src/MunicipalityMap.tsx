import {CollapsibleSection} from "./DashboardNavigation";
import {useEffect, useMemo, useState} from "react";
import type {Ranking} from "./types";
import {number, municipalityDisplayName} from "./format";
import {mapBounds, mapPath} from "./mapBounds";

type Feature = {properties: {gm_code: string; gm_naam: string; jaar: string}; geometry: unknown};
type Collection = {features?: unknown};

export function MunicipalityMap({year, ranking, selectedCode, selectedGrowth, onSelect}: {year: number; ranking: Ranking[]; selectedCode?: string; selectedGrowth?: number | null; onSelect: (item: Ranking) => void}) {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [hovered, setHovered] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => { const controller = new AbortController(); void fetch("/data/cbs-gemeenten-2026-simplified.geojson", {signal: controller.signal}).then((response) => { if (!response.ok) throw new Error("Map unavailable"); return response.json(); }).then((data: Collection | null) => { if (!Array.isArray(data?.features)) throw new Error("Invalid map"); setFeatures(data.features.filter((feature): feature is Feature => feature != null && typeof feature.properties?.gm_code === "string" && typeof feature.properties?.gm_naam === "string")); setLoaded(true); }).catch(() => { if (!controller.signal.aborted) setFailed(true); }); return () => controller.abort(); }, []);
  const values = useMemo(() => new Map(ranking.map((item) => [item.municipality_code, item])), [ranking]);
  const box = useMemo(() => features.length ? mapBounds(features) : null, [features]);
  if (failed || (loaded && !box)) return <CollapsibleSection id="kaart" title="Gemeentekaart" className="card map"><p className="empty compact">Kaartgeometrie is tijdelijk niet beschikbaar; selecteer een gemeente via zoeken.</p></CollapsibleSection>;
  const path = (feature: Feature) => mapPath(feature.geometry, box);
  const highlighted = values.get(hovered ?? selectedCode ?? "");
  const max = ranking.reduce((largest, item) => Math.max(largest, item.population_january_1), 1);
  return <CollapsibleSection id="kaart" title="Gemeentekaart" className="card map"><div className="comparison-heading"><div><p className="caption">Inwonertal op 1 januari {year}; klik of gebruik Enter om te selecteren.</p></div><span className="map-legend">Licht: lager · donker: hoger</span></div>{highlighted && <div className="map-info"><strong>{municipalityDisplayName(highlighted.municipality_name)}</strong><span>{number(highlighted.population_january_1)} inwoners</span><span>Groei: {highlighted.municipality_code === selectedCode ? number(selectedGrowth ?? null) : "Niet beschikbaar"}</span>{highlighted.municipality_code === selectedCode && <a href="#gemeente">Bekijk gemeenteprofiel</a>}</div>}{features.length ? <svg viewBox="0 0 700 820" role="img" aria-label={`Kaart met inwonertal per gemeente in ${year}`}>{features.map((feature, index) => { const item = values.get(feature.properties.gm_code); const missing = !item; const shade = missing ? "#dce6e7" : `rgba(11, 110, 105, ${.2 + .8 * item.population_january_1 / max})`; return <path key={`${feature.properties.gm_code}-${index}`} d={path(feature)} fill={shade} className={selectedCode === feature.properties.gm_code ? "map-selected" : ""} tabIndex={0} role="button" aria-label={`${municipalityDisplayName(feature.properties.gm_naam)} (${feature.properties.gm_code}), ${missing ? "waarde onbekend" : number(item.population_january_1)}`} onMouseEnter={() => setHovered(feature.properties.gm_code)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(feature.properties.gm_code)} onBlur={() => setHovered(null)} onClick={() => item && onSelect(item)} onKeyDown={(event) => { if (item && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onSelect(item); } }}><title>{`${municipalityDisplayName(feature.properties.gm_naam)}: ${missing ? "onbekend" : number(item.population_january_1)}`}</title></path>; })}</svg> : <p className="empty compact">Kaart laden…</p>}<p className="caption">Grenzen: CBS Wijken en Buurten 2026 versie 0 via PDOK, gemeentecode als join-key. Historische codes zonder 2026-geometrie blijven onbekend; dit duidt geen juridische herindeling.</p></CollapsibleSection>;
}
