/**
 * Yarım daire skor göstergesi. Renk, kartın tonundan değil skorun kendi
 * eşiklerinden gelir (sabit rubrik): >=%80 düşük risk, >=%55 orta, altı yüksek.
 * Eşikler yayın üzerinde çentik olarak da işaretlidir.
 */
const ARC = Math.PI * 50; // r=50 yarım çember uzunluğu

export default function ScoreGauge({
  value, max = 100, caption,
}: {
  value: number;
  max?: number;
  caption: string;
}) {
  const ratio = Math.max(0, Math.min(1, value / max));
  const band = ratio >= 0.8 ? "is-good" : ratio >= 0.55 ? "is-mid" : "is-bad";
  const tickAt = (r: number) => {
    const a = Math.PI * (1 - r);
    return { x: 60 + Math.cos(a) * 50, y: 60 - Math.sin(a) * 50 };
  };
  const t55 = tickAt(0.55);
  const t80 = tickAt(0.8);

  return (
    <div className={`gauge ${band}`}>
      <svg viewBox="0 0 120 72" role="img" aria-label={`${value} / ${max} — ${caption}`}>
        <path className="gauge-track" d="M10 60 A50 50 0 0 1 110 60" />
        <path
          className="gauge-fill"
          d="M10 60 A50 50 0 0 1 110 60"
          strokeDasharray={`${ratio * ARC} ${ARC}`}
        />
        <circle className="gauge-tick" cx={t55.x} cy={t55.y} r="2.4" />
        <circle className="gauge-tick" cx={t80.x} cy={t80.y} r="2.4" />
        <text className="gauge-value" x="60" y="54" textAnchor="middle">{value}</text>
        <text className="gauge-max" x="60" y="68" textAnchor="middle">/ {max}</text>
      </svg>
      <strong>{caption}</strong>
    </div>
  );
}
