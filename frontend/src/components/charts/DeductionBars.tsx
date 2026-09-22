import type { AnalysisResult } from "../../types";

/**
 * İlan kalitesi puanının nereden düştüğü. 100'den başlayıp her kuralın
 * götürdüğü puanı ağırlığa göre sıralar; kullanıcı "puan neden 62" sorusunu
 * grafikten okur. Puan götürmeyen uyarılar (0 puanlı red flag'ler) listenin
 * altında not olarak kalır.
 */
export default function DeductionBars({
  quality,
}: {
  quality: AnalysisResult["listing_quality"];
}) {
  const deductions = [...(quality.deductions || [])].sort((a, b) => b.points - a.points);
  const scored = new Set(deductions.map((d) => d.label));
  const notes = quality.warnings.filter((w) => !scored.has(w));
  const max = Math.max(1, ...deductions.map((d) => d.points));

  if (!deductions.length && !notes.length) {
    return <p className="quality-clean">Belirgin bir veri riski tespit edilmedi.</p>;
  }

  return (
    <div className="deduct">
      {deductions.length > 0 && (
        <>
          <h4>100 puandan ne götürdü?</h4>
          {deductions.map((d) => (
            <div className="deduct-row" key={d.label}>
              <span>{d.label}</span>
              <i><b style={{ width: `${(d.points / max) * 100}%` }} /></i>
              <strong>−{d.points}</strong>
            </div>
          ))}
        </>
      )}
      {notes.length > 0 && (
        <ul className="quality-warnings">
          {notes.map((n) => <li key={n}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}
