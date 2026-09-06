import type {ReactNode} from "react";
import {CollapsibleSection} from "./DashboardNavigation";
import {publicApiUrl} from "./api";
import {LINKEDIN_URL} from "./portfolio";

export function SourceTechnique({children}: {children: ReactNode}) {
  return <CollapsibleSection id="bron" title="Bron en techniek" className="card source-tech">
    <p>Van officiële bron tot controleerbaar inzicht: een portfolio van Salah Abdulkader.</p>
    <div className="source-grid">
      <div><h3>Bronnen en interpretatie</h3><p>CBS Open Data: <strong>03759ned</strong> voor bevolking en <strong>70072ned</strong> voor leeftijdsopbouw. De kaart gebruikt gemeentegrenzen van CBS/PDOK uit 2026.</p><p>Bevolking en leeftijd hebben als peildatum 1 januari. Beschikbare jaren staan in de jaarselectie en de kwaliteitsmonitor. Historische herindelingen kunnen vergelijkingen beïnvloeden; historische codes hebben niet altijd een huidige kaartgeometrie. Ontbrekende waarden blijven onbekend, nooit nul.</p></div>
      <div><h3>Technische keuzes</h3><p>Python verzorgt de reproduceerbare ETL. PostgreSQL bewaart de data, Alembic beheert het schema en mart-views maken analyses herbruikbaar. FastAPI biedt een read-only API; React en TypeScript verzorgen de interactieve presentatie.</p><p>Docker maakt de runtime reproduceerbaar. GitHub Actions voert CI uit. Render host dashboard en API; Neon levert PostgreSQL.</p></div>
    </div>
    <h3>Van bron naar dashboard</h3><ol className="data-chain" aria-label="Dataketen">{["CBS Open Data", "Extractie", "Validatie", "PostgreSQL", "Mart-views", "FastAPI", "React-dashboard"].map((step) => <li key={step}>{step}</li>)}</ol>
    <h3>Kwaliteit en betrouwbaarheid</h3><p>Datacontracten en validatie bewaken de verwerking. Atomaire loads voorkomen gedeeltelijk geladen datasets. Gescheiden rollen met minimale rechten houden de publieke API read-only. CI controleert wijzigingen; lineage en de kwaliteitsmonitor maken herkomst, verwerking en ontbrekende waarden zichtbaar.</p>
    {children}
    <nav className="portfolio-links" aria-label="Projectlinks">{[["https://gemeente-data-platform-dashboard.onrender.com", "Live dashboard"], [publicApiUrl("/docs"), "API-docs"], ["https://github.com/salahooo/gemeente-data-platform", "GitHub-repository"], ["https://github.com/salahooo", "GitHub-profiel"], [LINKEDIN_URL, "LinkedIn"]].map(([href, label]) => <a key={label} href={href} target="_blank" rel="noopener noreferrer">{label}</a>)}</nav>
  </CollapsibleSection>;
}
