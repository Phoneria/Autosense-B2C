import type { SimilarListing } from "../types";
import type React from "react";
import { num, tl } from "../format";

/**
 * Şu anda yayında olan emsal ilanlar. Liste EN UCUZDAN değil, kullanıcının
 * ilanına FİYATÇA EN YAKINDAN sıralı gelir (backend böyle sıralıyor) --
 * amaç "daha ucuzu var mı" değil, "bu fiyat emsallerin neresinde".
 */
export default function SimilarListings({
  listings, price,
}: { listings: SimilarListing[]; price: number }) {
  if (listings.length === 0) {
    return (
      <p className="card-empty">
        Bu model ve yıl aralığı için şu anda yayında eşleşen ilan bulunamadı.
      </p>
    );
  }
  return (
    <div className="az-similar">
      <table className="az-table">
        <caption className="az-table-caption">
          Aynı model ve yakın model yılındaki güncel galeri ilanları; ilan fiyatınıza en yakından sıralı.
        </caption>
        <thead>
          <tr>
            <th scope="col">Araç</th>
            <th scope="col" className="num">Yıl</th>
            <th scope="col" className="num">Kilometre</th>
            <th scope="col" className="num">Yayında</th>
            <th scope="col" className="num">Fiyat</th>
            <th scope="col" className="num">Sizin ilana göre</th>
          </tr>
        </thead>
        <tbody>
          {listings.map((listing, index) => {
            const diff = listing.price - price;
            const place = [listing.city, listing.district].filter(Boolean).join(" / ");
            return (
              <tr key={`${listing.price}-${listing.km}-${index}`} style={{ "--i": index } as React.CSSProperties}>
                <th scope="row" className="az-similar-name">
                  <span>{listing.model || "Emsal araç"}</span>
                  <small>{[listing.color, place].filter(Boolean).join(" · ") || "Konum belirtilmemiş"}</small>
                </th>
                <td className="num" data-label="Yıl">{listing.year}</td>
                <td className="num" data-label="Kilometre">{listing.km != null ? `${num(listing.km)} km` : "—"}</td>
                <td className="num" data-label="Yayında">{listing.post_age_days != null ? `${listing.post_age_days} gün` : "—"}</td>
                <td className="num az-similar-price" data-label="Fiyat">{tl(listing.price)}</td>
                <td className={`num az-similar-diff ${diff < 0 ? "is-lower" : diff > 0 ? "is-higher" : ""}`} data-label="Sizin ilana göre">
                  {diff === 0 ? "Aynı" : <><span aria-hidden="true">{diff < 0 ? "▼" : "▲"}</span> {diff < 0 ? "−" : "+"}{tl(Math.abs(diff))}</>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="card-note">
        Son sütun, ilanın sizin girdiğiniz <strong>{tl(price)}</strong> fiyatına göre farkını gösterir.
        Veriler en son galeri taramasından gelir.
      </p>
    </div>
  );
}
