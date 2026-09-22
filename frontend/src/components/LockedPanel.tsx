import { useRequestPlan } from "../planChange";
import type { PlanLock } from "../types";

type Skeleton = "listings" | "curve" | "facts" | "charts";

/** Blur edilen iskelet: GERÇEK veri değil, yalnızca bölümün şekli.
 *  (Gerçek veriyi gönderip CSS ile bulanıklaştırmak tarayıcıdan okunabilirdi.) */
function Ghost({ kind }: { kind: Skeleton }) {
  if (kind === "curve") {
    return (
      <svg className="ghost-curve" viewBox="0 0 320 110" aria-hidden="true">
        <path d="M10,25 C90,35 150,60 310,92" />
        <circle cx="10" cy="25" r="7" /><circle cx="160" cy="58" r="7" /><circle cx="310" cy="92" r="7" />
      </svg>
    );
  }
  if (kind === "facts") {
    return <div className="ghost-facts">{Array.from({ length: 6 }).map((_, i) => (
      <div key={i}><span /><b /></div>))}</div>;
  }
  if (kind === "charts") {
    return <div className="ghost-charts">{Array.from({ length: 12 }).map((_, i) => (
      <i key={i} style={{ height: `${25 + ((i * 37) % 60)}%` }} />))}</div>;
  }
  return <div className="ghost-listings">{Array.from({ length: 3 }).map((_, i) => (
    <div key={i}><span className="g-title" /><span className="g-meta" /><span className="g-price" /></div>))}</div>;
}

export default function LockedPanel({ lock, teaser, skeleton = "listings", compact }: {
  lock: PlanLock; teaser?: string; skeleton?: Skeleton; compact?: boolean;
}) {
  const requestPlan = useRequestPlan();
  const required = lock.required_plan === "premium" ? "Premium" : "Pro";
  return (
    <div className={`locked-panel${compact ? " compact" : ""}`}>
      <div className="locked-ghost" aria-hidden="true"><Ghost kind={skeleton} /></div>
      <div className="locked-overlay">
        <span className={`locked-badge plan-${lock.required_plan}`}>🔒 {required}</span>
        {teaser && <strong>{teaser}</strong>}
        <p>Bu bölümü görmek için <b>{lock.required_plan_name}</b> plan gerekiyor. Şu anki planınız: <b>{lock.current_plan_name}</b>.</p>
        <button type="button" className="primary-button" onClick={() => requestPlan(lock.required_plan)}>
          {required === "Premium" ? "Premium'a geç" : "Pro'ya geç"} <span>→</span></button>
      </div>
    </div>
  );
}
