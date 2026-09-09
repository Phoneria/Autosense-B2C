import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { TrendPoint } from "../types";
import { num, shortDate, tl } from "../format";

const HEIGHT = 150;
const PAD_TOP = 14;      // en yüksek noktanın markeri kırpılmasın
const PAD_BOTTOM = 6;

/**
 * Piyasa fiyat trendi -- tek serili zaman serisi ÇİZGİ grafiği.
 *
 * Tek seri olduğu için lejant yok (kart başlığı seriyi zaten adlandırıyor);
 * kimlik renkle değil, doğrudan etiketlerle veriliyor: ilk ve son nokta
 * etiketli, aradakiler sadece hover'da. Izgara çizgileri geri planda
 * (kesikli, açık gri), veri çizgisi 2px tek vurgu renginde.
 */
export default function TrendChart({ trend }: { trend: TrendPoint[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<number | null>(null);

  useLayoutEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  useEffect(() => { setHover(null); }, [trend]);

  if (!trend.length) {
    return <p className="card-empty">Bu araç için yeterli tarihsel veri bulunamadı.</p>;
  }

  const prices = trend.map((p) => p.avg_price);
  const first = trend[0];
  const last = trend[trend.length - 1];
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  // Tek ölçüm ya da düz çizgi durumunda 0'a bölmeyi engelle.
  const span = Math.max(1, max - min);
  const change = last.avg_price - first.avg_price;
  const changePct = first.avg_price ? (change / first.avg_price) * 100 : 0;
  const direction = change > 0 ? "up" : change < 0 ? "down" : "flat";

  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const x = (i: number) =>
    trend.length === 1 ? width / 2 : (i / (trend.length - 1)) * width;
  const y = (v: number) => PAD_TOP + (1 - (v - min) / span) * plotHeight;

  const line = trend.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.avg_price).toFixed(1)}`).join(" ");
  const area = `${line} L${x(trend.length - 1).toFixed(1)},${HEIGHT} L${x(0).toFixed(1)},${HEIGHT} Z`;

  const active = hover == null ? null : trend[hover];

  function onMove(event: React.MouseEvent<HTMLDivElement>) {
    if (!width || trend.length < 2) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - bounds.left) / bounds.width;
    const index = Math.round(ratio * (trend.length - 1));
    setHover(Math.max(0, Math.min(trend.length - 1, index)));
  }

  return (
    <div className="market-trend">
      <div className="trend-kpis">
        <div>
          <span>Güncel ortalama</span>
          <strong>{tl(last.avg_price)}</strong>
          <small>{last.sample_count} ilan</small>
        </div>
        <div>
          <span>Dönem değişimi</span>
          <strong className={direction}>{change > 0 ? "+" : ""}{tl(change)}</strong>
          <small className={direction}>
            {changePct > 0 ? "+" : ""}%{changePct.toFixed(1)}
          </small>
        </div>
        <div>
          <span>En düşük – yüksek</span>
          <strong>{num(min)} – {num(max)} TL</strong>
          <small>{trend.length} ölçüm tarihi</small>
        </div>
      </div>

      <div className="trend-chart">
        <div className="trend-axis">
          <span>{num(max)}</span>
          <span>{num((max + min) / 2)}</span>
          <span>{num(min)}</span>
        </div>

        <div
          className="trend-plot"
          ref={wrapRef}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          role="img"
          aria-label={`${shortDate(first.snapshot_date)} ile ${shortDate(last.snapshot_date)} arasındaki ortalama ilan fiyatları. Başlangıç ${tl(first.avg_price)}, bitiş ${tl(last.avg_price)}.`}
        >
          {width > 0 && (
            <svg
              className="trend-svg"
              width={width}
              height={HEIGHT}
              viewBox={`0 0 ${width} ${HEIGHT}`}
            >
              <defs>
                <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef6c28" stopOpacity="0.16" />
                  <stop offset="100%" stopColor="#ef6c28" stopOpacity="0" />
                </linearGradient>
              </defs>

              {/* Izgara -- geri planda, kesikli */}
              {[0, 0.5, 1].map((t) => (
                <line
                  key={t}
                  x1={0}
                  x2={width}
                  y1={PAD_TOP + t * plotHeight}
                  y2={PAD_TOP + t * plotHeight}
                  className="trend-gridline"
                />
              ))}

              <path d={area} fill="url(#trendFill)" />
              <path d={line} className="trend-line" />

              {active && (
                <line
                  x1={x(hover!)} x2={x(hover!)}
                  y1={0} y2={HEIGHT}
                  className="trend-crosshair"
                />
              )}

              {/* İlk ve son nokta her zaman görünür; arası sadece hover'da --
                  her noktaya marker koymak 56 ölçümde çizgiyi okunmaz yapıyor. */}
              <circle cx={x(0)} cy={y(first.avg_price)} r="4" className="trend-dot" />
              <circle
                cx={x(trend.length - 1)} cy={y(last.avg_price)}
                r="5" className="trend-dot current"
              />
              {active && hover !== 0 && hover !== trend.length - 1 && (
                <circle cx={x(hover!)} cy={y(active.avg_price)} r="5" className="trend-dot current" />
              )}
            </svg>
          )}

          {active && (
            <div
              className="trend-tooltip"
              style={{
                left: `${(hover! / Math.max(1, trend.length - 1)) * 100}%`,
                transform: `translate(${hover! === 0 ? "0" : hover! === trend.length - 1 ? "-100%" : "-50%"}, 0)`,
              }}
            >
              <strong>{tl(active.avg_price)}</strong>
              <span>{shortDate(active.snapshot_date)} · {active.sample_count} ilan</span>
            </div>
          )}
        </div>
      </div>

      <div className="trend-dates">
        <span>{shortDate(first.snapshot_date)}</span>
        <span>{shortDate(last.snapshot_date)}</span>
      </div>

      <p className="trend-explanation">
        Ortalama ilan fiyatı bu dönemde <strong>{tl(first.avg_price)}</strong> seviyesinden{" "}
        <strong>{tl(last.avg_price)}</strong> seviyesine{" "}
        {change > 0 ? "yükseldi" : change < 0 ? "geriledi" : "değişmeden kaldı"}.
      </p>
    </div>
  );
}
