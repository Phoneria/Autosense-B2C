import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { choosePlan, fetchBilling } from "../api";
import { isUnlimited, priceOf, resetLabel, VAT_NOTE } from "../billingDisplay";
import PlanCards, { cleanFeatures } from "../components/PlanCards";
import { useAuth } from "../auth/AuthProvider";
import type { BillingDetails } from "../types";
import { useDialogFocus } from "../components/useDialogFocus";

/** Sipariş özeti. Ücretli planlarda ödeme altyapısı (iyzico) henüz bağlı değil:
 *  "Ödemeye geç" planı DEĞİŞTİRMEZ, yalnızca bilgilendirir. Basic ücretsiz olduğu
 *  için doğrudan geçilebilir. */
function OrderSummary({ planId, plan, price, credits, unlimited, features, busy, onCancel, onFree }: {
  planId: string; plan: string; price: string; credits: number; unlimited: boolean; features: string[]; busy: boolean;
  onCancel: () => void; onFree: () => void;
}) {
  const ref = useDialogFocus<HTMLDivElement>(() => { if (!busy) onCancel(); });
  const [paymentNotice, setPaymentNotice] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const free = planId === "basic";
  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onCancel} role="presentation">
      <div ref={ref} className="modal pf-modal" role="dialog" aria-modal="true" aria-labelledby="pf-confirm-title" aria-describedby="pf-confirm-note"
        tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <p className="pf-label">{free ? "Plan değişikliği" : "Sipariş özeti"}</p>
        <h2 id="pf-confirm-title">{free ? `${plan} planına geçilsin mi?` : `${plan} planı`}</h2>
        <div className="pf-modal-price">
          <strong>{price}</strong>
          <span>{unlimited ? "Sınırsız analiz" : `Günde ${credits} analiz`}{free ? "" : ` · ${VAT_NOTE}`}</span>
        </div>
        <ul>{cleanFeatures(features, unlimited).map((f) => <li key={f}>{f}</li>)}</ul>
        {free
          ? <p className="modal-note" id="pf-confirm-note">Basic ücretsizdir; geçiş anında yapılır.</p>
          : paymentNotice
            ? <p className="modal-note pf-nopay-box" id="pf-confirm-note" role="status"><strong>Ödeme altyapısı yakında aktif olacak.</strong> Şu an satın alma tamamlanamıyor; planınız değişmedi ve ücret alınmadı.</p>
            : <p className="modal-note" id="pf-confirm-note">Fiyat aylık abonelik ücretidir.</p>}
        {!free && (
          <label className="pf-consent">
            <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} disabled={paymentNotice} />
            <span>
              <Link to="/on-bilgilendirme" target="_blank">Ön Bilgilendirme Formu</Link>'nu ve <Link to="/mesafeli-satis-sozlesmesi" target="_blank">Mesafeli Satış Sözleşmesi</Link>'ni
              okudum, kabul ediyorum. Hizmetin hemen başlamasını ve bu nedenle cayma hakkımın sona ereceğini onaylıyorum.
            </span>
          </label>
        )}
        <div className="modal-actions">
          <button type="button" className="pf-btn" onClick={onCancel} disabled={busy} data-autofocus>{paymentNotice ? "Kapat" : "Vazgeç"}</button>
          {free
            ? <button type="button" className="pf-btn is-primary" onClick={onFree} disabled={busy}>{busy ? "Geçiliyor…" : "Basic'e geç"}</button>
            : <button type="button" className="pf-btn is-primary" onClick={() => setPaymentNotice(true)} disabled={paymentNotice || !accepted}>Ödemeye geç</button>}
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
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [confirming, setConfirming] = useState<string | null>(null);

  useEffect(() => { if (pendingPlan) setConfirming(pendingPlan); }, [pendingPlan]);

  // Üst menüdeki "Fiyatlar" (/hesabim#planlar): planlar yüklenince o bölüme kaydır.
  const { hash } = useLocation();
  useEffect(() => {
    if (hash !== "#planlar" || !details) return;
    document.getElementById("planlar")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [hash, details]);

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
        <OrderSummary planId={confirmPlan.id} plan={confirmPlan.name} price={priceOf(confirmPlan.id, confirmPlan.price_label)} credits={confirmPlan.credits}
          features={confirmPlan.features} unlimited={confirmPlan.id === "premium"}
          busy={busy === `plan-${confirmPlan.id}`} onCancel={closeConfirm}
          onFree={async () => {
            await run(`plan-${confirmPlan.id}`, () => choosePlan(confirmPlan.id), `${confirmPlan.name} planına geçildi.`);
            closeConfirm();
          }} />
      )}
      <div className="tab-head">
        <span className="eyebrow">HESAP</span>
        <h1>Hesabım ve plan</h1>
        <p>{user?.email}</p>
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

      <h2 className="tab-subtitle" id="planlar">Planlar</h2>
      <p className="pf-hint pf-vat">{VAT_NOTE}</p>
      <p className="pf-hint">Senaryolar ücretsizdir. Plan kredileri her gün 00:00'da yenilenir. Premium'da analiz sınırı yoktur.</p>
      {details && <PlanCards plans={details.plans} currentPlan={current?.plan} busy={busy} onSelect={setConfirming} />}

    </section>
  );
}
