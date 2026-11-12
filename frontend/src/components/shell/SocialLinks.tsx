import { SELLER } from "../../seller";

/** Instagram ve TikTok simgeleri (resmi marka dosyaları, public/sosyal). Herkese açık ve uygulama üst şeridinde ortak. */
export default function SocialLinks() {
  return (
    <span className="as-social" aria-label="Sosyal medya">
      <a href={SELLER.instagram} target="_blank" rel="noopener noreferrer" className="as-social-icon" aria-label="AutoSense Instagram hesabı" title="Instagram">
        <img src="/sosyal/instagram.png" width="24" height="24" alt="" />
      </a>
      <a href={SELLER.tiktok} target="_blank" rel="noopener noreferrer" className="as-social-icon" aria-label="AutoSense TikTok hesabı" title="TikTok">
        <img src="/sosyal/tiktok.png" width="24" height="24" alt="" />
      </a>
    </span>
  );
}
