/**
 * Bölgesel fiyat sinyali: seçilen ilin ortalaması, ülke ortalamasına göre
 * nerede? Eksen ülke ortalamasında (0) ortalanır; ±%4'lük "uyumlu" bandı
 * backend'deki eşiklerle aynıdır (b2c.py::_regional_signal).
 */
const NEUTRAL = 4;

export default function RegionalScale({
  delta, city, confidence,
}: {
  delta: number;
  city: string;
  confidence: number;
}) {
  const domain = Math.max(8, Math.ceil(Math.abs(delta) * 1.3));
  const at = (v: number) => 50 + (v / domain) * 50;
  const state = delta >= NEUTRAL ? "is-high" : delta <= -NEUTRAL ? "is-low" : "is-flat";
  const verdict =
    state === "is-high" ? "Burada satmak avantajlı" :
    state === "is-low" ? "Burada almak avantajlı" :
    "Ülke ortalamasıyla uyumlu";

  return (
    <div className={`rscale ${state}`}>
      <div className="rscale-headline">
        <strong>
          {delta > 0 ? "+" : delta < 0 ? "−" : ""}%{Math.abs(delta).toLocaleString("tr-TR")}
        </strong>
        <span>{city ? `${city} · ${verdict}` : verdict}</span>
      </div>

      <div className="rscale-axis">
        <i className="rscale-neutral" style={{ left: `${at(-NEUTRAL)}%`, width: `${(2 * NEUTRAL / domain) * 50}%` }} />
        <i className="rscale-line" />
        <i className="rscale-center" />
        <span
          className="rscale-marker"
          style={{ left: `${Math.max(4, Math.min(96, at(delta)))}%` }}
          title={city}
        />
      </div>

      <div className="rscale-ends">
        <span>−%{domain} ucuz</span>
        <span>ülke ort.</span>
        <span>+%{domain} pahalı</span>
      </div>

      <div className="rscale-conf">
        <span>Sinyal güveni</span>
        <i><b style={{ width: `${Math.max(0, Math.min(100, confidence))}%` }} /></i>
        <strong>%{confidence}</strong>
      </div>
    </div>
  );
}
