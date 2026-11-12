import { useRequestPlan } from "../planChange";

const PLAN_NAME: Record<string, string> = { pro: "Pro", premium: "Premium" };

/** Planında olmayan bir sekmeye girilince gösterilen yükseltme kartı. */
export default function PlanLock({ eyebrow, title, description, bullets, requiredPlan }: {
  eyebrow: string; title: string; description: string; bullets: string[]; requiredPlan: "pro" | "premium";
}) {
  const requestPlan = useRequestPlan();
  return (
    <section className="tab-page">
      <div className="tab-head">
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className={`premium-lock lock-${requiredPlan}`}>
        <span className="premium-lock-icon">{requiredPlan === "premium" ? "★" : "◆"}</span>
        <h2>Bu bölüm {PLAN_NAME[requiredPlan]} planında{requiredPlan === "pro" ? " ve üzerinde" : ""}</h2>
        <ul>{bullets.map((b) => <li key={b}>{b}</li>)}</ul>
        <button type="button" className="primary-button" onClick={() => requestPlan(requiredPlan)}>
          {requiredPlan === "premium" ? "Premium'a geç" : "Pro'ya geç"} <span>→</span></button>
        <small>Fiyatlara KDV dahildir.</small>
      </div>
    </section>
  );
}
