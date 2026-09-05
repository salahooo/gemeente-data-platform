import {useEffect, useState} from "react";
import {Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";

import {api, publicApiUrl} from "./api";
import {number, percent} from "./format";
import {annualChanges} from "./changes";
import {LINKEDIN_URL} from "./portfolio";
import {SocialLink} from "./SocialLink";
import type {Municipality, National, Observation, Ranking, Year} from "./types";

type Series = Pick<Observation, "year" | "population_january_1" | "population_change_absolute">[];

export function App() {
  const parameters = new URLSearchParams(location.search);
  const initialCode = parameters.get("municipality");
  const [years, setYears] = useState<Year[]>([]);
  const [national, setNational] = useState<National[]>([]);
  const [ranking, setRanking] = useState<Ranking[]>([]);
  const [year, setYear] = useState(Number(parameters.get("year")) || 0);
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<Municipality[]>([]);
  const [selected, setSelected] = useState<Municipality | null>(null);
  const [series, setSeries] = useState<Series>([]);
  const [status, setStatus] = useState("Laden");
  const [error, setError] = useState("");

  async function select(municipality: Municipality) {
    try {
      setError("");
      setSelected(municipality);
      setSearch(municipality.municipality_name);
      setItems([]);
      setSeries((await api.population(municipality.municipality_code)).observations);
    } catch {
      setError("De gemeentelijke tijdreeks kon niet worden geladen.");
    }
  }

  async function load() {
    try {
      setError("");
      setStatus("Laden");
      await api.ready();
      const [availableYears, nationalSeries] = await Promise.all([api.years(), api.national()]);
      const selectedYear = year || availableYears.at(-1)?.year || 0;
      setYears(availableYears);
      setNational(nationalSeries);
      setYear(selectedYear);
      setRanking(await api.ranking(selectedYear));
      if (initialCode) await select(await api.municipality(initialCode));
      setStatus("Beschikbaar");
    } catch {
      setStatus("Niet beschikbaar");
      setError("De gegevens zijn tijdelijk niet beschikbaar. Probeer het later opnieuw.");
    }
  }

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (!year) return;
    const query = new URLSearchParams({year: String(year)});
    if (selected) query.set("municipality", selected.municipality_code);
    history.replaceState(null, "", `?${query.toString()}`);
    void api.ranking(year).then(setRanking).catch(() => setError("De ranking kon niet worden geladen."));
  }, [year, selected]);

  useEffect(() => {
    if (search.length < 2 || search === selected?.municipality_name) {
      setItems([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void api.municipalities(search, controller.signal)
        .then((response) => setItems(response.items))
        .catch(() => { if (!controller.signal.aborted) setError("Zoeken naar gemeenten is mislukt."); });
    }, 250);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [search, selected]);

  const current = national.find((item) => item.year === year);
  const previous = national.find((item) => item.year === year - 1);
  const change = current && previous && current.population_january_1 !== null && previous.population_january_1 !== null
    ? current.population_january_1 - previous.population_january_1 : null;

  return <main>
    <header>
      <div><p className="eyebrow">CBS Open Data · Bevolking in beeld</p><h1>Gemeente Data Platform</h1></div>
      <div className="header-actions">
      <div className={`status ${status === "Beschikbaar" ? "ok" : "bad"}`} aria-live="polite">API: {status}</div>
      <a className="button secondary" href={publicApiUrl("/docs")} target="_blank" rel="noopener noreferrer">API-documentatie</a><button onClick={() => void load()}>Vernieuwen</button>
      </div>
    </header>
    <section className="filters" aria-label="Dashboardfilters">
      <label>Jaar<select aria-label="Jaar" value={year} onChange={(event) => setYear(Number(event.target.value))}>{years.map((item) => <option key={item.year} value={item.year}>{item.year}</option>)}</select></label>
      <div className="municipality-filter"><label>Gemeente<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Zoek vanaf 2 letters" autoComplete="off" /></label>
      {items.length > 0 && <ul className="results" aria-label="Zoekresultaten">{items.map((municipality) => <li key={municipality.municipality_code}><button onClick={() => void select(municipality)}>{municipality.municipality_name} <small>{municipality.municipality_code}</small></button></li>)}</ul>}
      </div>
      <button onClick={() => { setSearch(""); setSelected(null); setSeries([]); }}>Wis filters</button>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    {current?.average_population === null && <p className="warning">Gemiddelde bevolking voor {year} ontbreekt; dit is geen nulwaarde.</p>}
    <section className="kpis" aria-label="Kerncijfers">
      <Card title="Nederlandse bevolking" value={number(current?.population_january_1 ?? null)} />
      <Card title="Gemeenten met waarneming" value={number(current?.municipality_count ?? null)} />
      <Card title="Verandering t.o.v. vorig jaar" value={number(change)} />
      <Card title="Procentuele verandering" value={previous && change !== null && previous.population_january_1 ? percent(String(change / previous.population_january_1 * 100)) : "Niet beschikbaar"} />
    </section>
    <section className="grid" aria-label="Bevolkingsanalyses" aria-busy={status === "Laden"}>
      <Chart title="Nationale bevolkingstrend" data={national} dataKey="population_january_1" xKey="year" />
      <Chart title="Top 10 gemeenten" data={ranking} dataKey="population_january_1" xKey="municipality_name" bar />
      <RankingTable ranking={ranking} year={year} />
      <Chart title="Jaarlijkse verandering Nederland" data={annualChanges(national)} dataKey="change" xKey="year" bar />
      <div className="card"><h2>{selected ? `Tijdreeks ${selected.municipality_name}` : "Selecteer een gemeente"}</h2>{series.length ? <Chart title="" data={series} dataKey="population_january_1" xKey="year" embedded /> : <p>Zoek en selecteer een gemeente voor de tijdreeks.</p>}</div>
      <Chart title={selected ? `Jaarlijkse verandering ${selected.municipality_name}` : "Jaarlijkse verandering gemeente"} data={annualChanges(series)} dataKey="change" xKey="year" bar />
    </section>
    <footer>
      <div><p className="eyebrow">Van bron tot inzicht</p><h2>Ontwikkeld door Salah Abdulkader</h2><p className="provenance">Bron: CBS via gevalideerde platformpipeline. Historische herindelingen kunnen tijdreeksen beïnvloeden.</p></div>
      <div><nav aria-label="Portfolio en documentatie"><SocialLink href="https://github.com/salahooo" label="GitHub-profiel Salah" brand="github" /><SocialLink href="https://github.com/salahooo/gemeente-data-platform" label="GitHub-repository" brand="github" repository /><SocialLink href={LINKEDIN_URL} label="LinkedIn Salah" brand="linkedin" /><a href={publicApiUrl("/docs")} target="_blank" rel="noopener noreferrer">Publieke API-documentatie</a></nav><p className="technology">Python · PostgreSQL · FastAPI · React · TypeScript · Docker · GitHub Actions</p></div>
    </footer>
  </main>;
}

function Card({title, value}: {title: string; value: string}) { return <article className="card kpi"><h2>{title}</h2><strong>{value}</strong></article>; }

function RankingTable({ranking, year}: {ranking: Ranking[]; year: number}) {
  return <div className="card ranking"><h2>Ranking {year}</h2><p className="caption">Top 10 · inwoners op 1 januari</p>{ranking.length ? <table><caption className="visually-hidden">Gemeenten naar inwonertal in {year}</caption><thead><tr><th scope="col">Rang</th><th scope="col">Gemeente</th><th scope="col">Inwoners</th></tr></thead><tbody>{ranking.map((item) => <tr key={item.municipality_code}><td>{item.rank}</td><th scope="row">{item.municipality_name}</th><td>{number(item.population_january_1)}</td></tr>)}</tbody></table> : <p>Geen ranking beschikbaar.</p>}</div>;
}

function Chart({title, data, dataKey, xKey, bar = false, embedded = false}: {title: string; data: object[]; dataKey: string; xKey: string; bar?: boolean; embedded?: boolean}) {
  const Content = bar ? BarChart : LineChart;
  const change = dataKey === "change";
  const horizontal = xKey === "municipality_name";
  const graph = data.length ? <div className="chart-frame" role="img" aria-label={title || "Bevolking geselecteerde gemeente"}><ResponsiveContainer width="100%" height={horizontal ? 290 : 240}><Content data={data} layout={horizontal ? "vertical" : "horizontal"} margin={{top: 12, right: 16, bottom: 4, left: 8}}><CartesianGrid stroke="#e5eded" vertical={horizontal} horizontal={!horizontal} /><XAxis type={horizontal ? "number" : "category"} dataKey={horizontal ? undefined : xKey} interval="preserveStartEnd" tick={{fontSize: 11}} tickLine={false} axisLine={false} tickFormatter={horizontal ? (value) => new Intl.NumberFormat("nl-NL", {notation: "compact"}).format(value) : undefined} /><YAxis type={horizontal ? "category" : "number"} dataKey={horizontal ? xKey : undefined} interval={horizontal ? 0 : undefined} width={horizontal ? 132 : 86} tick={{fontSize: 11}} tickLine={false} axisLine={false} tickFormatter={horizontal ? (value: string) => value.replace(" (gemeente)", "") : (value) => number(value)} /><Tooltip formatter={(value) => [value == null ? "Niet beschikbaar" : number(Number(value)), change ? "Verandering inwoners" : "Inwoners op 1 januari"]} />{change && <ReferenceLine y={0} stroke="#6d858a" />}{bar ? <Bar dataKey={dataKey} fill={change ? "#266ba0" : "#0b6e69"} maxBarSize={36} radius={[3, 3, 0, 0]} isAnimationActive={false} /> : <Line type="linear" dataKey={dataKey} stroke="#0b6e69" strokeWidth={2.5} dot={{r: 3}} connectNulls={false} isAnimationActive={false} />}</Content></ResponsiveContainer></div> : <p className="empty">{change ? "Selecteer een gemeente om de jaarlijkse verandering te bekijken." : "Nog geen gegevens beschikbaar."}</p>;
  return embedded ? graph : <article className="card chart"><h2>{title}</h2>{graph}<p className="caption">{change ? "Verschil tussen opeenvolgende 1-januaristanden. Ontbrekend jaar: onbekend." : "Inwoners op 1 januari · CBS"}</p></article>;
}
