// Herkese açık sayfalar: tanıtım (giriş yapmamış ziyaretçi için ana sayfa),
// gizlilik ve çerez politikası, KVKK aydınlatma metni. Google AdSense
// incelemesi ve arama motorları bu sayfaları görebilmeli.
import { useEffect, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import PlanCards from "../components/PlanCards";
import { PUBLIC_PLANS, VAT_NOTE, savePendingPlan } from "../billingDisplay";
import { GoogleButton } from "../auth/google";
import Logo from "../components/shell/Logo";
import SiteFooter, { CONTACT_EMAIL } from "../components/shell/SiteFooter";
import { useScrollReveal } from "../components/useScrollReveal";
import HeroDrawing from "../components/landing/HeroDrawing";
import { PriceGlyph, RegionGlyph, TrendGlyph } from "../components/landing/Glyphs";
import MethodFlow from "../components/landing/MethodFlow";
import { IconBranch, IconCheck, IconDoc, IconExit, IconRange, IconSearch, IconStore, IconTag, IconUser, IconWrench } from "../components/landing/Icons";
import "../landing.css";

/** Sıralı beliriş için gecikme sırası (CSS --i). */
const seq = (i: number) => ({ "--i": i }) as CSSProperties;

export { CONTACT_EMAIL };

export const OPERATOR = "İzzet Ahmet";
const UPDATED = "15 Ekim 2026";

function PublicShell({ children }: { children: ReactNode }) {
  const ref = useScrollReveal<HTMLDivElement>();
  // Sayfa kaydırılınca üst şerit belirginleşir (alt çizgi + yarı saydam zemin).
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <div className="as-public" ref={ref}>
      <header className={`as-header as-header-public${scrolled ? " is-scrolled" : ""}`}>
        <div className="as-header-inner">
          <Logo />
          <nav className="as-public-nav" aria-label="Hesap">
            <Link to="/fiyatlar" className="as-link-quiet as-hide-sm">Fiyatlar</Link>
            <Link to="/login" className="as-link-quiet">Giriş yap</Link>
            <Link to="/signup" className="as-btn as-btn-primary as-btn-sm"><span className="as-hide-sm">Ücretsiz hesap aç</span><span className="as-show-sm">Hesap aç</span></Link>
          </nav>
        </div>
      </header>
      <main className="as-public-main">{children}</main>
      <SiteFooter />
    </div>
  );
}

const FACTS = [
  { lead: "Her gün", rest: "güncellenen ilanlar" },
  { lead: "Son 30 günün", rest: "emsal ilanları" },
  { lead: "300 araç", rest: "için sorun rehberi" },
];

const TOOLS = [
  {
    id: "fiyat", label: "Fiyat analizi", title: "Bir ilanın piyasadaki yerini görün.",
    text: "Marka, model, yıl, kilometre ve hasarı girin; aynı modelin güncel ilanları farklara göre düzeltilerek karşılaştırılır.",
    points: ["Tahmini piyasa değeri ve aralığı", "Pazarlık için başlangıç ve hedef fiyat"],
    Glyph: PriceGlyph,
  },
  {
    id: "rehber", label: "Araç rehberi", title: "Modellerin piyasadaki hareketini izleyin.",
    text: "Galeri ilanlarının takibinden hangi modelin ilgi gördüğünü ve fiyatının nereye gittiğini çıkarın.",
    points: ["İlanda kalma süresi ve 4 haftalık fiyat değişimi", "Modele özel kronik sorunlar, kaynaklarıyla"],
    Glyph: TrendGlyph,
  },
  {
    id: "bolgesel", label: "Bölgesel fırsatlar", title: "Aynı model, hangi ilde daha uygun?",
    text: "Bir ildeki medyan ilan fiyatını ülke geneliyle karşılaştırın. Yetersiz örneklemli sonuçlar listelenmez.",
    points: ["İl bazında ortalama fiyat farkı", "Model bazında ülke medyanına göre fark"],
    Glyph: RegionGlyph,
  },
];

const STEPS = [
  { title: "Aracı tanımlayın", text: "İlan metnini yapıştırın ya da marka, model, yıl, kilometre ve fiyatı seçin." },
  { title: "Piyasayla karşılaştırın", text: "Aynı modelin güncel ilanları yaş, kilometre, hasar ve donanım farkıyla dengelenir." },
  { title: "Daha bilinçli karar verin", text: "Tahmini değeri, pazarlık yönünü ve ilanın piyasadaki yerini görün." },
];

