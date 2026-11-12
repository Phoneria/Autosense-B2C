import { priceOf } from "../billingDisplay";

export interface PlanCardData { id: string; name: string; credits: number; price_label: string; features: string[] }

/** Ek kredi kaldırıldı, krediler günlük yenileniyor: eski backend metinlerini de buna göre gösterir. */
export function cleanFeatures(features: string[], unlimited: boolean) {
  return features
    .filter((f) => !/ek kredi/i.test(f))
    .map((f) => /^\s*(10 dakikada|günde)\s+\d+\s+analiz/i.test(f)
      ? (unlimited ? "Sınırsız analiz" : f.replace(/10 dakikada/i, "Günde"))
      : f.replace(/fiyat\/satış grafikleri/gi, "fiyat ve ilandan kalkan (tahmini) grafikleri"));
}

export function planActionLabel(id: string) {
  return id === "basic" ? "Ücretsiz Başla" : "Satın Al";
}

/** Plan kartları: Hesabım sayfası ve herkese açık fiyat sayfası aynı kartları kullanır.
 *  currentPlan yalnızca giriş yapmış kullanıcı için verilir ("Mevcut plan" etiketi). */
export default function PlanCards({ plans, currentPlan, busy = "", onSelect }: {
  plans: PlanCardData[]; currentPlan?: string; busy?: string; onSelect: (id: string) => void;
}) {
  return (
    <div className="plan-grid pf-plans">
      {plans.map((plan) => {
        const active = !!currentPlan && currentPlan === plan.id;
        const unlimited = plan.id === "premium";
        return (
          <article key={plan.id} className={`pf-plan plan-${plan.id}${active ? " is-current" : ""}`} aria-labelledby={`pf-plan-${plan.id}`} aria-current={active ? "true" : undefined}>
            <div className="pf-plan-head">
              <h3 className="pf-plan-name" id={`pf-plan-${plan.id}`}>{plan.name}</h3>
              {active && <span className="pf-badge">Mevcut plan</span>}
            </div>
            <p className="pf-plan-credits">{unlimited ? <strong>Sınırsız</strong> : <><strong>{plan.credits}</strong> kredi / gün</>}</p>
            <p className="pf-plan-price">{priceOf(plan.id, plan.price_label)}</p>
            <ul aria-label={`${plan.name} planına dahil olanlar`}>{cleanFeatures(plan.features, unlimited).map((f) => <li key={f}>{f}</li>)}</ul>
            <button type="button" className={active ? "pf-btn is-current" : plan.id === "basic" ? "pf-btn" : "pf-btn is-primary"}
              disabled={active || !!busy} onClick={() => onSelect(plan.id)}
              aria-label={active ? `${plan.name}: kullandığınız plan` : `${plan.name}: ${planActionLabel(plan.id)}`}>
              {active ? "Kullandığınız plan" : busy === `plan-${plan.id}` ? "İşleniyor…" : planActionLabel(plan.id)}
            </button>
          </article>
        );
      })}
    </div>
  );
}
