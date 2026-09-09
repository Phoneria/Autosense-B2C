import type { AnalysisResult } from "../types";
import { num, tl } from "../format";
import TrendChart from "./TrendChart";
import DescriptionCard from "./DescriptionCard";
import SimilarListings from "./SimilarListings";

export default function Results({ data }: { data: AnalysisResult }) {
  const { estimate, decision, negotiation, depreciation, tco } = data;
  const costLines: [string, number | null][] = [
    ["Yakıt", tco.yakit.yillik_tl],
    ["MTV", tco.mtv.yillik_tl],
    ["Sigorta", tco.sigorta.yillik_tl],
    ["Bakım", tco.bakim.yillik_tl],
  ];
  const costMax = Math.max(1, ...costLines.map(([, v]) => v || 0));

  async function share() {
    const title = `${data.vehicle.year} ${data.vehicle.brand} ${data.vehicle.series} AutoSense analizi`;
    const text = [
      title,
      `İlan fiyatı: ${tl(data.vehicle.price)}`,
      `Tahmini piyasa değeri: ${tl(estimate.tahmini_fiyat)}`,
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
            <button type="button" onClick={() => window.print()}>PDF / Yazdır</button>
            <button type="button" onClick={share}>Paylaş</button>
          </div>
        </div>
      </div>

      <div className="decision-card">
        <div className="decision-main">
          <div className="score-ring">
            <strong>{decision.score}</strong>
            <span>/10</span>
          </div>
          <div>
            <span className="deal-badge">{decision.label.toLocaleUpperCase("tr-TR")}</span>
            <h2>{decision.title}</h2>
            <p>
              İlan fiyatı, AutoSense tahminine göre{" "}
              <strong>
                %{Math.abs(decision.deviation_pct).toLocaleString("tr-TR")}{" "}
                {decision.deviation_pct < 0 ? "altında" : decision.deviation_pct > 0 ? "üzerinde" : "seviyesinde"}
              </strong>.
            </p>
          </div>
        </div>
        <div className="price-comparison">
          <div><span>İlan fiyatı</span><strong>{tl(data.vehicle.price)}</strong></div>
          <div><span>Tahmini piyasa değeri</span><strong>{tl(estimate.tahmini_fiyat)}</strong></div>
          <div>
            <span>Tahmin aralığı</span>
            <strong>{num(estimate.estimated_low)} – {num(estimate.estimated_high)} TL</strong>
          </div>
          <div>
            <span>Güven / renk etkisi</span>
            <strong>
              %{estimate.confidence_pct}
              {estimate.color_adjustment
                ? ` · renk %${estimate.color_adjustment.factor_pct}`
                : ""}
            </strong>
          </div>
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

      <div className="source-strip">
        <span>Canlı veri kaynakları</span>
        <strong>{data.data_sources.gallery_matches} galeri ilanı</strong>
        <strong>{data.data_sources.listing_matches} analiz edilmiş ilan</strong>
        <strong>{data.data_sources.trend_points} fiyat trendi noktası</strong>
        <strong>{data.data_sources.similar_listings} yayındaki emsal</strong>
      </div>

      <div className="result-grid">
        {/* ── Pazarlık ─────────────────────────────────────────────── */}
        <article className="result-card tone-orange">
          <div className="card-top">
            <span className="card-icon orange">⇄</span>
            <div><h3>Pazarlık planı</h3><p>Veri destekli teklif aralığı</p></div>
          </div>
          {negotiation.available ? (
            <>
              <div className="negotiation-grid">
                <div><span>Açılış teklifi</span><strong>{tl(negotiation.opening_offer)}</strong></div>
                <div className="target"><span>Hedef fiyat</span><strong>{tl(negotiation.target_price)}</strong></div>
                <div><span>Tavan fiyat</span><strong>{tl(negotiation.ceiling_price)}</strong></div>
              </div>
              <p className="card-note">
                Hedefe inebilirseniz kazancınız <strong>{tl(negotiation.potential_saving)}</strong>. {negotiation.note}
              </p>
            </>
          ) : (
            <p className="card-empty">{negotiation.reason}</p>
          )}
        </article>

        {/* ── Fiyat kalemleri ──────────────────────────────────────── */}
        <article className="result-card tone-violet">
          <div className="card-top">
            <span className="card-icon orange">±</span>
            <div><h3>Fiyatı etkileyen kalemler</h3><p>Tahmine uygulanan artı ve eksi etkiler</p></div>
          </div>
          {data.price_factors.length ? (
            <div className="factor-list">
              {data.price_factors.map((factor) => (
                <div key={factor.label}>
                  <p><strong>{factor.label}</strong><small>{factor.note}</small></p>
                  <span className={factor.effect_pct > 0 ? "positive" : factor.effect_pct < 0 ? "negative" : "neutral"}>
                    {factor.effect_pct > 0 ? "+" : ""}%{factor.effect_pct.toLocaleString("tr-TR")}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="card-empty">Tahmine belirgin bir düzeltme uygulanmadı.</p>
          )}
        </article>

        {/* ── Değer kaybı ──────────────────────────────────────────── */}
        <article className="result-card tone-rose">
          <div className="card-top">
            <span className="card-icon orange">↘</span>
            <div><h3>Değer kaybı projeksiyonu</h3><p>Yaş grubuna göre tahmini ikinci el değeri</p></div>
          </div>
          {depreciation.available ? (
            <>
              <div className="depreciation-grid">
                <div><span>Bugün</span><strong>{tl(depreciation.current_value)}</strong></div>
                <div>
                  <span>1 yıl sonra</span><strong>{tl(depreciation.one_year_value)}</strong>
                  <small>−{tl(depreciation.one_year_loss)}</small>
                </div>
                <div>
                  <span>3 yıl sonra</span><strong>{tl(depreciation.three_year_value)}</strong>
                  <small>−{tl(depreciation.three_year_loss)}</small>
                </div>
              </div>
              <p className="card-note">{depreciation.note}</p>
            </>
          ) : (
            <p className="card-empty">{depreciation.reason}</p>
          )}
        </article>

        {/* ── İlan kalitesi ────────────────────────────────────────── */}
        <article className="result-card tone-gold">
          <div className="card-top">
            <span className="card-icon orange">◆</span>
            <div><h3>İlan kalitesi ve belirsizlik</h3><p>Veri riski ve açıklama sinyalleri</p></div>
            <span className="quality-score">{data.listing_quality.score}</span>
          </div>
          <div className="quality-status">
            <strong>{data.listing_quality.label}</strong>
            <i><b style={{ width: `${data.listing_quality.score}%` }} /></i>
          </div>
          {data.listing_quality.warnings.length ? (
            <ul className="quality-warnings">
              {data.listing_quality.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          ) : (
            <p className="quality-clean">Belirgin bir veri riski tespit edilmedi.</p>
          )}
        </article>

        {/* ── Açıklama analizi (tam genişlik) ──────────────────────── */}
        <DescriptionCard data={data.description_analysis} />

        {/* ── Sorular ──────────────────────────────────────────────── */}
        <article className="result-card questions tone-blue">
          <div className="card-top">
            <span className="card-icon orange">?</span>
            <div><h3>Satıcıya mutlaka sorun</h3><p>Açıklamada belirtilmeyen ve çelişen konular</p></div>
            <span className="count">{data.questions.length}</span>
          </div>
          {data.questions.length ? (
            <ul>
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
        </article>

        {/* ── Bölgesel sinyal ──────────────────────────────────────── */}
        <article className="result-card tone-green">
          <div className="card-top">
            <span className="card-icon orange">◎</span>
            <div><h3>Bölgesel fiyat sinyali</h3><p>Seçtiğiniz bölgenin ülke ortalamasına göre konumu</p></div>
          </div>
          <div className="signal-status">
            <span className="signal-dot" />
            <div>
              <strong>{data.regional_signal.label}</strong>
              <p>
                {data.regional_signal.city
                  ? [data.regional_signal.city, data.regional_signal.district].filter(Boolean).join(" / ")
                  : "İl ve ilçe opsiyoneldir; seçerseniz bölgesel karşılaştırma da yapılır."}
              </p>
            </div>
          </div>
          <div className="signal-stats">
            <div><span>Güven</span><strong>%{data.regional_signal.confidence_pct}</strong></div>
            <div><span>Emsal galeri ilanı</span><strong>{data.data_sources.gallery_matches}</strong></div>
            <div><span>Yayındaki emsal</span><strong>{data.data_sources.similar_listings}</strong></div>
          </div>
        </article>

        {/* ── Fiyat trendi (tam genişlik, çizgi grafik) ────────────── */}
        <article className="result-card wide-card tone-orange">
          <div className="card-top">
            <span className="card-icon orange">₺</span>
            <div><h3>Piyasa fiyat trendi</h3><p>Galeri ilanlarındaki ortalama fiyatın zaman içindeki hareketi</p></div>
          </div>
          <TrendChart trend={data.price_trend} />
        </article>

        {/* ── Yayındaki benzer ilanlar ─────────────────────────────── */}
        <SimilarListings listings={data.similar_listings} price={data.vehicle.price} />

        {/* ── Yıllık maliyet ───────────────────────────────────────── */}
        <article className="result-card wide-card tone-plum">
          <div className="card-top">
            <span className="card-icon orange">◷</span>
            <div>
              <h3>Yıllık sahip olma maliyeti</h3>
              <p>{num(tco.yillik_km_varsayimi)} km/yıl varsayımıyla</p>
            </div>
          </div>
          <div className="total-cost">
            <span>Tahmini toplam</span>
            <strong>{tl(tco.toplam_yillik_tl)} <small>/ yıl</small></strong>
          </div>
          <div className="cost-lines">
            {costLines.map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <i><b style={{ width: `${((value || 0) / costMax) * 100}%` }} /></i>
                <strong>{tl(value)}</strong>
              </div>
            ))}
          </div>
          {tco.mtv.not && <p className="card-note">{tco.mtv.not}</p>}
        </article>
      </div>

      <p className="disclaimer">
        Tüm değerler istatistiksel tahmindir; ekspertiz raporu, tramer sorgusu veya
        resmî değerleme yerine geçmez.
      </p>
    </section>
  );
}