const EXTRAS = [
  { title: "İlan metnini okuma", text: "Araç bilgileri, hasar ve çelişki işaretleri ayıklanır.", Icon: IconDoc },
  { title: "Ne olurdu? senaryoları", text: "Kilometre, yıl ya da hasar değişseydi değer nasıl etkilenirdi?", Icon: IconBranch },
  { title: "Kronik sorun rehberi", text: "300 araç için bilinen arızalar ve zayıf yönler, kaynaklarıyla.", Icon: IconWrench },
];

const LIMITS = [
  { title: "İlan fiyatı, satış fiyatı değildir.", text: "Kullanılan veriler ilan fiyatlarına dayanır.", Icon: IconTag },
  { title: "Her sonuç bir tahmindir.", text: "Veri tarihi ve emsal kapsamı sonuçla birlikte gösterilir.", Icon: IconRange },
  { title: "İlandan kalkan, satılan değildir.", text: "Yalnızca talebe dair dolaylı bir göstergedir.", Icon: IconExit },
  { title: "Ekspertizin yerini tutmaz.", text: "Nihai karar öncesinde aracı yerinde inceletin.", Icon: IconSearch },
];

const PERSONAS = [
  {
    id: "galeri", title: "Galericiler", Icon: IconStore,
    text: "Stoktaki araçların piyasa konumunu izleyin, doğru fiyatlayın ve fırsatları daha hızlı görün.",
    points: ["Stok alımında piyasa değeri", "Modellerin ilanda kalma süresi", "İller arası fiyat farkı"],
  },
  {
    id: "birey", title: "Bireysel alıcılar", Icon: IconUser,
    text: "Teklif vermeden önce fiyatın makul olup olmadığını görün ve pazarlığa hazırlıklı gidin.",
    points: ["İlanın tahmini değere göre yeri", "Pazarlık için başlangıç ve hedef fiyat", "Modele özel kronik sorunlar"],
  },
];

/** Herkese açık plan ve fiyat bölümü. "Satın Al" seçilen planı saklayıp kayda
 *  yönlendirir; giriş/kayıttan sonra kullanıcı o planın sipariş özetine döner. */
export function PricingSection({ headingLevel = 2 }: { headingLevel?: 1 | 2 }) {
  const navigate = useNavigate();
  const Heading = headingLevel === 1 ? "h1" : "h2";
  function select(id: string) {
    if (id === "pro" || id === "premium") { savePendingPlan(id); navigate(`/signup?plan=${id}`); return; }
    navigate("/signup");
  }
  return (
    <section className="ld-band ld-band-white ld-pricing" id="fiyatlar" aria-labelledby="ld-pricing-title">
      <div className="ld-wrap">
        <header className="ld-pricing-head">
          <p className="ld-kicker">Fiyatlar</p>
          <Heading id="ld-pricing-title">Planlar</Heading>
          <p className="ld-pricing-vat">{VAT_NOTE}</p>
          <p className="ld-pricing-sub">Ücretsiz Basic ile başlayın; daha fazla analiz ve özellik için Pro veya Premium'u seçin. Abonelikler aylıktır.</p>
        </header>
        <PlanCards plans={PUBLIC_PLANS} onSelect={select} />
      </div>
    </section>
  );
}

export function PricingPage() {
  useEffect(() => { document.title = "Fiyatlar · AutoSense"; }, []);
  return <PublicShell><div className="ld-pricing-page"><PricingSection headingLevel={1} /></div></PublicShell>;
}

