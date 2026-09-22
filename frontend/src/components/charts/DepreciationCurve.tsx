import { tl } from "../../format";

/**
 * Değer kaybı: üç sütun (bugün / 1 yıl / 3 yıl). Sütunun tamamı bugünkü
 * değeri temsil eder; dolu kısım o tarihte KALAN değer, üstteki taralı kısım
 * KAYBEDİLEN değerdir. Yükseklikler sabit bir çizim alanı üzerinden yüzdeyle
 * hesaplanır -- eski sürümde sütunun kendi yüksekliği tanımsızdı ve kutular
 * boş/kayık görünüyordu.
 */
type Col = { label: string; value: number | null; loss: number | null };

const PLOT_HEIGHT = 170;

export default function DepreciationCurve({
  current, oneYear, oneYearLoss, threeYear, threeYearLoss,
}: {
  current: number | null;
  oneYear: number | null;
  oneYearLoss: number | null;
  threeYear: number | null;
  threeYearLoss: number | null;
}) {
  const base = current ?? 0;
  const cols: Col[] = [
    { label: "Bugün", value: current, loss: null },
    { label: "1 yıl sonra", value: oneYear, loss: oneYearLoss },
    { label: "3 yıl sonra", value: threeYear, loss: threeYearLoss },
  ];
  const lossPct = base && threeYearLoss ? (threeYearLoss / base) * 100 : null;

  return (
    <div className="depr">
      <div className="depr-headline">
        <span>3 yılda tahmini değer kaybı</span>
        <strong>−{tl(threeYearLoss)}</strong>
        {lossPct != null && <em>bugünkü değerin %{lossPct.toFixed(1).replace(".", ",")}&apos;i</em>}
      </div>

      <div className="depr-plot" style={{ height: PLOT_HEIGHT }}>
        {cols.map((col) => {
          const keep = base && col.value != null ? Math.max(0, Math.min(100, (col.value / base) * 100)) : 0;
          return (
            <div className="depr-col" key={col.label}>
              <div className="depr-bar">
                <i className="depr-loss" style={{ height: `${100 - keep}%` }} />
                <i className="depr-keep" style={{ height: `${keep}%` }}>
                  <b>{tl(col.value)}</b>
                </i>
              </div>
              <span className="depr-label">{col.label}</span>
              <small className={col.loss == null ? "is-base" : ""}>
                {col.loss == null ? "başlangıç değeri" : `−${tl(col.loss)}`}
              </small>
            </div>
          );
        })}
      </div>

      <p className="depr-note">
        Bu tutarlar bugünkü fiyat seviyesine göredir; <b>enflasyon hesaba katılmamıştır</b>.
        Aracın TL cinsinden fiyatı artsa bile alım gücü olarak değer kaybı yaşanabilir.
      </p>

      <p className="depr-key">
        <i className="depr-keep" /> kalan değer
        <i className="depr-loss" /> kaybedilen değer
      </p>
    </div>
  );
}
