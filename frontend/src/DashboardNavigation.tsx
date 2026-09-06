import {createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode} from "react";

const Navigation = createContext({mobile: false, open: {} as Record<string, boolean>, toggle: (_id: string) => {}, navigate: (_id: string) => {}});
const sections = [["overzicht", "Overzicht"], ["nederland", "Nederland"], ["gemeente", "Gemeente"], ["vergelijken", "Vergelijken"], ["kaart", "Kaart"], ["bron", "Bron en techniek"]];
const behavior = (): ScrollBehavior => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";

export function NavigationProvider({children}: {children: ReactNode}) {
  const [mobile, setMobile] = useState(() => window.matchMedia?.("(max-width: 640px)").matches ?? false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [target, setTarget] = useState<string | null>(null);
  useEffect(() => {
    const media = window.matchMedia?.("(max-width: 640px)");
    if (!media) return;
    const change = () => setMobile(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  useLayoutEffect(() => {
    if (!target) return;
    const element = document.getElementById(target);
    element?.scrollIntoView({behavior: behavior(), block: "start"});
    element?.focus({preventScroll: true});
    setTarget(null);
  }, [target]);
  const navigate = (id: string) => {
    setOpen((current) => ({...current, [id]: true}));
    history.replaceState(null, "", `${location.pathname}${location.search}#${id}`);
    setTarget(id);
  };
  return <Navigation.Provider value={{mobile, open, navigate, toggle: (id) => setOpen((current) => ({...current, [id]: !current[id]}))}}>{children}</Navigation.Provider>;
}

export function CollapsibleSection({id, title, className, children}: {id: string; title: string; className?: string; children: ReactNode}) {
  const {mobile, open, toggle} = useContext(Navigation);
  const expanded = !mobile || !!open[id];
  return <section id={id} className={className} tabIndex={-1} aria-labelledby={`${id}-heading`}>
    <h2 id={`${id}-heading`}>{mobile ? <button className="section-toggle" aria-expanded={expanded} aria-controls={`${id}-content`} onClick={() => toggle(id)}>{title}<span aria-hidden="true">{expanded ? "⌃" : "⌄"}</span></button> : title}</h2>
    <div id={`${id}-content`} hidden={!expanded}>{children}</div>
  </section>;
}

export function SectionNavigation({ready}: {ready: boolean}) {
  const {navigate} = useContext(Navigation);
  const sentinel = useRef<HTMLSpanElement>(null);
  const [pastTop, setPastTop] = useState(false);
  useEffect(() => {
    if (!window.IntersectionObserver || !sentinel.current) return;
    const observer = new IntersectionObserver(([entry]) => setPastTop(!entry.isIntersecting && entry.boundingClientRect.top < 0));
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (ready && location.hash) navigate(location.hash.slice(1));
    // Restore a shared anchor only after its content has mounted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);
  return <><span className="top-sentinel" ref={sentinel} aria-hidden="true" /><nav className="section-nav" aria-label="Secties">{sections.map(([id, label]) => <a key={id} href={`#${id}`} onClick={(event) => {event.preventDefault(); navigate(id);}}>{label}</a>)}</nav>{pastTop && <button className="back-to-top" onClick={() => {window.scrollTo({top: 0, behavior: behavior()}); document.querySelector<HTMLElement>("h1")?.focus({preventScroll: true});}}>↑ Naar boven</button>}</>;
}
