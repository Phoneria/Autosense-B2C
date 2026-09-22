import { CAR_PARTS, DAMAGE_API_LABEL } from "./constants";
import type { DamageState, VehicleVariant } from "./types";

/** Analiz formunun backend'e giden hali; senaryo ve maliyet sekmeleri de kullanır. */
export interface VehicleInput {
  category: string;
  brand: string;
  series: string;
  engine: string;
  packageName: string | null;
  packages: VehicleVariant[];
  year: number;
  km: number;
  price: number;
  city: string;
  district: string;
  fuel: string;
  gear: string;
  color: string | null;
  description: string;
  agirHasar: boolean;
  damage: Record<string, DamageState>;
}

export function toPayload(input: VehicleInput): Record<string, unknown> {
  return {
    category: input.category,
    brand: input.brand, series: input.series, engine: input.engine,
    package: input.packageName,
    city: input.city, district: input.district,
    year: input.year, km: input.km, price: input.price,
    fuel: input.fuel, gear: input.gear, color: input.color,
    description: input.description,
    agir_hasar: input.agirHasar,
    damage: CAR_PARTS
      .filter(([key]) => input.damage[key] !== "original")
      .map(([key, label]) => ({ parca: label, durum: DAMAGE_API_LABEL[input.damage[key]] })),
  };
}
