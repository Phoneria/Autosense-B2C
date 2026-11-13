import { useEffect, useState } from "react";
import { calculateCost } from "../api";
import { groupDigits, tl } from "../format";
import type { VehicleInput } from "../payload";
import type { AnalysisResult, CostResult } from "../types";

const FUEL_MAP: Record<string, string> = { Benzin: "benzin", Dizel: "dizel", "LPG & Benzin": "lpg", Hibrit: "hibrit", Elektrik: "elektrik" };
const FUELS: [string, string][] = [["", "Motordan tahmin et"], ["benzin", "Benzin"], ["dizel", "Dizel"], ["lpg", "LPG"], ["hibrit", "Hibrit"], ["elektrik", "Elektrik"]];

type Form = Record<string, string>;
const EMPTY: Form = {
  engine: "", year: "", vehicle_value: "", annual_km: "15000", fuel: "", consumption: "", unit_price: "",
  kasko_tl: "", traffic_tl: "", maintenance_tl: "", parking_monthly_tl: "", toll_monthly_tl: "",
  tires_tl: "", inspection_tl: "", other_tl: "", loan_monthly_tl: "",
};

function MoneyField({ label, hint, value, onChange, unit = "TL" }: {
  label: string; hint?: string; value: string; onChange: (v: string) => void; unit?: string;
}) {
  return (
    <label className="field">
      <span>{label}{hint && <em>{hint}</em>}</span>
      <div className="input-unit">
        <input inputMode="decimal" value={unit === "TL" || unit === "km" ? groupDigits(value) : value} placeholder="Boş = tahmin"
          onChange={(e) => onChange(unit === "TL" || unit === "km" ? e.target.value.replace(/\D/g, "") : e.target.value.replace(/[^\d.,]/g, "").replace(",", "."))} />
        <span>{unit}</span>
      </div>
    </label>
  );
}

