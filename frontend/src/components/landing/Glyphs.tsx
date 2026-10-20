// Değer önerisi bölümündeki küçük, rakamsız ürün çizimleri. Hepsi dekoratif (aria-hidden);
// anlamı yanlarındaki metin taşır.

/** Fiyat analizi: emsal ilanların dağılımı ve ilanın bu dağılımdaki yeri. */
export function PriceGlyph() {
  const bars = [6, 11, 19, 30, 42, 50, 46, 36, 24, 15, 9, 5];
  return (
    <svg viewBox="0 0 240 96" className="ld-glyph" aria-hidden="true">
      {bars.map((h, i) => (
        <rect key={i} x={8 + i * 19} y={78 - h} width={13} height={h} rx={2} className={i === 8 ? "is-hit" : ""} />
      ))}
      <line x1="4" y1="80" x2="236" y2="80" className="ld-glyph-axis" />
      <line x1="166" y1="14" x2="166" y2="86" className="ld-glyph-mark" />
      <circle cx="166" cy="14" r="4" className="ld-glyph-dot" />
    </svg>
  );
}

/** Piyasa takibi: haftalık ilan fiyatı eğilimi (biçim temsilidir). */
export function TrendGlyph() {
  return (
    <svg viewBox="0 0 240 96" className="ld-glyph" aria-hidden="true">
      {[20, 44, 68].map((y) => <line key={y} x1="4" y1={y} x2="236" y2={y} className="ld-glyph-grid" />)}
      <line x1="4" y1="80" x2="236" y2="80" className="ld-glyph-axis" />
      <path d="M6 58 L40 54 L74 60 L108 48 L142 50 L176 38 L210 34 L234 26" className="ld-glyph-line" />
      <circle cx="234" cy="26" r="4" className="ld-glyph-dot" />
    </svg>
  );
}

/** Araç bilgisi: kaynaklı kronik sorun listesinin iskeleti. */
export function NotesGlyph() {
  const rows = [[0.92, "is-high"], [0.7, "is-mid"], [0.82, "is-mid"], [0.56, ""]] as const;
  return (
    <svg viewBox="0 0 240 96" className="ld-glyph" aria-hidden="true">
      {rows.map(([w, cls], i) => (
        <g key={i}>
          <circle cx="10" cy={14 + i * 22} r="4" className={`ld-glyph-sev ${cls}`} />
          <rect x="24" y={10 + i * 22} width={200 * w} height="8" rx="4" className="ld-glyph-bar" />
        </g>
      ))}
    </svg>
  );
}

/** Bölgesel karşılaştırma: illerin ülke geneline göre fiyat farkı (biçim temsilidir). */
export function RegionGlyph() {
  const diffs = [-22, -14, -9, -4, 3, 7, 12, 18, 26];
  return (
    <svg viewBox="0 0 240 96" className="ld-glyph" aria-hidden="true">
      <line x1="4" y1="48" x2="236" y2="48" className="ld-glyph-axis" />
      {diffs.map((d, i) => {
        const x = 16 + i * 26;
        return (
          <g key={i}>
            <line x1={x} y1="48" x2={x} y2={48 - d * 1.4} className={d < 0 ? "ld-glyph-stem is-low" : "ld-glyph-stem"} />
            <circle cx={x} cy={48 - d * 1.4} r="5" className={d < 0 ? "ld-glyph-pin is-low" : "ld-glyph-pin"} />
          </g>
        );
      })}
    </svg>
  );
}
