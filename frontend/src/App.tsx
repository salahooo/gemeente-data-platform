import {useEffect, useState} from "react";
import {Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";

import {api, publicApiUrl} from "./api";
import {annualChanges} from "./changes";
import {number, percent} from "./format";
import {LINKEDIN_URL} from "./portfolio";
import {SocialLink} from "./SocialLink";
import type {Lineage, Municipality, National, Observation, Ranking, Year} from "./types";

type Series = Observation[];
type ChartDatum = Record<string, string | number | null>;

export function App() {
  const [initialRoute] = useState(() => new URLSearchParams(location.search));
  const [years, setYears] = useState<Year[]>([]);
  const [national, setNational] = useState<National[]>([]);
  const [ranking, setRanking] = useState<Ranking[]>([]);
  const [year, setYear] = useState(Number(initialRoute.get("year")) || 0);
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<Municipality[]>([]);
  const [selected, setSelected] = useState<Municipality | null>(null);
  const [series, setSeries] = useState<Series>([]);
  const [compareSearch, setCompareSearch] = useState("");
  const [compareItems, setCompareItems] = useState<Municipality[]>([]);
  const [comparison, setComparison] = useState<Municipality | null>(null);
  const [comparisonSeries, setComparisonSeries] = useState<Series>([]);
  const [fullRanking, setFullRanking] = useState<Ranking[]>([]);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [status, setStatus] = useState("Laden");
  const [error, setError] = useState("");

  async function select(municipality: Municipality) {
    try {
      setError("");
      const response = await api.population(municipality.municipality_code);
      setSelected(municipality);
      setSearch(municipality.municipality_name);
      setItems([]);
      setSeries(response.observations);
    } catch { setError("De gemeentelijke tijdreeks kon niet worden geladen."); }
  }

  async function selectComparison(municipality: Municipality) {
    try {
      setError("");
      const response = await api.population(municipality.municipality_code);
      setComparison(municipality);
      setCompareSearch(municipality.municipality_name);
      setCompareItems([]);
      setComparisonSeries(response.observations);
    } catch { setError("De vergelijkingstijdreeks kon niet worden geladen."); }
  }

  async function load() {
    try {
      setError(""); setStatus("Laden"); await api.ready();
      const [availableYears, nationalSeries, latestLineage] = await Promise.all([api.years(), api.national(), api.lineage().catch(() => null)]);
      const selectedYear = year || availableYears.at(-1)?.year || 0;
      setYears(availableYears); setNational(nationalSeries); setYear(selectedYear); setLineage(latestLineage);
      setRanking(await api.ranking(selectedYear));
      const initialCode = initialRoute.get("municipality"); const initialComparison = initialRoute.get("compare");
      if (initialCode && !selected) await select(await api.municipality(initialCode));
      if (initialComparison && !comparison && initialComparison !== initialCode) await selectComparison(await api.municipality(initialComparison));
      setStatus("Beschikbaar");
    } catch { setStatus("Niet beschikbaar"); setError("De gegevens zijn tijdelijk niet beschikbaar. Probeer het later opnieuw."); }
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!year) return;
    const query = new URLSearchParams({year: String(year)});
    if (selected) query.set("municipality", selected.municipality_code);
    if (comparison) query.set("compare", comparison.municipality_code);
    history.replaceState(null, "", `?${query.toString()}`);
    void api.ranking(year).then(setRanking).catch(() => setError("De ranking kon niet worden geladen."));
    if (selected) void api.ranking(year, 500).then(setFullRanking).catch(() => setFullRanking([])); else setFullRanking([]);
  }, [year, selected, comparison]);

  useMunicipalitySearch(search, selected?.municipality_name, setItems, setError);
  useMunicipalitySearch(compareSearch, comparison?.municipality_name, setCompareItems, setError);

  const current = national.find((item) => item.year === year);
  const previous = national.find((item) => item.year === year - 1);
  const nationalChange = current && previous && current.population_january_1 !== null && previous.population_january_1 !== null ? current.population_january_1 - previous.population_january_1 : null;
  const selectedObservation = series.find((item) => item.year === year);
  const selectedChange = annualChanges(series).find((item) => item.year === year)?.change ?? null;
  const selectedRank = fullRanking.find((item) => item.municipality_code === selected?.municipality_code)?.rank ?? null;

  return <main>
    <header><div><p className="eyebrow">CBS Open Data · Bevolking in beeld</p><h1>Gemeente Data Platform</h1></div><div className="header-actions"><div className={`status ${status === "Beschikbaar" ? "ok" : "bad"}`} aria-live="polite">API: {status}</div><a className="button secondary" href={publicApiUrl("/docs")} target="_blank" rel="noopener noreferrer">API-documentatie</a><button onClick={() => void load()}>Vernieuwen</button></div></header>
    <section className="filters" aria-label="Dashboardfilters"><label>Jaar<select aria-label="Jaar" value={year} onChange={(event) => setYear(Number(event.target.value))}>{years.map((item) => <option key={item.year} value={item.year}>{item.year}</option>)}</select></label><SearchControl label="Gemeente" value={search} onChange={setSearch} items={items} onSelect={select} /><button onClick={() => { setSearch(""); setSelected(null); setSeries([]); setCompareSearch(""); setComparison(null); setComparisonSeries([]); }}>Wis filters</button></section>
    {error && <p role="alert" className="error">{error}</p>}
    {current?.average_population === null && <p className="warning">Gemiddelde bevolking voor {year} ontbreekt; dit is geen nulwaarde.</p>}
    <section className="kpis" aria-label="Kerncijfers"><Card title="Nederlandse bevolking" value={number(current?.population_january_1 ?? null)} /><Card title="Gemeenten met waarneming" value={number(current?.municipality_count ?? null)} /><Card title="Verandering t.o.v. vorig jaar" value={number(nationalChange)} /><Card title="Procentuele verandering" value={previous && nationalChange !== null && previous.population_january_1 ? percent(String(nationalChange / previous.population_january_1 * 100)) : "Niet beschikbaar"} /></section>
    <section className="grid" aria-label="Bevolkingsanalyses" aria-busy={status === "Laden"}><Chart title="Nationale bevolkingstrend" data={national} dataKey="population_january_1" xKey="year" /><Chart title="Top 10 gemeenten" data={ranking} dataKey="population_january_1" xKey="municipality_name" bar /><RankingTable ranking={ranking} year={year} /><Chart title="Jaarlijkse verandering Nederland" data={annualChanges(national)} dataKey="change" xKey="year" bar />{selected ? <><MunicipalityKpis municipality={selected} observation={selectedObservation} change={selectedChange} rank={selectedRank} /><Chart title={`Tijdreeks ${selected.municipality_name}`} data={series} dataKey="population_january_1" xKey="year" /><Chart title={`Jaarlijkse verandering ${selected.municipality_name}`} data={annualChanges(series)} dataKey="change" xKey="year" bar /><ComparisonPanel selected={selected} comparison={comparison} series={series} comparisonSeries={comparisonSeries} search={compareSearch} items={compareItems} onSearch={setCompareSearch} onSelect={selectComparison} onClear={() => { setCompareSearch(""); setComparison(null); setComparisonSeries([]); }} /></> : <SelectionCard />}</section>
    <LineageSummary years={years} lineage={lineage} />
    <footer><div><p className="eyebrow">Van bron tot inzicht</p><h2>Ontwikkeld door Salah Abdulkader</h2><p className="provenance">Een end-to-end portfolio-dataplatform op basis van CBS Open Data. Historische herindelingen kunnen tijdreeksen beïnvloeden.</p></div><div><nav aria-label="Portfolio en documentatie"><SocialLink href="https://github.com/salahooo" label="GitHub-profiel" brand="github" /><SocialLink href="https://github.com/salahooo/gemeente-data-platform" label="Broncode" brand="github" repository /><SocialLink href={LINKEDIN_URL} label="LinkedIn" brand="linkedin" /><a href={publicApiUrl("/docs")} target="_blank" rel="noopener noreferrer">API-documentatie</a></nav><p className="technology">Python · PostgreSQL · FastAPI · React · TypeScript · Docker · GitHub Actions</p></div></footer>
  </main>;
}

