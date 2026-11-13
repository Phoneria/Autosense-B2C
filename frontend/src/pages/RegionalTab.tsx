import React, { useEffect, useMemo, useState } from "react";
import { fetchRegional } from "../api";
import { num, tl } from "../format";
import type { PlanLock, RegionalDeal, RegionalOverview } from "../types";
import LockedPanel from "../components/LockedPanel";
import { useDialogFocus } from "../components/useDialogFocus";

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

/** Fark yönü: alıcı açısından ucuz = olumlu, pahalı = olumsuz; ±%3 içi nötr (tone() ile aynı eşik). */
function verdict(v: number) {
  return v <= -3 ? "Ülkeden ucuz" : v < 3 ? "Ülkeyle benzer" : "Ülkeden pahalı";
}

function longDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

/** Fark hücresi: değer + yön etiketi + sıfır çizgisi etrafında ince çubuk. */
function DiffCell({ v, scale }: { v: number; scale: number }) {
  const w = Math.min(50, (Math.abs(v) / Math.max(1, scale)) * 50);
  return (
    <span className={`rg-delta ${tone(v)}`}>
      <span className="rg-delta-bar" aria-hidden="true">
        <i style={v < 0 ? { right: "50%", width: `${w}%` } : { left: "50%", width: `${w}%` }} />
      </span>
      <span className="rg-delta-text"><b>{pct(v)}</b><small>{verdict(v)}</small></span>
    </span>
  );
}