export function LandingPage() {
  return (
    <PublicShell>
      <section className="ld-hero" aria-labelledby="ld-title">
        <div className="ld-hero-art"><HeroDrawing /></div>
        <div className="ld-wrap ld-hero-inner">
          <h1 id="ld-title" className="ld-hero-title">İkinci el araç piyasası için veri</h1>
          <p className="ld-hero-tagline">Piyasayı net görün.</p>
          <p className="ld-hero-lead">Aracın piyasa değerini analiz edin, fiyatları karşılaştırın ve alım kararınızı veriye dayandırın.</p>
          <div className="ld-actions">
            <Link to="/signup" className="as-btn as-btn-primary as-btn-lg ld-cta-main">Aracını analiz edin</Link>
            <a href="#nasil-calisir" className="as-btn as-btn-secondary as-btn-lg">Nasıl çalışır?</a>
          </div>
          <div className="ld-hero-alt">
            <span>Hesabınız var mı? <Link to="/login">Giriş yapın</Link></span>
            <GoogleButton label="Google ile devam et" divider={false} className="ld-google" />
          </div>
        </div>
      </section>

      <section className="ld-facts" aria-label="Veri kapsamı">
        <ul className="ld-wrap ld-facts-list">
          {FACTS.map((f, i) => (
            <li key={f.lead} data-reveal style={seq(i)}>
              <strong>{f.lead}</strong>
              <span>{f.rest}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="ld-section" aria-labelledby="ld-tools-title">
        <div className="ld-wrap">
          <header className="ld-tools-head" data-reveal>
            <p className="ld-kicker">Ürün</p>
            <h2 id="ld-tools-title">
              <span className="ld-tools-a">Aracın değerini</span>
              <span className="ld-tools-b">her açıdan görün.</span>
            </h2>
          </header>
          <div className="ld-tools">
            {TOOLS.map(({ id, label, title, text, points, Glyph }, i) => (
              <article key={id} className={`ld-tool ld-tool-${id}`} data-reveal style={seq(i)}>
                <Glyph />
                <p className="ld-tool-label">{label}</p>
                <h3>{title}</h3>
                <p className="ld-tool-text">{text}</p>
                <ul>{points.map((pt) => <li key={pt}>{pt}</li>)}</ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="ld-band ld-band-white" id="nasil-calisir" aria-labelledby="ld-how-title">
        <div className="ld-wrap">
          <header className="ld-split-head" data-reveal>
            <div>
              <p className="ld-kicker">Nasıl çalışır?</p>
              <h2 id="ld-how-title">Fiyat kararını üç adımda netleştirin</h2>
            </div>
            <p className="ld-split-sub">İlanı okuyun, piyasayı görün, teklifinizi veriyle oluşturun.</p>
          </header>
          <ol className="ld-steps">
            {STEPS.map((step, i) => (
              <li key={step.title} className="ld-step" data-reveal style={seq(i)}>
                <span className="ld-step-badge" aria-hidden="true">{i + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
          <div className="ld-extras" data-reveal>
            <div className="ld-extras-head">
              <p className="ld-extras-title">İlanın ötesini görün</p>
              <p className="ld-extras-sub">Her analizde birlikte gelen ek araçlar</p>
            </div>
            <ul className="ld-extras-list">
              {EXTRAS.map(({ title, text, Icon }) => (
                <li key={title}>
                  <span className="ld-chip" aria-hidden="true"><Icon /></span>
                  <div><h3>{title}</h3><p>{text}</p></div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="ld-band ld-method" aria-labelledby="ld-method-title">
        <div className="ld-wrap">
          <header className="ld-method-head" data-reveal>
            <div>
              <p className="ld-kicker">Yöntem ve sınırlar</p>
              <h2 id="ld-method-title">Veriden karara.</h2>
            </div>
            <p>
              Tahmin, aynı modelin güncel ilanlarından hesaplanır. Her emsal ilan; yaş, kilometre, hasar ve donanım
              farkı için ölçülmüş katsayılarla aracınıza göre düzeltilir. Sonuç, veri tarihi ve emsal sayısıyla
              birlikte bir değer ve aralık olarak gösterilir.
            </p>
          </header>
          <div className="ld-method-flow" data-reveal>
            <MethodFlow />
            <p className="mf-note">Çizimler yöntemi temsil eder; gerçek ilan, fiyat ya da model verisi içermez.</p>
          </div>
          <div className="ld-limits" data-reveal>
            <h3 className="ld-limits-title">Tahminin sınırları</h3>
            <dl>
              {LIMITS.map(({ title, text, Icon }) => (
                <div key={title}>
                  <dt><span className="ld-limit-icon" aria-hidden="true"><Icon /></span>{title}</dt>
                  <dd>{text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </section>

      <section className="ld-band ld-band-tint" aria-labelledby="ld-who-title">
        <div className="ld-wrap">
          <header className="ld-split-head" data-reveal>
            <div>
              <p className="ld-kicker">Kimler için?</p>
              <h2 id="ld-who-title">Doğru teklifi vermek isteyenler için</h2>
            </div>
            <p className="ld-split-sub">Aynı veri, iki farklı karar: stok alımı ve araç satın alma.</p>
          </header>
          <div className="ld-personas">
            {PERSONAS.map(({ id, title, text, points, Icon }, i) => (
              <article key={id} className={`ld-persona ld-persona-${id}`} data-reveal style={seq(i)}>
                <span className="ld-chip ld-chip-lg" aria-hidden="true"><Icon /></span>
                <h3>{title}</h3>
                <p>{text}</p>
                <ul>
                  {points.map((pt) => <li key={pt}><IconCheck />{pt}</li>)}
                </ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <PricingSection />

      <section className="ld-band ld-band-cta" aria-labelledby="ld-final-title">
        <div className="ld-wrap">
          <div className="ld-final" data-reveal>
            <div className="ld-final-copy">
              <p className="ld-final-kicker">Ücretsiz değerlendirme</p>
              <h2 id="ld-final-title">Teklifinizi sezgiyle değil, veriyle oluşturun.</h2>
              <p>Ücretsiz hesabınızla başlayın; aracın piyasadaki yerini birkaç adımda görün.</p>
              <div className="ld-actions">
                <Link to="/signup" className="as-btn as-btn-lg ld-btn-light">Ücretsiz hesap aç</Link>
                <Link to="/login" className="ld-final-login">Hesabım var, giriş yap</Link>
              </div>
            </div>
            <ul className="ld-final-list" aria-label="Hesapla erişilen alanlar">
              <li><IconCheck /><span><b>Fiyat analizi</b>İlanın piyasadaki yeri</span></li>
              <li><IconCheck /><span><b>Araç rehberi</b>Modellerin piyasa hareketi</span></li>
              <li><IconCheck /><span><b>Bölgesel fırsatlar</b>İller arası fiyat farkı</span></li>
            </ul>
          </div>
        </div>
      </section>
    </PublicShell>
  );
}

function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <PublicShell>
      <article className="pub-legal">
        <h1>{title}</h1>
        <p className="pub-updated">Son güncelleme: {UPDATED}</p>
        {children}
      </article>
    </PublicShell>
  );
}

export function PrivacyPage() {
  return (
    <LegalPage title="Gizlilik ve Çerez Politikası">
      <p>
        Bu politika, auto-sense.com.tr adresinde sunulan AutoSense hizmetini (“Hizmet”) kullanırken
        hangi bilgilerin toplandığını, nasıl kullanıldığını ve haklarınızı açıklar. Hizmet {OPERATOR}{" "}
        tarafından işletilmektedir. Sorularınız için: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
      </p>

      <h2>Topladığımız bilgiler</h2>
      <ul>
        <li><strong>Hesap bilgileri:</strong> e-posta adresiniz ve şifrelenmiş (geri çözülemez biçimde saklanan) parolanız. Google ile giriş yaparsanız Google'ın bize ilettiği ad ve e-posta adresiniz.</li>
        <li><strong>Kullanım bilgileri:</strong> analiz için girdiğiniz araç bilgileri (marka, model, yıl, kilometre, fiyat, il/ilçe), yapıştırdığınız ilan metinleri ve özelliklerin kullanım sayıları.</li>
        <li><strong>Teknik bilgiler:</strong> IP adresi, tarayıcı türü, istek zamanı ve hata kayıtları. Bunlar güvenlik ve kötüye kullanımı önlemek için tutulur.</li>
      </ul>

      <h2>Bilgileri nasıl kullanıyoruz?</h2>
      <ul>
        <li>Hesabınızı oluşturmak, giriş yapmanızı ve e-posta doğrulamasını sağlamak,</li>
        <li>İstediğiniz analizleri yapmak ve sonuçları göstermek,</li>
        <li>Hizmetin güvenliğini sağlamak, aşırı kullanımı ve kötüye kullanımı engellemek,</li>
        <li>Hizmeti geliştirmek için toplu ve anonim kullanım istatistikleri çıkarmak,</li>
        <li>Hizmeti ücretsiz sunabilmek için reklam göstermek.</li>
      </ul>
      <p>Kişisel bilgilerinizi satmayız.</p>

      <h2>Reklamlar</h2>
      <p>
        Hizmet ücretsiz olarak sunulur ve bazı işlemlerden sonra Google (Google Ad Manager / AdSense)
        aracılığıyla reklam gösterilebilir. Google ve iş ortakları, size ve başka sitelere yaptığınız
        ziyaretlere göre reklam sunmak için çerez kullanabilir. Google'ın reklam çerezlerini nasıl
        kullandığını <a href="https://policies.google.com/technologies/ads" target="_blank" rel="noreferrer">Google reklam politikalarında</a> okuyabilir,
        kişiselleştirilmiş reklamları <a href="https://adssettings.google.com" target="_blank" rel="noreferrer">Google Reklam Ayarları</a> sayfasından kapatabilirsiniz.
      </p>

      <h2>Çerezler</h2>
      <ul>
        <li><strong>Zorunlu çerezler:</strong> oturumunuzu açık tutan (<code>b2c_sessionid</code>) ve güvenlik için kullanılan (<code>b2c_csrftoken</code>) çerezler. Bunlar olmadan Hizmet çalışmaz.</li>
        <li><strong>Tercih kayıtları:</strong> çerez bildirimini kapattığınızı hatırlamak gibi küçük tarayıcı kayıtları.</li>
        <li><strong>Reklam çerezleri:</strong> reklam gösterildiğinde Google tarafından yerleştirilen çerezler. Çerez bildiriminde “Kabul et” seçerseniz reklamlar ilgi alanlarınıza göre kişiselleştirilebilir; “Sadece zorunlu” seçerseniz kişiselleştirilmemiş reklam gösterilir.</li>
      </ul>
      <p>Seçiminizi değiştirmek için <button type="button" className="pub-inline-button" onClick={resetCookieChoice}>çerez tercihini sıfırlayın</button>; bildirim yeniden görünür.</p>
      <p>Çerezleri tarayıcı ayarlarınızdan silebilir veya engelleyebilirsiniz; zorunlu çerezler engellenirse giriş yapamazsınız.</p>

      <h2>Bilgileri kimlerle paylaşıyoruz?</h2>
      <ul>
        <li><strong>Barındırma:</strong> Hizmet, Almanya'daki sunucularda (Hetzner) çalışır.</li>
        <li><strong>E-posta gönderimi:</strong> doğrulama ve parola sıfırlama e-postaları Resend aracılığıyla gönderilir.</li>
        <li><strong>Google:</strong> Google ile giriş ve reklam hizmetleri için.</li>
        <li>Yasal bir zorunluluk olduğunda yetkili kamu kurumları.</li>
      </ul>

      <h2>Saklama süresi</h2>
      <p>
        Hesap bilgileriniz hesabınız açık olduğu sürece saklanır. Hesabınızın silinmesini istediğinizde
        bilgileriniz, yasal saklama yükümlülükleri dışında silinir. Teknik kayıtlar en fazla 1 yıl tutulur.
      </p>

      <h2>Haklarınız</h2>
      <p>
        Kişisel verilerinize ilişkin haklarınız <Link to="/kvkk">KVKK aydınlatma metninde</Link> açıklanmıştır.
        Hesabınızın silinmesi dahil her talep için <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> adresine yazabilirsiniz.
      </p>

      <h2>Değişiklikler</h2>
      <p>Bu politika güncellenebilir; güncel metin her zaman bu sayfada yayınlanır.</p>
    </LegalPage>
  );
}

export function KvkkPage() {
  return (
    <LegalPage title="KVKK Aydınlatma Metni">
      <p>
        6698 sayılı Kişisel Verilerin Korunması Kanunu (“KVKK”) uyarınca, AutoSense hizmeti kapsamında
        işlenen kişisel verileriniz hakkında sizi bilgilendirmek isteriz.
      </p>

      <h2>1. Veri sorumlusu</h2>
      <p>Veri sorumlusu: {OPERATOR}. İletişim: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.</p>

      <h2>2. İşlenen kişisel veriler</h2>
      <ul>
        <li><strong>Kimlik ve iletişim:</strong> e-posta adresi; Google ile giriş yapılırsa ad ve soyad.</li>
        <li><strong>Müşteri işlem:</strong> analiz için girilen araç bilgileri ve ilan metinleri, kullanım sayıları.</li>
        <li><strong>İşlem güvenliği:</strong> şifrelenmiş parola, IP adresi, oturum ve erişim kayıtları.</li>
        <li><strong>Pazarlama:</strong> reklam gösterimi sırasında Google tarafından işlenen çerez verileri.</li>
      </ul>

      <h2>3. İşleme amaçları ve hukuki sebepler</h2>
      <ul>
        <li>Üyelik ve hizmetin sunulması: bir sözleşmenin kurulması veya ifası (KVKK m. 5/2-c).</li>
        <li>Bilgi güvenliğinin sağlanması ve kötüye kullanımın önlenmesi: meşru menfaat (m. 5/2-f) ve hukuki yükümlülük (m. 5/2-ç).</li>
        <li>Hizmetin geliştirilmesi için anonim istatistikler: meşru menfaat (m. 5/2-f).</li>
        <li>Kişiselleştirilmiş reklam gösterimi: açık rıza (m. 5/1). Çerez bildiriminde “Kabul et” seçilmezse yalnızca kişiselleştirilmemiş reklam gösterilir.</li>
      </ul>

      <h2>4. Aktarım</h2>
      <p>
        Kişisel verileriniz, hizmetin sunulması için barındırma (Hetzner, Almanya), e-posta gönderimi
        (Resend) ve giriş/reklam hizmetleri (Google) sağlayıcılarına, KVKK'nın 8. ve 9. maddelerine uygun
        olarak yurt içine ve yurt dışına aktarılabilir. Yasal zorunluluk hâlinde yetkili kurumlarla paylaşılabilir.
      </p>

      <h2>5. Toplama yöntemi</h2>
      <p>Verileriniz, siteye kayıt olurken, giriş yaparken ve özellikleri kullanırken elektronik ortamda ve otomatik yollarla toplanır.</p>

      <h2>6. Haklarınız (KVKK m. 11)</h2>
      <ul>
        <li>Kişisel verilerinizin işlenip işlenmediğini öğrenme ve işlenmişse bilgi talep etme,</li>
        <li>İşlenme amacını ve amacına uygun kullanılıp kullanılmadığını öğrenme,</li>
        <li>Yurt içinde veya yurt dışında aktarıldığı üçüncü kişileri bilme,</li>
        <li>Eksik veya yanlış işlenmişse düzeltilmesini, şartları oluştuğunda silinmesini veya yok edilmesini isteme,</li>
        <li>Bu işlemlerin verilerin aktarıldığı üçüncü kişilere bildirilmesini isteme,</li>
        <li>Otomatik sistemlerle analiz edilmesi sonucu aleyhinize bir sonuca itiraz etme,</li>
        <li>Kanuna aykırı işleme nedeniyle zarara uğramanız hâlinde zararın giderilmesini talep etme.</li>
      </ul>
      <p>
        Taleplerinizi <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> adresine iletebilirsiniz.
        Talepler en geç 30 gün içinde ücretsiz olarak yanıtlanır.
      </p>
    </LegalPage>
  );
}

const COOKIE_KEY = "b2c:cookie-consent";       // "all" | "essential"
const COOKIE_EVENT = "b2c:cookie-consent";

/** Kişiselleştirilmiş reklama izin verildi mi? (ads.ts okur) */
export function personalizedAdsAllowed(): boolean {
  try { return localStorage.getItem(COOKIE_KEY) === "all"; } catch { return false; }
}

function resetCookieChoice() {
  try { localStorage.removeItem(COOKIE_KEY); } catch { /* yoksay */ }
  window.dispatchEvent(new Event(COOKIE_EVENT));
}

function storedChoice(): string {
  try { return localStorage.getItem(COOKIE_KEY) || ""; } catch { return ""; }
}

export function CookieNotice() {
  const [choice, setChoice] = useState(storedChoice);
  useEffect(() => {
    const sync = () => setChoice(storedChoice());
    window.addEventListener(COOKIE_EVENT, sync);
    return () => window.removeEventListener(COOKIE_EVENT, sync);
  }, []);
  if (choice) return null;
  const save = (value: "all" | "essential") => {
    try { localStorage.setItem(COOKIE_KEY, value); } catch { /* depolama yoksa sadece bu oturumda gizle */ }
    setChoice(value);
  };
  return (
    <div className="cookie-notice" role="region" aria-label="Çerez bildirimi">
      <p>
        Oturumunuzu açık tutmak için zorunlu çerezler kullanıyoruz. Reklamların ilgi alanlarınıza göre
        kişiselleştirilmesi için Google çerezlerine izin verebilirsiniz. Ayrıntılar: <Link to="/gizlilik">Gizlilik ve çerez politikası</Link>.
      </p>
      <div className="cookie-actions">
        <button type="button" className="secondary-button" onClick={() => save("essential")}>Sadece zorunlu</button>
        <button type="button" className="primary-button" onClick={() => save("all")}>Kabul et</button>
      </div>
    </div>
  );
}
