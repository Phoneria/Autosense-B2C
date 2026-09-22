import type { DescriptionAnalysis } from "../types";
import { tl } from "../format";
import ScoreGauge from "./charts/ScoreGauge";
import FactorBars from "./charts/FactorBars";
import SignalGrid from "./charts/SignalGrid";

/**
 * İlan açıklamasından anlam çıkarımı.
 *
 * Kartın omurgası ÇELİŞKİLER: ilanın metinde iddia ettiği şey ile kullanıcının
 * araç bilgilerinde girdiği şey çakışıyorsa, alıcının elindeki en somut
 * pazarlık kozu odur. Bu yüzden en üstte ve vurgulu duruyor.
 *
 * Sırayla: skor göstergesi + özet → çelişkiler → metnin fiyata etkisi
 * (backend'in price_impact kuralları) → sinyal ızgarası.
 */
export default function DescriptionCard({ data }: { data: DescriptionAnalysis }) {
  if (!data.available) {
    return (
      <article className="result-card wide-card tone-teal">
        <div className="card-top">
          <span className="card-icon orange">¶</span>
          <div>
            <h3>Açıklama analizi</h3>
            <p>İlan metninden çıkarılan anlam ve çelişkiler</p>
          </div>
        </div>
        <p className="card-empty">
          İlan açıklamasını yapıştırırsanız metni analiz eder, girdiğiniz araç
          bilgileriyle çelişen ifadeleri işaretlerim.
        </p>
      </article>
    );
  }

  const impact = data.price_impact;
  const hasImpact = !!impact && (impact.total_pct !== 0 || impact.rules.length > 0);

  return (
    <article className="result-card wide-card tone-teal">
      <div className="card-top">
        <span className="card-icon orange">¶</span>
        <div>
          <h3>Açıklama analizi</h3>
          <p>İlan metninden çıkarılan anlam ve çelişkiler</p>
        </div>
      </div>

      <div className="desc-head">
        <ScoreGauge value={data.score} max={10} caption={data.label} />
        <div className="desc-summary">
          <p>{data.summary}</p>
          <ul className="desc-counts">
            <li className="is-flag"><strong>{data.contradictions.length}</strong><span>çelişki</span></li>
            <li className="is-missing"><strong>{data.missing.length}</strong><span>değinilmemiş konu</span></li>
            <li className="is-claim"><strong>{data.claims.length}</strong><span>iddia</span></li>
          </ul>
        </div>
      </div>

      {data.contradictions.length > 0 && (
        <div className="contradiction-list">
          {data.contradictions.map((c) => (
            <div key={c.claim}>
              <span>Çelişki</span>
              <p>
                <strong>“{c.claim}”</strong>
                {c.conflict}
              </p>
            </div>
          ))}
        </div>
      )}

      {hasImpact && impact && (
        <div className="impact">
          <div className="impact-head">
            <span>Metindeki sinyallerin fiyata etkisi</span>
            <strong className={impact.total_pct > 0 ? "is-pos" : impact.total_pct < 0 ? "is-neg" : "is-zero"}>
              {impact.total_pct > 0 ? "+" : impact.total_pct < 0 ? "−" : ""}
              %{Math.abs(impact.total_pct).toLocaleString("tr-TR")}
            </strong>
          </div>
          {impact.base_price != null && impact.adjusted_price != null && (
            <div className="impact-prices">
              <div>
                <span>İlan fiyatı</span>
                <strong>{tl(impact.base_price)}</strong>
              </div>
              <i className="impact-arrow" aria-hidden="true" />
              <div className="is-adj">
                <span>Metne göre düzeltilmiş</span>
                <strong>{tl(impact.adjusted_price)}</strong>
                {impact.delta != null && impact.delta !== 0 && (
                  <small className={impact.delta > 0 ? "is-pos" : "is-neg"}>
                    {impact.delta > 0 ? "+" : "−"}{tl(Math.abs(impact.delta))}
                  </small>
                )}
              </div>
            </div>
          )}
          {impact.rules.length > 0 && (
            <FactorBars rows={impact.rules.map((r) => ({ key: r.key, label: r.label, pct: r.pct }))} />
          )}
        </div>
      )}

      <SignalGrid
        groups={[
          { kind: "flag", items: data.red_flags },
          { kind: "positive", items: data.positives },
          { kind: "claim", items: data.claims.map((c) => c.label) },
          { kind: "missing", items: data.missing },
        ]}
      />
    </article>
  );
}
