import { tl } from "../../format";

/**
 * Pazarlık planı: açılış / hedef / tavan teklifleri ile ilan fiyatını tek bir
 * fiyat ekseninde gösterir. Eksen 0'dan değil, noktaların kendi aralığından
 * başlar — amaç mutlak büyüklük değil, birbirlerine göre konum.
 *
 * Etiketler eksenin üstünde değil ayrı bir künye satırında duruyor; dar
 * kartta üst üste binmesin diye.
 */
type Kind = "open" | "target" | "ceiling" | "listing";
type Stop = { kind: Kind; label: string; value: number };

export default function PriceLadder({
  opening, target, ceiling, listing, saving,
}: {
  opening: number | null;
  target: number | null;
  ceiling: number | null;
  listing: number;
  saving: number | null;
}) {
  const all: Stop[] = [
    { kind: "open", label: "Açılış teklifi", value: opening ?? NaN },
    { kind: "target", label: "Hedef fiyat", value: target ?? NaN },
    { kind: "ceiling", label: "Tavan fiyat", value: ceiling ?? NaN },
    { kind: "listing", label: "İlan fiyatı", value: listing },
  ];
  const stops = all.filter((s) => Number.isFinite(s.value));

  const values = stops.map((s) => s.value);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const pad = (hi - lo || Math.max(hi * 0.02, 1)) * 0.12;
  const min = lo - pad;
  const span = hi + pad - min;
  const at = (v: number) => ((v - min) / span) * 100;

  const bandFrom = target != null ? at(target) : null;
  const bandTo = at(listing);
  const savingPct = saving != null && listing ? (saving / listing) * 100 : null;

  return (
    <div className="ladder">
      <div className="ladder-headline">
        <span>Hedefe inebilirseniz kazanç</span>
        <strong>{tl(saving)}</strong>
        {savingPct != null && savingPct > 0 && (
          <em>ilan fiyatının %{savingPct.toFixed(1).replace(".", ",")}'i</em>
        )}
      </div>

      <div className="ladder-axis">
        {bandFrom != null && bandTo > bandFrom && (
          <i className="ladder-band" style={{ left: `${bandFrom}%`, width: `${bandTo - bandFrom}%` }} />
        )}
        <i className="ladder-line" />
        {stops.map((s) => (
          <span key={s.kind} className={`ladder-stop is-${s.kind}`} style={{ left: `${at(s.value)}%` }} />
        ))}
        {/* Etiketler barın üstünde/altında dönüşümlü: soldan sağa çakışmasın. */}
        {[...stops].sort((a, b) => a.value - b.value).map((s, i) => (
          <span key={s.kind} className={`ladder-tip is-${s.kind} ${i % 2 === 0 ? "below" : "above"}`}
                style={{ left: `${at(s.value)}%` }}>
            <small>{s.label}</small>
            <b>{tl(s.value)}</b>
          </span>
        ))}
      </div>
    </div>
  );
}
