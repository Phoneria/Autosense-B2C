import { useEffect, useMemo, useState } from "react";
import { fetchGuide, fetchGuideCompare, fetchGuideModel, fetchVehicleTraits } from "../api";
import { useAuth } from "../auth/AuthProvider";
import { num, tl } from "../format";
import type { GuideCompare, GuideHome, GuideModel, GuideSummary, VehicleTraits as Traits } from "../types";
import VehicleTraits from "../components/VehicleTraits";
import WeeklyChart from "../components/charts/WeeklyChart";
import LockedPanel from "../components/LockedPanel";

const COMPARE_COLORS = ["#ef6c28", "#2f6fe4", "#2e9e5b"];

function pct(v: number | null | undefined) {
  if (v == null) return "—";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}%${Math.abs(v).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}`;
}

function ListCard({ title, hint, color, items, metric, onOpen }: {
  title: string; hint: string; color: string; items: GuideSummary[];
  metric: (m: GuideSummary) => string; onOpen: (key: string) => void;
}) {
  return (
    <article className="guide-list" style={{ ["--c" as string]: color }}>
      <h3>{title}</h3>
      <p>{hint}</p>
      {items.length ? (
        <ol>
          {items.map((m, i) => (
            <li key={m.key}>
              <button type="button" onClick={() => onOpen(m.key)}>
                <span className="guide-rank">{i + 1}</span>
                <span className="guide-name">{m.name}<small>{m.median_price ? tl(m.median_price) : ""}</small></span>
                <b>{metric(m)}</b>
              </button>
            </li>
          ))}
        </ol>
      ) : <p className="card-empty">Yeterli veri yok.</p>}
    </article>
  );
}

function ModelPage({ modelKey, index, onOpen, onBack }: {
  modelKey: string; index: GuideHome["models"]; onOpen: (key: string) => void; onBack: () => void;
}) {
  const { user } = useAuth();
  const [model, setModel] = useState<GuideModel | null>(null);
  const [error, setError] = useState("");
  const [engine, setEngine] = useState("");
  const [traits, setTraits] = useState<Traits | null>(null);
  const [compareKeys, setCompareKeys] = useState<string[]>([]);
  const [compare, setCompare] = useState<GuideCompare | null>(null);
  const [compareMetric, setCompareMetric] = useState<"price_index" | "removed" | "stock">("price_index");

  useEffect(() => {
    setModel(null); setError(""); setTraits(null); setCompareKeys([]); setCompare(null);
    fetchGuideModel(modelKey).then((m) => { setModel(m); setEngine(m.trait_engines[0]?.key || ""); })
      .catch((e: Error) => setError(e.message));
  }, [modelKey, user?.billing?.plan]);

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

  if (error) return <p role="alert" className="form-error">{error}</p>;
  if (!model) return <p className="card-empty">Yükleniyor…</p>;

  if (model.lock) {
    return (
      <div className="guide-model">
        <button type="button" className="ghost-button" onClick={onBack}>← Rehbere dön</button>
        <div className="guide-model-head">
          <div>
            <span className="eyebrow">{model.category.toLocaleUpperCase("tr-TR")}</span>
            <h1>{model.name}</h1>
          </div>
        </div>
        <LockedPanel lock={model.lock} skeleton="charts"
          teaser={`${model.name}: fiyat trendi, satış hızı, stok ve kronik sorunlar`} />
      </div>
    );
  }

  const kpis: [string, string, string][] = [
    ["Aktif ilan", num(model.active), `${model.dealers} galeride`],
    ["Medyan fiyat", tl(model.median_price), "Şu an yayındaki ilanlar"],
    [`Son ${model.window_days} günde satılan*`, num(model.removed_30d), `${num(model.new_30d)} yeni ilan girdi`],
    ["Ortalama satış süresi*", model.median_days_on_market != null ? `${model.median_days_on_market} gün` : "—", "İlanda kalma süresi (medyan)"],
    ["Stok devir hızı", model.turnover_pct != null ? `%${model.turnover_pct.toLocaleString("tr-TR")}` : "—", "30 günde satılan / ortalama stok"],
    ["4 haftalık fiyat değişimi", pct(model.price_change_4w_pct), "Yaş ve km'den arındırılmış"],
  ];

  return (
    <div className="guide-model">
      <button type="button" className="ghost-button" onClick={onBack}>← Rehbere dön</button>
      <div className="guide-model-head">
        <div>
          <span className="eyebrow">{model.category.toLocaleUpperCase("tr-TR")}</span>
          <h1>{model.name}</h1>
        </div>
        <span className={`guide-trend ${(model.price_change_4w_pct || 0) > 0.5 ? "up" : (model.price_change_4w_pct || 0) < -0.5 ? "down" : "flat"}`}>
          Fiyat trendi {pct(model.price_change_4w_pct)}
        </span>
      </div>

      <div className="guide-kpis">
        {kpis.map(([label, value, hint], i) => (
          <div key={label} className={`guide-kpi k${i}`}><span>{label}</span><strong>{value}</strong><small>{hint}</small></div>
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
                series={[{ name: "Fiyat endeksi", color: "#ef6c28", values: model.weekly.price_index }]} />
            </article>
            <article className="guide-chart-card">
              <h3>Medyan ilan fiyatı</h3>
              <p>O hafta yayında olan ilanların medyan fiyatı (araç karışımına göre oynayabilir).</p>
              <WeeklyChart weeks={model.weeks} format={(v) => `${(v / 1000).toLocaleString("tr-TR", { maximumFractionDigits: 0 })} B`}
                series={[{ name: "Medyan fiyat", color: "#7c4ddb", values: model.weekly.median_price }]} />
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
              <div className="regional-view">
                {([["price_index", "Fiyat endeksi"], ["removed", "Satılan"], ["stock", "Stok"]] as const).map(([k, l]) => (
                  <button key={k} type="button" className={compareMetric === k ? "active" : ""} onClick={() => setCompareMetric(k)}>{l}</button>
                ))}
              </div>
            </div>
            {compare ? (
              <>
                <WeeklyChart weeks={compare.weeks} baseline={compareMetric === "price_index" ? 100 : undefined}
                  format={(v) => compareMetric === "price_index" ? v.toLocaleString("tr-TR", { maximumFractionDigits: 1 }) : num(v)}
                  series={compare.models.map((m, i) => ({ name: m.name, color: COMPARE_COLORS[i], values: m.weekly[compareMetric] }))} />
                <div className="guide-compare-table">
                  {compare.models.map((m, i) => (
                    <div key={m.key} style={{ ["--c" as string]: COMPARE_COLORS[i] }}>
                      <strong>{m.name}</strong>
                      <span>Medyan {tl(m.median_price)}</span>
                      <span>{num(m.removed_30d)} satılan · {num(m.active)} aktif</span>
                      <span>Satış süresi {m.median_days_on_market ?? "—"} gün · Fiyat {pct(m.price_change_4w_pct)}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : <p className="card-empty">Karşılaştırmak için bir veya iki model seçin.</p>}
          </div>

          {!!model.similar?.length && (
            <>
              <h2 className="tab-subtitle">Benzer fiyatlı modeller</h2>
              <div className="guide-similar">
                {model.similar.map((m) => (
                  <button key={m.key} type="button" onClick={() => onOpen(m.key)}>
                    <strong>{m.name}</strong><span>{tl(m.median_price)}</span>
                    <small>{num(m.removed_30d)} satılan · fiyat {pct(m.price_change_4w_pct)}</small>
                  </button>
                ))}
              </div>
            </>
          )}
        </>
      ) : null}

      <h2 className="tab-subtitle">Kronik sorunlar, iyi ve kötü yönler</h2>
      {model.trait_engines.length ? (
        <>
          <div className="guide-engines">
            {model.trait_engines.map((e) => (
              <button key={e.key} type="button" className={engine === e.key ? "active" : ""} onClick={() => setEngine(e.key)}>
                {e.label}<small>{e.kronik} kronik · {e.iyi} iyi · {e.kotu} kötü</small>
              </button>
            ))}
          </div>
          {traits ? <VehicleTraits initial={traits} /> : <p className="card-empty">Yükleniyor…</p>}
        </>
      ) : <p className="card-empty">Bu model için henüz derlenmiş kronik / artı-eksi bilgisi yok.</p>}

      <p className="billing-note">
        * Gerçek satış verisi değildir: yayından kalkan galeri ilanları “satılan” sayılır (galeri taranmaya devam ederken ilan kaybolduysa).
        Veri: galeri ilanları, {model.snapshot_date} tarihine kadar.
      </p>
    </div>
  );
}

export default function GuideTab() {
  const [data, setData] = useState<GuideHome | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetchGuide().then(setData).catch((e: Error) => setError(e.message));
  }, []);

  const matches = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("tr-TR");
    if (!data || q.length < 2) return [];
    return data.models.filter((m) => m.name.toLocaleLowerCase("tr-TR").includes(q)).slice(0, 8);
  }, [data, query]);

  const openModel = (key: string) => { setOpen(key); setQuery(""); window.scrollTo({ top: 0, behavior: "smooth" }); };

  return (
    <section className="tab-page">
      {!open && (
        <div className="tab-head">
          <span className="eyebrow">ARAÇ REHBERİ</span>
          <h1>Piyasada neler oluyor?</h1>
          <p>En çok talep gören modeller, fiyat trendleri ve modellere özel kronik sorunlar. Galeri ilanlarının günlük takibinden hesaplanır.</p>
        </div>
      )}

      <div className="guide-search">
        <input value={query} placeholder="Model ara: Egea, Clio, Corolla…" onChange={(e) => setQuery(e.target.value)} />
        {matches.length > 0 && (
          <div className="guide-search-results">
            {matches.map((m) => (
              <button key={m.key} type="button" onClick={() => openModel(m.key)}>
                <strong>{m.name}</strong><small>{num(m.active)} aktif ilan · {num(m.removed_30d)} satılan{m.has_traits ? " · kronik bilgi var" : ""}</small>
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <p role="alert" className="form-error">{error}</p>}
      {!data && !error && <p className="card-empty">Rehber hazırlanıyor…</p>}

      {data && open && <ModelPage modelKey={open} index={data.models} onOpen={openModel} onBack={() => setOpen("")} />}

      {data && !open && (
        <>
          <div className="guide-grid">
            <ListCard title="En çok talep gören" hint={`Son ${data.window_days} günde en çok satılan (tahmini)`} color="#ef6c28"
              items={data.home.most_demand} metric={(m) => `${num(m.removed_30d)} satış`} onOpen={openModel} />
            <ListCard title="En hızlı satılan" hint="İlanda en kısa kalan modeller" color="#2e9e5b"
              items={data.home.fastest} metric={(m) => `${m.median_days_on_market} gün`} onOpen={openModel} />
            <ListCard title="Fiyatı yükselen" hint="Son 4 hafta, yaş/km'den arındırılmış" color="#e0457b"
              items={data.home.rising} metric={(m) => pct(m.price_change_4w_pct)} onOpen={openModel} />
            <ListCard title="Fiyatı düşen" hint="Son 4 hafta, yaş/km'den arındırılmış" color="#2f6fe4"
              items={data.home.falling} metric={(m) => pct(m.price_change_4w_pct)} onOpen={openModel} />
            <ListCard title="En çok ilanı olan" hint="Şu an yayındaki ilan sayısı" color="#7c4ddb"
              items={data.home.most_listed} metric={(m) => `${num(m.active)} ilan`} onOpen={openModel} />
          </div>
          <p className="billing-note">
            “Satılan” gerçek satış verisi değildir; yayından kalkan galeri ilanlarından tahmin edilir. Veri {data.first_date} – {data.snapshot_date}
            arasındaki {data.snapshot_count} günlük taramadan hesaplanır ve yeni veri geldikçe güncellenir.
          </p>
        </>
      )}
    </section>
  );
}
