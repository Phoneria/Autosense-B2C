import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { cancelSubscription, choosePlan, fetchBilling, startPayment } from "../api";
import { isUnlimited, priceOf, resetLabel, VAT_NOTE } from "../billingDisplay";
import PlanCards, { cleanFeatures } from "../components/PlanCards";
import { useAuth } from "../auth/AuthProvider";
import type { BillingDetails, PaymentCustomer } from "../types";
import { useDialogFocus } from "../components/useDialogFocus";

const EMPTY_CUSTOMER: PaymentCustomer = { name: "", surname: "", phone: "", identity_number: "", address: "", city: "" };

/** iyzico'nun döndürdüğü form betiğini sayfada çalıştırır (innerHTML script'leri çalıştırmaz). */
function IyzicoForm({ html }: { html: string }) {
  useEffect(() => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const added: HTMLScriptElement[] = [];
    doc.querySelectorAll("script").forEach((old) => {
      const el = document.createElement("script");
      for (const { name, value } of Array.from(old.attributes)) el.setAttribute(name, value);
      el.text = old.text;
      document.body.appendChild(el);
      added.push(el);
    });
    return () => added.forEach((el) => el.remove());
  }, [html]);
  return <div id="iyzipay-checkout-form" className="responsive" />;
}

/** Sipariş özeti. Basic ücretsizdir, doğrudan geçilir. Ücretli planlarda
 *  iyzico açıksa fatura bilgileri alınır ve iyzico abonelik ödeme formu açılır;
 *  kapalıysa yalnızca bilgilendirme gösterilir, plan değişmez. */
