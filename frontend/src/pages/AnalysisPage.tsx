import { useEffect, useMemo, useRef, useState } from "react";
import { analyze, fetchBilling, lookupListingText, fetchGearDefault, fetchLocations, fetchVehicles } from "../api";
import { ApiError } from "../http";
import { toPayload, type VehicleInput } from "../payload";
import AccountBadge from "../components/AccountBadge";
import ScenarioTab from "./ScenarioTab";
import ProfileTab from "./ProfileTab";
import RegionalTab from "./RegionalTab";
import GuideTab from "./GuideTab";
import PlanLock from "../components/PlanLock";
import AccountMenu from "../components/AccountMenu";
import { PlanChangeContext } from "../planChange";
import {
  CAR_PARTS, CATEGORIES, COLORS, DEFAULT_DAMAGE,
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
  const { user, setBilling } = useAuth();
  const [tab, setTab] = useState<"analysis" | "scenario" | "guide" | "regional" | "profile">("analysis");
  const [base, setBase] = useState<{ input: VehicleInput; result: AnalysisResult } | null>(null);
  const planFeatures = user?.billing?.plan_features || ["analysis"];
  const can = (feature: string) => planFeatures.includes(feature);
  const TAB_FEATURE: Record<string, string> = { scenario: "scenarios", guide: "guide", regional: "regional" };
  const requestPlan = (plan: "pro" | "premium") => { setPendingPlan(plan); setTab("profile"); };
  const [pendingPlan, setPendingPlan] = useState<"pro" | "premium" | null>(null);
  const [autoAnalyze, setAutoAnalyze] = useState(false);
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

  // Plan değişince analiz ekranı sıfırdan başlasın: eski sonuç yeni planın
  // açtığı/kapattığı bölümlerle karışmasın.
  const plan = user?.billing?.plan;
  const firstPlan = useRef<string | undefined>(plan);
  useEffect(() => {
    if (!plan || firstPlan.current === undefined) { firstPlan.current = plan; return; }
    if (firstPlan.current === plan) return;
    firstPlan.current = plan;
    setResult(null); setBase(null); setError(""); setLookupText(""); setLookupNotice("");
    setCategory("otomobil"); setBrandSlug(""); setSeriesSlug(""); setEngineSlug(""); setPackageSlug("");
    setYear(""); setKm(""); setPrice(""); setCity(""); setDistrict("");
    setFuel(""); setGear(""); setColor(""); setDescription(""); setAgirHasar(false);
    setDamage({ ...DEFAULT_DAMAGE });
  }, [plan]);

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
      setAutoAnalyze(!!(selection.engine && data.year && data.km && data.price));
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

  async function onSubmit(event?: React.FormEvent) {
    event?.preventDefault();
    // İl/ilçe BİLEREK zorunlu değil -- bkz. Backend/search/views_b2c.py
    if (!brand || !series || !engine || !year || !km || !price) {
      setError("Lütfen marka, seri, motor, yıl, km ve fiyat alanlarını doldurun.");
      return;
    }
    setSubmitting(true);
    setError("");
    setResult(null);
    try {
      const input: VehicleInput = {
        category: brand.category,
        brand: brand.name, series: series.name, engine: engine.name,
        packageName: pack?.name || null, packages,
        city, district,
        year: Number(year), km: Number(km), price: Number(price),
        fuel, gear, color: color || null,
        description,
        agirHasar,
        damage: { ...damage },
      };
      const data = await analyze(toPayload(input));
      if (data.billing) setBilling(data.billing);
      setBase({ input, result: data });
      setResult(data);
      window.setTimeout(
        () => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }),
        80,
      );
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) fetchBilling().then(setBilling).catch(() => undefined);
      setError(e instanceof Error ? e.message : "Analiz tamamlanamadı.");
    } finally {
      setSubmitting(false);
    }
  }

  // "Metinden doldur" sonrası analiz kendiliğinden başlasın: alanlar state'e
  // yazıldıktan SONRA çalışması gerektiği için effect ile tetikleniyor.
  useEffect(() => {
    if (!autoAnalyze || lookupLoading || submitting) return;
    if (!brand || !series || !engine || !year || !km || !price) return;
    setAutoAnalyze(false);
    void onSubmit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoAnalyze, lookupLoading, submitting, brand?.name, series?.name, engine?.name, year, km, price]);

  return (
    <PlanChangeContext.Provider value={requestPlan}>
      <header className="topbar">
        <button type="button" className="brand-logo" onClick={() => setTab("analysis")} aria-label="Analiz sayfasına git">
          <img src="/autosense-logo-trim.png" alt="AutoSense" />
        </button>
        <nav className="top-nav" aria-label="Bölümler">
          {([
            ["analysis", "Analiz"], ["guide", "Araç Rehberi"], ["regional", "Bölgesel Fırsatlar"],
          ] as const).map(([key, label]) => {
            const locked = !!TAB_FEATURE[key] && !can(TAB_FEATURE[key]);
            const active = tab === key || (key === "analysis" && tab === "scenario");
            return (
              <button key={key} type="button" className={`${active ? "active" : ""}${locked ? " locked" : ""}`}
                aria-current={active ? "page" : undefined} onClick={() => setTab(key)}>
                {label}
                {locked && <em className="tab-lock">PRO</em>}
              </button>
            );
          })}
        </nav>
        <div className="account-nav">
          <AccountBadge onOpen={() => setTab("profile")} />
          <AccountMenu onProfile={() => setTab("profile")} />
        </div>
      </header>

      {(tab === "analysis" || tab === "scenario") && (
        <nav className="tabbar" aria-label="Analiz bölümleri">
          {([["analysis", "Analiz"], ["scenario", "Senaryolar"]] as const).map(([key, label]) => (
            <button key={key} type="button" className={`tab-${key}${tab === key ? " active" : ""}${key === "scenario" && !can("scenarios") ? " locked" : ""}`}
              aria-current={tab === key ? "page" : undefined} onClick={() => setTab(key)}>
              {label}
              {key === "scenario" && !can("scenarios") && <em className="tab-lock">Pro</em>}
            </button>
          ))}
        </nav>
      )}
      {tab === "scenario" && (can("scenarios") ? <ScenarioTab base={base} onGoAnalysis={() => setTab("analysis")} /> : (
        <PlanLock eyebrow="NE OLURDU?" title="Senaryolar" requiredPlan="pro"
          description="Km, hasar, paket veya vites farklı olsaydı piyasa değeri nasıl değişirdi?"
          bullets={["Hızlı senaryolar: km ±20.000, hasarsız, paketi bilmiyorum…", "Kendi senaryonuzu kurun, 6 senaryoyu yan yana kıyaslayın", "Senaryolar kredi harcamaz"]} />
      ))}
      {tab === "guide" && (can("guide") ? <GuideTab /> : (
        <PlanLock eyebrow="ARAÇ REHBERİ" title="Piyasada neler oluyor?" requiredPlan="pro"
          description="En çok talep gören modeller, fiyat trendleri ve modellere özel kronik sorunlar."
          bullets={["En çok talep gören, en hızlı satılan, fiyatı yükselen / düşen modeller", "Model arama ve talep listeleri", "Premium'da: model sayfası, fiyat/satış grafikleri, kronik sorunlar, karşılaştırma"]} />
      ))}
      {tab === "regional" && (can("regional") ? <RegionalTab /> : (
        <PlanLock eyebrow="BÖLGESEL FIRSATLAR" title="Bölgesel fırsatlar" requiredPlan="pro"
          description="Bir şehirde hangi modellerin hangi ilçede şehrin geri kalanına göre daha uygun satıldığını görün."
          bullets={["İlçe bazında en uygun modeller", "İlçe ısı haritası", "Aynı model için ilçe ilçe karşılaştırma", "Premium'da: her fırsatın arkasındaki gerçek ilanlar"]} />
      ))}
      {tab === "profile" && <ProfileTab pendingPlan={pendingPlan} onPendingHandled={() => setPendingPlan(null)} />}
      <div hidden={tab !== "analysis"}>
      <section className="hero">
        <div>
          <span className="eyebrow">İKİNCİ EL ARAÇ ANALİZİ</span>
          <h1>Bu ilan <i>gerçekten</i> uygun mu?</h1>
        </div>
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
          {user?.billing && (
            <p className="credit-hint">
              Her analiz <b>1 kredi</b> harcar · Kalan: <b>{user.billing.total_credits}</b>
              {user.billing.total_credits === 0 && <> · <button type="button" onClick={() => setTab("profile")}>{can("extra_credits") ? "Kredi ekle" : "Planı yükselt"}</button></>}
            </p>
          )}
        </div>
      </form>

      {result ? <Results data={result} /> : (
        <div className="empty-results">
          <span>↓</span>
          <h2>Analiz sonucunuz burada görünecek</h2>
          <p>Formu doldurup “Analizi başlat” butonuna basın.</p>
        </div>
      )}
      </div>

      <footer>
        <div className="footer-inner">
          <div className="footer-brand">
            <div className="footer-logo"><img src="/autosense-logo-trim.png" alt="AutoSense" /></div>
            <p>Analizler mevcut ilan ve fiyat referanslarına dayanır; ekspertiz raporu yerine geçmez.</p>
          </div>
          <div className="footer-contact">
            <strong>İletişim</strong>
            <p>Soru, geri bildirim ve iş birliği için bize yazın:</p>
            <a href="mailto:autosense@gmail.org?subject=AutoSense%20ileti%C5%9Fim">autosense@gmail.org</a>
          </div>
        </div>
        <div className="footer-bottom">© {new Date().getFullYear()} AutoSense</div>
      </footer>
    </PlanChangeContext.Provider>
  );
}
