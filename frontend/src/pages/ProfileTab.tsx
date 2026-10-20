import { useEffect, useState } from "react";
import { choosePlan, fetchBilling } from "../api";
import { isUnlimited, priceOf, resetLabel } from "../billingDisplay";
import { useAuth } from "../auth/AuthProvider";
import type { BillingDetails } from "../types";
import { useDialogFocus } from "../components/useDialogFocus";

function PlanConfirm({ plan, price, credits, unlimited, features, busy, onCancel, onConfirm }: {
  plan: string; price: string; credits: number; unlimited: boolean; features: string[]; busy: boolean; onCancel: () => void; onConfirm: () => void;
}) {
  const ref = useDialogFocus<HTMLDivElement>(() => { if (!busy) onCancel(); });
  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onCancel} role="presentation">
      <div ref={ref} className="modal pf-modal" role="dialog" aria-modal="true" aria-labelledby="pf-confirm-title" aria-describedby="pf-confirm-note"
        tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <h2 id="pf-confirm-title">{plan} planına geçilsin mi?</h2>
        <div className="pf-modal-price">
          <strong>{unlimited ? "Sınırsız analiz" : `Günde ${credits} analiz`}</strong>
          <span>Liste fiyatı {price} · şimdilik ücretsiz</span>
        </div>
        <ul>{cleanFeatures(features, unlimited).map((f) => <li key={f}>{f}</li>)}</ul>
        <p className="modal-note pf-nopay-box" id="pf-confirm-note"><strong>Ödeme alınmaz.</strong> Ödeme sistemi henüz aktif değil; onayladığınızda plan anında tanımlanır ve ücret tahsil edilmez.</p>
        <div className="modal-actions">
          <button type="button" className="pf-btn" onClick={onCancel} disabled={busy} data-autofocus>Vazgeç</button>
          <button type="button" className="pf-btn is-primary" onClick={onConfirm} disabled={busy}>
            {busy ? "Etkinleştiriliyor…" : "Ödemesiz etkinleştir"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Backend'in özellik metinlerinde ödeme alınmıyorken yanıltıcı olan ifadeleri ekranda yumuşatır. */
function featureLabel(f: string) {
  return f.replace(/fiyat\/satış grafikleri/gi, "fiyat ve ilandan kalkan (tahmini) grafikleri");
}

/** Ek kredi kaldırıldı, krediler günlük yenileniyor: eski backend metinlerini de buna göre gösterir. */
function cleanFeatures(features: string[], unlimited: boolean) {
  return features
    .filter((f) => !/ek kredi/i.test(f))
    .map((f) => /^\s*(10 dakikada|günde)\s+\d+\s+analiz/i.test(f)
      ? (unlimited ? "Sınırsız analiz" : f.replace(/10 dakikada/i, "Günde"))
      : featureLabel(f));
}

export default function ProfileTab({ pendingPlan, onPendingHandled }: {
  pendingPlan?: string | null; onPendingHandled?: () => void;
}) {
  const { user, setBilling } = useAuth();
  const [details, setDetails] = useState<BillingDetails | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [confirming, setConfirming] = useState<string | null>(null);

  useEffect(() => { if (pendingPlan) setConfirming(pendingPlan); }, [pendingPlan]);

  useEffect(() => {
    setLoadError("");
    fetchBilling().then((d) => { setDetails(d); setBilling(d); }).catch((e: Error) => setLoadError(e.message));
  }, [setBilling, attempt]);

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
  const currentPlan = details?.plans.find((p) => p.id === current?.plan);
  const unlimited = isUnlimited(current);
  const next = resetLabel(current?.next_reset_at);
  const ratio = unlimited ? 1 : current && current.quota ? Math.min(1, Math.max(0, current.credits / current.quota)) : 0;

  return (
    <section className="tab-page pf-page">
      {confirmPlan && (
        <PlanConfirm plan={confirmPlan.name} price={priceOf(confirmPlan.id, confirmPlan.price_label)} credits={confirmPlan.credits}
          features={confirmPlan.features} unlimited={confirmPlan.id === "premium"}
          busy={busy === `plan-${confirmPlan.id}`} onCancel={closeConfirm}
          onConfirm={async () => {
            await run(`plan-${confirmPlan.id}`, () => choosePlan(confirmPlan.id), `${confirmPlan.name} planı etkinleştirildi. Ücret alınmadı.`);
            closeConfirm();
          }} />
      )}
      <div className="tab-head">
        <span className="eyebrow">HESAP</span>
        <h1>Hesabım ve plan</h1>
        <p>{user?.email}</p>
      </div>

      <div className="pf-nopay-box" role="note">
        <span className="pf-nopay-badge">Ödeme alınmaz</span>
        <p>
          Ödeme sistemi henüz aktif değil. Planlar <b>anında ve ücretsiz</b> tanımlanır; kart bilgisi istenmez.
          Gösterilen fiyatlar ileride uygulanacak liste fiyatlarıdır.
        </p>
      </div>

      {loadError && !current && (
        <div className="gd-state is-error" role="alert">
          <strong>Hesap bilgileri yüklenemedi</strong>
          <p>{loadError}</p>
          <button type="button" className="gd-retry" onClick={() => setAttempt((n) => n + 1)}>Tekrar dene</button>
        </div>
      )}

      {current && (
        <section className="pf-summary" aria-labelledby="pf-summary-title">
          <div className="pf-current">
            <div>
              <p className="pf-label" id="pf-summary-title">Mevcut plan</p>
              <h2 className="pf-current-name">{current.plan_name}</h2>
              {currentPlan && <p className="pf-current-meta">{unlimited ? "Sınırsız analiz" : `Günde ${currentPlan.credits} analiz`} · liste fiyatı {priceOf(currentPlan.id, currentPlan.price_label)}</p>}
            </div>
            {current.open_access && (
              <div className="pf-open">
                <span className="as-plan-dot" aria-hidden="true" />
                <div>
                  <strong>Tüm özellikler şu an açık</strong>
                  <p>Analizler kredi harcamaz; plan seçimi şimdilik analizlerinizi etkilemez.</p>
                </div>
              </div>
            )}
          </div>
          <dl className="pf-stats">
            <div className="pf-stat-credits">
              <dt>Bugünkü kredi</dt>
              <dd>
                {unlimited ? <b>Sınırsız</b> : <><b>{current.credits}</b> / {current.quota}</>}
                <span className="pf-meter" role="meter" aria-label="Kalan günlük kredi" aria-valuemin={0} aria-valuemax={unlimited ? 1 : current.quota} aria-valuenow={unlimited ? 1 : current.credits}>
                  <i style={{ width: `${ratio * 100}%` }} />
                </span>
              </dd>
            </div>
            <div><dt>Analiz başına</dt><dd><b>{unlimited ? "Sınırsız" : "1 kredi"}</b><small>Senaryolar ücretsiz</small></dd></div>
            <div><dt>Kredi yenilenmesi</dt><dd><b>Her gün</b><small>{unlimited ? "Premium'da sınır yok" : next ? `Sonraki: ${next}` : "Her gün 00:00"}</small></dd></div>
          </dl>
        </section>
      )}

      <div aria-live="polite">
        {message && <p role="status" className="billing-ok pf-ok">{message}</p>}
        {error && <p role="alert" className="form-error">{error}</p>}
      </div>

      <h2 className="tab-subtitle">Planlar</h2>
      <p className="pf-hint">Senaryolar ücretsizdir. Plan kredileri her gün 00:00'da yenilenir. Premium'da analiz sınırı yoktur.</p>
      <div className="plan-grid pf-plans">
        {details?.plans.map((plan) => {
          const active = current?.plan === plan.id;
          return (
            <article key={plan.id} className={`pf-plan plan-${plan.id}${active ? " is-current" : ""}`} aria-labelledby={`pf-plan-${plan.id}`} aria-current={active ? "true" : undefined}>
              <div className="pf-plan-head">
                <h3 className="pf-plan-name" id={`pf-plan-${plan.id}`}>{plan.name}</h3>
                {active && <span className="pf-badge">Mevcut plan</span>}
              </div>
              <p className="pf-plan-credits">{plan.id === "premium" ? <strong>Sınırsız</strong> : <><strong>{plan.credits}</strong> kredi / gün</>}</p>
              <p className="pf-plan-price"><span>Liste fiyatı</span> {priceOf(plan.id, plan.price_label)}</p>
              <ul aria-label={`${plan.name} planına dahil olanlar`}>{cleanFeatures(plan.features, plan.id === "premium").map((f) => <li key={f}>{f}</li>)}</ul>
              <button type="button" className={active ? "pf-btn is-current" : "pf-btn"} disabled={active || !!busy}
                onClick={() => setConfirming(plan.id)} aria-label={active ? `${plan.name}: kullandığınız plan` : `${plan.name} planını ödemesiz etkinleştir`}>
                {active ? "Kullandığınız plan" : busy === `plan-${plan.id}` ? "Etkinleştiriliyor…" : "Ödemesiz etkinleştir"}
              </button>
            </article>
          );
        })}
      </div>

    </section>
  );
}
