import {useCallback, useEffect, useState, type ReactNode} from "react";

export type FeedbackKind = "success" | "warning" | "info" | "error";
export function Feedback({kind, children, onClose}: {kind: FeedbackKind; children: ReactNode; onClose?: () => void}) {
  return <div className={`feedback feedback-${kind}`} role={kind === "error" ? "alert" : "status"} aria-live={kind === "error" ? "assertive" : "polite"} aria-atomic="true">
    <span aria-hidden="true" className="feedback-icon">{{success: "✓", warning: "⚠", info: "ⓘ", error: "✕"}[kind]}</span>
    <div>{children}</div>{onClose && <button className="feedback-close" aria-label="Melding sluiten" onClick={onClose}>×</button>}
  </div>;
}

export function useFeedback() {
  const [message, setMessage] = useState<{kind: FeedbackKind; text: string} | null>(null);
  const clear = useCallback(() => setMessage(null), []);
  const notify = useCallback((kind: FeedbackKind, text: string) => {
    setMessage((previous) => previous?.kind === kind && previous.text === text ? previous : {kind, text});
  }, []);
  useEffect(() => {
    if (message?.kind !== "success") return;
    const timer = setTimeout(clear, 3000);
    return () => clearTimeout(timer);
  }, [message, clear]);
  return {message, notify, clear};
}

export async function copyViewLink() {
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(location.href);
  } catch {
    const previous = document.activeElement as HTMLElement | null;
    const input = document.createElement("textarea");
    input.value = location.href;
    input.className = "clipboard-fallback";
    input.setAttribute("aria-label", "Weergavelink");
    document.body.append(input);
    try {
      input.select();
      if (!document.execCommand?.("copy")) throw new Error("Copy failed");
    } finally {
      input.remove();
      previous?.focus();
    }
  }
}

export function DashboardSkeleton() {
  return <div aria-busy="true" aria-label="Dashboard laden" className="dashboard-skeleton">
    <span className="visually-hidden" role="status">Dashboardgegevens laden…</span>
    <div className="kpis" aria-hidden="true">{Array.from({length: 4}, (_, i) => <div className="card kpi" key={i}><div className="skeleton-line" /><div className="skeleton-line skeleton-value" /></div>)}</div>
    <div className="grid" aria-hidden="true">{Array.from({length: 5}, (_, i) => <div className="card skeleton-chart" key={i}><div className="skeleton-line" /><div className="skeleton-plot" /></div>)}</div>
  </div>;
}
