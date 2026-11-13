import { useId, useState, type PointerEvent } from "react";
import { shortDate } from "../../format";

export interface Series { name: string; color: string; values: (number | null)[]; kind?: "line" | "bar" }

const P = { top: 16, right: 12, bottom: 28, left: 56 };

/** Noktalar arasından yumuşak eğri (monoton kübik): tepe/dip noktalarını taşırmaz. */
function smoothPath(pts: [number, number][]) {
  if (pts.length < 3) return pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");
  const n = pts.length;
  const dx: number[] = [], m: number[] = [];
  for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; m[i] = (pts[i + 1][1] - pts[i][1]) / dx[i]; }
  const t: number[] = [m[0]];
  for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
  t[n - 1] = m[n - 2];
  for (let i = 0; i < n - 1; i++) {
    if (m[i] === 0) { t[i] = 0; t[i + 1] = 0; continue; }
    const a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
    if (s > 9) { const k = 3 / Math.sqrt(s); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
  }
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const c1x = pts[i][0] + dx[i] / 3, c1y = pts[i][1] + (t[i] * dx[i]) / 3;
    const c2x = pts[i + 1][0] - dx[i] / 3, c2y = pts[i + 1][1] - (t[i + 1] * dx[i]) / 3;
    d += `C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${pts[i + 1][0].toFixed(1)},${pts[i + 1][1].toFixed(1)}`;
  }
  return d;
}

/** Haftalık SVG grafik: yumuşak çizgi (tek seride altı dolgulu) ve/veya yuvarlak köşeli gruplu çubuk.
 *  Fareyle/dokunarak bir haftanın üzerine gelince o haftanın değerleri gösterilir. Boş (null) haftalar atlanır. */
