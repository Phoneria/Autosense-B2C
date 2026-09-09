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

  return (
    <div className="damage-panel">
      <div className="damage-title">
        <div>
          <span className="step">2</span>
          <div>
            <h2>Hasar durumu</h2>
            <p>Parçalara tıklayarak durumu değiştirin</p>
          </div>
        </div>
        <span>{marked} parça işaretli</span>
      </div>

      <p className="car-direction">Ö N &nbsp;&nbsp;&nbsp; T A R A F</p>

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
            {label}
          </button>
        ))}
      </div>

      <div className="legend">
        {DAMAGE_CYCLE.map((state) => (
          <span key={state}>
            <i className={state} /> {DAMAGE_LABEL[state]}
          </span>
        ))}
      </div>

      <button type="button" className="reset" onClick={() => onChange({ ...DEFAULT_DAMAGE })}>
        Tümünü orijinale döndür
      </button>

      <label className="check-field" style={{ marginTop: 20 }}>
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