/** Bir il-model detayının pop-up'ı: ilan listesi + fiyat/piyasa karşılaştırması. */
function DealModal({ deal, listingsLock, onClose }: { deal: RegionalDeal; listingsLock?: PlanLock; onClose: () => void }) {
  const ref = useDialogFocus<HTMLDivElement>(onClose);
  const titleId = "rg-modal-title";
  const v = deal.diff_pct;
  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div ref={ref} className="modal-card deal-modal rg-modal" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">{deal.city.toLocaleUpperCase("tr-TR")} · {(CATEGORY_LABEL[deal.category] || deal.category).toLocaleUpperCase("tr-TR")}</span>
            <h2 id={titleId}>{deal.model}</h2>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Kapat" data-autofocus>×</button>
        </div>
        <div className={`rg-modal-verdict ${tone(v)}`}>
          <strong>{pct(v)}</strong>
          <p>
            {Math.abs(v) < 3
              ? <>{deal.city} ilinde ilan fiyatı / piyasa değeri oranı ülkenin geri kalanıyla <b>benzer</b>.</>
              : <>{deal.city} ilinde ilan fiyatı / piyasa değeri oranı ülkenin geri kalanından <b>%{Math.abs(v).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} {v < 0 ? "düşük" : "yüksek"}</b>.</>}
            {" "}Yaş ve km farkları bu oranda dengelenir.
          </p>
        </div>
        <dl className="modal-kpis rg-kpis">
          <div><dt>İldeki medyan ilan fiyatı</dt><dd>{tl(deal.median_price)}</dd></div>
          <div><dt>Ülkenin geri kalanında medyan ilan fiyatı</dt><dd>{tl(deal.country_median_price)}</dd></div>
          <div><dt>İldeki en düşük ilan</dt><dd>{tl(deal.min_price)}</dd></div>
          <div><dt>Medyan yıl / km</dt><dd>{deal.median_year} · {num(deal.median_km)} km</dd></div>
          <div className="rg-kpi-wide"><dt>Örneklem</dt><dd>{num(deal.listings)} ilan · {num(deal.dealers)} galeri <small>(ülkenin geri kalanı: {num(deal.country_listings)} ilan)</small></dd></div>
        </dl>
        {listingsLock ? (
          <LockedPanel lock={listingsLock} skeleton="listings" compact
            teaser={`${deal.city} ilindeki ${deal.listings} ${deal.model} ilanı`} />
        ) : deal.top_listings.length ? (
          <>
            <h3 className="rg-modal-sub">İldeki ilanlar <span>piyasa değerine göre en uygundan başlayarak</span></h3>
            <ul className="deal-listings rg-listings">
              {deal.top_listings.map((l, i) => (
                <li key={`${l.title}-${i}`} className="deal-listing">
                  <div>
                    <strong>{l.title}</strong>
                    <small>{[l.engine, `${l.year}`, `${num(l.km)} km`, l.color, l.dealer, l.post_age_days != null ? `${l.post_age_days} gündür yayında` : null].filter(Boolean).join(" · ")}</small>
                  </div>
                  <div className="deal-listing-price">
                    <b>{tl(l.price)}</b>
                    <span className={l.below_market_pct > 0 ? "below" : "above"}>
                      <i aria-hidden="true">{l.below_market_pct > 0 ? "▼" : "▲"}</i>
                      {l.below_market_pct > 0
                        ? ` Piyasanın %${l.below_market_pct.toLocaleString("tr-TR")} altında`
                        : ` Piyasanın %${Math.abs(l.below_market_pct).toLocaleString("tr-TR")} üstünde`}
                    </span>
                  </div>
                  {l.url && <a href={l.url} target="_blank" rel="noreferrer">İlana git <span aria-hidden="true">↗</span><span className="sr-only"> (yeni sekmede açılır)</span></a>}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="gd-empty-note">Bu il için gösterilecek ilan bulunmuyor.</p>
        )}
        <p className="rg-modal-foot">Fiyatlar ilan fiyatıdır; gerçekleşmiş satış fiyatı değildir. Piyasa değeri AutoSense tahminidir.</p>
      </div>
    </div>
  );
}

/** İl-model satırları tablosu. Sıralama çağıran görünümde yapılır; burada değişmez. */
function DealTable({ rows, nameLabel, name, caption, onOpen }: {
  rows: RegionalDeal[]; nameLabel: string; name: (r: RegionalDeal) => React.ReactNode; caption: string; onOpen: (r: RegionalDeal) => void;
}) {
  const scale = Math.max(8, ...rows.map((r) => Math.abs(r.diff_pct)));
  return (
    <div className="gd-table-wrap">
      <table className="gd-table rg-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="gd-rank">#</th>
            <th scope="col" className="gd-model">{nameLabel}</th>
            <th scope="col" className="num">Medyan ilan fiyatı</th>
            <th scope="col" className="rg-diff-col" title="İldeki ilanların fiyat / piyasa değeri oranının ülkenin geri kalanına göre farkı">Ülkeye göre fark</th>
            <th scope="col" className="num">Örneklem</th>
            <th scope="col" className="gd-go"><span className="sr-only">Ayrıntı</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.city}-${r.brand}-${r.series}`} className="gd-row" style={{ "--i": Math.min(i, 24) } as React.CSSProperties} onClick={(e) => { if (!(e.target as HTMLElement).closest("button")) onOpen(r); }}>
              <td className="gd-rank">{i + 1}</td>
              <th scope="row" className="gd-model"><button type="button" onClick={() => onOpen(r)}>{name(r)}<span className="sr-only">, ayrıntıyı aç</span></button></th>
              <td className="num" data-label="Medyan ilan fiyatı">{tl(r.median_price)}</td>
              <td className="rg-diff-col" data-label="Ülkeye göre fark"><DiffCell v={r.diff_pct} scale={scale} /></td>
              <td className="num rg-sample" data-label="Örneklem">{num(r.listings)} ilan · {num(r.dealers)} galeri</td>
              <td className="gd-go" aria-hidden="true">›</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Prompt({ title, text }: { title: string; text: string }) {
  return <div className="gd-state rg-prompt"><strong>{title}</strong><p>{text}</p></div>;
}

/** "Aracın en uygun olduğu şehirler": marka + model seçilir, şehirler en
 * uygundan (en düşük medyan fiyat) en pahalıya sıralanır. */
function CitiesForModelView({ deals, listingsLock, need }: { deals: RegionalDeal[]; listingsLock?: PlanLock; need: string }) {
  const [brand, setBrand] = useState("");
  const [series, setSeries] = useState("");
  const [openDeal, setOpenDeal] = useState<RegionalDeal | null>(null);

  const brands = useMemo(() => [...new Set(deals.map((d) => d.brand))].sort((a, b) => a.localeCompare(b, "tr")), [deals]);
  const seriesOptions = useMemo(
    () => [...new Set(deals.filter((d) => d.brand === brand).map((d) => d.series))].sort((a, b) => a.localeCompare(b, "tr")),
    [deals, brand],
  );
  const cityCount = (s: string) => deals.filter((d) => d.brand === brand && d.series === s).length;
  const modelCount = (b: string) => new Set(deals.filter((d) => d.brand === b).map((d) => d.series)).size;

  const rows = useMemo(() => {
    if (!brand || !series) return [];
    return deals.filter((d) => d.brand === brand && d.series === series)
      .slice().sort((a, b) => a.median_price - b.median_price);
  }, [deals, brand, series]);

  return (
    <div className="model-compare">
      <div className="regional-picker-row rg-pickers">
        <label className="field"><span>Marka</span>
          <select aria-label="Marka" value={brand} onChange={(e) => { setBrand(e.target.value); setSeries(""); }}>
            <option value="">Seçiniz ({brands.length} marka)</option>
            {brands.map((b) => <option key={b} value={b}>{b} · {modelCount(b)} model</option>)}
          </select>
        </label>
        <label className="field"><span>Model</span>
          <select aria-label="Model" value={series} onChange={(e) => setSeries(e.target.value)} disabled={!brand}>
            <option value="">{brand ? "Seçiniz" : "Önce marka seçin"}</option>
            {seriesOptions.map((s) => <option key={s} value={s}>{s} · {cityCount(s)} il</option>)}
          </select>
        </label>
      </div>

      {!(brand && series) ? (
        <Prompt title="Marka ve model seçin" text="Seçtiğiniz modelin yeterli ilanı olan illeri, medyan ilan fiyatına göre düşükten yükseğe sıralarız." />
      ) : rows.length ? (
        <>
          <p className="rg-summary" role="status">
            <b>{brand} {series}</b> için <b>{rows.length} ilde</b> karşılaştırma yapılabildi. Sıralama: medyan ilan fiyatı, düşükten yükseğe.
            Listede olmayan illerde yeterli ilan yok ({need}); bu, o ilin pahalı olduğu anlamına gelmez.
          </p>
          <DealTable rows={rows} nameLabel="İl" name={(r) => r.city} onOpen={setOpenDeal}
            caption={`${brand} ${series}: il bazında medyan ilan fiyatı ve ülkeye göre fark`} />
        </>
      ) : <Prompt title="Yeterli il verisi yok" text={`Bu model için hiçbir ilde karşılaştırma eşiği (${need}) karşılanmıyor.`} />}

      {openDeal && <DealModal deal={openDeal} listingsLock={listingsLock} onClose={() => setOpenDeal(null)} />}
    </div>
  );
}

/** "Şehirdeki en uygun modeller": il seçilir, o ildeki modeller en uygundan
 * (ülkeye göre en avantajlı fiyat oranından) sıralanır. */
function ModelsForCityView({ deals, listingsLock, need }: { deals: RegionalDeal[]; listingsLock?: PlanLock; need: string }) {
  const [city, setCity] = useState("");
  const [openDeal, setOpenDeal] = useState<RegionalDeal | null>(null);

  const cities = useMemo(() => [...new Set(deals.map((d) => d.city))].sort((a, b) => a.localeCompare(b, "tr")), [deals]);
  const modelCount = (c: string) => deals.filter((d) => d.city === c).length;
  const rows = useMemo(() => {
    if (!city) return [];
    return deals.filter((d) => d.city === city).slice().sort((a, b) => a.diff_pct - b.diff_pct);
  }, [deals, city]);
  const cheaper = rows.filter((r) => r.diff_pct <= -3).length;

  return (
    <div className="model-compare">
      <label className="field rg-single"><span>İl</span>
        <select aria-label="İl" value={city} onChange={(e) => setCity(e.target.value)}>
          <option value="">Seçiniz ({cities.length} il)</option>
          {cities.map((c) => <option key={c} value={c}>{c} · {modelCount(c)} model</option>)}
        </select>
      </label>

      {!city ? (
        <Prompt title="Bir il seçin" text="O ildeki modelleri, ülkenin geri kalanına göre en avantajlı fiyat oranından başlayarak sıralarız." />
      ) : rows.length ? (
        <>
          <p className="rg-summary" role="status">
            <b>{city}</b> ilinde <b>{rows.length} model</b> karşılaştırılabildi; <b>{cheaper}</b> tanesi ülkeden belirgin ucuz (en az %3).
            Sıralama: ülkeye göre fark, en avantajlıdan. Listede olmayan modellerde yeterli ilan yok ({need}).
          </p>
          <DealTable rows={rows} nameLabel="Model" onOpen={setOpenDeal}
            caption={`${city}: model bazında ülkeye göre fiyat farkı`}
            name={(r) => <>{r.model}<small>{CATEGORY_LABEL[r.category] || r.category}</small></>} />
        </>
      ) : <Prompt title="Yeterli model verisi yok" text={`Bu ilde hiçbir model için karşılaştırma eşiği (${need}) karşılanmıyor.`} />}

      {openDeal && <DealModal deal={openDeal} listingsLock={listingsLock} onClose={() => setOpenDeal(null)} />}
    </div>
  );
}

const VIEWS = [
  { key: "cities", title: "Aracın en uygun olduğu şehirler", hint: "Bir model seçin, hangi ilde daha uygun fiyatla ilan verildiğini görün." },
  { key: "models", title: "Şehirdeki en uygun modeller", hint: "Bir il seçin, o ilde ülkeye göre avantajlı fiyatlanan modelleri görün." },
] as const;

export default function RegionalTab() {
  const [data, setData] = useState<RegionalOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [view, setView] = useState<"cities" | "models">("cities");

  useEffect(() => {
    setLoading(true); setError("");
    fetchRegional().then(setData).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
  }, [attempt]);

  const need = data ? `en az ${data.thresholds.min_listings} ilan ve ${data.thresholds.min_dealers} galeri` : "";

  return (
    <section className="tab-page rg-page">
      <div className="tab-head">
        <span className="eyebrow">BÖLGESEL FIRSATLAR</span>
        <h1>Hangi model hangi ilde <span className="hl">daha uygun?</span></h1>
        <p>Her ilan önce AutoSense ile fiyatlanır; ilin fiyat / piyasa değeri oranı ülkenin geri kalanıyla kıyaslanır. Böylece yaş ve km farkları karşılaştırmayı bozmaz.</p>
        {data && (
          <dl className="gd-coverage">
            <div><dt>Veri tarihi</dt><dd>{longDate(data.snapshot_date)}</dd></div>
            {data.priced_listings != null && <div><dt>Fiyatlanmış ilan</dt><dd>{num(data.priced_listings)}</dd></div>}
            <div><dt>Karşılaştırma eşiği</dt><dd>İlde ≥{data.thresholds.min_listings} ilan, ≥{data.thresholds.min_dealers} galeri</dd></div>
            <div><dt>Fiyat türü</dt><dd>İlan fiyatı</dd></div>
          </dl>
        )}
      </div>

      {error && (
        <div className="gd-state is-error" role="alert">
          <strong>Bölgesel veriler yüklenemedi</strong>
          <p>{error}</p>
          <button type="button" className="gd-retry" onClick={() => setAttempt((n) => n + 1)}>Tekrar dene</button>
        </div>
      )}
      {loading && (
        <div className="rg-loading" aria-busy="true">
          <p role="status">Bölgesel veriler hazırlanıyor… (ilk açılışta birkaç saniye sürebilir)</p>
          <div className="gd-skeleton" aria-hidden="true">{Array.from({ length: 4 }, (_, i) => <div key={i}><span /><span /><span /><span /></div>)}</div>
        </div>
      )}

      {data && !loading && (
        <>
          <div className="regional-view as-segmented rg-modes" role="group" aria-label="Görünüm">
            {VIEWS.map((v) => (
              <button key={v.key} type="button" aria-pressed={view === v.key} className={view === v.key ? "active" : ""} onClick={() => setView(v.key)}>{v.title}</button>
            ))}
          </div>
          <p className="rg-mode-hint">{VIEWS.find((v) => v.key === view)?.hint}</p>

          {view === "cities"
            ? <CitiesForModelView deals={data.deals} listingsLock={data.listings_lock} need={need} />
            : <ModelsForCityView deals={data.deals} listingsLock={data.listings_lock} need={need} />}

          <dl className="gd-glossary">
            <div><dt>Ülkeye göre fark</dt><dd>İldeki ilanların fiyat / piyasa değeri oranının, ülkenin geri kalanındaki orana göre farkı. Negatif değer ilde daha uygun fiyat demektir; ±%3 içi benzer kabul edilir.</dd></div>
            <div><dt>Örneklem ve eşik</dt><dd>Bir il-model karşılaştırması için ilde {need}, ülkenin geri kalanında en az {data.thresholds.min_country_listings} ilan gerekir. Eşiği karşılamayan il ve modeller listelenmez.</dd></div>
            <div><dt>Veri</dt><dd>{longDate(data.snapshot_date)} tarihli galeri ilanları. Değerler satış değil ilan fiyatıdır; il, galerinin bulunduğu ildir.</dd></div>
          </dl>
        </>
      )}
    </section>
  );
}
