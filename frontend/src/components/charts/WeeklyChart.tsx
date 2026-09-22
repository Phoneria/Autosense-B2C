import { shortDate } from "../../format";

export interface Series { name: string; color: string; values: (number | null)[]; kind?: "line" | "bar" }

const W = 640;
const H = 220;
const P = { top: 16, right: 12, bottom: 28, left: 56 };

/** Haftalık basit SVG grafik: çizgi ve/veya gruplu çubuk. Boş (null) haftalar atlanır. */
export default function WeeklyChart({ weeks, series, format, baseline }: {
  weeks: string[]; series: Series[]; format: (v: number) => string; baseline?: number;
}) {
  const all = series.flatMap((s) => s.values.filter((v): v is number => v != null));
  if (!all.length) return <p className="card-empty">Grafik için yeterli veri yok.</p>;
  const bars = series.filter((s) => s.kind === "bar");
  let min = Math.min(...all, ...(baseline != null ? [baseline] : []));
  let max = Math.max(...all, ...(baseline != null ? [baseline] : []));
  if (bars.length) min = Math.min(0, min);
  if (max === min) { max += 1; min -= 1; }
  const pad = (max - min) * 0.08;
  if (!bars.length) { min -= pad; }
  max += pad;
  const iw = W - P.left - P.right;
  const ih = H - P.top - P.bottom;
  const step = iw / weeks.length;
  const x = (i: number) => P.left + step * i + step / 2;
  const y = (v: number) => P.top + ih - ((v - min) / (max - min)) * ih;
  const ticks = [0, 0.5, 1].map((t) => min + (max - min) * t);
  const barW = Math.max(3, (step * 0.7) / Math.max(1, bars.length));

  return (
    <div className="weekly-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={P.left} x2={W - P.right} y1={y(t)} y2={y(t)} className="wc-grid" />
            <text x={P.left - 6} y={y(t) + 4} textAnchor="end" className="wc-label">{format(t)}</text>
          </g>
        ))}
        {baseline != null && <line x1={P.left} x2={W - P.right} y1={y(baseline)} y2={y(baseline)} className="wc-base" />}
        {bars.map((s, si) => s.values.map((v, i) => v == null ? null : (
          <rect key={`${s.name}-${i}`} x={x(i) - (barW * bars.length) / 2 + si * barW} y={Math.min(y(v), y(0))}
            width={barW - 1} height={Math.abs(y(0) - y(v))} fill={s.color} rx={2}>
            <title>{`${shortDate(weeks[i])} haftası · ${s.name}: ${format(v)}`}</title>
          </rect>
        )))}
        {series.filter((s) => s.kind !== "bar").map((s) => {
          const pts = s.values.map((v, i) => (v == null ? null : [x(i), y(v)] as const));
          const segments: string[] = [];
          let cur = "";
          pts.forEach((p) => {
            if (!p) { if (cur) segments.push(cur); cur = ""; return; }
            cur += `${cur ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`;
          });
          if (cur) segments.push(cur);
          return (
            <g key={s.name}>
              {segments.map((d, i) => <path key={i} d={d} fill="none" stroke={s.color} strokeWidth={2.5} strokeLinejoin="round" />)}
              {pts.map((p, i) => p && (
                <circle key={i} cx={p[0]} cy={p[1]} r={3.5} fill="#fff" stroke={s.color} strokeWidth={2}>
                  <title>{`${shortDate(weeks[i])} haftası · ${s.name}: ${format(s.values[i] as number)}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        {weeks.map((w, i) => (i % 2 === 0 || i === weeks.length - 1) && (
          <text key={w} x={x(i)} y={H - 8} textAnchor="middle" className="wc-label">{shortDate(w)}</text>
        ))}
      </svg>
      {series.length > 1 && (
        <div className="wc-legend">{series.map((s) => <span key={s.name}><i style={{ background: s.color }} />{s.name}</span>)}</div>
      )}
    </div>
  );
}
