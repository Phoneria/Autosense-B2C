import type { DescriptionAnalysis } from "../types";

/**
 * İlan açıklamasından anlam çıkarımı.
 *
 * Kartın omurgası ÇELİŞKİLER: ilanın metinde iddia ettiği şey ile kullanıcının
 * araç bilgilerinde girdiği şey çakışıyorsa, alıcının elindeki en somut
 * pazarlık kozu odur. Bu yüzden en üstte ve vurgulu duruyor.
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

  return (
    <article className="result-card wide-card tone-teal">
      <div className="card-top">
        <span className="card-icon orange">¶</span>
        <div>
          <h3>Açıklama analizi</h3>
          <p>İlan metninden çıkarılan anlam ve çelişkiler</p>
        </div>
        <span className="quality-score">{data.score}</span>
      </div>

      <div className="quality-status">
        <strong>{data.label}</strong>
        <i><b style={{ width: `${data.score * 10}%` }} /></i>
      </div>

      <p className="card-note" style={{ marginTop: 12 }}>{data.summary}</p>

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

      <div className="insight-columns">
        <div>
          <h4>İlanın iddiaları</h4>
          {data.claims.length ? (
            <ul className="chip-list">
              {data.claims.map((c) => (
                <li key={c.key}>{c.label}</li>
              ))}
            </ul>
          ) : (
            <p className="card-empty">Metinde tanınan bir iddia bulunamadı.</p>
          )}
        </div>

        <div>
          <h4>Değinilmemiş konular</h4>
          {data.missing.length ? (
            <ul className="chip-list muted">
              {data.missing.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          ) : (
            <p className="quality-clean">Kritik konuların tamamına değinilmiş.</p>
          )}
        </div>
      </div>

      {data.red_flags.length > 0 && (
        <ul className="quality-warnings">
          {data.red_flags.map((flag) => (
            <li key={flag}>{flag}</li>
          ))}
        </ul>
      )}
    </article>
  );
}
