import { useEffect, useMemo, useState } from "react";
import type { TraitVehicleOption, VehicleTrait, VehicleTraits as Traits } from "../types";
import { fetchTraitVehicles, fetchVehicleTraits } from "../api";
import { useRequestPlan } from "../planChange";

/**
 * Araca özel kronik arızalar ve artı/eksi yönler.
 *
 * Veri hazır bir veritabanından okunur (data/vehicle_traits.db); bu kartta
 * hesap ya da çıkarım YAPILMAZ, aynı araç her zaman aynı listeyi verir.
 * Her iddianın arkasında açılıp okunmuş bir kaynak vardır ve kaynak linki
 * kullanıcıya gösterilir — doğrulayabilsin diye.
 *
 * Üstteki seçim kutusu analiz edilen araçla açılır ve veritabanındaki BÜTÜN
 * araçları listeler; kullanıcı başka bir araca geçerse o aracın verisi çekilir.
 * Liste 300 araca çıkacağı için markaya göre gruplanır. Analiz edilen araç için
 * veri yoksa kart gizlenmez, boş durumu gösterir — seçim kutusu yine çalışsın diye.
 *
 * Okuma yükünü azaltmak için: üstte özet sayılar, kronik arızalar için kilometre
 * çizelgesi, altta sekmeli tek liste. Liste kaynak sayısına göre (en yaygın önce)
 * sıralanır; ilk 3 satır görünür, ilki açık gelir, gerisi "Tümünü göster" ile açılır.
 */

type TraitTip = "kronik" | "iyi" | "kotu";
const TIPLER: TraitTip[] = ["kronik", "iyi", "kotu"];
const SEKME: Record<TraitTip, { ad: string; ozet: string; not: string }> = {
  kronik: { ad: "Kronik arızalar", ozet: "Kronik arıza", not: "Bu motorda tekrar eden, bilinen sorunlar" },
  iyi: { ad: "İyi yönleri", ozet: "Artı", not: "Sahiplik açısından olumlu bulunanlar" },
  kotu: { ad: "Kötü yönleri", ozet: "Eksi", not: "Arıza değil; maliyet, konfor ve kullanım" },
};

const GUVEN_SIRA: Record<VehicleTrait["guven"], number> = { yuksek: 0, orta: 1, dusuk: 2 };
const GUVEN_KAYNAK: Record<VehicleTrait["guven"], string> = { yuksek: "3+ kaynak", orta: "2 kaynak", dusuk: "Tek kaynak" };
/** Rozet: kronik arızada "ne kadar yaygın", artı/eksilerde "ne kadar çok dile geliyor". */
const ROZET: Record<TraitTip, Record<VehicleTrait["guven"], string>> = {
  kronik: { yuksek: "Yaygın", orta: "Sık", dusuk: "Az" },
  iyi: { yuksek: "Çok bahsedilen", orta: "Bahsedilen", dusuk: "Tek kaynak" },
  kotu: { yuksek: "Çok bahsedilen", orta: "Bahsedilen", dusuk: "Tek kaynak" },
};
const ILK_GORUNEN = 3;

/** Teknik kısaltmalar büyük harf kalsın: "dpf-partikul-filtresi" → "DPF partikul filtresi". */
const KISALTMA = new Set(["dpf", "egr", "abs", "esp", "dsg", "cvt", "lpg", "ecu", "tdi", "tsi", "tce", "edc", "scr", "vvt", "dct", "amt", "obd", "led", "usb"]);
function baslik(etiket: string) {
  const kelimeler = etiket.replace(/[-_]+/g, " ").trim().toLocaleLowerCase("tr-TR").split(/\s+/)
    .map((k) => (KISALTMA.has(k) ? k.toLocaleUpperCase("en-US") : k));
  const t = kelimeler.join(" ");
  return KISALTMA.has(kelimeler[0]) ? t : t.charAt(0).toLocaleUpperCase("tr-TR") + t.slice(1);
}

function sirala(list: VehicleTrait[]) {
  return list.map((t, i) => ({ t, i })).sort((a, b) => GUVEN_SIRA[a.t.guven] - GUVEN_SIRA[b.t.guven] || a.i - b.i).map((x) => x.t);
}

/** "50.000+ km", "90.000-120.000 km" → [başlangıç, bitiş|null]. Okunamazsa null. */
function kmAraligi(metin: string | null): [number, number | null] | null {
  if (!metin) return null;
  const sayilar = (metin.match(/\d{1,3}(?:[.\s]\d{3})+|\d+/g) || []).map((x) => Number(x.replace(/[.\s]/g, ""))).filter((n) => n === 0 || n >= 1000);
  if (!sayilar.length || (sayilar.length === 1 && sayilar[0] === 0)) return null;
  return [sayilar[0], sayilar[1] && sayilar[1] > sayilar[0] ? sayilar[1] : null];
}

function binKm(n: number) {
  return n === 0 ? "0" : `${Math.round(n / 1000).toLocaleString("tr-TR")} bin`;
}

