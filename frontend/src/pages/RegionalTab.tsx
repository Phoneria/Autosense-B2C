import { useEffect, useMemo, useState } from "react";
import { fetchRegional } from "../api";
import { num, tl } from "../format";
import type { PlanLock, RegionalDeal, RegionalOverview } from "../types";
import LockedPanel from "../components/LockedPanel";

const CATEGORY_LABEL: Record<string, string> = {
  otomobil: "Otomobil", "arazi-suv-pick-up": "Arazi / SUV / Pick-up", "minivan-panelvan": "Minivan / Panelvan",
};

function pct(v: number) {
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}%${Math.abs(v).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}`;
}

function tone(v: number) {
  if (v <= -8) return "t-great";
  if (v <= -3) return "t-good";
  if (v < 3) return "t-flat";
  if (v < 8) return "t-bad";
  return "t-worse";
}

/** Bir il-model detayının pop-up'ı: ilan listesi + fiyat/piyasa karşılaştırması. */
function DealModal({ deal, listingsLock, onClose }: { deal: RegionalDeal; listingsLock?: PlanLock; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card deal-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">{deal.city}</span>
            <h2>{deal.model}</h2>
            <p>{CATEGORY_LABEL[deal.category] || deal.category} · Ülkeye göre <b className={tone(deal.diff_pct)}>{pct(deal.diff_pct)}</b></p>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Kapat">×</button>
        </div>
        <div className="modal-kpis">
          <div><span>Medyan fiyat</span><strong>{tl(deal.median_price)}</strong></div>
          <div><span>Ülke geneli medyan</span><strong>{tl(deal.country_median_price)}</strong></div>
          <div><span>Medyan yıl / km</span><strong>{deal.median_year} · {num(deal.median_km)} km</strong></div>
          <div><span>Örneklem</span><strong>{deal.listings} ilan · {deal.dealers} galeri</strong></div>
        </div>
        {listingsLock ? (
          <LockedPanel lock={listingsLock} skeleton="listings" compact
            teaser={`${deal.city} ilindeki ${deal.listings} ${deal.model} ilanı`} />
        ) : (
          <>
            <p className="card-note">{deal.city} ilindeki {deal.model} ilanları, piyasa değerine göre en uygundan başlayarak:</p>
            <div className="deal-listings">
              {deal.top_listings.map((l, i) => (
                <div key={`${l.title}-${i}`} className="deal-listing">
                  <div>
                    <strong>{l.title}</strong>
                    <small>{[l.engine, `${l.year}`, `${num(l.km)} km`, l.color, l.dealer].filter(Boolean).join(" · ")}</small>
                  </div>
                  <div className="deal-listing-price">
                    <b>{tl(l.price)}</b>
                    <span className={l.below_market_pct > 0 ? "below" : "above"}>
                      {l.below_market_pct > 0
                        ? `Piyasanın %${l.below_market_pct.toLocaleString("tr-TR")} altında`
                        : `Piyasanın %${Math.abs(l.below_market_pct).toLocaleString("tr-TR")} üstünde`}
                    </span>
                  </div>
                  {l.url && <a href={l.url} target="_blank" rel="noreferrer">İlana git ↗</a>}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/** "Aracın en uygun olduğu şehirler": marka + model seçilir, şehirler en
 * uygundan (en düşük medyan fiyat) en pahalıya sıralanır. */
function CitiesForModelView({ deals, listingsLock }: { deals: RegionalDeal[]; listingsLock?: PlanLock }) {
  const [brand, setBrand] = useState("");
  const [series, setSeries] = useState("");
  const [openDeal, setOpenDeal] = useState<RegionalDeal | null>(null);

  const brands = useMemo(() => [...new Set(deals.map((d) => d.brand))].sort((a, b) => a.localeCompare(b, "tr")), [deals]);
  const seriesOptions = useMemo(
    () => [...new Set(deals.filter((d) => d.brand === brand).map((d) => d.series))].sort((a, b) => a.localeCompare(b, "tr")),
    [deals, brand],
  );

  const rows = useMemo(() => {
    if (!brand || !series) return [];
    return deals.filter((d) => d.brand === brand && d.series === series)
      .slice().sort((a, b) => a.median_price - b.median_price);
  }, [deals, brand, series]);

  return (
    <div className="model-compare">
      <div className="regional-picker-row">
        <label className="field"><span>Marka</span>
          <select value={brand} onChange={(e) => { setBrand(e.target.value); setSeries(""); }}>
            <option value="">Seçiniz</option>
            {brands.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </label>
        <label className="field"><span>Model</span>
          <select value={series} onChange={(e) => setSeries(e.target.value)} disabled={!brand}>
            <option value="">Seçiniz</option>
            {seriesOptions.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
      </div>

      {brand && series && (
        rows.length ? (
          <div className="city-rank-list">
            {rows.map((r, i) => (
              <button key={r.city} type="button" className="city-rank-row" onClick={() => setOpenDeal(r)}>
                <span className="city-rank-pos">{i + 1}</span>
                <span className="city-rank-city">{r.city}</span>
                <span className="city-rank-price">{tl(r.median_price)}</span>
                <span className={`city-rank-diff ${tone(r.diff_pct)}`}>{pct(r.diff_pct)}</span>
                <small>{r.listings} ilan · {r.dealers} galeri</small>
              </button>
            ))}
          </div>
        ) : <p className="card-empty">Bu model için yeterli il verisi yok.</p>
      )}

      {openDeal && <DealModal deal={openDeal} listingsLock={listingsLock} onClose={() => setOpenDeal(null)} />}
    </div>
  );
}

/** "Şehirdeki en uygun modeller": il seçilir, o ildeki modeller en uygundan
 * (ülkeye göre en avantajlı fiyat oranından) sıralanır. */
function ModelsForCityView({ deals, listingsLock }: { deals: RegionalDeal[]; listingsLock?: PlanLock }) {
  const [city, setCity] = useState("");
  const [openDeal, setOpenDeal] = useState<RegionalDeal | null>(null);

  const cities = useMemo(() => [...new Set(deals.map((d) => d.city))].sort((a, b) => a.localeCompare(b, "tr")), [deals]);
  const rows = useMemo(() => {
    if (!city) return [];
    return deals.filter((d) => d.city === city).slice().sort((a, b) => a.diff_pct - b.diff_pct);
  }, [deals, city]);

  return (
    <div className="model-compare">
      <label className="field"><span>İl</span>
        <select value={city} onChange={(e) => setCity(e.target.value)}>
          <option value="">Seçiniz</option>
          {cities.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>

      {city && (
        rows.length ? (
          <div className="city-rank-list">
            {rows.map((r, i) => (
              <button key={`${r.brand}-${r.series}`} type="button" className="city-rank-row" onClick={() => setOpenDeal(r)}>
                <span className="city-rank-pos">{i + 1}</span>
                <span className="city-rank-city">{r.model}<small>{CATEGORY_LABEL[r.category] || r.category}</small></span>
                <span className="city-rank-price">{tl(r.median_price)}</span>
                <span className={`city-rank-diff ${tone(r.diff_pct)}`}>{pct(r.diff_pct)}</span>
                <small>{r.listings} ilan · {r.dealers} galeri</small>
              </button>
            ))}
          </div>
        ) : <p className="card-empty">Bu il için yeterli model verisi yok.</p>
      )}

      {openDeal && <DealModal deal={openDeal} listingsLock={listingsLock} onClose={() => setOpenDeal(null)} />}
    </div>
  );
}

export default function RegionalTab() {
  const [data, setData] = useState<RegionalOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [view, setView] = useState<"cities" | "models">("cities");

  useEffect(() => {
    fetchRegional().then(setData).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
  }, []);

  return (
    <section className="tab-page">
      <div className="tab-head">
        <span className="eyebrow">BÖLGESEL FIRSATLAR</span>
        <h1>Hangi model hangi ilde daha uygun?</h1>
        <p>Her ilan önce AutoSense ile fiyatlanır; ilin fiyat / piyasa değeri oranı ülkenin geri kalanıyla kıyaslanır. Böylece yaş ve km farkları karşılaştırmayı bozmaz.</p>
      </div>

      {error && <p role="alert" className="form-error">{error}</p>}
      {loading && <p className="card-empty">Bölgesel veriler hazırlanıyor… (ilk açılışta birkaç saniye sürebilir)</p>}

      {data && !loading && (
        <>
          <div className="regional-view">
            <button type="button" className={view === "cities" ? "active" : ""} onClick={() => setView("cities")}>Aracın en uygun olduğu şehirler</button>
            <button type="button" className={view === "models" ? "active" : ""} onClick={() => setView("models")}>Şehirdeki en uygun modeller</button>
          </div>

          {view === "cities"
            ? <CitiesForModelView deals={data.deals} listingsLock={data.listings_lock} />
            : <ModelsForCityView deals={data.deals} listingsLock={data.listings_lock} />}

          <p className="billing-note">
            Veri: {data.snapshot_date} tarihli galeri ilanları. Değerler satış değil ilan fiyatıdır; il, galerinin bulunduğu ildir.
            Bir il-model karşılaştırması için en az {data.thresholds.min_listings} ilan ve {data.thresholds.min_dealers} farklı galeri,
            ülkenin geri kalanında en az {data.thresholds.min_country_listings} ilan gerekir.
          </p>
        </>
      )}
    </section>
  );
}
