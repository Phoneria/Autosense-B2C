import { useState, type ReactNode } from "react";
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

function titleTr(text: string) {
  return text.split(" ").map((w) => w ? w.charAt(0).toLocaleUpperCase("tr-TR") + w.slice(1) : w).join(" ");
}

function Section({ icon, title, hint, chip, color, children }: {
  icon: string; title: string; hint: string; chip?: string | null; color: string; children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <details className={`acc acc-${color}`} open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        <span className="acc-icon">{icon}</span>
        <span className="acc-text"><strong>{titleTr(title)}</strong><small>{titleTr(hint)}</small></span>
        {chip && <span className="acc-chip">{chip}</span>}
        <span className="acc-arrow" aria-hidden="true">⌄</span>
      </summary>
      <div className="acc-body">{children}</div>
    </details>
  );
}

function PriceBar({ low, high, value, price }: { low: number; high: number; value: number; price: number }) {
  const min = Math.min(low, price, value);
  const max = Math.max(high, price, value);
  const span = Math.max(1, max - min);
  const pos = (v: number) => Math.min(94, Math.max(6, ((v - min) / span) * 100));
  const priceLeft = pos(price);
  const valueLeft = pos(value);
  const cheaper = price <= value;
  return (
    <div className="simple-bar">
      <div className="simple-bar-tags top">
        <span className={`bar-tag listing ${cheaper ? "good" : "bad"}`} style={{ left: `${priceLeft}%` }}>
          <small>İlan fiyatı</small><b>{tl(price)}</b>
        </span>
      </div>
      <div className="simple-bar-track">
        <span className={`simple-bar-mark listing ${cheaper ? "good" : "bad"}`} style={{ left: `${priceLeft}%` }} />
        <span className="simple-bar-mark estimate" style={{ left: `${valueLeft}%` }} />
      </div>
      <div className="simple-bar-tags bottom">
        <span className="bar-tag estimate" style={{ left: `${valueLeft}%` }}>
          <small>Piyasa değeri</small><b>{tl(value)}</b>
        </span>
      </div>
      <div className="simple-bar-labels"><span>Ucuz</span><span>Normal</span><span>Pahalı</span></div>
    </div>
  );
}

export default function Results({ data }: { data: AnalysisResult }) {
  const { estimate, decision, negotiation, depreciation, tco } = data;
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
  const actionSentence = negotiation.available
    ? <><strong>{tl(negotiation.opening_offer)}</strong> teklifle başlayın, <strong>{tl(negotiation.target_price)}</strong> civarında anlaşmaya çalışın.</>
    : negotiation.reason;

  function printAll() {
    document.querySelectorAll<HTMLDetailsElement>("details.acc").forEach((d) => { d.open = true; });
    window.print();
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
    <section className="results visible" id="results">
      <div className="results-heading">
        <div>
          <span className="updated"><span />{new Date(data.generated_at).toLocaleString("tr-TR")}</span>
          <h2>Analiz sonucu</h2>
        </div>
        <div className="result-meta">
          <div className="result-actions">
            <button type="button" onClick={printAll}>PDF / Yazdır</button>
            <button type="button" onClick={share}>Paylaş</button>
          </div>
        </div>
      </div>

      {/* ── Özet: herkesin anlayacağı tek cevap ─────────────────── */}
      <div className={`decision-card tone-${verdictTone}`}>
        <div className="decision-main">
          <div className="score-ring">
            <strong>{decision.score}</strong>
            <span>/10</span>
          </div>
          <div>
            <span className="deal-badge">{decision.label.toLocaleUpperCase("tr-TR")}</span>
            <h2>{decision.title}</h2>
            <p>{priceSentence}</p>
            <p className="simple-action"><span>Önerimiz</span>{actionSentence}</p>
          </div>
        </div>
        <div className="price-comparison">
          <div><span>İlan fiyatı</span><strong>{tl(price)}</strong></div>
          <div><span>Piyasa değeri</span><strong>{tl(value)}</strong></div>
          {value != null && estimate.estimated_low != null && estimate.estimated_high != null && (
            <PriceBar low={estimate.estimated_low} high={estimate.estimated_high} value={value} price={price} />
          )}
        </div>
      </div>

      {estimate.fallback_reason && (
        <p className="estimate-note">
          <strong>Not.</strong> {estimate.fallback_reason}
          {estimate.package_fallback && (
            <> Hesaba katılan paketler: {estimate.package_fallback.packages.join(", ")}.</>
          )}
        </p>
      )}

      <p className="acc-intro">Detayları görmek için başlıklara dokunun.</p>

      <div className="acc-list">
        <Section
          icon="⇄" color="orange" title="Fiyat ve pazarlık"
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
          icon="?" color="blue" title="Satıcıya Ne Sorulmalı?" hint="Açıklamada eksik veya çelişkili konular"
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
          icon="◆" color="gold" title="İlan güvenilir mi?" hint="İlan kalitesi ve açıklama analizi"
          chip={data.listing_quality.label}
        >
          <div className="quality-body">
            <ScoreGauge value={data.listing_quality.score} caption={data.listing_quality.label} />
            <DeductionBars quality={data.listing_quality} />
          </div>
          <DescriptionCard data={data.description_analysis} />
        </Section>

        <Section icon="⚠" color="rose" title="Bu modelde bilinen sorunlar" hint="Kronik arızalar, artılar ve eksiler">
          <VehicleTraits initial={data.vehicle_traits} />
        </Section>

        <Section
          icon="≡" color="teal" title="Benzer ilanlar" hint="Şu an yayında olan emsal araçlar"
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
          icon="↘" color="red" title="İleride ne kadar değer kaybeder?" hint="1 ve 3 yıl sonraki tahmini değer"
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
          icon="◷" color="plum" title="Yıllık masrafı ne olur?" hint={`${num(tco.yillik_km_varsayimi)} km/yıl varsayımıyla`}
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

        <Section icon="₺" color="green" title="Piyasa durumu" hint="Aynı model için ortalama ilan fiyatının son 90 gündeki seyri">
          <TrendChart trend={data.price_trend} />
        </Section>

        <Section icon="◎" color="teal" title="Bölge analizi"
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

      <p className="disclaimer">
        Tüm değerler istatistiksel tahmindir; ekspertiz raporu, tramer sorgusu veya
        resmî değerleme yerine geçmez.
      </p>
    </section>
  );
}
