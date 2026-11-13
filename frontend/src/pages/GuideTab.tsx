import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import { fetchGuide, fetchGuideCompare, fetchGuideModel, fetchVehicleTraits } from "../api";
import { useAuth } from "../auth/AuthProvider";
import { num, tl } from "../format";
import type { GuideCompare, GuideHome, GuideModel, GuideSummary, VehicleTraits as Traits } from "../types";
import VehicleTraits from "../components/VehicleTraits";
import WeeklyChart from "../components/charts/WeeklyChart";
import LockedPanel from "../components/LockedPanel";

// Karşılaştırma serileri: merkezi grafik tokenları (tokens.css --chart-*).
const COMPARE_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)"];

function pct(v: number | null | undefined) {
  if (v == null) return "—";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}%${Math.abs(v).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}`;
}

/** "2026-10-16" → "16 Ekim 2026" */
function longDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

/** Fiyat değişimi: yön oku + metin; renk nötr (yükseliş alıcı için iyi de kötü de olabilir). */
function Change({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="gd-delta is-none">—</span>;
  const dir = value > 0.05 ? "up" : value < -0.05 ? "down" : "flat";
  const word = dir === "up" ? "yükseliş" : dir === "down" ? "düşüş" : "değişim yok";
  return (
    <span className={`gd-delta is-${dir}`} aria-label={`${word} ${pct(value)}`}>
      <i aria-hidden="true">{dir === "up" ? "▲" : dir === "down" ? "▼" : "■"}</i>{pct(value)}
    </span>
  );
}

type ListKey = "most_demand" | "fastest" | "rising" | "falling" | "most_listed";
type SortKey = "rank" | "median_price" | "active" | "removed_30d" | "median_days_on_market" | "price_change_4w_pct";

const SORT_LABEL: Record<SortKey, string> = {
  rank: "Sıra", median_price: "Medyan ilan fiyatı", active: "Aktif ilan", removed_30d: "İlandan kalkan (tahmini)",
  median_days_on_market: "İlanda kalma süresi", price_change_4w_pct: "4 haftalık fiyat değişimi",
};

/** Ana sayfa sıralamaları: her liste backend'in kendi sıralamasıyla gelir.
 *  Sütun başlığına tıklamak yalnızca ekrandaki sırayı değiştirir; "#" her zaman
 *  backend'deki sırayı gösterir. */
/** Benzer modelin fiyatı, incelenen modele göre: "2.600 TL daha ucuz". */
function PriceDiff({ value, base }: { value: number; base: number }) {
  const oran = Math.abs(value) / base * 100;
  if (oran < 0.05) return <em className="gd-diff is-same">aynı seviyede</em>;
  const metin = `${tl(Math.abs(value))} ${value < 0 ? "daha ucuz" : "daha pahalı"}`;
  return <em className={`gd-diff ${value < 0 ? "is-down" : "is-up"}`}>{metin}</em>;
}

function RankingTable({ items, highlight, caption, onOpen }: {
  items: GuideSummary[]; highlight: SortKey; caption: string; onOpen: (key: string) => void;
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "rank", dir: 1 });
  const rows = useMemo(() => {
    const ranked = items.map((m, i) => ({ m, rank: i + 1 }));
    if (sort.key === "rank") return sort.dir === 1 ? ranked : [...ranked].reverse();
    const k = sort.key;
    return [...ranked].sort((a, b) => {
      const av = a.m[k] as number | null, bv = b.m[k] as number | null;
      if (av == null && bv == null) return 0; if (av == null) return 1; if (bv == null) return -1;
      return (av - bv) * sort.dir;
    });
  }, [items, sort]);
  // Anahtar sayaç sütununda listedeki en büyük değere göre ince oran çubuğu
  const barMax = highlight === "removed_30d" || highlight === "active"
    ? Math.max(1, ...items.map((m) => (m[highlight] as number) || 0)) : 0;
  const head = (key: SortKey, label: string, cls = "") => {
    const active = sort.key === key;
    return (
      <th scope="col" className={`${cls}${key === highlight ? " is-key" : ""}`} aria-sort={active ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
        <button type="button" onClick={() => setSort({ key, dir: active ? (sort.dir === 1 ? -1 : 1) : (key === "rank" ? 1 : -1) })}
          aria-label={`${SORT_LABEL[key]} sütununa göre sırala`}>
          {label}<span className="gd-sort" aria-hidden="true">{active ? (sort.dir === 1 ? "↑" : "↓") : "↕"}</span>
        </button>
      </th>
    );
  };
  const keyCls = (k: SortKey) => (highlight === k ? " is-key" : "");
  if (!items.length) {
    return (
      <div className="gd-state">
        <strong>Bu sıralama için yeterli veri yok</strong>
        <p>Liste, yeterli sayıda ilan ve tarama günü biriktiğinde oluşur. Diğer sekmelere göz atabilirsiniz.</p>
      </div>
    );
  }
  return (
    <div className="gd-table-wrap">
      <table className="gd-table gd-rtable">
        <caption className="sr-only">{caption}{sort.key !== "rank" ? ` Ekranda ${SORT_LABEL[sort.key].toLocaleLowerCase("tr-TR")} sütununa göre sıralı.` : ""}</caption>
        <thead>
          <tr>
            {head("rank", "#", "gd-rank")}
            <th scope="col" className="gd-model">Model</th>
            {head("median_price", "Medyan ilan fiyatı", "num")}
            {head("removed_30d", "İlandan kalkan (tahmini)", "num")}
            {head("median_days_on_market", "İlanda kalma", "num")}
            {head("active", "Aktif ilan", "num")}
            {head("price_change_4w_pct", "4 hafta fiyat", "num")}
            <th scope="col" className="gd-go"><span className="sr-only">Ayrıntı</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ m, rank }, i) => (
            <tr key={m.key} className="gd-row" style={{ "--i": Math.min(i, 24) } as CSSProperties} onClick={(e) => { if (!(e.target as HTMLElement).closest("button")) onOpen(m.key); }}>
              <td className="gd-rank">{rank}</td>
              <th scope="row" className="gd-model">
                <button type="button" onClick={() => onOpen(m.key)}>{m.name}<span className="sr-only">, model ayrıntısını aç</span></button>
                <small>{m.category}</small>
              </th>
              <td className={`num${keyCls("median_price")}`} data-label="Medyan ilan fiyatı">{m.median_price ? tl(m.median_price) : "—"}</td>
              <td className={`num${keyCls("removed_30d")}`} data-label="İlandan kalkan (tahmini)">
                {num(m.removed_30d)}
                {barMax > 0 && highlight === "removed_30d" && <i className="gd-bar" aria-hidden="true" style={{ width: `${(m.removed_30d / barMax) * 100}%` }} />}
              </td>
              <td className={`num${keyCls("median_days_on_market")}`} data-label="İlanda kalma">{m.median_days_on_market != null ? `${m.median_days_on_market} gün` : "—"}</td>
              <td className={`num${keyCls("active")}`} data-label="Aktif ilan">
                {num(m.active)}
                {barMax > 0 && highlight === "active" && <i className="gd-bar" aria-hidden="true" style={{ width: `${(m.active / barMax) * 100}%` }} />}
              </td>
              <td className={`num${keyCls("price_change_4w_pct")}`} data-label="4 hafta fiyat"><Change value={m.price_change_4w_pct} /></td>
              <td className="gd-go" aria-hidden="true">›</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkeletonTable() {
  return (
    <div className="gd-skeleton" aria-hidden="true">
      {Array.from({ length: 6 }, (_, i) => <div key={i}><span /><span /><span /><span /></div>)}
    </div>
  );
}

function ModelPage({ modelKey, index, onOpen, onBack }: {
  modelKey: string; index: GuideHome["models"]; onOpen: (key: string) => void; onBack: () => void;
}) {
  const { user } = useAuth();
  const [model, setModel] = useState<GuideModel | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [engine, setEngine] = useState("");
  const [traits, setTraits] = useState<Traits | null>(null);
  const [compareKeys, setCompareKeys] = useState<string[]>([]);
  const [compare, setCompare] = useState<GuideCompare | null>(null);
  const [compareMetric, setCompareMetric] = useState<"price_index" | "removed" | "stock">("price_index");

  useEffect(() => {
    setModel(null); setError(""); setTraits(null); setCompareKeys([]); setCompare(null);
    fetchGuideModel(modelKey).then((m) => { setModel(m); setEngine(m.trait_engines[0]?.key || ""); })
      .catch((e: Error) => setError(e.message));
  }, [modelKey, user?.billing?.plan, attempt]);

  useEffect(() => {
    if (!engine) { setTraits(null); return; }
    const ac = new AbortController();
    fetchVehicleTraits(engine, ac.signal).then(setTraits).catch(() => setTraits(null));
    return () => ac.abort();
  }, [engine]);

  useEffect(() => {
    if (!model?.premium || !compareKeys.length) { setCompare(null); return; }
    fetchGuideCompare([modelKey, ...compareKeys]).then(setCompare).catch(() => setCompare(null));
  }, [model?.premium, modelKey, compareKeys]);

  const back = <button type="button" className="gd-back" onClick={onBack}><span aria-hidden="true">←</span> Rehbere dön</button>;

  if (error) {
    return (
      <div className="guide-model">
        {back}
        <div className="gd-state is-error" role="alert">
          <strong>Model bilgileri yüklenemedi</strong>
          <p>{error}</p>
          <button type="button" className="gd-retry" onClick={() => setAttempt((n) => n + 1)}>Tekrar dene</button>
        </div>
      </div>
    );
  }
  if (!model) {
    return (
      <div className="guide-model" aria-busy="true">
        {back}
        <p className="sr-only" role="status">Model bilgileri yükleniyor…</p>
        <div className="gd-skeleton gd-skeleton-head" aria-hidden="true"><div><span /><span /></div></div>
        <SkeletonTable />
      </div>
    );
  }

  const head = (
    <div className="guide-model-head">
      <div>
        <span className="eyebrow">{model.category.toLocaleUpperCase("tr-TR")}</span>
        <h1>{model.name}</h1>
        {!model.lock && (
          <p className="gd-model-sub">
            {num(model.active)} aktif ilan · {num(model.dealers)} galeri · Veri {longDate(model.snapshot_date)} tarihine kadar · Fiyatlar ilan fiyatıdır
          </p>
        )}
      </div>
    </div>
  );

  if (model.lock) {
    return (
      <div className="guide-model">
        {back}
        {head}
        <LockedPanel lock={model.lock} skeleton="charts"
          teaser={`${model.name}: fiyat trendi, ilandan kalkma hızı, stok ve kronik sorunlar`} />
      </div>
    );
  }

  // Metrikler karar sorusuna göre gruplanır: fiyat (ne kadar), arz (ne kadar seçenek), talep hızı (ne kadar çabuk satılıyor).
  const groups: { title: string; items: { label: string; value: ReactNode; hint: string; est?: boolean }[] }[] = [
    { title: "Fiyat", items: [
      { label: "Medyan ilan fiyatı", value: tl(model.median_price), hint: "Şu an yayındaki ilanlar" },
      { label: "4 haftalık değişim", value: <Change value={model.price_change_4w_pct} />, hint: "Yaş ve km'den arındırılmış" },
    ] },
    { title: "Arz", items: [
      { label: "Aktif ilan", value: num(model.active), hint: `${num(model.dealers)} galeride` },
      { label: `Son ${model.window_days} günde yeni ilan`, value: num(model.new_30d), hint: "Piyasaya giren araç" },
    ] },
    { title: "Talep hızı", items: [
      { label: "İlanda kalma süresi", value: model.median_days_on_market != null ? `${model.median_days_on_market} gün` : "—", hint: "Yayından kalkana kadar (medyan)", est: true },
      { label: `Son ${model.window_days} günde ilandan kalkan`, value: num(model.removed_30d), hint: model.turnover_pct != null ? `Stok devir hızı %${model.turnover_pct.toLocaleString("tr-TR")}` : "Stok devir hızı —", est: true },
    ] },
  ];
  const change = model.price_change_4w_pct;
  const trendText = change == null ? null
    : Math.abs(change) < 0.5 ? `Fiyatlar son 4 haftada yatay seyretti (${pct(change)})`
    : `Fiyatlar son 4 haftada %${Math.abs(change).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} ${change > 0 ? "yükseldi" : "düştü"}`;
  const verdict = [
    trendText,
    model.median_days_on_market != null ? `ilanlar ortalama ${model.median_days_on_market} günde yayından kalkıyor` : null,
    model.median_price != null ? `medyan ilan fiyatı ${tl(model.median_price)}` : null,
  ].filter(Boolean).join("; ");
  const similarKeys = (model.similar || []).map((m) => m.key).filter((k) => index.some((x) => x.key === k)).slice(0, 4);
  const samples = model.weekly?.samples?.filter((n) => n > 0) || [];
  const sampleText = samples.length
    ? `Haftalık örneklem ${num(Math.min(...samples))}–${num(Math.max(...samples))} ilan · ${model.weeks?.length || 0} hafta`
    : null;

  return (
    <div className="guide-model">
      {back}
      {head}

      {verdict && <p className="gd-verdict">{verdict.charAt(0).toLocaleUpperCase("tr-TR") + verdict.slice(1)}.</p>}

      <div className="gd-overview">
        {groups.map((g) => (
          <section key={g.title} className="gd-group" aria-label={g.title}>
            <h3>{g.title}</h3>
            <dl>
              {g.items.map((k) => (
                <div key={k.label}>
                  <dt>{k.label}{k.est && <em className="gd-est" title="Satış verisi değil; yayından kalkan ilanlardan hesaplanır">tahmini</em>}</dt>
                  <dd><strong>{k.value}</strong><small>{k.hint}</small></dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>

      <h2 className="tab-subtitle">Fiyat ve talep</h2>
      {model.premium && model.weekly && model.weeks ? (
        <>
          <div className="guide-charts">
            <article className="guide-chart-card">
              <h3>Fiyat endeksi</h3>
              <p>İlan fiyatının piyasa değerine oranı, ilk hafta = 100. Yaş/km karışımından etkilenmez.</p>
              <WeeklyChart weeks={model.weeks} baseline={100} format={(v) => v.toLocaleString("tr-TR", { maximumFractionDigits: 1 })}
                series={[{ name: "Fiyat endeksi", color: "var(--chart-1)", values: model.weekly.price_index }]} />
              {sampleText && <p className="gd-chart-meta">{sampleText}</p>}
            </article>
            <article className="guide-chart-card">
              <h3>Medyan ilan fiyatı</h3>
              <p>O hafta yayında olan ilanların medyan fiyatı, bin TL (B). Araç karışımına göre oynayabilir.</p>
              <WeeklyChart weeks={model.weeks} format={(v) => `${(v / 1000).toLocaleString("tr-TR", { maximumFractionDigits: 0 })} B`}
                series={[{ name: "Medyan fiyat", color: "var(--chart-2)", values: model.weekly.median_price }]} />
              {sampleText && <p className="gd-chart-meta">{sampleText}</p>}
            </article>
          </div>

          <h2 className="tab-subtitle">Karşılaştır</h2>
          <div className="guide-compare">
            <div className="guide-compare-controls">
              {[0, 1].map((slot) => (
                <label key={slot} className="field"><span>{slot + 2}. model</span>
                  <select value={compareKeys[slot] || ""} onChange={(e) => {
                    const next = [...compareKeys]; next[slot] = e.target.value;
                    setCompareKeys(next.filter(Boolean));
                  }}>
                    <option value="">Seçiniz</option>
                    {index.filter((m) => m.key !== modelKey).map((m) => <option key={m.key} value={m.key}>{m.name}</option>)}
                  </select>
                </label>
              ))}
              <div className="regional-view" role="group" aria-label="Karşılaştırma ölçütü">
                {([["price_index", "Fiyat endeksi"], ["removed", "İlandan kalkan"], ["stock", "Stok"]] as const).map(([k, l]) => (
                  <button key={k} type="button" aria-pressed={compareMetric === k} className={compareMetric === k ? "active" : ""} onClick={() => setCompareMetric(k)}>{l}</button>
                ))}
              </div>
            </div>
            {compare ? (
              <div className="gd-compare-body">
                <WeeklyChart weeks={compare.weeks} baseline={compareMetric === "price_index" ? 100 : undefined}
                  format={(v) => compareMetric === "price_index" ? v.toLocaleString("tr-TR", { maximumFractionDigits: 1 }) : num(v)}
                  series={compare.models.map((m, i) => ({ name: m.name, color: COMPARE_COLORS[i], values: m.weekly[compareMetric] }))} />
                <div className="gd-table-wrap">
                  <table className="gd-ctable">
                    <caption className="sr-only">Karşılaştırılan modellerin özet değerleri</caption>
                    <thead>
                      <tr>
                        <th scope="col">Model</th><th scope="col" className="num">Medyan fiyat</th>
                        <th scope="col" className="num">İlandan kalkan (tahmini)</th><th scope="col" className="num">Aktif</th>
                        <th scope="col" className="num">İlanda kalma</th><th scope="col" className="num">4 hafta fiyat</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compare.models.map((m, i) => (
                        <tr key={m.key}>
                          <th scope="row"><i className="gd-swatch" style={{ background: COMPARE_COLORS[i] }} aria-hidden="true" />{m.name}</th>
                          <td className="num" data-label="Medyan fiyat">{tl(m.median_price)}</td>
                          <td className="num" data-label="İlandan kalkan (tahmini)">{num(m.removed_30d)}</td>
                          <td className="num" data-label="Aktif">{num(m.active)}</td>
                          <td className="num" data-label="İlanda kalma">{m.median_days_on_market != null ? `${m.median_days_on_market} gün` : "—"}</td>
                          <td className="num" data-label="4 hafta fiyat"><Change value={m.price_change_4w_pct} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="gd-compare-empty">
                <p className="gd-empty-note">{model.name} ile yan yana görmek için bir veya iki model seçin.</p>
                {similarKeys.length > 0 && (
                  <div className="gd-quickpick" role="group" aria-label="Hızlı seçim">
                    <span>Benzer fiyatlılar:</span>
                    {similarKeys.map((k) => (
                      <button key={k} type="button" onClick={() => setCompareKeys((cur) => cur.includes(k) ? cur : [...cur, k].slice(-2))}>
                        + {model.similar!.find((m) => m.key === k)!.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {!!model.similar?.length && (
            <>
              <h2 className="tab-subtitle">Benzer fiyatlı modeller</h2>
              <ul className="gd-similar">
                {model.similar.map((m) => (
                  <li key={m.key}>
                    <button type="button" onClick={() => onOpen(m.key)}>
                      <span className="gd-similar-name">{m.name}</span>
                      <span className="gd-similar-price">{tl(m.median_price)}
                        {model.median_price ? <PriceDiff value={m.median_price - model.median_price} base={model.median_price} /> : null}
                      </span>
                      <span className="gd-similar-meta">{num(m.removed_30d)} ilandan kalkan (tahmini) · <Change value={m.price_change_4w_pct} /></span>
                      <span className="gd-go" aria-hidden="true">›</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      ) : null}

      <h2 className="tab-subtitle">Kronik sorunlar, iyi ve kötü yönler</h2>
      {model.trait_engines.length ? (
        <>
          <div className="guide-engines" role="group" aria-label="Motor seçimi">
            {model.trait_engines.map((e) => (
              <button key={e.key} type="button" aria-pressed={engine === e.key} className={engine === e.key ? "active" : ""} onClick={() => setEngine(e.key)}>
                {e.label}<small>{e.kronik} kronik · {e.iyi} iyi · {e.kotu} kötü</small>
              </button>
            ))}
          </div>
          {traits ? <VehicleTraits initial={traits} /> : <p className="card-empty" role="status">Yükleniyor…</p>}
        </>
      ) : <p className="gd-empty-note">Bu model için henüz derlenmiş kronik / artı-eksi bilgisi yok.</p>}

      <p className="billing-note as-method">
        <strong>Tahmini değerler:</strong> “İlandan kalkan” ve buna dayanan ilanda kalma ve stok devir hızı gerçek satış verisi değildir;
        galeri taranmaya devam ederken yayından kalkan ilanları sayar, aracın satıldığı kesin değildir.
        Veri: galeri ilanları, {longDate(model.snapshot_date)} tarihine kadar.
      </p>
    </div>
  );
}

const LIST_INFO: Record<ListKey, { title: string; hint: (days: number) => string; metric: SortKey; basis: string }> = {
  most_demand: { title: "En çok talep gören", metric: "removed_30d", basis: "İlandan kalkan (tahmini), çoktan aza",
    hint: (d) => `Son ${d} günde en çok ilandan kalkan (tahmini) modeller. Yayından kalkan ilan sayısıdır; satış adedi değildir.` },
  fastest: { title: "En kısa sürede ilandan kalkan", metric: "median_days_on_market", basis: "İlanda kalma süresi, kısadan uzuna",
    hint: () => "İlanları yayında en kısa süre kalan modeller (medyan gün). Hızlı kalkma, talebe işaret edebilir." },
  rising: { title: "Fiyatı yükselen", metric: "price_change_4w_pct", basis: "4 haftalık fiyat değişimi, yüksekten düşüğe",
    hint: () => "Son 4 haftada ilan fiyatı en çok yükselen modeller; yaş ve km etkisinden arındırılmış." },
  falling: { title: "Fiyatı düşen", metric: "price_change_4w_pct", basis: "4 haftalık fiyat değişimi, düşükten yükseğe",
    hint: () => "Son 4 haftada ilan fiyatı en çok düşen modeller; yaş ve km etkisinden arındırılmış." },
  most_listed: { title: "En çok ilanı olan", metric: "active", basis: "Aktif ilan sayısı, çoktan aza",
    hint: () => "Şu an yayında en çok galeri ilanı olan modeller." },
};
const LIST_ORDER: ListKey[] = ["most_demand", "fastest", "rising", "falling", "most_listed"];

export default function GuideTab() {
  const [data, setData] = useState<GuideHome | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState("");
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(-1);
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  useEffect(() => {
    setError("");
    fetchGuide().then(setData).catch((e: Error) => setError(e.message));
  }, [attempt]);

  const q = query.trim().toLocaleLowerCase("tr-TR");
  const matches = useMemo(() => {
    if (!data || q.length < 2) return [];
    return data.models.filter((m) => m.name.toLocaleLowerCase("tr-TR").includes(q)).slice(0, 8);
  }, [data, q]);
  useEffect(() => { setActive(-1); }, [q]);

  const [list, setList] = useState<ListKey>("most_demand");
  const current = LIST_INFO[list];
  const openModel = (key: string) => { setOpen(key); setQuery(""); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const onTabKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = LIST_ORDER.indexOf(list);
    const next = e.key === "ArrowRight" ? (i + 1) % LIST_ORDER.length
      : e.key === "ArrowLeft" ? (i - 1 + LIST_ORDER.length) % LIST_ORDER.length
      : e.key === "Home" ? 0 : e.key === "End" ? LIST_ORDER.length - 1 : -1;
    if (next < 0) return;
    e.preventDefault();
    setList(LIST_ORDER[next]);
    tabRefs.current[LIST_ORDER[next]]?.focus();
  };

  const showList = q.length >= 2;
  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" && matches.length) { e.preventDefault(); setActive((a) => (a + 1) % matches.length); }
    else if (e.key === "ArrowUp" && matches.length) { e.preventDefault(); setActive((a) => (a <= 0 ? matches.length - 1 : a - 1)); }
    else if (e.key === "Enter" && matches.length) { e.preventDefault(); openModel(matches[Math.max(0, active)].key); }
    else if (e.key === "Escape") { setQuery(""); }
  };

  return (
    <section className="tab-page gd-page">
      {!open && (
        <div className="tab-head">
          <span className="eyebrow">ARAÇ REHBERİ</span>
          <h1>Piyasada neler oluyor?</h1>
          <p>En çok talep gören modeller, fiyat trendleri ve modellere özel kronik sorunlar. Galeri ilanlarının günlük takibinden hesaplanır.</p>
          {data && (
            <dl className="gd-coverage">
              <div><dt>Veri dönemi</dt><dd>{longDate(data.first_date)} – {longDate(data.snapshot_date)}</dd></div>
              <div><dt>Tarama</dt><dd>{num(data.snapshot_count)} gün</dd></div>
              <div><dt>Hesap penceresi</dt><dd>Son {data.window_days} gün</dd></div>
              <div><dt>Fiyat türü</dt><dd>İlan fiyatı</dd></div>
            </dl>
          )}
        </div>
      )}

      <div className="guide-search gd-search">
        <label htmlFor="gd-search-input" className="sr-only">Model ara</label>
        <input id="gd-search-input" type="search" value={query} role="combobox" autoComplete="off"
          aria-autocomplete="list" aria-expanded={showList} aria-controls="gd-search-list"
          aria-activedescendant={active >= 0 && matches[active] ? `gd-opt-${matches[active].key}` : undefined}
          placeholder="Model ara: Egea, Clio, Corolla…" disabled={!data}
          onChange={(e) => setQuery(e.target.value)} onKeyDown={onSearchKey} />
        {showList && (
          <div className="guide-search-results" id="gd-search-list" role="listbox" aria-label="Arama sonuçları">
            {matches.length ? matches.map((m, i) => (
              <div key={m.key} id={`gd-opt-${m.key}`} role="option" aria-selected={i === active}
                className={i === active ? "is-active" : ""} onMouseDown={(e) => e.preventDefault()} onClick={() => openModel(m.key)}
                onMouseMove={() => { if (active !== i) setActive(i); }}>
                <strong>{m.name}</strong>
                <small>{num(m.active)} aktif ilan · {num(m.removed_30d)} ilandan kalkan (tahmini){m.has_traits ? " · kronik bilgi var" : ""}</small>
              </div>
            )) : (
              <p className="gd-search-empty">“{query.trim()}” ile eşleşen model yok. Farklı bir yazım deneyin.</p>
            )}
          </div>
        )}
        <p className="sr-only" role="status" aria-live="polite">
          {showList ? (matches.length ? `${matches.length} model bulundu. Ok tuşlarıyla seçip Enter'a basın.` : "Eşleşen model yok.") : ""}
        </p>
      </div>

      {error && (
        <div className="gd-state is-error" role="alert">
          <strong>Rehber yüklenemedi</strong>
          <p>{error}</p>
          <button type="button" className="gd-retry" onClick={() => setAttempt((n) => n + 1)}>Tekrar dene</button>
        </div>
      )}
      {!data && !error && (
        <div className="gd-home" aria-busy="true">
          <p className="sr-only" role="status">Rehber hazırlanıyor…</p>
          <SkeletonTable />
        </div>
      )}

      {data && open && <ModelPage modelKey={open} index={data.models} onOpen={openModel} onBack={() => setOpen("")} />}

      {data && !open && (
        <>
          <div className="gd-home">
            <div className="gd-tabs" role="tablist" aria-label="Sıralamalar" onKeyDown={onTabKey}>
              {LIST_ORDER.map((k) => (
                <button key={k} ref={(el) => { tabRefs.current[k] = el; }} type="button" role="tab" id={`gd-tab-${k}`}
                  aria-selected={list === k} tabIndex={list === k ? 0 : -1}
                  aria-controls="gd-panel" className={list === k ? "active" : ""} onClick={() => setList(k)}>
                  {LIST_INFO[k].title}
                </button>
              ))}
            </div>
            <div id="gd-panel" role="tabpanel" aria-labelledby={`gd-tab-${list}`} className="gd-panel">
              <div className="gd-panel-head">
                <p className="gd-panel-hint">{current.hint(data.window_days)}</p>
                <p className="gd-panel-meta">
                  <span>Sıralama: {current.basis}</span>
                  <span>{data.home[list].length} model</span>
                </p>
              </div>
              <RankingTable key={list} items={data.home[list]} highlight={current.metric}
                caption={`${current.title}: ${current.hint(data.window_days)}`} onOpen={openModel} />
            </div>
          </div>
          <dl className="gd-glossary">
            <div><dt>İlandan kalkan (tahmini)</dt><dd>Son {data.window_days} günde yayından kalkan galeri ilanı. Satış verisi değildir; ilanın satıldığı kesin değildir.</dd></div>
            <div><dt>İlanda kalma</dt><dd>İlanın yayından kalkana kadar geçen medyan gün sayısı.</dd></div>
            <div><dt>4 hafta fiyat</dt><dd>Son 4 haftadaki ilan fiyatı değişimi; yaş ve kilometre etkisinden arındırılmış.</dd></div>
            <div><dt>Kapsam</dt><dd>Sıralamalar yalnızca yeterli sayıda aktif ilanı olan modelleri içerir. İlanda kalma süresi, yeterli sayıda ilan yayından kalktığında hesaplanır; aksi halde “—” görünür.</dd></div>
            <div><dt>Veri</dt><dd>{longDate(data.first_date)} – {longDate(data.snapshot_date)} arasındaki {num(data.snapshot_count)} günlük taramadan hesaplanır, yeni veri geldikçe güncellenir.</dd></div>
          </dl>
        </>
      )}
    </section>
  );
}