function KmCizelgesi({ list }: { list: VehicleTrait[] }) {
  const noktalar = list
    .map((t) => ({ t, r: kmAraligi(t.km_araligi) }))
    .filter((x): x is { t: VehicleTrait; r: [number, number | null] } => !!x.r)
    .sort((a, b) => a.r[0] - b.r[0]);
  if (!noktalar.length) return null;
  const enBuyuk = Math.max(...noktalar.map((x) => x.r[1] ?? x.r[0]));
  const ust = Math.max(150000, Math.ceil((enBuyuk * 1.15) / 50000) * 50000);
  const yuzde = (n: number) => `${Math.min(100, (n / ust) * 100)}%`;
  return (
    <section className="trait-km-card" aria-labelledby="trait-km-title">
      <h4 id="trait-km-title">Ne zaman çıkar? <span>kilometreye göre</span></h4>
      <div className="trait-km-track" aria-hidden="true">
        {noktalar.map(({ t, r }, i) => r[1]
          ? <i key={i} className="trait-km-range" style={{ left: yuzde(r[0]), width: `calc(${yuzde(r[1])} - ${yuzde(r[0])})` }} title={`${baslik(t.etiket)}: ${t.km_araligi}`} />
          : <i key={i} className="trait-km-dot" style={{ left: yuzde(r[0]) }} title={`${baslik(t.etiket)}: ${t.km_araligi}`} />)}
      </div>
      <div className="trait-km-scale" aria-hidden="true"><span>0</span><span>{ust.toLocaleString("tr-TR")} km</span></div>
      <ul className="trait-km-legend">
        {noktalar.map(({ t, r }, i) => (
          <li key={i}><i className={r[1] ? "is-range" : "is-dot"} aria-hidden="true" />
            <strong>{r[1] ? `${binKm(r[0])}–${binKm(r[1])}` : `${binKm(r[0])}+`}</strong> {baslik(t.etiket)}</li>
        ))}
      </ul>
    </section>
  );
}

