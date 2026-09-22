import { useEffect, useState } from "react";
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
 * Üç liste (kronik / iyi / kötü) yan yana sütunlarda durur: kullanıcı bir aracın
 * artısını ve eksisini aynı anda görsün, aşağı kaydırarak karşılaştırmasın.
 */

const BASLIK: Record<TraitTip, { ad: string; not: string }> = {
  kronik: { ad: "Kronik arızalar", not: "Bu motorda tekrar eden, bilinen sorunlar" },
  iyi: { ad: "İyi yönleri", not: "Sahiplik açısından olumlu bulunanlar" },
  kotu: { ad: "Kötü yönleri", not: "Arıza değil; maliyet, konfor ve kullanım" },
};
type TraitTip = "kronik" | "iyi" | "kotu";
const TIPLER: TraitTip[] = ["kronik", "iyi", "kotu"];

const GUVEN_ETIKET: Record<VehicleTrait["guven"], string> = {
  yuksek: "3+ kaynak",
  orta: "2 kaynak",
  dusuk: "tek kaynak",
};

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

function TraitRow({ trait }: { trait: VehicleTrait }) {
  const requestPlan = useRequestPlan();
  return (
    <li className={`trait-row trait-${trait.guven}`}>
      <div className="trait-main">
        <span className="trait-tag">{trait.etiket.replace(/-/g, " ")}</span>
        <p>{trait.iddia}</p>
      </div>
      <div className="trait-meta">
        {trait.km_araligi && <span className="trait-km">{trait.km_araligi}</span>}
        <span className="trait-conf" title={`Güven: ${trait.guven}`}>
          {GUVEN_ETIKET[trait.guven]}
        </span>
        {trait.kaynak_url ? (
          <a href={trait.kaynak_url} target="_blank" rel="noopener noreferrer"
             title={trait.kaynak_alinti || trait.kaynak_url}>
            {trait.kaynak_alan}
          </a>
        ) : (
          <button type="button" className="trait-source-lock" title="Kaynak linki Premium planında görünür"
                  onClick={() => requestPlan("premium")}>
            Kaynak · Premium
          </button>
        )}
      </div>
    </li>
  );
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
          <div className="trait-columns">
            {TIPLER.map((tip) => (
              <section key={tip} className={`trait-col trait-col-${tip}`}>
                <div className="trait-col-head">
                  <h4>{BASLIK[tip].ad}</h4>
                  <span>{BASLIK[tip].not}</span>
                </div>
                {data[tip].length > 0 ? (
                  <ul className="trait-list">
                    {data[tip].map((t, i) => <TraitRow key={`${tip}-${i}`} trait={t} />)}
                  </ul>
                ) : (
                  <p className="trait-col-empty">Kaynaklı kayıt yok.</p>
                )}
              </section>
            ))}
          </div>
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
