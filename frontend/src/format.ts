export const tl = (v: number | null | undefined) =>
  v == null ? "—" : `${Math.round(v).toLocaleString("tr-TR")} TL`;

export const num = (v: number | null | undefined) =>
  v == null ? "—" : Math.round(v).toLocaleString("tr-TR");

export const groupDigits = (v: string) => (v ? Number(v).toLocaleString("tr-TR") : "");

export const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });

export const pct = (v: number) => `%${Math.abs(v).toLocaleString("tr-TR")}`;