function TraitRow({ trait, tip, open, onToggle, id }: { trait: VehicleTrait; tip: TraitTip; open: boolean; onToggle: () => void; id: string }) {
  const requestPlan = useRequestPlan();
  return (
    <li className={`trait-item${open ? " is-open" : ""}`}>
      <button type="button" className="trait-item-head" aria-expanded={open} aria-controls={id} onClick={onToggle}>
        <span className="trait-chevron" aria-hidden="true" />
        <span className="trait-item-title">{baslik(trait.etiket)}</span>
        {trait.km_araligi && <span className="trait-item-km">{trait.km_araligi}</span>}
        <span className={`trait-badge tip-${tip} guven-${trait.guven}`}>{ROZET[tip][trait.guven]}</span>
      </button>
      {open && (
        <div className="trait-item-body" id={id}>
          <p>{trait.iddia}</p>
          <div className="trait-item-meta">
            <span>{GUVEN_KAYNAK[trait.guven]}</span>
            {trait.kaynak_url ? (
              <a href={trait.kaynak_url} target="_blank" rel="noopener noreferrer" title={trait.kaynak_alinti || trait.kaynak_url}>
                {trait.kaynak_alan}
              </a>
            ) : (
              <button type="button" className="trait-source-lock" title="Kaynak linki Premium planında görünür"
                      onClick={() => requestPlan("premium")}>
                Kaynak · Premium
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function TraitTabs({ data }: { data: Traits }) {
  const ilkSekme = TIPLER.find((t) => data[t].length > 0) || "kronik";
  const [tip, setTip] = useState<TraitTip>(ilkSekme);
  const [hepsi, setHepsi] = useState(false);
  const sirali = useMemo(() => sirala(data[tip]), [data, tip]);
  const [acik, setAcik] = useState<Set<number>>(new Set([0]));
  useEffect(() => { setTip(ilkSekme); }, [data]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setHepsi(false); setAcik(new Set([0])); }, [data, tip]);
  const gorunen = hepsi ? sirali : sirali.slice(0, ILK_GORUNEN);
  const kalan = sirali.length - gorunen.length;
  const toggle = (i: number) => setAcik((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; });

  return (
    <>
      <div className="trait-summary" role="tablist" aria-label="Araca özel bilgiler">
        {TIPLER.map((t) => (
          <button key={t} type="button" role="tab" id={`trait-tab-${t}`} aria-selected={t === tip} aria-controls="trait-panel"
                  className={`trait-stat stat-${t}${t === tip ? " is-active" : ""}`} onClick={() => setTip(t)}>
            <span>{SEKME[t].ozet}</span><strong>{data[t].length}</strong>
          </button>
        ))}
      </div>
      <div className="trait-panel" id="trait-panel" role="tabpanel" aria-labelledby={`trait-tab-${tip}`}>
        {tip === "kronik" && <KmCizelgesi list={data.kronik} />}
        <p className="trait-panel-note"><strong>{SEKME[tip].ad}</strong> · {SEKME[tip].not}{sirali.length > 1 ? ", en yaygından başlayarak" : ""}</p>
        {sirali.length > 0 ? (
          <ul className="trait-items">
            {gorunen.map((t, i) => (
              <TraitRow key={`${tip}-${i}`} trait={t} tip={tip} open={acik.has(i)} onToggle={() => toggle(i)} id={`trait-${tip}-${i}`} />
            ))}
          </ul>
        ) : (
          <p className="trait-col-empty">Kaynaklı kayıt yok.</p>
        )}
        {kalan > 0 && (
          <button type="button" className="trait-more" onClick={() => setHepsi(true)}>Tümünü göster ({kalan} daha)</button>
        )}
        {hepsi && sirali.length > ILK_GORUNEN && (
          <button type="button" className="trait-more" onClick={() => setHepsi(false)}>Daha az göster</button>
        )}
      </div>
    </>
  );
}

/** Seçim kutusu 300 araca çıkacak; markaya göre gruplanmazsa kullanılamaz. */
function markaGruplari(options: TraitVehicleOption[]) {
  const gruplar = new Map<string, TraitVehicleOption[]>();
  for (const o of options) {
    const liste = gruplar.get(o.marka);
    if (liste) liste.push(o);
    else gruplar.set(o.marka, [o]);
  }
  return [...gruplar.entries()];
}

export default function VehicleTraits({ initial }: { initial: Traits }) {
  const [options, setOptions] = useState<TraitVehicleOption[]>([]);
  const [selected, setSelected] = useState(initial.anahtar);
  const [data, setData] = useState<Traits>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");

  // Analiz değişirse (yeni analiz çalıştırıldıysa) karta o araçla dön.
  useEffect(() => {
    setSelected(initial.anahtar);
    setData(initial);
  }, [initial]);

  useEffect(() => {
    const ac = new AbortController();
    fetchTraitVehicles(ac.signal)
      .then(setOptions)
      .catch((e) => {
        // Sessizce yutma: liste boş kalırsa kullanıcı sebebini bilemez.
        if (e?.name !== "AbortError") setListError("Araç listesi yüklenemedi.");
      });
    return () => ac.abort();
  }, []);

  useEffect(() => {
    if (!selected || selected === initial.anahtar) {
      setData(initial);
      setError("");
      return;
    }
    const ac = new AbortController();
    setLoading(true);
    setError("");
    fetchVehicleTraits(selected, ac.signal)
      .then(setData)
      .catch((e) => { if (e?.name !== "AbortError") setError("Bu aracın verisi yüklenemedi."); })
      .finally(() => setLoading(false));
    return () => ac.abort();
  }, [selected, initial]);

  const analizAracVeride = options.some((o) => o.anahtar === initial.anahtar);
  const yil = data.yil_baslangic && data.yil_bitis
    ? `${data.yil_baslangic}-${data.yil_bitis}` : null;

  return (
    <article className="result-card wide-card tone-teal traits-card">
      <div className="card-top">
        <span className="card-icon orange">⚙</span>
        <div>
          <h3>Araca özel bilgiler</h3>
          <p>Kullanıcı forumlarından derlenmiş kronik arızalar ve artı/eksi yönler</p>
        </div>
      </div>

      <div className="traits-picker">
        <label htmlFor="traits-vehicle">Araç</label>
        <select id="traits-vehicle" value={selected}
                onChange={(e) => setSelected(e.target.value)}>
          {!analizAracVeride && (
            <option value={initial.anahtar}>
              {initial.etiket} — analiz edilen araç (veri yok)
            </option>
          )}
          {markaGruplari(options).map(([marka, liste]) => (
            <optgroup key={marka} label={marka}>
              {liste.map((o) => (
                <option key={o.anahtar} value={o.anahtar}>
                  {o.seri} {o.motor}
                  {o.anahtar === initial.anahtar ? " — analiz edilen araç" : ""}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {yil && <span className="traits-years">{yil} modelleri</span>}
        {options.length > 0 && (
          <span className="traits-count">{options.length} araç</span>
        )}
        {listError && <span className="traits-error">{listError}</span>}
      </div>

      {loading && <p className="card-note">Yükleniyor…</p>}
      {error && <p className="card-empty">{error}</p>}

      {!loading && !error && !data.available && (
        <p className="card-empty">
          <strong>{data.etiket}</strong> için henüz kaynaklı veri yok. Kaynağı
          doğrulanamayan hiçbir iddia bu listeye eklenmiyor; yukarıdaki listeden
          verisi olan bir araca geçebilirsiniz.
        </p>
      )}

      {!loading && !error && data.available && (
        <>
          <TraitTabs data={data} />
          <p className="card-note">
            {data.kaynak_n} farklı kaynaktan derlendi. Her satırdaki bağlantı, o
            iddianın alındığı sayfaya gider. Kullanıcı beyanlarıdır; ekspertiz
            raporu yerine geçmez.
          </p>
        </>
      )}
    </article>
  );
}
