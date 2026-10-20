import { useEffect, useState } from "react";
import { runScenario } from "../api";
import { CAR_PARTS, DAMAGE_LABEL, GEAR_OPTIONS } from "../constants";
import { groupDigits, tl } from "../format";
import { toPayload, type VehicleInput } from "../payload";
import type { AnalysisResult, ScenarioResult } from "../types";
import DamageMap from "../components/DamageMap";

interface Row { id: number; label: string; input: VehicleInput; result: ScenarioResult }

function describe(base: VehicleInput, next: VehicleInput): string {
  const parts: string[] = [];
  if (next.km !== base.km) parts.push(`${groupDigits(String(next.km))} km`);
  if (next.year !== base.year) parts.push(`${next.year} model`);
  if (next.price !== base.price) parts.push(`ilan ${tl(next.price)}`);
  if (next.gear !== base.gear) parts.push(next.gear || "vites bilinmiyor");
  if (next.packageName !== base.packageName) parts.push(next.packageName || "paket bilinmiyor");
  if (next.agirHasar !== base.agirHasar) parts.push(next.agirHasar ? "ağır hasar kayıtlı" : "ağır hasar yok");
  const changed = CAR_PARTS.filter(([key]) => next.damage[key] !== base.damage[key]);
  if (changed.length) {
    parts.push(changed.slice(0, 3).map(([key, label]) => `${label}: ${DAMAGE_LABEL[next.damage[key]].toLocaleLowerCase("tr-TR")}`).join(", ")
      + (changed.length > 3 ? ` +${changed.length - 3} parça` : ""));
  }
  return parts.join(" · ") || "Değişiklik yok";
}

