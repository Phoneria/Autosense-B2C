/**
 * Açıklama analizindeki dört sinyal ailesini tek ızgarada gösterir:
 * çelişki / olumlu / iddia / değinilmemiş. Renk kodu sabittir, metni
 * okumadan da ağırlık görünür.
 */
export type SignalKind = "flag" | "positive" | "claim" | "missing";

const TITLES: Record<SignalKind, string> = {
  flag: "Çelişki ve uyarı",
  positive: "Olumlu sinyal",
  claim: "İlanın iddiası",
  missing: "Değinilmemiş",
};

export default function SignalGrid({
  groups,
}: {
  groups: { kind: SignalKind; items: string[] }[];
}) {
  const shown = groups.filter((g) => g.items.length > 0);
  if (!shown.length) return null;

  return (
    <div className="sgrid">
      {shown.map((group) => (
        <section className={`sgroup is-${group.kind}`} key={group.kind}>
          <h4>{TITLES[group.kind]}<b>{group.items.length}</b></h4>
          <ul>
            {group.items.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      ))}
    </div>
  );
}