export default function WeeklyChart({ weeks, series, format, baseline, wide = false }: {
  weeks: string[]; series: Series[]; format: (v: number) => string; baseline?: number;
  /** Tam genişlik kartlar için: yazılar büyümesin diye çizim alanı genişler. */
  wide?: boolean;
}) {
  const W = wide ? 1280 : 640;
  const H = wide ? 240 : 220;
  const gid = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);
  const all = series.flatMap((s) => s.values.filter((v): v is number => v != null));
  if (!all.length) return <p className="card-empty">Grafik için yeterli veri yok.</p>;
  const bars = series.filter((s) => s.kind === "bar");
  const lines = series.filter((s) => s.kind !== "bar");
  let min = Math.min(...all, ...(baseline != null ? [baseline] : []));
  let max = Math.max(...all, ...(baseline != null ? [baseline] : []));
  if (bars.length) min = Math.min(0, min);
  if (max === min) { max += 1; min -= 1; }
  const pad = (max - min) * 0.1;
  if (!bars.length) { min -= pad; }
  max += pad;
  const iw = W - P.left - P.right;
  const ih = H - P.top - P.bottom;
  const step = iw / weeks.length;
  const x = (i: number) => P.left + step * i + step / 2;
  const y = (v: number) => P.top + ih - ((v - min) / (max - min)) * ih;
  const ticks = [0, 1 / 3, 2 / 3, 1].map((t) => min + (max - min) * t);
  const groupW = step * (bars.length > 1 ? 0.72 : 0.5);
  const barW = Math.max(3, groupW / Math.max(1, bars.length));
  const fillArea = lines.length === 1 && !bars.length;

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const i = Math.floor((px - P.left) / step);
    setHover(i >= 0 && i < weeks.length ? i : null);
  };
  const tipLeft = hover != null ? (x(hover) / W) * 100 : 0;

  return (
    <div className="weekly-chart">
      <div className="wc-frame">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" onPointerMove={onMove} onPointerDown={onMove} onPointerLeave={(e) => { if (e.pointerType === "mouse") setHover(null); }}
          aria-label={`${series.map((s) => s.name).join(", ")}: haftalık grafik, ${shortDate(weeks[0])} – ${shortDate(weeks[weeks.length - 1])}`}>
          <defs>
            {lines.map((s, si) => (
              <linearGradient key={si} id={`${gid}-g${si}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" style={{ stopColor: s.color, stopOpacity: 0.22 }} />
                <stop offset="100%" style={{ stopColor: s.color, stopOpacity: 0 }} />
              </linearGradient>
            ))}
          </defs>
          {ticks.map((t, ti) => (
            <g key={ti}>
              <line x1={P.left} x2={W - P.right} y1={y(t)} y2={y(t)} className="wc-grid" />
              <text x={P.left - 8} y={y(t) + 4} textAnchor="end" className="wc-label">{format(t)}</text>
            </g>
          ))}
          {baseline != null && <line x1={P.left} x2={W - P.right} y1={y(baseline)} y2={y(baseline)} className="wc-base" />}
          {hover != null && <rect x={x(hover) - step / 2} y={P.top} width={step} height={ih} className="wc-hover-band" />}
          {bars.map((s, si) => s.values.map((v, i) => v == null ? null : (
            <rect key={`${s.name}-${i}`} x={x(i) - (barW * bars.length) / 2 + si * barW + 1} y={Math.min(y(v), y(0))}
              width={Math.max(2, barW - 2)} height={Math.max(1, Math.abs(y(0) - y(v)))} style={{ fill: s.color }}
              rx={Math.min(5, barW / 2 - 1)} className={hover != null && hover !== i ? "wc-dim" : undefined}>
              <title>{`${shortDate(weeks[i])} haftası · ${s.name}: ${format(v)}`}</title>
            </rect>
          )))}
          {lines.map((s, si) => {
            const segments: [number, number][][] = [];
            let cur: [number, number][] = [];
            s.values.forEach((v, i) => {
              if (v == null) { if (cur.length) segments.push(cur); cur = []; return; }
              cur.push([x(i), y(v)]);
            });
            if (cur.length) segments.push(cur);
            const lastIdx = s.values.map((v, i) => (v == null ? -1 : i)).filter((i) => i >= 0).pop();
            return (
              <g key={s.name}>
                {fillArea && segments.map((seg, i) => seg.length > 1 && (
                  <path key={`a${i}`} d={`${smoothPath(seg)}L${seg[seg.length - 1][0].toFixed(1)},${(P.top + ih).toFixed(1)}L${seg[0][0].toFixed(1)},${(P.top + ih).toFixed(1)}Z`}
                    style={{ fill: `url(#${gid}-g${si})` }} />
                ))}
                {segments.map((seg, i) => <path key={i} d={smoothPath(seg)} fill="none" style={{ stroke: s.color }} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />)}
                {lastIdx != null && hover == null && (
                  <circle cx={x(lastIdx)} cy={y(s.values[lastIdx] as number)} r={4.5} style={{ fill: s.color, stroke: "var(--chart-point-bg)" }} strokeWidth={2.5} />
                )}
                {hover != null && s.values[hover] != null && (
                  <circle cx={x(hover)} cy={y(s.values[hover] as number)} r={5} style={{ fill: "var(--chart-point-bg)", stroke: s.color }} strokeWidth={2.5} />
                )}
              </g>
            );
          })}
          {weeks.map((w, i) => (i % 2 === 0 || i === weeks.length - 1) && (
            <text key={w} x={x(i)} y={H - 8} textAnchor="middle" className="wc-label">{shortDate(w)}</text>
          ))}
        </svg>
        {hover != null && (
          <div className={`wc-tip${tipLeft > 70 ? " is-left" : ""}`} style={{ left: `${tipLeft}%` }} aria-hidden="true">
            <strong>{shortDate(weeks[hover])} haftası</strong>
            {series.map((s) => (
              <span key={s.name}><i style={{ background: s.color }} />{s.name}<b>{s.values[hover] == null ? "—" : format(s.values[hover] as number)}</b></span>
            ))}
          </div>
        )}
      </div>
      {series.length > 1 && (
        <div className="wc-legend">{series.map((s) => <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>)}</div>
      )}
    </div>
  );
}
