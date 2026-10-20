import { useEffect, useId, useState, type ReactNode } from "react";
import type React from "react";
import type { AnalysisResult } from "../types";
import LockedPanel from "./LockedPanel";
import { num, tl } from "../format";
import TrendChart from "./TrendChart";
import DescriptionCard from "./DescriptionCard";
import SimilarListings from "./SimilarListings";
import VehicleTraits from "./VehicleTraits";
import PriceLadder from "./charts/PriceLadder";
import FactorBars from "./charts/FactorBars";
import DepreciationCurve from "./charts/DepreciationCurve";
import ScoreGauge from "./charts/ScoreGauge";
import DeductionBars from "./charts/DeductionBars";
import RegionalScale from "./charts/RegionalScale";

/** Ayrıntı bölümü. İçerik her açılışta yeniden kurulur; böylece grafikler ve
 *  çubuklar her seferinde sıfırdan dolarak gelir. Kapanırken içerik animasyon
 *  bitene kadar yerinde kalır. */
function Section({ title, hint, chip, color, children }: {
  title: string; hint: string; chip?: string | null; color: string; children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [round, setRound] = useState(0);
  const id = useId();
  useEffect(() => {
    const openAll = () => { setMounted(true); setOpen(true); };
    window.addEventListener("as-open-all", openAll);
    window.addEventListener("beforeprint", openAll);
    return () => { window.removeEventListener("as-open-all", openAll); window.removeEventListener("beforeprint", openAll); };
  }, []);
  const toggle = () => {
    if (open) { setOpen(false); return; }
    setRound((n) => n + 1); setMounted(true); setOpen(true);
  };
  return (
    <section className={`acc acc-${color}${open ? " is-open" : ""}`}>
      <h4 className="acc-heading">
        <button type="button" className="acc-summary" aria-expanded={open} aria-controls={id} onClick={toggle}>
          <span className="acc-text"><strong>{title}</strong><small>{hint}</small></span>
          {chip && <span className="acc-chip">{chip}</span>}
          <span className="acc-arrow" aria-hidden="true" />
        </button>
      </h4>
      <div className="acc-panel" id={id} role="region" aria-label={title} inert={!open}
        onTransitionEnd={(e) => { if (e.target === e.currentTarget && !open) setMounted(false); }}>
        <div className="acc-panel-inner">
          {mounted && <div className="acc-body" key={round}>{children}</div>}
        </div>
      </div>
    </section>
  );
}

/** İlan fiyatı ile tahmini değerin aynı eksendeki yeri. Gölgeli bant,
 *  backend'in döndürdüğü tahmini aralıktır; eksen yalnızca bu değerleri kapsar. */
function PositionBar({ low, high, value, price }: { low: number; high: number; value: number; price: number }) {
  const min = Math.min(low, price, value, value * 0.88);
  const max = Math.max(high, price, value, value * 1.14);
  const pad = Math.max(1, (max - min) * 0.12);
  const lo = min - pad, span = Math.max(1, max + pad - lo);
  const pos = (v: number) => ((v - lo) / span) * 100;
  const label = (v: number) => Math.min(88, Math.max(12, pos(v)));
  const zones = {
    "--z1": `${pos(value * 0.9)}%`, "--z2": `${pos(value * 0.97)}%`,
    "--z3": `${pos(value * 1.03)}%`, "--z4": `${pos(value * 1.1)}%`,
  } as React.CSSProperties;
  return (
    <figure className="az-pos" aria-label={`İlan fiyatı ${tl(price)}, tahmini değer ${tl(value)}, tahmini aralık ${tl(low)} – ${tl(high)}`}>
      <div className="az-pos-row az-pos-top" aria-hidden="true">
        <span className="az-pos-tag is-listing" style={{ left: `${label(price)}%` }}><small>İlan fiyatı</small><b>{tl(price)}</b></span>
      </div>
      <div className="az-pos-track" aria-hidden="true" style={zones}>
        <span className="az-pos-band" style={{ left: `${pos(low)}%`, width: `${Math.max(1, pos(high) - pos(low))}%` }} />
        <span className="az-pos-mark is-estimate" style={{ left: `${pos(value)}%` }} />
        <span className="az-pos-mark is-listing" style={{ left: `${pos(price)}%` }} />
      </div>
      <div className="az-pos-row az-pos-bottom" aria-hidden="true">
        <span className="az-pos-tag is-estimate" style={{ left: `${label(value)}%` }}><small>Tahmini değer</small><b>{tl(value)}</b></span>
      </div>
      <div className="az-pos-zones" aria-hidden="true" style={zones}>
        <span className="z-great">Fırsat</span><span className="z-cheap">Uygun</span>
        <span className="z-fair">Piyasa</span><span className="z-high">Yüksek</span><span className="z-exp">Pahalı</span>
      </div>
      <figcaption className="az-pos-legend">
        <span><i className="is-band" />Tahmini aralık {tl(low)} – {tl(high)}</span>
        <span><i className="is-listing" />İlan fiyatı</span>
        <span><i className="is-estimate" />Tahmini değer</span>
      </figcaption>
    </figure>
  );
}

export type VerdictTone = "great" | "cheap" | "fair" | "high" | "expensive";
export function verdictToneOf(dev: number): VerdictTone {
  return dev <= -10 ? "great" : dev < -3 ? "cheap" : dev <= 3 ? "fair" : dev <= 10 ? "high" : "expensive";
}
const TONE_META: Record<VerdictTone, { icon: string; word: string }> = {
  great: { icon: "★", word: "Fırsat" },
  cheap: { icon: "✓", word: "Uygun fiyat" },
  fair: { icon: "=", word: "Piyasa fiyatı" },
  high: { icon: "↑", word: "Biraz yüksek" },
  expensive: { icon: "!", word: "Pahalı" },
};

function Signal({ tone, label, value }: { tone: "good" | "mid" | "bad" | "info"; label: string; value: ReactNode }) {
  return <li className={`az-signal is-${tone}`}><small>{label}</small><b>{value}</b></li>;
}

const STRENGTH_LABEL: Record<string, string> = { strong: "Güçlü", medium: "Orta", weak: "Zayıf" };
const TRIM_LABEL: Record<string, string> = {
  exact: "Paket birebir", engine: "Motor seviyesinde", engine_median: "Paket ortalaması", none: "Eşleşme yok",
};

export default function Results({ data }: { data: AnalysisResult }) {
  const { estimate, decision, negotiation, depreciation, tco } = data;
  const ev: Partial<AnalysisResult["evidence"]> & { strength: string } = data.evidence || { strength: "medium" };
  const locks = data.locks || {};
  const price = data.vehicle.price;
  const value = estimate.tahmini_fiyat;
  const diff = value != null ? price - value : null;
  const costLines: [string, number | null][] = [
    ["Yakıt", tco.yakit.yillik_tl],
    ["MTV", tco.mtv.yillik_tl],
    ["Sigorta", tco.sigorta.yillik_tl],
    ["Bakım", tco.bakim.yillik_tl],
  ];
  const costMax = Math.max(1, ...costLines.map(([, v]) => v || 0));

  const priceSentence =
    diff == null ? "Bu araç için piyasa değeri hesaplanamadı."
    : Math.abs(diff) < 1000 ? "İlan fiyatı piyasa değeriyle aynı seviyede."
    : diff < 0 ? <>Bu araç piyasa değerinden <strong>{tl(-diff)} daha ucuz</strong>.</>
    : <>Bu araç piyasa değerinden <strong>{tl(diff)} daha pahalı</strong>.</>;

  const verdictTone = decision.deviation_pct > 5 ? "expensive" : decision.deviation_pct < -5 ? "cheap" : "fair";
  const vt = verdictToneOf(decision.deviation_pct);
  const devAbs = Math.abs(decision.deviation_pct).toLocaleString("tr-TR", { maximumFractionDigits: 1 });
  const headline = diff == null ? "Değer hesaplanamadı"
    : Math.abs(decision.deviation_pct) < 1 ? "Piyasa değerinde"
    : `%${devAbs} piyasanın ${decision.deviation_pct < 0 ? "altında" : "üstünde"}`;
  const scorePct = Math.max(0, Math.min(100, decision.score * 10));
  const q = data.listing_quality.score;
  const region = data.regional_signal.delta_pct;
  const actionSentence = negotiation.available
    ? <><strong>{tl(negotiation.opening_offer)}</strong> teklifle başlayın, <strong>{tl(negotiation.target_price)}</strong> civarında anlaşmaya çalışın.</>
    : negotiation.reason;

  function printAll() {
    window.dispatchEvent(new Event("as-open-all"));
    window.setTimeout(() => window.print(), 450);
  }

  async function share() {
    const title = `${data.vehicle.year} ${data.vehicle.brand} ${data.vehicle.series} AutoSense analizi`;
    const text = [
      title,
      `İlan fiyatı: ${tl(price)}`,
      `Tahmini piyasa değeri: ${tl(value)}`,
      negotiation.available ? `Hedef pazarlık fiyatı: ${tl(negotiation.target_price)}` : null,
      `Karar: ${decision.title}`,
    ].filter(Boolean).join("\n");
    try {
      if (navigator.share) await navigator.share({ title, text });
      else await navigator.clipboard.writeText(text);
    } catch { /* kullanıcı vazgeçti -- sessiz geç */ }
  }

  return (
    <section className="results visible az-results" id="results" aria-labelledby="az-result-title">
      <div className="az-result-head">
        <div>
          <h2 id="az-result-title">Analiz sonucu</h2>
          <p className="az-result-vehicle">
            {[`${data.vehicle.year} ${data.vehicle.brand} ${data.vehicle.series}`, data.vehicle.engine, data.vehicle.package,
              `${num(data.vehicle.km)} km`, [data.vehicle.city, data.vehicle.district].filter(Boolean).join(" / ")].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="result-actions az-result-actions">
          <button type="button" onClick={printAll}>PDF / Yazdır</button>
          <button type="button" onClick={share}>Paylaş</button>
        </div>
      </div>

      {/* ── Özet: karar, temel değerler ve fiyatın konumu ─────────── */}
      <div className={`az-summary tone-${verdictTone} vt-${vt}`}>
        <div className="az-hero">
          <div className="az-hero-main">
            <span className="az-hero-icon" aria-hidden="true">{TONE_META[vt].icon}</span>
            <div>
              <div className="az-verdict-meta">
                <span className="az-verdict-badge">{TONE_META[vt].word}</span>
                {decision.label !== TONE_META[vt].word && <span className="az-hero-label">{decision.label}</span>}
              </div>
              <h3 className="az-hero-title">{headline}</h3>
              <p className="az-verdict-sentence">{priceSentence}</p>
            </div>
          </div>
          <div className="az-hero-side">
            <div className="az-score-ring" style={{ "--p": `${scorePct}%` } as React.CSSProperties}
              role="img" aria-label={`Karar puanı ${num(decision.score)} / 10`}>
              <span><b>{decision.score.toLocaleString("tr-TR")}</b><small>/10</small></span>
            </div>
            <p className="az-verdict-action"><span>Önerimiz</span>{actionSentence}</p>
          </div>
        </div>

        <ul className="az-signals" aria-label="Hızlı özet">
          <Signal tone={ev.strength === "strong" ? "good" : ev.strength === "weak" ? "bad" : "mid"}
            label="Veri gücü" value={STRENGTH_LABEL[ev.strength] || ev.strength} />
          <Signal tone={q >= 80 ? "good" : q >= 55 ? "mid" : "bad"} label="İlan güveni" value={`${q}/100`} />
          <Signal tone={data.questions.length === 0 ? "good" : data.questions.length <= 2 ? "mid" : "bad"}
            label="Satıcıya sor" value={data.questions.length ? `${data.questions.length} soru` : "Yok"} />
          {region != null && (
            <Signal tone={region <= -2 ? "good" : region >= 2 ? "bad" : "info"} label="Bölge"
              value={`${region > 0 ? "+" : region < 0 ? "−" : ""}%${Math.abs(region).toLocaleString("tr-TR")}`} />
          )}
          {!locks.depreciation && depreciation.available && depreciation.one_year_loss != null && (
            <Signal tone="info" label="1 yılda kayıp" value={`−${tl(depreciation.one_year_loss)}`} />
          )}
          <Signal tone="info" label="Yıllık masraf" value={tl(tco.toplam_yillik_tl)} />
        </ul>

        <dl className="az-metrics">
          <div className="az-metric is-listing">
            <dt>İlan fiyatı</dt>
            <dd><strong>{tl(price)}</strong><small>Girdiğiniz fiyat</small></dd>
          </div>
          <div className="az-metric is-estimate">
            <dt>Tahmini piyasa değeri</dt>
            <dd>
              <strong>{tl(value)}</strong>
              <small>{estimate.estimated_low != null && estimate.estimated_high != null
                ? <>Aralık {tl(estimate.estimated_low)} – {tl(estimate.estimated_high)}</>
                : "Aralık hesaplanamadı"}</small>
            </dd>
          </div>
          <div className={`az-metric is-diff tone-${verdictTone}`}>
            <dt>İlan ile tahmin farkı</dt>
            <dd>
              <strong>{diff == null ? "—" : Math.abs(diff) < 1000 ? "≈ 0 TL" : `${diff > 0 ? "+" : "−"}${tl(Math.abs(diff))}`}</strong>
              <small>{diff == null ? "Hesaplanamadı"
                : Math.abs(diff) < 1000 ? "Piyasa değerine yakın"
                : <><span aria-hidden="true">{diff > 0 ? "▲" : "▼"}</span> %{Math.abs(decision.deviation_pct).toLocaleString("tr-TR")} {diff > 0 ? "piyasanın üstünde" : "piyasanın altında"}</>}</small>
            </dd>
          </div>
          <div className="az-metric is-target">
            <dt>Pazarlık hedefi</dt>
            <dd>
              <strong>{negotiation.available ? tl(negotiation.target_price) : "—"}</strong>
              <small>{negotiation.available
                ? <>Açılış {tl(negotiation.opening_offer)} · Üst sınır {tl(negotiation.ceiling_price)}</>
                : "Bu ilan için hesaplanmadı"}</small>
            </dd>
          </div>
        </dl>

        {value != null && estimate.estimated_low != null && estimate.estimated_high != null && (
          <div className="az-summary-pos">
            <p className="az-section-label">İlan fiyatının piyasadaki yeri</p>
            <PositionBar low={estimate.estimated_low} high={estimate.estimated_high} value={value} price={price} />
          </div>
        )}
      </div>

      {/* ── Veri ve güven: tahminin neye dayandığı (backend'in evidence alanı) ── */}
      <section className="az-provenance" aria-labelledby="az-prov-title">
        <h3 id="az-prov-title" className="az-section-label">Tahminin dayanağı</h3>
        <dl>
          <div>
            <dt>Kanıt gücü</dt>
            <dd><span className={`az-strength is-${ev.strength}`}>{STRENGTH_LABEL[ev.strength] || ev.strength}</span></dd>
          </div>
          <div><dt>Tahmin güveni</dt><dd>%{num(estimate.confidence_pct)}</dd></div>
          {!ev.locked && ev.unique_comparables != null && (
            <div><dt>Emsal araç</dt><dd>{num(ev.unique_comparables)}{ev.unique_sellers ? <small> · {num(ev.unique_sellers)} galeri</small> : null}</dd></div>
          )}
          {!ev.locked && ev.trim_match && (
            <div><dt>Paket eşleşmesi</dt><dd>{TRIM_LABEL[ev.trim_match] || "—"}</dd></div>
          )}
          {!ev.locked && (
            <div><dt>Veri tarihi</dt><dd>{ev.data_date ? new Date(ev.data_date).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }) : "Bilinmiyor"}</dd></div>
          )}
          <div><dt>Fiyat türü</dt><dd>İlan fiyatı</dd></div>
        </dl>
        <div className="az-evidence-cols">
          {!ev.locked && ev.notes && ev.notes.length > 0 && (
            <div>
              <h4>Bu tahmin için</h4>
              <ul className="az-evidence-notes">
                {ev.notes.map((note) => <li key={note}>{note}</li>)}
              </ul>
            </div>
          )}
          <div>
            <h4>Sınırlar</h4>
            <ul className="az-evidence-notes is-limits">
              <li>Fiyatlar ilan fiyatıdır; gerçekleşmiş satış fiyatı değildir.</li>
              <li>Tahmin girdiğiniz araç bilgilerine dayanır; eksik veya hatalı bilgi sonucu etkiler.</li>
              <li>Ekspertiz raporu ve tramer sorgusunun yerini tutmaz.</li>
            </ul>
          </div>
        </div>
        <p className="az-provenance-foot">
          Analiz {new Date(data.generated_at).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" })} tarihinde hesaplandı.
          {!ev.locked && ev.window_days ? ` Emsaller son ${ev.window_days} günün galeri ilanlarından.` : ""}
        </p>
      </section>

      {estimate.liste && ev.locked && (
        <p className="estimate-note az-note">
          <strong>Güncel piyasa.</strong> Tahmine son 30 günde yayınlanan {estimate.liste.count} benzer
          ilan da katıldı (ağırlık %{Math.round(estimate.liste.weight * 100)}).
        </p>
      )}

      {estimate.fallback_reason && (
        <p className="estimate-note az-note">
          <strong>Not.</strong> {estimate.fallback_reason}
          {estimate.package_fallback && (
            <> Hesaba katılan paketler: {estimate.package_fallback.packages.join(", ")}.</>
          )}
        </p>
      )}


      <h3 className="az-details-title">Ayrıntılar <span>Başlıklara dokunarak açın</span></h3>

      <div className="acc-list">
        <Section
          color="orange" title="Fiyat ve pazarlık"
          hint="Pazarlık adımları, fiyatı etkileyenler ve tahminin dayanağı"
          chip={negotiation.available ? `Hedef ${tl(negotiation.target_price)}` : null}
        >
          <div className="merged-block">
            <h4>Pazarlık payı nedir?</h4>
          {negotiation.available ? (
            <>
              <p className="deal-line">
                İlan <strong>{tl(price)}</strong>. <strong>{tl(negotiation.opening_offer)}</strong> ile başlayın,
                <strong> {tl(negotiation.target_price)}</strong> civarında anlaşmaya çalışın.
              </p>
              <ol className="deal-steps">
                <li className="step-open"><span>1</span><div><small>Şununla başla</small><strong>{tl(negotiation.opening_offer)}</strong></div></li>
                <li className="step-target"><span>2</span><div><small>Buraya çekmeye çalış</small><strong>{tl(negotiation.target_price)}</strong></div></li>
                <li className="step-ceiling"><span>3</span><div><small>Bunun üstüne çıkma</small><strong>{tl(negotiation.ceiling_price)}</strong></div></li>
              </ol>
              <PriceLadder
                opening={negotiation.opening_offer}
                target={negotiation.target_price}
                ceiling={negotiation.ceiling_price}
                listing={price}
                saving={negotiation.potential_saving}
              />
            </>
          ) : (
            <p className="card-empty">{negotiation.reason}</p>
          )}
          </div>

          <div className="merged-block">
            <h4>Fiyatı neler etkiledi?</h4>
            <p className="merged-hint">Tahmini artıran ve düşüren etkenler</p>
          {data.price_factors.length ? (
            <FactorBars
              rows={data.price_factors.map((factor) => ({
                key: factor.label, label: factor.label, note: factor.note, pct: factor.effect_pct,
              }))}
            />
          ) : (
            <p className="card-empty">Tahmine belirgin bir düzeltme uygulanmadı.</p>
          )}
          </div>

        </Section>

        <Section
          color="blue" title="Satıcıya ne sorulmalı?" hint="Açıklamada eksik veya çelişkili konular"
          chip={data.questions.length ? `${data.questions.length} soru` : null}
        >
          {data.questions.length ? (
            <ul className="acc-questions">
              {data.questions.map((item, index) => (
                <li key={item.question}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <p><strong>{item.question}</strong>{item.reason}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="card-empty">Temel konular açıklamada belirtilmiş görünüyor.</p>
          )}
        </Section>

        <Section
          color="gold" title="İlan güvenilir mi?" hint="İlan kalitesi ve açıklama analizi"
          chip={data.listing_quality.label}
        >
          <div className="quality-body">
            <ScoreGauge value={data.listing_quality.score} caption={data.listing_quality.label} />
            <DeductionBars quality={data.listing_quality} />
          </div>
          <DescriptionCard data={data.description_analysis} />
        </Section>

        <Section color="rose" title="Bu modelde bilinen sorunlar" hint="Kronik arızalar, artılar ve eksiler">
          <VehicleTraits initial={data.vehicle_traits} />
        </Section>

        <Section
          color="teal" title="Benzer ilanlar" hint="Şu an yayında olan emsal araçlar"
          chip={data.similar_listings.length ? `${data.similar_listings.length} ilan` : null}
        >
          {locks.similar_listings ? (
            <LockedPanel lock={locks.similar_listings} skeleton="listings"
              teaser={locks.similar_listings.count ? `Bu araca benzer ${locks.similar_listings.count} ilan bulundu` : "Yayındaki benzer ilanlar"} />
          ) : (
            <SimilarListings listings={data.similar_listings} price={price} />
          )}
        </Section>


        <Section
          color="red" title="İleride ne kadar değer kaybeder?" hint="1 ve 3 yıl sonraki tahmini değer"
          chip={locks.depreciation ? "Pro" : depreciation.available ? `1 yılda −${tl(depreciation.one_year_loss)}` : null}
        >
          {locks.depreciation ? (
            <LockedPanel lock={locks.depreciation} skeleton="curve"
              teaser="Bu araç 1 ve 3 yıl sonra ne kadar eder?" />
          ) : depreciation.available ? (
            <>
              <DepreciationCurve
                current={depreciation.current_value}
                oneYear={depreciation.one_year_value}
                oneYearLoss={depreciation.one_year_loss}
                threeYear={depreciation.three_year_value}
                threeYearLoss={depreciation.three_year_loss}
              />
              <p className="card-note">{depreciation.note}</p>
            </>
          ) : (
            <p className="card-empty">{depreciation.reason}</p>
          )}
        </Section>

        <Section
          color="plum" title="Yıllık masrafı ne olur?" hint={`${num(tco.yillik_km_varsayimi)} km/yıl varsayımıyla`}
          chip={`${tl(tco.toplam_yillik_tl)} / yıl`}
        >
          <div className="total-cost">
            <span>Tahmini toplam</span>
            <strong>{tl(tco.toplam_yillik_tl)} <small>/ yıl</small></strong>
          </div>
          <div className="cost-lines">
            {costLines.map(([label, v]) => (
              <div key={label}>
                <span>{label}</span>
                <i><b style={{ width: `${((v || 0) / costMax) * 100}%` }} /></i>
                <strong>{tl(v)}</strong>
              </div>
            ))}
          </div>
          {tco.mtv.not && <p className="card-note">{tco.mtv.not}</p>}
        </Section>

        <Section color="green" title="Piyasa durumu" hint="Aynı model için ortalama ilan fiyatının son 90 gündeki seyri">
          <TrendChart trend={data.price_trend} />
        </Section>

        <Section color="indigo" title="Bölge analizi"
          hint="Seçtiğiniz ilin ülke ortalamasına göre konumu"
          chip={data.regional_signal.delta_pct != null ? `${data.regional_signal.delta_pct > 0 ? "+" : ""}%${Math.abs(data.regional_signal.delta_pct).toLocaleString("tr-TR")}` : null}>
          {data.regional_signal.delta_pct != null ? (
            <RegionalScale
              delta={data.regional_signal.delta_pct}
              city={[data.regional_signal.city, data.regional_signal.district].filter(Boolean).join(" / ")}
              confidence={data.regional_signal.confidence_pct}
            />
          ) : (
            <div className="signal-status">
              <span className="signal-dot" />
              <div>
                <strong>{data.regional_signal.label}</strong>
                <p>
                  {data.regional_signal.city
                    ? "Bu bölgede karşılaştırma için yeterli emsal ilan yok."
                    : "İl ve ilçe opsiyoneldir; seçerseniz bölgesel karşılaştırma da yapılır."}
                </p>
              </div>
            </div>
          )}
        </Section>

      </div>

      <p className="disclaimer az-disclaimer">
        Tüm değerler istatistiksel tahmindir; ekspertiz raporu, tramer sorgusu veya
        resmî değerleme yerine geçmez.
      </p>
    </section>
  );
}
