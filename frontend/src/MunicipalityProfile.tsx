import {useEffect, useState} from "react";
import {api} from "./api";
import {number} from "./format";
import type {AgeProfileData, DataQuality} from "./types";

const labels: Record<string, string> = {"0-14": "0–14 jaar", "15-24": "15–24 jaar", "25-44": "25–44 jaar", "45-64": "45–64 jaar", "65+": "65 jaar en ouder"};
const percentage = (value: string | null) => value === null ? "Onbekend" : `${new Intl.NumberFormat("nl-NL", {maximumFractionDigits: 1}).format(Number(value))}%`;

export function AgeProfile({code, year, revision}: {code: string; year: number; revision: number}) {
  const [data, setData] = useState<AgeProfileData | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void api.profile(code, year, controller.signal).then((result) => { if (!controller.signal.aborted) setData(result); }).catch(() => {});
    return () => controller.abort();
  }, [code, year, revision]);
  const categories = data?.municipality_code === code && data.year === year ? data.categories : [];
  if (!categories.length) return <p className="profile-unavailable">Aanvullende profielgegevens zijn nog niet beschikbaar.</p>;
  return <div className="age-profile">
    <h3>Leeftijdsopbouw op 1 januari {year}</h3>
    <p className="caption">Aandeel van de bevolking; Nederland is het landelijke aandeel, geen ongewogen gemiddelde van gemeenten.</p>
    <table className="age-chart"><caption>Leeftijdsopbouw: inwoners en aandeel, met Nederland als referentie</caption>
      <thead><tr><th scope="col">Leeftijd</th><th scope="col">Inwoners</th><th scope="col">Gemeente / NL</th></tr></thead>
      <tbody>{categories.map((item) => <tr key={item.category}><th scope="row">{labels[item.category] ?? item.category}</th><td>{number(item.population)}</td><td>
        <span>{percentage(item.share_percent)} / {percentage(item.national_share_percent)}</span>
        <span className="age-bars" aria-hidden="true"><i style={{width: `${Number(item.share_percent ?? 0)}%`}} /><i className="national-bar" style={{width: `${Number(item.national_share_percent ?? 0)}%`}} /></span>
      </td></tr>)}</tbody></table>
    <p className="caption">Groen: gemeente · blauw: Nederland. Ontbrekende waarden blijven onbekend.</p>
    <p className="caption">Bron: <a href="https://www.cbs.nl/nl-nl/cijfers/detail/70072ned" target="_blank" rel="noopener noreferrer">CBS Regionale kerncijfers Nederland (70072ned)</a>. Leeftijd in voltooide jaren op 1 januari; 65+ omvat 65–79 en 80+.</p>
  </div>;
}

export function QualityMonitor({revision}: {revision: number}) {
  const [datasets, setDatasets] = useState<DataQuality[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    void api.dataQuality(controller.signal).then((data) => { if (!controller.signal.aborted) setDatasets(Array.isArray(data) ? data : []); }).catch(() => {});
    return () => controller.abort();
  }, [revision]);
  return <section className="quality-monitor" id="bron" aria-labelledby="quality-heading"><h2 id="quality-heading">Datakwaliteit</h2>
    {!datasets.length ? <p className="profile-unavailable">Publieke kwaliteitsgegevens zijn nog niet beschikbaar.</p> : <div className="quality-cards">{datasets.map((data) => <article className="card" key={data.dataset_code}>
      <h3>{data.dataset_name}</h3><p className="caption">{data.source} · {data.dataset_code}</p>
      <dl><div><dt>Periode</dt><dd>{data.first_year === null ? "Niet beschikbaar" : `${data.first_year}–${data.last_year}`}</dd></div>
        <div><dt>Laatste succesvolle verwerking</dt><dd>{data.completed_at ? new Intl.DateTimeFormat("nl-NL", {dateStyle: "medium", timeStyle: "short"}).format(new Date(data.completed_at)) : "Niet beschikbaar"}</dd></div>
        <div><dt>Geladen records</dt><dd>{number(data.record_count)}</dd></div>
        <div><dt>Validatie</dt><dd>{data.validation_status === "validated" ? "✓ Gevalideerd" : "Nog niet beschikbaar"}</dd></div>
        <div><dt>Ontbrekende kernwaarden</dt><dd>{number(data.missing_values)}</dd></div></dl>
      <p className="caption">{data.warning}</p>
    </article>)}</div>}
  </section>;
}
