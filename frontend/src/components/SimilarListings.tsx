import type { SimilarListing } from "../types";
import { num, tl } from "../format";

/**
 * Şu anda yayında olan emsal ilanlar. Liste EN UCUZDAN değil, kullanıcının
 * ilanına FİYATÇA EN YAKINDAN sıralı gelir (backend böyle sıralıyor) --
 * amaç "daha ucuzu var mı" değil, "bu fiyat emsallerin neresinde".
 */
export default function SimilarListings({
  listings, price,
}: { listings: SimilarListing[]; price: number }) {
  return (
    <article className="result-card wide-card tone-slate">
      <div className="card-top">
        <span className="card-icon orange">≡</span>
        <div>
          <h3>Yayındaki benzer ilanlar</h3>
          <p>Aynı model ve yakın model yılındaki güncel galeri ilanları</p>
        </div>
        <span className="count">{listings.length}</span>
      </div>

      {listings.length === 0 ? (
        <p className="card-empty">
          Bu model ve yıl aralığı için şu anda yayında eşleşen ilan bulunamadı.
        </p>
      ) : (
        <>
          <div className="listing-head">
            <span>İlan</span>
            <span>Fark</span>
            <span>Fiyat</span>
          </div>
          {listings.map((listing, index) => {
            const diff = listing.price - price;
            const cheaper = diff < 0;
            const Row = listing.url ? "a" : "div";
            return (
              <Row
                key={listing.url || `${listing.title}-${index}`}
                className="listing-row"
                {...(listing.url
                  ? { href: listing.url, target: "_blank", rel: "noopener noreferrer" }
                  : {})}
              >
                <div className="listing-car">
                  <span>{listing.year}</span>
                  <p>
                    <strong>{listing.title || listing.model}</strong>
                    <small>
                      {[
                        listing.km != null ? `${num(listing.km)} km` : null,
                        listing.color,
                        listing.city,
                        listing.post_age_days != null ? `${listing.post_age_days} gündür yayında` : null,
                      ].filter(Boolean).join(" · ")}
                    </small>
                  </p>
                </div>
                <span className={cheaper ? "down" : "up"}>
                  {diff === 0 ? "aynı" : `${cheaper ? "" : "+"}${Math.round(diff / 1000)}b`}
                </span>
                <strong>{tl(listing.price)}</strong>
              </Row>
            );
          })}
          <p className="card-note">
            Fark sütunu, ilanın sizin girdiğiniz <strong>{tl(price)}</strong> fiyatına göre
            farkını bin TL cinsinden gösterir. Veriler en son galeri taramasından gelir.
          </p>
        </>
      )}
    </article>
  );
}
