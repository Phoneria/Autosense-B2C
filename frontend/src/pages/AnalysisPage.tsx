import { useEffect, useMemo, useRef, useState } from "react";
import { analyze, lookupListingText, fetchGearDefault, fetchLocations, fetchVehicles } from "../api";
import {
  CAR_PARTS, CATEGORIES, COLORS, DAMAGE_API_LABEL, DEFAULT_DAMAGE,
  FUEL_OPTIONS, GEAR_OPTIONS, guessFuel,
} from "../constants";
import type { AnalysisResult, DamageState, LocationOption, VehicleBrand } from "../types";
import { groupDigits } from "../format";
import { resolveListingSelection } from "../listingText";
import DamageMap from "../components/DamageMap";
import { useAuth } from "../auth/AuthProvider";
import Results from "../components/Results";

function Field({ label, optional, children }: {
  label: string; optional?: boolean; children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}{optional && <em>Opsiyonel</em>}</span>
      {children}
    </label>
  );
}

export default function AnalysisPage() {
  const { user, logout } = useAuth();
  const [logoutError, setLogoutError] = useState("");
  const [vehicles, setVehicles] = useState<VehicleBrand[]>([]);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [error, setError] = useState("");

  const [category, setCategory] = useState("otomobil");
  const [brandSlug, setBrandSlug] = useState("");
  const [seriesSlug, setSeriesSlug] = useState("");
  const [engineSlug, setEngineSlug] = useState("");
  const [packageSlug, setPackageSlug] = useState("");
  const [year, setYear] = useState("");
  const [km, setKm] = useState("");
  const [price, setPrice] = useState("");
  const [city, setCity] = useState("");
  const [district, setDistrict] = useState("");
  const [fuel, setFuel] = useState("");
  const [gear, setGear] = useState("");
  const [color, setColor] = useState("");
  const [description, setDescription] = useState("");
  const [agirHasar, setAgirHasar] = useState(false);
  const [damage, setDamage] = useState<Record<string, DamageState>>({ ...DEFAULT_DAMAGE });

  const [lookupText, setLookupText] = useState("");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupNotice, setLookupNotice] = useState("");
  const gearOverride = useRef<{ key: string; value: string; fuel: string } | null>(null);

  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchVehicles()
      .then(setVehicles)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoadingOptions(false));
    // İl/ilçe OPSİYONEL -- yüklenemezse form yine de kullanılabilir olmalı,
    // bu yüzden burada hata kullanıcıya blokaj olarak gösterilmiyor.
    fetchLocations().then(setLocations).catch(() => setLocations([]));
  }, []);

  const brands = useMemo(
    () => vehicles.filter((v) => v.category === category),
    [vehicles, category],
  );
  const brand = brands.find((b) => b.slug === brandSlug);
  const series = brand?.series.find((s) => s.slug === seriesSlug);
  const engine = series?.engines.find((e) => e.slug === engineSlug);
  const packages = engine?.variants?.length ? engine.variants : series?.variants || [];
  const pack = packages.find((p) => p.slug === packageSlug);
  const districts = locations.find((l) => l.city === city)?.districts || [];

  // Motor değişince yakıtı tahmin et, vitesi backend'den öğren.
  useEffect(() => {
    const selectionKey = [category, brandSlug, seriesSlug, engineSlug, packageSlug].join("|");
    const override = gearOverride.current;
    if (override && override.key !== selectionKey) gearOverride.current = null;
    if (override?.key === selectionKey) {
      setFuel(override.fuel || (engine && brand && series ? guessFuel(brand.name, series.name, engine.name, pack?.name) : ""));
      setGear(override.value);
      return;
    }
    if (!engine || !brand || !series) { setFuel(""); setGear(""); return; }
    setFuel(guessFuel(brand.name, series.name, engine.name, pack?.name));
    const controller = new AbortController();
    fetchGearDefault(
      {
        category: brand.category, brand: brand.name, series: series.name,
        engine: engine.name, package: pack?.name || null,
      },
      controller.signal,
    ).then((value) => {
      if (!controller.signal.aborted && !gearOverride.current) setGear(GEAR_OPTIONS.includes(value) ? value : "");
    }).catch((error: Error) => { if (!controller.signal.aborted) setError(error.message); });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brand?.name, series?.name, engine?.name, pack?.name]);

  async function onLookupText() {
    if (!lookupText.trim() || lookupLoading) return;
    setLookupLoading(true);
    setLookupNotice("");
    try {
      const data = await lookupListingText(lookupText.trim());
      const selection = resolveListingSelection(data, vehicles);
      gearOverride.current = {
        key: [data.category, selection.brand, selection.series, selection.engine, selection.variant].join("|"),
        fuel: FUEL_OPTIONS.includes(data.fuel) ? data.fuel : "",
        value: GEAR_OPTIONS.includes(data.gear) ? data.gear : "",
      };
      setCategory(data.category);
      setBrandSlug(selection.brand);
      setSeriesSlug(selection.series);
      setEngineSlug(selection.engine);
      setPackageSlug(selection.variant);
      setYear(data.year == null ? "" : String(data.year));
      setKm(data.km == null ? "" : String(data.km));
      setGear(gearOverride.current.value);
      setFuel(gearOverride.current.fuel);
      setAgirHasar(data.agir_hasar);
      const statuses: Record<string, DamageState> = {
        orijinal: "original", lokal_boyali: "local", boyali: "painted", degismis: "changed",
      };
      setDamage(Object.fromEntries(CAR_PARTS.map(([key]) => [key, statuses[data.damage_map[key]] || "original"])));
      setPrice(data.price == null ? "" : String(data.price));
      setCity(data.city || ""); setDistrict(data.district || "");
      setColor(COLORS.includes(data.color) ? data.color : "");
      setDescription(data.description || "");
      setResult(null);
      setError("");
      setLookupNotice([selection.engine
        ? "İlan bilgileri dolduruldu. Analiz öncesinde alanları kontrol edin."
        : "Araç tam eşleştirilemedi. Okunan alanlar dolduruldu; eksikleri elle tamamlayın.",
        ...(data.warnings || []),
      ].join(" "));
    } catch (e) {
      setLookupNotice(e instanceof Error ? e.message : "İlan metni okunamadı.");
    } finally {
      setLookupLoading(false);
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    // İl/ilçe BİLEREK zorunlu değil -- bkz. Backend/search/views_b2c.py
    if (!brand || !series || !engine || !year || !km || !price) {
      setError("Lütfen marka, seri, motor, yıl, km ve fiyat alanlarını doldurun.");
      return;
    }
    setSubmitting(true);
    setError("");
    setResult(null);
    try {
      const data = await analyze({
        category: brand.category,
        brand: brand.name, series: series.name, engine: engine.name,
        package: pack?.name || null,
        city, district,
        year: Number(year), km: Number(km), price: Number(price),
        fuel, gear, color: color || null,
        description,
        agir_hasar: agirHasar,
        damage: CAR_PARTS
          .filter(([key]) => damage[key] !== "original")
          .map(([key, label]) => ({ parca: label, durum: DAMAGE_API_LABEL[damage[key]] })),
      });
      setResult(data);
      window.setTimeout(
        () => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }),
        80,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analiz tamamlanamadı.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="brand-logo"><img src="/autosense-logo.png" alt="AutoSense" /></div>
        <div className="account-nav"><span>{user?.email}</span><button type="button" onClick={() => { setLogoutError(""); void logout().catch((e: Error) => setLogoutError(e.message)); }}>Çıkış yap</button></div>
      </header>

      {logoutError && <p role="alert" className="form-error">{logoutError}</p>}
      <section className="hero">
        <div>
          <span className="eyebrow">İKİNCİ EL ARAÇ ANALİZİ</span>
          <h1>Bu ilan <i>gerçekten</i> uygun mu?</h1>
        </div>
        <p>
          Aracın bilgilerini girin; fiyatı gerçek piyasa verisiyle karşılaştırıp
          pazarlık planınızı, değer kaybınızı ve ilanın açıklamasındaki çelişkileri
          çıkaralım.
        </p>
      </section>

      <form className="analysis-shell" onSubmit={onSubmit}>
        <div className="section-heading">
          <div>
            <span className="step">1</span>
            <div>
              <h2>Araç ve ilan bilgileri</h2>
              <p>İl ve ilçe opsiyoneldir — seçerseniz bölgesel karşılaştırma da yapılır</p>
            </div>
          </div>
        </div>

        <div className="listing-autofill">
          <Field label="İlan metninden otomatik doldur" optional>
            <textarea value={lookupText} maxLength={500000} disabled={lookupLoading}
              onChange={(e) => { setLookupText(e.target.value); setLookupNotice(""); }}
              placeholder="arabam.com veya sahibinden.com ilan sayfasının tamamını kopyalayıp buraya yapıştırın." />
          </Field>
          <button type="button" className="primary-button" onClick={onLookupText}
            disabled={lookupLoading || loadingOptions || !vehicles.length || !lookupText.trim() || submitting}>
            {lookupLoading ? "Metin okunuyor…" : "Metinden doldur"}
          </button>
          {lookupNotice && <p role="status">{lookupNotice}</p>}
        </div>
        <fieldset className="vehicle-fields" disabled={lookupLoading}>
        <div className="form-grid">
          <div className="vehicle-form">
            <div className="fields-grid three">
              <Field label="Kategori">
                <select value={category} onChange={(e) => {
                  setCategory(e.target.value);
                  setBrandSlug(""); setSeriesSlug(""); setEngineSlug(""); setPackageSlug("");
                }}>
                  {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </Field>
              <Field label="Marka">
                <select
                  value={brandSlug}
                  disabled={loadingOptions}
                  onChange={(e) => { setBrandSlug(e.target.value); setSeriesSlug(""); setEngineSlug(""); setPackageSlug(""); }}
                >
                  <option value="">{loadingOptions ? "Yükleniyor…" : "Seçiniz"}</option>
                  {brands.map((b) => <option key={b.slug} value={b.slug}>{b.name}</option>)}
                </select>
              </Field>
              <Field label="Seri">
                <select
                  value={seriesSlug}
                  disabled={!brand}
                  onChange={(e) => { setSeriesSlug(e.target.value); setEngineSlug(""); setPackageSlug(""); }}
                >
                  <option value="">Seçiniz</option>
                  {brand?.series.map((s) => <option key={s.slug} value={s.slug}>{s.name}</option>)}
                </select>
              </Field>
            </div>

            <div className="fields-grid two">
              <Field label="Motor">
                <select value={engineSlug} disabled={!series}
                        onChange={(e) => { setEngineSlug(e.target.value); setPackageSlug(""); }}>
                  <option value="">Seçiniz</option>
                  {series?.engines.map((e) => <option key={e.slug} value={e.slug}>{e.name}</option>)}
                </select>
              </Field>
              <Field label="Paket" optional>
                <select value={packageSlug} disabled={!packages.length}
                        onChange={(e) => setPackageSlug(e.target.value)}>
                  <option value="">Seçiniz</option>
                  {packages.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
                </select>
              </Field>
            </div>

            <div className="fields-grid three">
              <Field label="Model yılı">
                <input type="number" inputMode="numeric" min={1950} max={new Date().getFullYear() + 1}
                       value={year} placeholder="2019" onChange={(e) => setYear(e.target.value)} />
              </Field>
              <Field label="Kilometre">
                <div className="input-unit">
                  <input inputMode="numeric" value={groupDigits(km)} placeholder="120.000"
                         onChange={(e) => setKm(e.target.value.replace(/\D/g, ""))} />
                  <span>km</span>
                </div>
              </Field>
              <Field label="İlan fiyatı">
                <div className="input-unit">
                  <input inputMode="numeric" value={groupDigits(price)} placeholder="850.000"
                         onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))} />
                  <span>TL</span>
                </div>
              </Field>
            </div>

            <div className="fields-grid three">
              <Field label="İl" optional>
                <select value={city} onChange={(e) => { setCity(e.target.value); setDistrict(""); }}>
                  <option value="">{locations.length ? "Seçiniz" : "Yüklenemedi"}</option>
                  {locations.map((l) => <option key={l.city} value={l.city}>{l.city}</option>)}
                </select>
              </Field>
              <Field label="İlçe" optional>
                <select value={district} disabled={!districts.length}
                        onChange={(e) => setDistrict(e.target.value)}>
                  <option value="">Seçiniz</option>
                  {districts.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </Field>
              <Field label="Renk" optional>
                <select value={color} onChange={(e) => setColor(e.target.value)}>
                  <option value="">Seçiniz</option>
                  {COLORS.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Field>
            </div>

            <div className="fields-grid two">
              <Field label="Yakıt" optional>
                <select value={fuel} onChange={(e) => setFuel(e.target.value)}>
                  <option value="">Seçiniz</option>
                  {FUEL_OPTIONS.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </Field>
              <Field label="Vites" optional>
                <select value={gear} onChange={(e) => setGear(e.target.value)}>
                  <option value="">Seçiniz</option>
                  {GEAR_OPTIONS.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              </Field>
            </div>

            <div className="fields-grid">
              <Field label="İlan açıklaması" optional>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="İlandaki açıklama metnini buraya yapıştırın. Metindeki iddiaları girdiğiniz araç bilgileriyle karşılaştırıp çelişkileri işaretlerim."
                />
              </Field>
            </div>
          </div>

          <DamageMap
            damage={damage} onChange={setDamage}
            agirHasar={agirHasar} onAgirHasarChange={setAgirHasar}
          />
        </div>

        </fieldset>

        {error && <p role="alert" className="form-error">{error}</p>}

        <div className="submit-row">
          <button type="submit" className="primary-button" disabled={submitting || lookupLoading}>
            {submitting ? "Analiz ediliyor…" : "Analizi başlat"}
            <span>→</span>
          </button>
        </div>
      </form>

      {result ? <Results data={result} /> : (
        <div className="empty-results">
          <span>↓</span>
          <h2>Analiz sonucunuz burada görünecek</h2>
          <p>Formu doldurup “Analizi başlat” butonuna basın.</p>
        </div>
      )}

      <footer>
        <div className="footer-logo"><img src="/autosense-logo.png" alt="AutoSense" /></div>
        <p>Analizler mevcut ilan ve fiyat referanslarına dayanır.</p>
      </footer>
    </>
  );
}