function useMunicipalitySearch(value: string, selectedName: string | undefined, setItems: (items: Municipality[]) => void, setError: (message: string) => void) { useEffect(() => { if (value.length < 2 || value === selectedName) { setItems([]); return; } const controller = new AbortController(); const timer = setTimeout(() => { void api.municipalities(value, controller.signal).then((response) => setItems(response.items)).catch(() => { if (!controller.signal.aborted) setError("Zoeken naar gemeenten is mislukt."); }); }, 250); return () => { controller.abort(); clearTimeout(timer); }; }, [value, selectedName, setItems, setError]); }
function SearchControl({label, value, onChange, items, onSelect}: {label: string; value: string; onChange: (value: string) => void; items: Municipality[]; onSelect: (municipality: Municipality) => void}) { return <div className="municipality-filter"><label>{label}<input aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} placeholder="Zoek vanaf 2 letters" autoComplete="off" /></label>{items.length > 0 && <ul className="results" aria-label={`${label} zoekresultaten`}>{items.map((municipality) => <li key={municipality.municipality_code}><button onClick={() => void onSelect(municipality)}>{municipality.municipality_name} <small>{municipality.municipality_code}</small></button></li>)}</ul>}</div>; }
function SelectionCard() { return <article className="card selection-card"><p className="eyebrow">Gemeenteanalyse</p><h2>Selecteer een gemeente</h2><p>Zoek bovenaan naar een gemeente om de tijdreeks, jaarlijkse verandering en positie in Nederland te bekijken.</p></article>; }
function Card({title, value}: {title: string; value: string}) { return <article className="card kpi"><h2>{title}</h2><strong>{value}</strong></article>; }
function MunicipalityKpis({municipality, observation, change, rank}: {municipality: Municipality; observation: Observation | undefined; change: number | null; rank: number | null}) { const changePercent = observation?.population_change_percent ?? null; return <section className="municipality-kpis" aria-label={`Kerncijfers ${municipality.municipality_name}`}><Card title={`${municipality.municipality_name} in ${observation?.year ?? "gekozen jaar"}`} value={number(observation?.population_january_1 ?? null)} /><Card title="Verandering t.o.v. vorig jaar" value={change === null ? "Niet beschikbaar" : `${number(change)} (${percent(changePercent)})`} /><Card title="Positie in Nederland" value={rank === null ? "Niet beschikbaar" : `#${number(rank)}`} /></section>; }
function ComparisonPanel({selected, comparison, series, comparisonSeries, search, items, onSearch, onSelect, onClear}: {selected: Municipality; comparison: Municipality | null; series: Series; comparisonSeries: Series; search: string; items: Municipality[]; onSearch: (value: string) => void; onSelect: (municipality: Municipality) => void; onClear: () => void}) { const availableItems = items.filter((item) => item.municipality_code !== selected.municipality_code); const comparisonValues = comparisonData(selected, series, comparison ?? selected, comparisonSeries); const latest = comparisonValues.filter((item) => item.primary !== null && item.secondary !== null).at(-1); return <article className="card comparison"><div className="comparison-heading"><div><h2>Vergelijk gemeenten</h2><p className="caption">Vergelijk maximaal twee gemeenten in dezelfde jaren.</p></div>{comparison && <button className="text-button" onClick={onClear}>Vergelijking wissen</button>}</div><SearchControl label="Vergelijk met gemeente" value={search} onChange={onSearch} items={availableItems} onSelect={onSelect} />{comparison ? <><Chart title="" data={comparisonValues} dataKey="primary" xKey="year" comparison={{first: selected.municipality_name, second: comparison.municipality_name}} embedded /><p className="caption">Laatste gezamenlijke jaar {latest?.year ?? "niet beschikbaar"}: {selected.municipality_name} {number(latest?.primary as number ?? null)} · {comparison.municipality_name} {number(latest?.secondary as number ?? null)} · verschil {number(latest?.difference as number ?? null)}. Historische herindelingen kunnen de vergelijking beïnvloeden.</p></> : <p className="empty compact">Kies een tweede gemeente voor een vergelijking op gelijke jaren.</p>}</article>; }
function comparisonData(firstMunicipality: Municipality, first: Series, secondMunicipality: Municipality, second: Series): ChartDatum[] { const values = new Map<number, ChartDatum>(); for (const item of first) values.set(item.year, {year: item.year, primary: item.population_january_1}); for (const item of second) values.set(item.year, {...(values.get(item.year) ?? {year: item.year, primary: null}), secondary: item.population_january_1}); return [...values.values()].sort((a, b) => Number(a.year) - Number(b.year)).map((item) => ({...item, difference: item.primary !== null && item.secondary !== null ? Number(item.primary) - Number(item.secondary) : null})); }
function LineageSummary({years, lineage}: {years: Year[]; lineage: Lineage | null}) { return <aside className="lineage" aria-label="Databron en actualiteit"><span><strong>Bron</strong> CBS Open Data</span><span><strong>Beschikbare periode</strong> {years.length ? `${years[0]?.year}–${years.at(-1)?.year}` : "Niet beschikbaar"}</span><span><strong>Laatste succesvolle dataset</strong> {lineage ? `${lineage.processed_run_id} · ${new Intl.DateTimeFormat("nl-NL", {dateStyle: "medium", timeStyle: "short"}).format(new Date(lineage.completed_at))}` : "Niet beschikbaar"}</span></aside>; }
function RankingTable({ranking, year}: {ranking: Ranking[]; year: number}) { return <div className="card ranking"><h2>Ranking {year}</h2><p className="caption">Top 10 · inwoners op 1 januari</p>{ranking.length ? <table><caption className="visually-hidden">Gemeenten naar inwonertal in {year}</caption><thead><tr><th scope="col">Rang</th><th scope="col">Gemeente</th><th scope="col">Inwoners</th></tr></thead><tbody>{ranking.map((item) => <tr key={item.municipality_code}><td>{item.rank}</td><th scope="row">{item.municipality_name}</th><td>{number(item.population_january_1)}</td></tr>)}</tbody></table> : <p>Geen ranking beschikbaar.</p>}</div>; }
function Chart({title, data, dataKey, xKey, bar = false, embedded = false, comparison}: {title: string; data: ChartDatum[]; dataKey: string; xKey: string; bar?: boolean; embedded?: boolean; comparison?: {first: string; second: string}}) { const Content = bar ? BarChart : LineChart; const change = dataKey === "change"; const horizontal = xKey === "municipality_name"; const values = data.map((item) => Number(item[dataKey])).filter(Number.isFinite); const padding = values.length ? Math.max((Math.max(...values) - Math.min(...values)) * .12, Math.max(...values) * .005, 1) : 0; const dynamicDomain = !change && !horizontal && values.length ? [Math.max(0, Math.floor(Math.min(...values) - padding)), Math.ceil(Math.max(...values) + padding)] : undefined; const graph = data.length ? <div className="chart-frame" role="img" aria-label={title || "Vergelijking geselecteerde gemeenten"}><ResponsiveContainer width="100%" height={horizontal ? 290 : 240}><Content data={data} layout={horizontal ? "vertical" : "horizontal"} margin={{top: 12, right: 18, bottom: 4, left: 18}}><CartesianGrid stroke="#e5eded" vertical={horizontal} horizontal={!horizontal} /><XAxis type={horizontal ? "number" : "category"} dataKey={horizontal ? undefined : xKey} interval="preserveStartEnd" tick={{fontSize: 11}} tickLine={false} axisLine={false} tickFormatter={horizontal ? (value) => new Intl.NumberFormat("nl-NL", {notation: "compact"}).format(value) : undefined} /><YAxis type={horizontal ? "category" : "number"} dataKey={horizontal ? xKey : undefined} interval={horizontal ? 0 : undefined} width={horizontal ? 132 : 100} domain={horizontal ? undefined : dynamicDomain} tick={{fontSize: 11}} tickLine={false} axisLine={false} tickFormatter={horizontal ? (value: string) => value.replace(" (gemeente)", "") : (value) => number(value)} /><Tooltip formatter={(value, name) => [value == null ? "Niet beschikbaar" : number(Number(value)), comparison ? name : change ? "Verandering inwoners" : "Inwoners op 1 januari"]} labelFormatter={(value) => `Jaar ${value}`} />{comparison && <Legend />}{change && <ReferenceLine y={0} stroke="#6d858a" />}{bar ? <Bar dataKey={dataKey} fill={change ? "#266ba0" : "#0b6e69"} maxBarSize={36} radius={[3, 3, 0, 0]} isAnimationActive={false} /> : comparison ? <><Line type="linear" dataKey="primary" name={comparison.first} stroke="#0b6e69" strokeWidth={2.5} dot={{r: 3}} connectNulls={false} isAnimationActive={false} /><Line type="linear" dataKey="secondary" name={comparison.second} stroke="#266ba0" strokeWidth={2.5} dot={{r: 3}} connectNulls={false} isAnimationActive={false} /></> : <Line type="linear" dataKey={dataKey} stroke="#0b6e69" strokeWidth={2.5} dot={{r: 3}} connectNulls={false} isAnimationActive={false} />}</Content></ResponsiveContainer></div> : <p className="empty">Nog geen gegevens beschikbaar.</p>; const caption = change ? "Verschil tussen opeenvolgende 1-januaristanden. Ontbrekend jaar: onbekend." : title === "Nationale bevolkingstrend" ? "Inwoners op 1 januari · CBS. De Y-as gebruikt een dynamisch bereik en start niet bij nul." : "Inwoners op 1 januari · CBS"; return embedded ? graph : <article className="card chart"><h2>{title}</h2>{graph}<p className="caption">{caption}</p></article>; }
