import {useEffect, useState} from "react";
import {Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";

import {api, publicApiUrl} from "./api";
import {number, percent} from "./format";
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
        .catch(() => setError("Zoeken naar gemeenten is mislukt."));
    }, 250);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [search, selected]);

  const current = national.find((item) => item.year === year);
  const previous = national.find((item) => item.year === year - 1);
  const change = current && previous && current.population_january_1 !== null && previous.population_january_1 !== null
    ? current.population_january_1 - previous.population_january_1 : null;

  return <main>
    <header>
      <div><p className="eyebrow">CBS bevolkingsdata · read-only analytics</p><h1>Gemeente Data Platform</h1></div>
      <div className={`status ${status === "Beschikbaar" ? "ok" : "bad"}`} aria-live="polite">API: {status}</div>
      <a href={publicApiUrl("/docs")}>API-documentatie</a><button onClick={() => void load()}>Vernieuwen</button>
    </header>
    <section className="filters" aria-label="Dashboardfilters">
      <label>Jaar<select value={year} onChange={(event) => setYear(Number(event.target.value))}>{years.map((item) => <option key={item.year} value={item.year}>{item.year}</option>)}</select></label>
      <label>Gemeente<input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Zoek vanaf 2 letters" /></label>
      <button onClick={() => { setSearch(""); setSelected(null); setSeries([]); }}>Wis filters</button>
      {items.length > 0 && <ul className="results" aria-label="Zoekresultaten">{items.map((municipality) => <li key={municipality.municipality_code}><button onClick={() => void select(municipality)}>{municipality.municipality_name} <small>{municipality.municipality_code}</small></button></li>)}</ul>}
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    {current?.average_population === null && <p className="warning">Gemiddelde bevolking voor {year} ontbreekt; dit is geen nulwaarde.</p>}
    <section className="kpis" aria-label="Kerncijfers">
      <Card title="Nederlandse bevolking" value={number(current?.population_january_1 ?? null)} />
      <Card title="Gemeenten met waarneming" value={number(current?.municipality_count ?? null)} />
      <Card title="Verandering t.o.v. vorig jaar" value={number(change)} />
      <Card title="Procentuele verandering" value={previous && change !== null && previous.population_january_1 ? percent(String(change / previous.population_january_1 * 100)) : "Niet beschikbaar"} />
    </section>
    <section className="grid">
      <Chart title="Nationale bevolkingstrend" data={national} dataKey="population_january_1" xKey="year" />
      <Chart title="Top 10 gemeenten" data={ranking} dataKey="population_january_1" xKey="municipality_name" bar />
      <div className="card"><h2>{selected ? `Tijdreeks ${selected.municipality_name}` : "Selecteer een gemeente"}</h2>{series.length ? <Chart title="" data={series} dataKey="population_january_1" xKey="year" embedded /> : <p>Zoek en selecteer een gemeente voor de tijdreeks.</p>}</div>
      <RankingTable ranking={ranking} year={year} />
    </section>
    <footer>Bron: CBS via gevalideerde platformpipeline. Historische herindelingen kunnen tijdreeksen beïnvloeden. Officiële gemeentekaart: toekomstig.</footer>
  </main>;
}

function Card({title, value}: {title: string; value: string}) { return <article className="card kpi"><h2>{title}</h2><strong>{value}</strong></article>; }

function RankingTable({ranking, year}: {ranking: Ranking[]; year: number}) {
  return <div className="card"><h2>Ranking {year}</h2><table><thead><tr><th>Rang</th><th>Gemeente</th><th>Bevolking</th></tr></thead><tbody>{ranking.map((item) => <tr key={item.municipality_code}><td>{item.rank}</td><td>{item.municipality_name}</td><td>{number(item.population_january_1)}</td></tr>)}</tbody></table></div>;
}

function Chart({title, data, dataKey, xKey, bar = false, embedded = false}: {title: string; data: object[]; dataKey: string; xKey: string; bar?: boolean; embedded?: boolean}) {
  const Content = bar ? BarChart : LineChart;
  const graph = <ResponsiveContainer width="100%" height={260}><Content data={data}><XAxis dataKey={xKey} interval="preserveStartEnd" /><YAxis width={72} tickFormatter={(value) => number(value)} /><Tooltip />{bar ? <Bar dataKey={dataKey} fill="#0b6e69" isAnimationActive={false} /> : <Line type="monotone" dataKey={dataKey} stroke="#0b6e69" strokeWidth={3} isAnimationActive={false} />}</Content></ResponsiveContainer>;
  return embedded ? graph : <article className="card chart"><h2>{title}</h2>{graph}<p className="sr">Grafiek met gevalideerde gegevens.</p></article>;
}
