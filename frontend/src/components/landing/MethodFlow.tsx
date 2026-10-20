// "Veriden karara" veri akışı: piyasa ilanları → özelliklere göre düzeltme → tahmini değer ve aralık.
// Çizimler yalnızca biçimi anlatır; eksen, rakam, fiyat veya model içermez (aria-hidden).
import type { ReactNode } from "react";

// Sabit, tekrarlanabilir nokta bulutu (rastgele değil; her çizimde aynı görünür).
const CLOUD: Array<[number, number]> = [
  [18, 74], [26, 40], [34, 88], [41, 58], [48, 30], [55, 80], [62, 50], [70, 96], [76, 36], [84, 66],
  [92, 46], [99, 84], [106, 26], [113, 60], [121, 92], [128, 42], [136, 72], [143, 54], [151, 32], [158, 86],
  [166, 62], [173, 44], [181, 78], [189, 28], [196, 58], [204, 90], [211, 48], [219, 70],
];
// Düzeltme sonrası: aynı noktalar ortak bir eğilime yaklaşır.
const trend = (x: number) => 86 - (x - 14) * 0.24;
const ADJUSTED = CLOUD.map(([x, y]) => [x, trend(x) + (y - 60) * 0.18] as [number, number]);

function Frame({ children }: { children: ReactNode }) {
  return <svg viewBox="0 0 236 112" className="mf-viz" aria-hidden="true" focusable="false">{children}</svg>;
}

function ListingsViz() {
  return (
    <Frame>
      <line x1="8" y1="104" x2="228" y2="104" className="mf-axis" />
      {CLOUD.map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="3.2" className="mf-dot" />)}
    </Frame>
  );
}

function AdjustViz() {
  return (
    <Frame>
      <line x1="8" y1="104" x2="228" y2="104" className="mf-axis" />
      <line x1="12" y1={trend(12)} x2="224" y2={trend(224)} className="mf-trend" />
      {ADJUSTED.map(([x, y]) => <circle key={x} cx={x} cy={y} r="3.2" className="mf-dot is-adjusted" />)}
    </Frame>
  );
}

function EstimateViz() {
  // Çan eğrisi yalnızca "aralık" fikrini anlatır; ölçeği yoktur.
  const bell = Array.from({ length: 41 }, (_, i) => {
    const x = 18 + i * 5;
    const t = (x - 118) / 34;
    return `${i ? "L" : "M"}${x} ${92 - Math.exp(-t * t / 2) * 62}`;
  }).join(" ");
  return (
    <Frame>
      <rect x="84" y="20" width="68" height="84" rx="4" className="mf-band" />
      <path d={bell} className="mf-bell" />
      <line x1="8" y1="104" x2="228" y2="104" className="mf-axis" />
      <line x1="118" y1="22" x2="118" y2="104" className="mf-center" />
      <circle cx="118" cy="30" r="4.5" className="mf-center-dot" />
    </Frame>
  );
}

const STAGES = [
  {
    no: "01", title: "Piyasa ilan verisi", text: "Aynı modelin güncel ilanları toplanır.",
    tags: ["Güncel emsaller", "İlan fiyatı"], Viz: ListingsViz,
  },
  {
    no: "02", title: "Özelliklere göre düzeltme", text: "Her emsal, aracınızla arasındaki farka göre dengelenir.",
    tags: ["Yaş", "Kilometre", "Hasar", "Donanım"], Viz: AdjustViz,
  },
  {
    no: "03", title: "Tahmini değer ve aralık", text: "Sonuç tek bir sayı değil, bir değer ve aralık olarak verilir.",
    tags: ["Değer", "Aralık", "Veri tarihi"], Viz: EstimateViz,
  },
];

export default function MethodFlow() {
  return (
    <ol className="mf" aria-label="Tahminin hesaplanma akışı">
      {STAGES.map(({ no, title, text, tags, Viz }, i) => (
        <li key={no} className={`mf-stage${i === STAGES.length - 1 ? " is-result" : ""}`}>
          <div className="mf-head">
            <span className="mf-node" aria-hidden="true">{no}</span>
            <span className="mf-rail" aria-hidden="true" />
          </div>
          <h3>{title}</h3>
          <p>{text}</p>
          <Viz />
          <ul className="mf-tags" aria-label={`${title}: girdiler`}>
            {tags.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </li>
      ))}
    </ol>
  );
}
