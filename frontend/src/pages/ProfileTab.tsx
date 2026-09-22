import { useEffect, useState } from "react";
import { addCredits, choosePlan, fetchBilling } from "../api";
import { useAuth } from "../auth/AuthProvider";
import type { BillingDetails } from "../types";

function PlanConfirm({ plan, price, features, busy, onCancel, onConfirm }: {
  plan: string; price: string; features: string[]; busy: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{plan} planına geçilsin mi?</h2>
        <p className="modal-price">{price}</p>
        <ul>{features.map((f) => <li key={f}>{f}</li>)}</ul>
        <p className="modal-note">Ödeme sistemi henüz aktif değil; onayladığınızda plan anında tanımlanır, ücret tahsil edilmez.</p>
        <div className="modal-actions">
          <button type="button" className="ghost-button" onClick={onCancel} disabled={busy}>Vazgeç</button>
          <button type="button" className="primary-button" onClick={onConfirm} disabled={busy}>
            {busy ? "Onaylanıyor…" : "Onaylıyorum"} <span>→</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProfileTab({ pendingPlan, onPendingHandled }: {
  pendingPlan?: string | null; onPendingHandled?: () => void;
}) {
  const { user, setBilling } = useAuth();
  const [details, setDetails] = useState<BillingDetails | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  useEffect(() => { if (pendingPlan) setConfirming(pendingPlan); }, [pendingPlan]);

  useEffect(() => {
    fetchBilling().then((d) => { setDetails(d); setBilling(d); }).catch((e: Error) => setError(e.message));
  }, [setBilling]);

  async function run(key: string, action: () => Promise<BillingDetails>, done: string) {
    setBusy(key); setError(""); setMessage("");
    try {
      const d = await action();
      setDetails(d); setBilling(d); setMessage(done);
    } catch (e) {
      setError(e instanceof Error ? e.message : "İşlem tamamlanamadı.");
    } finally {
      setBusy("");
    }
  }

  const current = user?.billing || details;
  const confirmPlan = details?.plans.find((p) => p.id === confirming);
  const closeConfirm = () => { setConfirming(null); onPendingHandled?.(); };
  const canBuy = !!current?.plan_features?.includes("extra_credits");

  return (
    <section className="tab-page">
      {confirmPlan && (
        <PlanConfirm plan={confirmPlan.name} price={confirmPlan.price_label} features={confirmPlan.features}
          busy={busy === `plan-${confirmPlan.id}`} onCancel={closeConfirm}
          onConfirm={async () => {
            await run(`plan-${confirmPlan.id}`, () => choosePlan(confirmPlan.id), `${confirmPlan.name} planına geçildi.`);
            closeConfirm();
          }} />
      )}
      <div className="tab-head">
        <span className="eyebrow">PROFİL</span>
        <h1>Hesabım ve planım</h1>
        <p>{user?.email}</p>
      </div>

      {current && (
        <div className="profile-summary">
          <div><span>Mevcut plan</span><strong>{current.plan_name}</strong></div>
          <div><span>Plan kredisi</span><strong>{current.credits} / {current.quota}</strong></div>
          <div><span>Ek kredi</span><strong>{current.extra_credits}</strong></div>
          <div><span>Yenilenme</span><strong>Her {current.reset_minutes} dakikada bir</strong></div>
        </div>
      )}

      <p className="billing-note">
        Ödeme sistemi henüz aktif değil: seçtiğiniz plan ve eklediğiniz krediler anında onaylanır.
        Her analiz 1 kredi harcar; senaryolar ücretsizdir. Plan kredileri her
        10 dakikada bir yenilenir, ek krediler sıfırlanmaz. Ek kredi Pro ve Premium planlarda alınabilir.
      </p>
      {message && <p role="status" className="billing-ok">{message}</p>}
      {error && <p role="alert" className="form-error">{error}</p>}

      <h2 className="tab-subtitle">Plan seçin</h2>
      <div className="plan-grid">
        {details?.plans.map((plan) => {
          const active = current?.plan === plan.id;
          return (
            <article key={plan.id} className={`plan-card plan-${plan.id}${active ? " active" : ""}`}>
              <span className="plan-name">{plan.name}</span>
              <strong className="plan-price">{plan.price_label}</strong>
              <p className="plan-credits"><b>{plan.credits}</b> kredi / 10 dk</p>
              <ul>{plan.features.map((f) => <li key={f}>{f}</li>)}</ul>
              <button type="button" disabled={active || !!busy}
                onClick={() => setConfirming(plan.id)}>
                {active ? "Mevcut plan" : busy === `plan-${plan.id}` ? "Onaylanıyor…" : "Bu planı seç"}
              </button>
            </article>
          );
        })}
      </div>

      <h2 className="tab-subtitle">Kredi ekle</h2>
      {!canBuy && <p className="card-empty">Basic planda yalnızca 10 dakikada yenilenen 3 kredi var. Ek kredi almak için Pro veya Premium'a geçin.</p>}
      <div className="pack-grid">
        {details?.credit_packs.map((pack) => (
          <article key={pack.amount} className="pack-card">
            <strong>+{pack.amount}</strong>
            <span>kredi</span>
            <small>{pack.price_label}</small>
            <button type="button" disabled={!!busy || !canBuy}
              onClick={() => run(`pack-${pack.amount}`, () => addCredits(pack.amount), `${pack.amount} kredi eklendi.`)}>
              {!canBuy ? "Pro gerekli" : busy === `pack-${pack.amount}` ? "Ekleniyor…" : "Ekle"}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
