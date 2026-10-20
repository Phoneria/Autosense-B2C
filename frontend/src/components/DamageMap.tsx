import { CAR_PARTS, DAMAGE_CYCLE, DAMAGE_LABEL, DEFAULT_DAMAGE } from "../constants";
import type { DamageState } from "../types";

/** Araç şeması. Her parçaya tıklandıkça durum sırayla ilerler:
 *  Orijinal -> Lokal boyalı -> Boyalı -> Değişen -> Orijinal. */
export default function DamageMap({
  damage, onChange, agirHasar, onAgirHasarChange,
}: {
  damage: Record<string, DamageState>;
  onChange: (next: Record<string, DamageState>) => void;
  agirHasar: boolean;
  onAgirHasarChange: (next: boolean) => void;
}) {
  const cycle = (key: string) => {
    const index = DAMAGE_CYCLE.indexOf(damage[key]);
    onChange({ ...damage, [key]: DAMAGE_CYCLE[(index + 1) % DAMAGE_CYCLE.length] });
  };

  const marked = CAR_PARTS.filter(([key]) => damage[key] !== "original").length;
  const counts = Object.fromEntries(DAMAGE_CYCLE.map((state) => [state, CAR_PARTS.filter(([key]) => damage[key] === state).length]));

  return (
    <div className="damage-panel az-damage-panel">
      <div className="az-card-head az-damage-head">
        <h2><span className="az-step is-orange">2</span>Hasar durumu</h2>
        <p>Parçaya her dokunuşta durum sırayla değişir: Orijinal → Lokal boyalı → Boyalı → Değişen → Orijinal.</p>
        <span className={`az-damage-count${marked ? " has-marks" : ""}`} aria-live="polite">{marked ? `${marked} parça işaretli` : "Tüm parçalar orijinal"}</span>
      </div>

      <p className="az-direction" aria-hidden="true">Ön</p>

      <div className="car-map">
        {CAR_PARTS.map(([key, label, area]) => (
          <button
            key={key}
            type="button"
            className={`car-part ${damage[key]}`}
            style={{ gridArea: area }}
            onClick={() => cycle(key)}
            title={`${label}: ${DAMAGE_LABEL[damage[key]]}`}
            aria-label={`${label}, ${DAMAGE_LABEL[damage[key]]}. Değiştirmek için tıklayın.`}
          >
            <span className="car-part-name">{label}</span>
            {damage[key] !== "original" && <span className="car-part-state" aria-hidden="true">{DAMAGE_LABEL[damage[key]]}</span>}
          </button>
        ))}
      </div>


      <p className="az-direction" aria-hidden="true">Arka</p>

      <ul className="legend az-legend" aria-label="Durum dağılımı">
        {DAMAGE_CYCLE.map((state) => (
          <li key={state} className={counts[state] ? "has-count" : ""}>
            <i className={state} aria-hidden="true" /> {DAMAGE_LABEL[state]} <b>{counts[state]}</b>
          </li>
        ))}
      </ul>

      <button type="button" className="reset" disabled={!marked} onClick={() => onChange({ ...DEFAULT_DAMAGE })}>
        Tümünü orijinale döndür
      </button>

      <label className="check-field az-check">
        <input
          type="checkbox"
          checked={agirHasar}
          onChange={(e) => onAgirHasarChange(e.target.checked)}
        />
        Ağır hasar kaydı var
      </label>
    </div>
  );
}
