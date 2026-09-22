/**
 * Sıfır ekseninden iki yöne açılan yüzde etkisi grafiği (tornado).
 * Hem "Fiyatı etkileyen kalemler" hem de açıklama analizindeki fiyat etkisi
 * kuralları için kullanılıyor: ikisi de {etiket, yüzde} listesi.
 *
 * Çubuk uzunluğu, listedeki en büyük mutlak etkiye göre ölçekleniyor; yani
 * en baskın kalem her zaman yarım genişliği doldurur.
 */
export type FactorRow = { key: string; label: string; note?: string; pct: number };

export default function FactorBars({ rows }: { rows: FactorRow[] }) {
  const sorted = [...rows].sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct));
  const max = Math.max(1, ...sorted.map((r) => Math.abs(r.pct)));

  return (
    <div className="fbars">
      {sorted.map((row) => {
        const width = (Math.abs(row.pct) / max) * 50;
        const tone = row.pct > 0 ? "is-pos" : row.pct < 0 ? "is-neg" : "is-zero";
        return (
          <div className="fbar" key={row.key}>
            <div className="fbar-head">
              <strong>{row.label}</strong>
              <span className={`fbar-val ${tone}`}>
                {row.pct > 0 ? "+" : row.pct < 0 ? "−" : ""}%{Math.abs(row.pct).toLocaleString("tr-TR")}
              </span>
            </div>
            <div className="fbar-track">
              <i className="fbar-zero" />
              {row.pct !== 0 && (
                <i
                  className={`fbar-fill ${tone}`}
                  style={row.pct > 0 ? { left: "50%", width: `${width}%` } : { right: "50%", width: `${width}%` }}
                />
              )}
            </div>
            {row.note && <small>{row.note}</small>}
          </div>
        );
      })}
      <div className="fbar-scale">
        <span>−%{max.toLocaleString("tr-TR")}</span>
        <span>0</span>
        <span>+%{max.toLocaleString("tr-TR")}</span>
      </div>
    </div>
  );
}