export default function CostTab({ base }: { base: { input: VehicleInput; result: AnalysisResult } | null }) {
  const [form, setForm] = useState<Form>(EMPTY);
  const [result, setResult] = useState<CostResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!base) return;
    const value = base.result.estimate.tahmini_fiyat || base.input.price;
    setForm((f) => ({ ...f, engine: base.input.engine, year: String(base.input.year), vehicle_value: String(value), fuel: FUEL_MAP[base.input.fuel] || "" }));
    setResult(null);
  }, [base]);

  const set = (key: string) => (v: string) => setForm((f) => ({ ...f, [key]: v }));
  const num = (v: string) => (v.trim() === "" ? null : Number(v));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.engine.trim() || !form.year || !form.annual_km) {
      setError("Motor, model yılı ve yıllık km alanlarını doldurun.");
      return;
    }
    setBusy(true); setError("");
    try {
      setResult(await calculateCost({
        engine: form.engine.trim(), year: Number(form.year), annual_km: Number(form.annual_km),
        vehicle_value: num(form.vehicle_value), fuel: form.fuel || null,
        consumption: num(form.consumption), unit_price: num(form.unit_price),
        kasko_tl: num(form.kasko_tl), traffic_tl: num(form.traffic_tl), maintenance_tl: num(form.maintenance_tl),
        parking_monthly_tl: num(form.parking_monthly_tl) || 0, toll_monthly_tl: num(form.toll_monthly_tl) || 0,
        tires_tl: num(form.tires_tl) || 0, inspection_tl: num(form.inspection_tl) || 0,
        other_tl: num(form.other_tl) || 0, loan_monthly_tl: num(form.loan_monthly_tl) || 0,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Maliyet hesaplanamadı.");
    } finally {
      setBusy(false);
    }
  }

  const max = Math.max(1, ...(result?.lines.map((l) => l.yearly_tl) || [1]));

  return (
    <section className="tab-page">
      <div className="tab-head">
        <span className="eyebrow">KİŞİSEL MALİYET</span>
        <h1>Bu araç bana yılda kaça patlar?</h1>
        <p>Kendi kullanımınızı ve tekliflerinizi girin. Boş bıraktığınız kalemler ortalama değerlerle tahmin edilir ve “tahmini” olarak işaretlenir. Hesaplama kredi harcamaz.</p>
      </div>

      <form className="cost-layout" onSubmit={submit}>
        <div className="cost-form">
          <h2 className="tab-subtitle">Araç</h2>
          <div className="fields-grid three">
            <label className="field"><span>Motor</span>
              <input value={form.engine} placeholder="1.6 TDI" onChange={(e) => set("engine")(e.target.value)} /></label>
            <label className="field"><span>Model yılı</span>
              <input type="number" value={form.year} placeholder="2020" onChange={(e) => set("year")(e.target.value)} /></label>
            <MoneyField label="Araç değeri" value={form.vehicle_value} onChange={set("vehicle_value")} />
          </div>

          <h2 className="tab-subtitle">Kullanımınız</h2>
          <div className="fields-grid three">
            <MoneyField label="Yıllık km" value={form.annual_km} onChange={set("annual_km")} unit="km" />
            <label className="field"><span>Yakıt</span>
              <select value={form.fuel} onChange={(e) => set("fuel")(e.target.value)}>
                {FUELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select></label>
            <MoneyField label="Ortalama tüketim" hint="Opsiyonel" value={form.consumption} onChange={set("consumption")} unit={form.fuel === "elektrik" ? "kWh/100" : "L/100"} />
            <MoneyField label="Yakıt birim fiyatı" hint="Opsiyonel" value={form.unit_price} onChange={set("unit_price")} unit={form.fuel === "elektrik" ? "TL/kWh" : "TL/L"} />
          </div>

          <h2 className="tab-subtitle">Yıllık giderler</h2>
          <div className="fields-grid three">
            <MoneyField label="Kasko teklifi" hint="Yıllık" value={form.kasko_tl} onChange={set("kasko_tl")} />
            <MoneyField label="Trafik sigortası" hint="Yıllık" value={form.traffic_tl} onChange={set("traffic_tl")} />
            <MoneyField label="Bakım" hint="Yıllık" value={form.maintenance_tl} onChange={set("maintenance_tl")} />
            <MoneyField label="Lastik" hint="Yıllık" value={form.tires_tl} onChange={set("tires_tl")} />
            <MoneyField label="Muayene / egzoz" hint="Yıllık" value={form.inspection_tl} onChange={set("inspection_tl")} />
            <MoneyField label="Diğer" hint="Yıllık" value={form.other_tl} onChange={set("other_tl")} />
          </div>

          <h2 className="tab-subtitle">Aylık giderler</h2>
          <div className="fields-grid three">
            <MoneyField label="Otopark" hint="Aylık" value={form.parking_monthly_tl} onChange={set("parking_monthly_tl")} />
            <MoneyField label="Köprü / otoyol" hint="Aylık" value={form.toll_monthly_tl} onChange={set("toll_monthly_tl")} />
            <MoneyField label="Kredi taksiti" hint="Aylık" value={form.loan_monthly_tl} onChange={set("loan_monthly_tl")} />
          </div>

          {error && <p role="alert" className="form-error">{error}</p>}
          <div className="scenario-actions">
            <button type="submit" className="primary-button" disabled={busy}>{busy ? "Hesaplanıyor…" : "Maliyeti hesapla"} <span>→</span></button>
          </div>
        </div>

        <aside className="cost-result">
          {result ? (
            <>
              <div className="cost-total">
                <span>Yıllık toplam</span>
                <strong>{tl(result.total_yearly_tl)}</strong>
                <div className="cost-sub">
                  <div><span>Aylık</span><b>{tl(result.total_monthly_tl)}</b></div>
                  {result.per_km_tl != null && <div><span>Km başı</span><b>{result.per_km_tl.toLocaleString("tr-TR")} TL</b></div>}
                </div>
              </div>
              <div className="cost-breakdown">
                {result.lines.map((line) => (
                  <div key={line.key} className={`cost-row cost-${line.key}`}>
                    <div className="cost-row-top">
                      <span>{line.label}{line.estimated && <em>tahmini</em>}</span>
                      <strong>{tl(line.yearly_tl)}</strong>
                    </div>
                    <i><b style={{ width: `${(line.yearly_tl / max) * 100}%` }} /></i>
                    {line.note && <small>{line.note}</small>}
                  </div>
                ))}
              </div>
              {result.estimated_count > 0 && (
                <p className="card-note">{result.estimated_count} kalem ortalama değerle tahmin edildi. Kendi teklifinizi girerseniz sonuç netleşir.</p>
              )}
            </>
          ) : (
            <div className="cost-placeholder">
              <h2>Sonuç burada</h2>
              <p>{base ? "Araç bilgileri son analizden dolduruldu. Kullanımınızı girip hesaplayın." : "Araç bilgilerini girin veya önce bir analiz yapın."}</p>
            </div>
          )}
        </aside>
      </form>
    </section>
  );
}