function OrderSummary({ planId, plan, price, credits, unlimited, features, busy, paymentEnabled, onCancel, onFree }: {
  planId: string; plan: string; price: string; credits: number; unlimited: boolean; features: string[]; busy: boolean;
  paymentEnabled: boolean; onCancel: () => void; onFree: () => void;
}) {
  const ref = useDialogFocus<HTMLDivElement>(() => { if (!busy && !starting) onCancel(); });
  const [paymentNotice, setPaymentNotice] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [customer, setCustomer] = useState<PaymentCustomer>(EMPTY_CUSTOMER);
  const [formHtml, setFormHtml] = useState("");
  const [starting, setStarting] = useState(false);
  const [payError, setPayError] = useState("");
  const free = planId === "basic";
  const set = (key: keyof PaymentCustomer) => (e: React.ChangeEvent<HTMLInputElement>) => setCustomer((c) => ({ ...c, [key]: e.target.value }));
  const filled = Object.values(customer).every((v) => v.trim().length >= 2);

  async function pay() {
    if (!paymentEnabled) { setPaymentNotice(true); return; }
    setStarting(true); setPayError("");
    try {
      const r = await startPayment(planId, customer);
      setFormHtml(r.checkout_form_content);
    } catch (e) {
      setPayError(e instanceof Error ? e.message : "Ödeme başlatılamadı.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={busy || starting || formHtml ? undefined : onCancel} role="presentation">
      <div ref={ref} className={`modal pf-modal${formHtml ? " pf-modal-pay" : ""}`} role="dialog" aria-modal="true" aria-labelledby="pf-confirm-title" aria-describedby="pf-confirm-note"
        tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <p className="pf-label">{free ? "Plan değişikliği" : formHtml ? "Güvenli ödeme" : "Sipariş özeti"}</p>
        <h2 id="pf-confirm-title">{free ? `${plan} planına geçilsin mi?` : `${plan} planı`}</h2>
        <div className="pf-modal-price">
          <strong>{price}</strong>
          <span>{unlimited ? "Sınırsız analiz" : `Günde ${credits} analiz`}{free ? "" : ` · ${VAT_NOTE}`}</span>
        </div>
        {formHtml ? (
          <>
            <p className="modal-note" id="pf-confirm-note">Kart bilgileriniz iyzico'nun güvenli ödeme formunda alınır; AutoSense kart bilgisi saklamaz. Abonelik her ay yenilenir, istediğiniz zaman iptal edebilirsiniz.</p>
            <IyzicoForm html={formHtml} />
          </>
        ) : (
          <>
            <ul>{cleanFeatures(features, unlimited).map((f) => <li key={f}>{f}</li>)}</ul>
            {free
              ? <p className="modal-note" id="pf-confirm-note">Basic ücretsizdir; geçiş anında yapılır.</p>
              : paymentNotice
                ? <p className="modal-note pf-nopay-box" id="pf-confirm-note" role="status"><strong>Ödeme altyapısı yakında aktif olacak.</strong> Şu an satın alma tamamlanamıyor; planınız değişmedi ve ücret alınmadı.</p>
                : <p className="modal-note" id="pf-confirm-note">Aylık abonelik ücretidir; her ay otomatik yenilenir, istediğiniz zaman iptal edebilirsiniz.</p>}
            {!free && paymentEnabled && (
              <fieldset className="pf-billing">
                <legend>Fatura bilgileri</legend>
                <label>Ad<input value={customer.name} onChange={set("name")} autoComplete="given-name" required /></label>
                <label>Soyad<input value={customer.surname} onChange={set("surname")} autoComplete="family-name" required /></label>
                <label>Cep telefonu<input value={customer.phone} onChange={set("phone")} autoComplete="tel-national" inputMode="tel" placeholder="5xx xxx xx xx" required /></label>
                <label>T.C. kimlik no<input value={customer.identity_number} onChange={set("identity_number")} inputMode="numeric" maxLength={11} required /></label>
                <label className="pf-billing-wide">Adres<input value={customer.address} onChange={set("address")} autoComplete="street-address" required /></label>
                <label>İl<input value={customer.city} onChange={set("city")} autoComplete="address-level1" required /></label>
                <p className="pf-billing-note">Bu bilgiler fatura ve ödeme sağlayıcısı (iyzico) için gereklidir.</p>
              </fieldset>
            )}
            {!free && (
              <label className="pf-consent">
                <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} disabled={paymentNotice} />
                <span>
                  <Link to="/on-bilgilendirme" target="_blank">Ön Bilgilendirme Formu</Link>'nu ve <Link to="/mesafeli-satis-sozlesmesi" target="_blank">Mesafeli Satış Sözleşmesi</Link>'ni
                  okudum, kabul ediyorum. Hizmetin hemen başlamasını ve bu nedenle cayma hakkımın sona ereceğini onaylıyorum.
                </span>
              </label>
            )}
            {payError && <p role="alert" className="form-error">{payError}</p>}
            {!free && <img className="pf-pay-logos" src="/odeme/iyzico-logo-band.svg" width="429" height="32" alt="iyzico ile Öde, Mastercard, Visa, American Express, Troy" />}
          </>
        )}
        <div className="modal-actions">
          <button type="button" className="pf-btn" onClick={onCancel} disabled={busy || starting} data-autofocus>{paymentNotice || formHtml ? "Kapat" : "Vazgeç"}</button>
          {free
            ? <button type="button" className="pf-btn is-primary" onClick={onFree} disabled={busy}>{busy ? "Geçiliyor…" : "Basic'e geç"}</button>
            : !formHtml && <button type="button" className="pf-btn is-primary" onClick={pay}
                disabled={paymentNotice || !accepted || starting || (paymentEnabled && !filled)}>{starting ? "Hazırlanıyor…" : "Ödemeye geç"}</button>}
        </div>
      </div>
    </div>
  );
}

function untilLabel(iso: string | null): string {
  if (!iso) return "dönem sonu";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
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
  const [cancelAsk, setCancelAsk] = useState(false);

  useEffect(() => { if (pendingPlan) setConfirming(pendingPlan); }, [pendingPlan]);

  // Üst menüdeki "Fiyatlar" (/hesabim#planlar): planlar yüklenince o bölüme kaydır.
  const { hash, search } = useLocation();
  const navigate = useNavigate();

  // iyzico ödemesinden dönüş: /hesabim?odeme=basarili|basarisiz
  useEffect(() => {
    const result = new URLSearchParams(search).get("odeme");
    if (!result) return;
    if (result === "basarili") setMessage("Ödemeniz alındı, planınız etkinleştirildi. Teşekkürler!");
    else setError("Ödeme tamamlanamadı; ücret alınmadı ve planınız değişmedi. Kart bilgilerinizi kontrol edip tekrar deneyebilirsiniz.");
    navigate({ search: "", hash: "#planlar" }, { replace: true });
  }, [search, navigate]);
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
          busy={busy === `plan-${confirmPlan.id}`} paymentEnabled={!!current?.payment?.enabled} onCancel={closeConfirm}
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
          {current.payment?.status && (
            <div className="pf-sub" role="group" aria-label="Abonelik">
              <p>
                <strong>Abonelik: </strong>
                {current.payment.status === "ACTIVE" && <>aktif · {untilLabel(current.payment.paid_until)} tarihinde otomatik yenilenir.</>}
                {current.payment.status === "UNPAID" && <>son yenileme ödemesi alınamadı. Planınız {untilLabel(current.payment.paid_until)} tarihine kadar açık.</>}
                {current.payment.status === "CANCELED" && <>iptal edildi. Planınız {untilLabel(current.payment.paid_until)} tarihine kadar açık, sonra Basic'e döner.</>}
              </p>
              {current.payment.can_cancel && (
                cancelAsk
                  ? <span className="pf-sub-actions">
                      <button type="button" className="pf-btn" onClick={() => setCancelAsk(false)} disabled={busy === "cancel"}>Vazgeç</button>
                      <button type="button" className="pf-btn is-danger" disabled={busy === "cancel"}
                        onClick={async () => { await run("cancel", cancelSubscription, "Aboneliğiniz iptal edildi. Ödenen dönem sonuna kadar planınızı kullanabilirsiniz."); setCancelAsk(false); }}>
                        {busy === "cancel" ? "İptal ediliyor…" : "Evet, iptal et"}
                      </button>
                    </span>
                  : <button type="button" className="pf-btn" onClick={() => setCancelAsk(true)}>Aboneliği iptal et</button>
              )}
            </div>
          )}
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