export default function ScenarioTab({ base, onGoAnalysis, embedded = false, onClose }: {
  base: { input: VehicleInput; result: AnalysisResult } | null;
  onGoAnalysis: () => void;
  embedded?: boolean;
  onClose?: () => void;
}) {
  const Title = embedded ? "h2" : "h1";
  const [draft, setDraft] = useState<VehicleInput | null>(base?.input || null);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { setDraft(base?.input || null); setRows([]); setError(""); }, [base]);

  if (!base || !draft) {
    return (
      <section className="tab-page">
        <div className="tab-head">
          <span className="eyebrow">NE OLURDU?</span>
          <Title>Alternatif senaryolar</Title>
          <p>Km, hasar, paket veya vites farklı olsaydı fiyat nasıl değişirdi? Görmek için önce bir araç analiz edin.</p>
        </div>
        <div className="az-empty sc-empty">
          <h2>Henüz analiz yok</h2>
          <p>Senaryolar, Analiz sayfasında hesapladığınız aracın üzerine kurulur.</p>
          <button type="button" className="primary-button" onClick={onGoAnalysis}>Analiz sayfasına git <span aria-hidden="true">→</span></button>
        </div>
      </section>
    );
  }

  const set = (patch: Partial<VehicleInput>) => setDraft({ ...draft, ...patch });
  const baseValue = base.result.estimate.tahmini_fiyat;
  const v = base.input;

  const presets: [string, () => VehicleInput][] = [
    ["Km +20.000", () => ({ ...v, km: v.km + 20000 })],
    ["Km −20.000", () => ({ ...v, km: Math.max(0, v.km - 20000) })],
    ["1 yıl daha yeni", () => ({ ...v, year: v.year + 1 })],
    ["Hiç hasarsız olsaydı", () => ({ ...v, agirHasar: false, damage: Object.fromEntries(CAR_PARTS.map(([k]) => [k, "original"])) as VehicleInput["damage"] })],
    ["Boyalılar değişen çıksaydı", () => ({ ...v, damage: Object.fromEntries(CAR_PARTS.map(([k]) => [k, ["painted", "local"].includes(v.damage[k]) ? "changed" : v.damage[k]])) as VehicleInput["damage"] })],
    ["Paketi bilmiyorum", () => ({ ...v, packageName: null })],
  ];

  async function calculate(input: VehicleInput) {
    setBusy(true); setError("");
    try {
      const result = await runScenario(toPayload(input));
      setRows((current) => [{ id: Date.now(), label: describe(v, input), input, result }, ...current].slice(0, 6));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Senaryo hesaplanamadı.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`tab-page${embedded ? " is-embedded" : ""}`}>
      <div className="tab-head">
        {onClose && <button type="button" className="sc-close" onClick={onClose} aria-label="Senaryoları kapat">Kapat ✕</button>}
        <span className="eyebrow">NE OLURDU?</span>
        <Title>Alternatif senaryolar</Title>
        <p>{v.year} {v.brand} {v.series} {v.engine}{v.packageName ? ` ${v.packageName}` : ""} için bilgileri değiştirip piyasa değerinin nasıl değiştiğini görün. Senaryolar kredi harcamaz.</p>
      </div>

      <div className="scenario-presets">
        <span>Hızlı senaryolar</span>
        {presets.map(([label, make]) => (
          <button key={label} type="button" disabled={busy} onClick={() => { const next = make(); setDraft(next); void calculate(next); }}>{label}</button>
        ))}
      </div>

      <div className="scenario-layout">
        <div className="scenario-editor">
          <h2 className="tab-subtitle">Kendi senaryonuz</h2>
          <div className="fields-grid two">
            <label className="field"><span>Kilometre</span>
              <input inputMode="numeric" value={groupDigits(String(draft.km))}
                onChange={(e) => set({ km: Number(e.target.value.replace(/\D/g, "") || 0) })} />
            </label>
            <label className="field"><span>Model yılı</span>
              <input type="number" value={draft.year} onChange={(e) => set({ year: Number(e.target.value) || v.year })} />
            </label>
            <label className="field"><span>İlan fiyatı</span>
              <input inputMode="numeric" value={groupDigits(String(draft.price))}
                onChange={(e) => set({ price: Number(e.target.value.replace(/\D/g, "") || 0) })} />
            </label>
            <label className="field"><span>Vites</span>
              <select value={draft.gear} onChange={(e) => set({ gear: e.target.value })}>
                <option value="">Bilinmiyor</option>
                {GEAR_OPTIONS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </label>
            <label className="field"><span>Paket</span>
              <select value={draft.packageName || ""} onChange={(e) => set({ packageName: e.target.value || null })}>
                <option value="">Bilmiyorum</option>
                {draft.packages.map((p) => <option key={p.slug} value={p.name}>{p.name}</option>)}
              </select>
            </label>
          </div>
          <DamageMap damage={draft.damage} onChange={(damage) => set({ damage })}
            agirHasar={draft.agirHasar} onAgirHasarChange={(agirHasar) => set({ agirHasar })} />
          <div className="scenario-actions">
            <button type="button" className="ghost-button" onClick={() => setDraft(v)} disabled={busy}>Analizdeki değerlere dön</button>
            <button type="button" className="primary-button" onClick={() => calculate(draft)} disabled={busy || !draft.km || !draft.price}>
              {busy ? "Hesaplanıyor…" : "Senaryoyu hesapla"} <span>→</span>
            </button>
          </div>
          {error && <p role="alert" className="form-error">{error}</p>}
        </div>

        <div className="scenario-results">
          <h2 className="tab-subtitle">Karşılaştırma</h2>
          <article className="scenario-card base">
            <span className="scenario-tag">Mevcut analiz</span>
            <strong>{tl(baseValue)}</strong>
            <p>{base.result.decision.title}</p>
          </article>
          {rows.length === 0 && <p className="card-empty">Bir hızlı senaryo seçin veya kendi senaryonuzu hesaplayın.</p>}
          {rows.map((row) => {
            const value = row.result.estimate.tahmini_fiyat;
            const diff = value != null && baseValue != null ? value - baseValue : null;
            const tone = diff == null || Math.abs(diff) < 1000 ? "flat" : diff > 0 ? "up" : "down";
            return (
              <article key={row.id} className={`scenario-card ${tone}`}>
                <div className="scenario-card-top">
                  <span className="scenario-tag">{row.label}</span>
                  <button type="button" aria-label="Kaldır" onClick={() => setRows(rows.filter((r) => r.id !== row.id))}>×</button>
                </div>
                <strong>{tl(value)}</strong>
                {diff != null && (
                  <span className="scenario-diff">
                    {tone === "flat" ? "Fark yok" : `${diff > 0 ? "+" : "−"}${tl(Math.abs(diff))}${baseValue ? ` (%${(Math.abs(diff) / baseValue * 100).toLocaleString("tr-TR", { maximumFractionDigits: 1 })})` : ""}`}
                  </span>
                )}
                <p>{row.result.decision.title}
                  {row.result.negotiation.available && <> · Hedef {tl(row.result.negotiation.target_price)}</>}
                </p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
