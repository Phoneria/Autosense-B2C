"""
listing_url_lookup.py
======================
"Araç Fiyat Tahmini" sayfasındaki "arabam.com linkinden doldur" özelliği
için: tek bir arabam.com ilan detay URL'ini açıp sayfanın TÜM görünür
metnini (document.body.innerText) çekip, o düz metni satır satır parse
ederek formu doldurmak için gereken marka/seri/motor/paket slug'ları +
yıl/km/vites/hasar bilgisini döner.

Neden innerText parse, neden tek tek CSS selector değil:
arabam.com'un class isimleri (örn. "property-key"/"property-value")
zaman içinde değişebiliyor -- önceki sürüm fetch_data.scrape_detail()'i
(selector bazlı) kullanıyordu ve production'da "İlan sayfası okunamadı"
hatası aldı. Sayfanın kullanıcıya görünen düz metni ("Yıl\\n2023\\n
Kilometre\\n159.000 km\\n...") CSS sınıflarından çok daha kararlı --
kullanıcının tarayıcıda gördüğü şey zaten budur. Bu modül o metni,
kullanıcının bu özelliği isterken referans olarak yapıştırdığı gerçek bir
ilan sayfası çıktısına göre parse ediyor (bkz. PARSE ŞEMASI aşağıda).

PARSE ŞEMASI (arabam.com ilan detay sayfası innerText'inde gözlemlenen):

  Marka
  Fiat
  Seri
  Egea
  Model
  1.3 Multijet Easy
  Yıl
  2023
  Kilometre
  159.000 km
  Vites Tipi
  Düz
  ...

  -- üstteki "özet" blok: Label\\nValue çiftleri ardışık satırlarda.
  Aynı format "Genel Bakış" ve "Motor ve Performans" bölümlerinde de
  tekrarlanıyor (daha fazla alan, örn. Silindir Sayısı/Motor Hacmi/
  Motor Gücü) -- bu yüzden TÜM sayfada bilinen etiketleri arayıp bir
  sonraki satırı değer olarak alan tek bir genel LABEL->sonraki-satır
  eşleştiricisi kullanılıyor; hangi bölümde olduğu önemli değil.

  Boya, Değişen ve Tramer
  Orijinal
  Boyalı
  Lokal Boyalı
  Değişmiş
  Belirtilmemiş
  Orjinal
  Sağ Arka Çamurluk
  Arka Kaput
  ...
  Lokal boyalı
  -
  Boyalı
  -
  Değişmiş
  Sol Ön Çamurluk
  Belirtilmemiş
  -

  -- panel/hasar bloğu: "Boya, Değişen ve Tramer" başlığından sonra 5 sabit
  kategori satırı (Orijinal/Boyalı/Lokal Boyalı/Değişmiş/Belirtilmemiş) bu
  sırayla geçer, HER BİRİNİN ARDINDAN o kategorideki parça adları (virgülle
  değil, ayrı satırlarda) gelir, boşsa "-" görülür. Kategori sırası sabit
  olduğu için sırayla ilerleyip her kategori bloğunu bir sonraki bilinen
  kategori etiketine kadar (ya da "Tramer"e kadar) okuyoruz.
"""

import asyncio
import re
import threading

from .listing_identity import resolve_listing_identity


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
PAGE_TIMEOUT = 30_000

# CarDamageTemplate.tsx PARTS[].label -> id (frontend'deki tanımla birebir
# aynı olmalı -- bkz. frontend/src/components/filters/CarDamageTemplate.tsx).
_PART_LABEL_TO_ID = {
    "Ön Tampon": "on_tampon",
    "Sol Ön Çamurluk": "sol_on_camurluk",
    "Motor Kaputu": "motor_kaputu",
    "Sağ Ön Çamurluk": "sag_on_camurluk",
    "Sol Ön Kapı": "sol_on_kapi",
    "Tavan": "tavan",
    "Sağ Ön Kapı": "sag_on_kapi",
    "Sol Arka Kapı": "sol_arka_kapi",
    "Sağ Arka Kapı": "sag_arka_kapi",
    "Sol Arka Çamurluk": "sol_arka_camurluk",
    "Sağ Arka Çamurluk": "sag_arka_camurluk",
    # Sayfada "Arka Kaput" olarak geçiyor (fetch_data.py'nin eski
    # scrape_panel_data'sında da aynı isimle "arka_kaput" koluna eşleniyordu);
    # CarDamageTemplate.tsx'te aynı parça "Bagaj" etiketiyle gösteriliyor --
    # ikisi de aynı part_id'ye (arka_kaput) map'lenir.
    "Arka Kaput": "arka_kaput",
    "Bagaj": "arka_kaput",
    "Bagaj Kapağı": "arka_kaput",
    "Arka Tampon": "arka_tampon",
}

# Panel bloğundaki 5 sabit kategori başlığı, sayfadaki sırasıyla ->
# CarDamageTemplate.tsx DamageStatus değeri. "Belirtilmemiş" için form
# tarafında bir karşılık yok -- o kategoriye düşen parçalar atlanır
# (frontend zaten DEFAULT_MAP ile dolduruyor, olduğu gibi bırakılır).
#
# ÖNEMLİ: sayfada bu başlıklar İKİ FARKLI yazımla geçiyor -- üstteki
# "legend" satırlarında "Orijinal"/"Lokal Boyalı" (tam yazım), asıl veri
# bloğunun kendi alt-başlıklarında ise "Orjinal"/"Lokal boyalı" (i eksik,
# farklı büyük/küçük harf) görülüyor. Bu yüzden eşleştirme case-insensitive
# ve normalize edilmiş (Türkçe karakter foldlanmış) yapılıyor -- bkz. _norm.
_DAMAGE_CATEGORY_ORDER = [
    ("orijinal", "orijinal"),
    ("boyali", "boyali"),
    ("lokalboyali", "lokal_boyali"),
    ("degismis", "degismis"),
    ("belirtilmemis", None),
]


def _norm_label(s: str) -> str:
    """Kategori/parça etiketlerini kıyaslamak için normalize eder: küçük
    harfe çevirir, Türkçe karakterleri sadeleştirir, boşlukları atar."""
    s = s.strip().casefold().replace("\u0307", "")
    for a, b in (("ı", "i"), ("ğ", "g"), ("ş", "s"), ("ç", "c"), ("ö", "o"), ("ü", "u")):
        s = s.replace(a, b)
    return s.replace(" ", "")

# Özet/Genel Bakış/Motor ve Performans bloklarında aranan "Label -> sonraki
# satır = değer" eşleşmeleri. Birden fazla bölümde aynı etiket tekrar
# edebiliyor (örn. Yıl hem üst özet hem Genel Bakış'ta) -- ilk bulunan kabul
# edilir, aynı değeri taşıdıkları gözlemlendi.
_FIELD_LABELS = {
    "marka": ("Marka",),
    "seri": ("Seri",),
    "model": ("Model",),
    "yil": ("Yıl",),
    "kilometre": ("Kilometre", "KM"),
    "vites_tipi": ("Vites Tipi", "Vites"),
    "agir_hasar": ("Ağır Hasar Kayıtlı",),
    "fiyat": ("Fiyat",),
    "yakit": ("Yakıt / Motor Tipi", "Yakıt Tipi", "Yakıt"),
    "renk": ("Renk",),
    "il": ("İl",),
    "ilce": ("İlçe",),
}


class ListingLookupError(Exception):
    """Kullanıcıya doğrudan gösterilebilir, Türkçe bir hata mesajı taşır.

    raw_text: sayfa açılıp metin çekildi ama parse (marka bulma) başarısız
    olduysa, o ham metin buraya konur -- view bunu response'a ekler, frontend
    "Sayfa metni alındı" bildirimini yine gösterip kullanıcının en azından
    neyin okunduğunu görüp elle tamamlayabilmesini sağlar. Sayfa hiç
    açılamadıysa (network/timeout hatası) None kalır."""

    def __init__(self, message: str, raw_text: str | None = None):
        super().__init__(message)
        self.raw_text = raw_text


def _run_in_thread(coro, timeout: float = 45):
    """Playwright için izole event loop'ta çalıştır (Django/WSGI thread'inde
    zaten çalışan bir loop olabilir -- asyncio.run() doğrudan çakışabilir).
    similar_listings.py'deki aynı isimli fonksiyonla aynı desen."""
    result_holder: list = []
    error_holder: list = []

    def _target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_holder.append(loop.run_until_complete(coro))
        except Exception as e:
            error_holder.append(e)
        finally:
            loop.close()

    t = threading.Thread(target=_target)
    t.start()
    t.join(timeout=timeout)

    if error_holder:
        raise error_holder[0]
    if not result_holder:
        raise TimeoutError("İlan sayfası zaman aşımına uğradı.")
    return result_holder[0]


async def _fetch_page_text(url: str) -> str:
    """Sayfayı açıp document.body.innerText'ini döner -- tek tek elementleri
    okumak yerine kullanıcının tarayıcıda gördüğü düz metnin tamamı."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
            locale="tr-TR",
        )
        page = await context.new_page()
        try:
            # "networkidle" arabam.com'da reklam/analytics scriptlerinin
            # sürekli arka plan isteği atmasından dolayı hiç tetiklenmeyip
            # PAGE_TIMEOUT'a kadar beklenip zaman aşımına düşebiliyor --
            # "domcontentloaded" (DOM hazır, ağın tamamen susmasını beklemez)
            # + sabit bir ek bekleme ile aynı sonuca çok daha güvenilir
            # ulaşılıyor (fetch_data.py'nin sayfa listesi taramasında da
            # aynı seçim kullanılıyor, bkz. fetch_page_links).
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
            # Cookie/consent banner'ı kapatmayı dene -- açık kalırsa innerText'e
            # karışıp aşağıdaki parse'ı bozabilir. Best-effort, hata yutulur.
            try:
                btn = await page.wait_for_selector(
                    "button:has-text('Kabul Et')", timeout=3_000
                )
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(500)
            except Exception:
                pass
            await page.wait_for_timeout(2_500)
            return await page.evaluate("() => document.body.innerText")
        finally:
            await browser.close()


def _split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _find_field_values(lines: list[str]) -> dict:
    """Arabam'la Sahibinden'in iki metin düzenini birlikte okur.

    Arabam alanları genellikle ``Marka\\nBMW``, Sahibinden alanları ise
    ``Marka BMW`` biçimindedir. Etiketin tek başına olduğu durumda sonraki
    satırı, satırın başındaysa etiketin sağında kalan kısmı alır.
    """
    values = {key: "" for key in _FIELD_LABELS}
    label_to_key = {
        label.casefold(): key
        for key, labels in _FIELD_LABELS.items()
        for label in labels
    }
    labels_longest_first = sorted(
        ((label, key) for key, labels in _FIELD_LABELS.items() for label in labels),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for i, line in enumerate(lines):
        key = label_to_key.get(line.casefold())
        if key and not values[key] and i + 1 < len(lines):
            # Kendi kendine etiket olan bir sonraki satırı değer sanmayalım
            # (örn. "Model" hemen "Yıl" ile ardışıksa) -- değer satırı bilinen
            # bir başka etiketle birebir aynıysa atla, o zaman bu alan
            # sayfada boş bırakılmış demektir.
            nxt = lines[i + 1]
            if nxt.casefold() in label_to_key:
                continue
            values[key] = nxt
            continue

        for label, inline_key in labels_longest_first:
            if values[inline_key]:
                continue
            match = re.match(rf"^{re.escape(label)}\s*[:\-]?\s*(.+)$", line, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            # sahibinden.com'da etiket ve değer AYNI satırda, aralarında
            # boşluk olmadan geçiyor ("Yıl2011", "KM270.000", "RenkBeyaz").
            # Bu yüzden ayırıcı zorunlu değil; ama ayırıcı yoksa değerin
            # büyük harf ya da rakamla başlaması şartı aranıyor -- yoksa
            # "Marka" etiketi "Markalı ..." gibi bir kelimeyi de yakalardı.
            glued = re.match(rf"^{re.escape(label)}(?=\S)", line, re.IGNORECASE)
            if glued and not (value[:1].isdigit() or value[:1] != value[:1].lower()):
                continue
            values[inline_key] = value
            break
    return values


def _detect_source(lines: list[str]) -> str:
    head = "\n".join(lines[:80]).casefold()
    if "sahibinden.com" in head or "detaylı arama" in head:
        return "sahibinden.com"
    if "arabam.com" in head or "trink sat" in head:
        return "arabam.com"
    return "bilinmeyen"


def _extract_damage_map(lines: list[str]) -> dict:
    """"Boya, Değişen ve Tramer" bloğunu bulup parça-durum eşleşmelerini
    çıkarır. Blok içinde 5 sabit kategori başlığı (Orijinal/Boyalı/Lokal
    Boyalı/Değişmiş/Belirtilmemiş, bkz. _norm_label için yazım varyasyonları)
    tekrar tekrar geçer; her başlıktan sonraki satırlar bir sonraki bilinen
    kategori başlığına (veya "Tramer"e ya da bir sonraki büyük bölüm
    başlığına) kadar o kategorinin parçalarıdır. Boş kategoride "-" görülür.

    NOT: önceki sürüm başlıktan hemen sonra TAM SIRAYLA 5 legend satırı
    bekliyordu (Orijinal\\nBoyalı\\nLokal Boyalı\\n...) -- sayfada araya
    sayı/yüzde gibi ekstra metin girdiğinde veya sıra farklı olduğunda bu
    hiç eşleşmeyip damage_map'i tamamen boş bırakıyordu. Artık böyle sabit
    bir "legend" beklemiyoruz: başlıktan sonraki geniş bir pencerede kategori
    etiketlerini nerede geçerse geçsin arıyoruz."""
    # "Boya, Değişen ve Tramer" başlığı sayfada birden fazla geçebiliyor
    # (örn. üstteki menü/breadcrumb linki + asıl bölüm başlığı). Hangisinin
    # asıl veri bloğu olduğunu anlamak için: her adaydan sonraki 40 satırda
    # bilinen kategori etiketlerinden en az biri geçiyor mu diye bakıyoruz --
    # geçen ilk aday kabul edilir.
    status_by_norm = {_norm_label(label): status for label, status in _DAMAGE_CATEGORY_ORDER}
    header_idx = None
    for i, ln in enumerate(lines):
        if ln != "Boya, Değişen ve Tramer":
            continue
        lookahead = [_norm_label(x) for x in lines[i + 1:i + 1 + 40]]
        if any(x in status_by_norm for x in lookahead):
            header_idx = i
            break
    if header_idx is None:
        return {}

    # Blok sayfada kısa; 150 satır çok bolca pay (legend + veri + varyasyon).
    body = lines[header_idx + 1:header_idx + 1 + 150]

    damage_map: dict = {}
    current_status = None
    seen_any_category = False
    stop_headers = {_norm_label("Tramer Kaydı"), _norm_label("Tramer")}
    for ln in body:
        norm = _norm_label(ln)
        if norm in status_by_norm:
            current_status = status_by_norm[norm]
            seen_any_category = True
            continue
        if seen_any_category and norm in stop_headers:
            break
        if not seen_any_category:
            # İlk kategori başlığından önceki (legend/açıklama) satırları atla.
            continue
        if ln == "-" or not current_status:
            continue
        part_id = _PART_LABEL_TO_ID.get(ln)
        if part_id and part_id not in damage_map:
            damage_map[part_id] = current_status
    return damage_map


def _extract_sahibinden_damage_map(lines: list[str]) -> dict:
    """Sahibinden ekspertiz özetindeki açık parça listelerini okur."""
    header_status = {
        "lokalboyaliparcalar": "lokal_boyali",
        "boyaliparcalar": "boyali",
        "degisenparcalar": "degismis",
        "degismisparcalar": "degismis",
    }
    stop_headers = {
        "guvenlik", "icdonanim", "disdonanim", "multimedya",
        "eidsbilgileri", "ilandetaylari", "teknikozellikler", "aciklama",
    }
    part_by_norm = {_norm_label(label): part_id for label, part_id in _PART_LABEL_TO_ID.items()}
    damage_map: dict = {}
    current_status = None

    for line in lines:
        norm = _norm_label(line)
        if norm in header_status:
            current_status = header_status[norm]
            continue
        if current_status and norm in stop_headers:
            current_status = None
            continue
        if current_status and norm in part_by_norm:
            damage_map[part_by_norm[norm]] = current_status

    return damage_map


def _extract_int(raw: str):
    """'159.000 km' -> 159000, '2023' -> 2023, '' -> None."""
    digits = re.sub(r"[^\d]", "", raw or "")
    return int(digits) if digits else None


def _extract_gear(raw: str) -> str:
    """'Düz' -> 'Manuel', 'Otomatik'/'Yarı Otomatik' -> 'Otomatik'.
    PriceEstimatePage formunda üçüncü seçenek yok; tanınmayan/boş değerde
    'Manuel' varsayılan kalır, kullanıcı formu göndermeden düzeltebilir."""
    text = (raw or "").strip().lower()
    if "yarı otomatik" in text:
        return "Yarı Otomatik"
    if "otomatik" in text:
        return "Otomatik"
    return "Manuel"


def _extract_bool(raw: str) -> bool:
    return _norm_label(raw) in {"evet", "var", "mevcut", "agirhasarkayitli"}


# arabam.com'da konum, ilan basliginin hemen altinda ETIKETSIZ tek satirda
# gecer ("Fevzi Cakmak Mh. Esenler, Istanbul") -- "Il"/"Ilce" etiketi yoktur.
# Boyle bir satiri ancak son virgul parcasinin bilinen bir il olmasindan
# taniyabiliyoruz; bu yuzden 81 ilin listesi burada sabit tutuluyor (DB'siz de
# calismali). Yazim varyasyonlari _norm_label ile foldlanir.
_PROVINCES = {
    _norm_label(name): name
    for name in (
        "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara",
        "Antalya", "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman",
        "Bayburt", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa",
        "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Düzce", "Edirne",
        "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun",
        "Gümüşhane", "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul", "İzmir",
        "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri",
        "Kilis", "Kırıkkale", "Kırklareli", "Kırşehir", "Kocaeli", "Konya",
        "Kütahya", "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
        "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun",
        "Şanlıurfa", "Siirt", "Sinop", "Sivas", "Şırnak", "Tekirdağ", "Tokat",
        "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak",
    )
}
# Sayfada bazen kisaltilmis/eski adiyla gecen iller.
_PROVINCES.update({
    _norm_label("Afyon"): "Afyonkarahisar",
    _norm_label("Hakkâri"): "Hakkari",
    _norm_label("Maraş"): "Kahramanmaraş",
    _norm_label("Urfa"): "Şanlıurfa",
    _norm_label("İçel"): "Mersin",
})

# Konum satirinda ilcenin onune eklenen mahalle/koy ekleri -- ilce bunlarin
# SONRASINDA kalan kisimdir ("Fevzi Cakmak Mh. Esenler" -> "Esenler").
_NEIGHBOURHOOD_MARKERS = {"mah", "mh", "mahalle", "mahallesi", "mevkii", "koy", "koyu", "beldesi"}


def _strip_neighbourhood(segment: str) -> str:
    tokens = segment.split()
    marker = -1
    for i, token in enumerate(tokens):
        if _norm_label(token.strip(".")) in _NEIGHBOURHOOD_MARKERS:
            marker = i
    if marker < 0:
        return segment.strip(" .,")
    return " ".join(tokens[marker + 1:]).strip(" .,")


def _canonical_location(city: str, district: str) -> tuple[str, str]:
    """Okunan il/ilceyi formun acilir listesindeki yazimla eslestirir. Liste
    DB'den geldigi icin best-effort: erisilemezse okunan degerler aynen kalir
    (frontend eslesmeyen degeri zaten bos gosterir, kullanici elle secer)."""
    try:
        from .b2c import load_locations
        options = load_locations()
    except Exception:
        return city, district
    city_norm, district_norm = _norm_label(city), _norm_label(district)
    for option in options:
        if _norm_label(option.get("city", "")) != city_norm:
            continue
        city = option["city"]
        for known in option.get("districts", []):
            if _norm_label(known) == district_norm:
                return city, known
        return city, district
    return city, district


def _location_from_summary(summary: list[str]) -> tuple[str, str]:
    """Etiketsiz konum satirindan (il, ilce) cikarir; bulunamazsa ("", "")."""
    for line in summary:
        if len(line) > 80:
            continue
        parts = [part.strip() for part in line.split(",") if part.strip()]
        if len(parts) < 2:
            continue
        city = _PROVINCES.get(_norm_label(parts[-1]))
        if not city:
            continue
        return _canonical_location(city, _strip_neighbourhood(parts[-2]))
    return "", ""


def _extract_listing_details(page_text: str, lines: list[str], fields: dict) -> dict:
    # Only the listing summary may supply price/location. Description prices
    # can be repair bills or instalments, and breadcrumbs also contain slashes.
    summary = []
    for line in lines:
        if _norm_label(line) in {"aciklama", "ilandetaylari", "ozellikler"}:
            break
        summary.append(line)
    price = _extract_int(fields["fiyat"])
    city, district = fields["il"], fields["ilce"]
    for i, line in enumerate(summary):
        money = re.fullmatch(r"([0-9]+(?:[.\s][0-9]{3})*)(?:,00)?\s*(?:TL|₺)", line)
        if money and price is None:
            price = _extract_int(money.group(1))
        # Sahibinden places the location directly above the listing number.
        if re.match(r"^İlan No\b|^İlan No(?=\d|\s|:|$)", line, re.IGNORECASE) and i:
            parts = [part.strip() for part in summary[i - 1].split("/")]
            if len(parts) in (2, 3) and all(parts):
                city, district = parts[:2]

    # "Açıklama" sayfada birden fazla geçebiliyor: arabam.com'da önce sekme
    # menüsünde (Açıklama / Boya, Değişen ve Tramer / Araç Bilgileri / Donanım),
    # sonra asıl blokta. Menüdeki başlığın hemen ardından bir sonraki bölüm
    # başlığı geldiği için gövdesi boş çıkar -- bu yüzden ilk eşleşmeye
    # takılmayıp gövdesi anlamlı olan ilk bloğu alıyoruz.
    description = ""
    for start in re.finditer(r"^\s*Açıklama\s*$", page_text, re.MULTILINE | re.IGNORECASE):
        body = page_text[start.end():]
        end = re.search(
            r"^\s*(?:Özellikler|Boyalı veya Değişen Parça|Boya, Değişen ve Tramer|"
            r"Teknik Özellikler|Güvenlik|EİDS Bilgileri|Sponsorlu Bağlantı|"
            r"Araç Bilgileri|Donanım)\s*$",
            body, re.MULTILINE | re.IGNORECASE,
        )
        candidate = body[:end.start() if end else len(body)].strip()
        if not description:
            description = candidate
        if len(candidate) >= 20:
            description = candidate
            break

    if not city:
        city, district = _location_from_summary(summary)

    raw_fuel = fields["yakit"]
    fuel_norm = _norm_label(raw_fuel)
    # Mild hybrid still uses its stated combustion fuel for consumption.
    if "lpg" in fuel_norm:
        fuel = "LPG & Benzin"
    elif "hafifhibrit" in fuel_norm:
        fuel = "Dizel" if "dizel" in fuel_norm else "Benzin" if "benzin" in fuel_norm else "Hibrit"
    elif "hibrit" in fuel_norm or "hybrid" in fuel_norm:
        fuel = "Hibrit"
    else:
        fuel = next((name for name in ("Dizel", "Benzin", "Elektrik") if _norm_label(name) in fuel_norm), "")
    color = fields["renk"]
    if _norm_label(color) in {"gri", "gumus", "grigumus"}:
        color = "Gri / Gümüş"
    return {"price": price, "city": city, "district": district,
            "fuel": fuel, "fuel_raw": raw_fuel, "color": color, "description": description}


def validate_listing_url(url: str) -> str:
    """URL'yi normalize eder, geçersizse ListingLookupError fırlatır. Hem
    doğrudan lookup hem relay (job oluşturma) yolunda ilk adım olarak kullanılır."""
    url = (url or "").strip()
    if not url.startswith("https://www.arabam.com/ilan/"):
        raise ListingLookupError(
            "Geçerli bir arabam.com ilan linki girin (https://www.arabam.com/ilan/... ile başlamalı)."
        )
    return url


def parse_listing_page_text(url: str, page_text: str) -> dict:
    """Sayfanın (yerel runner'dan gelen ya da doğrudan çekilen) innerText'ini
    parse ederek lookup_listing_for_estimate ile aynı şemayı döner. Fetch
    adımından ayrı tutulur çünkü relay modunda metni Monster üzerindeki
    listing_lookup_runner.py çekiyor -- parse her zaman sunucuda kalır."""
    lines = _split_lines(page_text)
    if len(page_text.strip()) < 40:
        raise ListingLookupError("Yapıştırılan ilan metni çok kısa. İlan sayfasının tamamını kopyalayıp tekrar deneyin.")

    source = _detect_source(lines)
    field_lines = lines
    if source == "sahibinden.com":
        # Seller prose and equipment menus are not structured vehicle fields.
        end = next((i for i, line in enumerate(lines)
                    if _norm_label(line) in {"ilandetaylari", "aciklama", "ozellikler"}), len(lines))
        field_lines = lines[:end]
    fields = _find_field_values(field_lines)

    marka = fields["marka"]
    seri = fields["seri"]
    model = fields["model"]  # motor+paket birleşik, örn. "1.3 Multijet Easy"

    guess, warnings = resolve_listing_identity(fields, field_lines)
    if not guess.get("brand_slug"):
        raise ListingLookupError(
            "Metinden araç bilgisi okunamadı. arabam.com veya sahibinden.com ilan sayfasının tamamını kopyaladığınızdan emin olun.",
            raw_text=page_text,
        )
    tam_isim = " ".join(p for p in (marka, seri, model) if p).strip()

    # Sayfanın en üstündeki ilan başlığı (kullanıcıya "şunu okuduk" göstermek
    # için) -- innerText'te genelde ilk birkaç satır arasında, "Fiyat"
    # etiketinden önce geçiyor. Bulamazsak tam_isim'e düşer.
    title = tam_isim
    if "Fiyat" in lines:
        idx = lines.index("Fiyat")
        # Fiyat'tan önceki, breadcrumb (Otomobil/Marka/Seri/Model) sonrası
        # ilk uzunca satır genelde ilan başlığıdır.
        for ln in lines[max(0, idx - 6):idx]:
            if len(ln) > 20 and ln not in (marka, seri, model):
                title = ln
                break
    elif source == "sahibinden.com":
        try:
            candidate = lines[lines.index("Karşılaştır") + 1]
            title = re.split(r"Favorilerime Ekle|Yazdır|Facebook", candidate)[0].strip() or title
        except (ValueError, IndexError):
            pass

    damage_map = (
        _extract_sahibinden_damage_map(lines)
        if source == "sahibinden.com"
        else _extract_damage_map(lines)
    )

    return {
        "warnings": warnings,
        "matched": bool(guess.get("matched")),
        "category": guess.get("category", "otomobil"),
        "brand_slug": guess.get("brand_slug", ""),
        "series_slug": guess.get("series_slug", ""),
        "engine_slug": guess.get("engine_slug", ""),
        "variant_slug": guess.get("variant_slug", ""),
        "brand_name": guess.get("brand_name", ""),
        "series_name": guess.get("series_name", ""),
        "engine_name": guess.get("engine_name", ""),
        "variant_name": guess.get("variant_name", ""),
        **_extract_listing_details(page_text, lines, fields),
        "year": _extract_int(fields["yil"]),
        "km": _extract_int(fields["kilometre"]),
        "gear": _extract_gear(fields["vites_tipi"]),
        "agir_hasar": _extract_bool(fields["agir_hasar"]),
        "damage_map": damage_map,
        "title": title,
        "source": source,
        # Sayfadan çekilen ham metnin tamamı -- frontend'de "sayfa metni
        # alındı" bildirimine tıklanınca doğrulama amaçlı gösteriliyor
        # (bkz. PriceEstimatePage.tsx). Parse hatalı/eksik çıksa bile
        # kullanıcı neyin okunduğunu görüp kendisi tamamlayabiliyor.
        "raw_text": page_text,
    }


def parse_pasted_listing_text(page_text: str) -> dict:
    """Kullanıcının tarayıcıdan kopyaladığı ilan metnini parse eder."""
    return parse_listing_page_text("pasted-text", page_text)


def lookup_listing_for_estimate(url: str) -> dict:
    """Doğrudan (server-side) fetch + parse. Production'da arabam.com ilan
    sayfaları Cloudflare tarafından datacenter IP'lere kapatıldığı için bu
    yol sunucuda pratikte hep ListingLookupError fırlatır -- gerçek akış
    search/services/listing_lookup_relay.py üzerinden Monster'a devrediyor.
    Yine de yerelde (geliştirici makinesinde / ileride residential IP'den
    çalışacak bir sunucuda) çalışabilsin diye fonksiyon burada kalıyor."""
    url = validate_listing_url(url)

    try:
        page_text = _run_in_thread(_fetch_page_text(url))
    except TimeoutError:
        raise ListingLookupError("İlan sayfası zaman aşımına uğradı. Birkaç saniye sonra tekrar deneyin.")
    except Exception as e:
        import traceback
        print(f"[listing_url_lookup] _fetch_page_text HATASI ({url}): {e}")
        traceback.print_exc()
        msg = str(e)
        if any(s in msg for s in ("ERR_CONNECTION_RESET", "net::", "ERR_CONNECTION", "ERR_NAME_NOT_RESOLVED")):
            raise ListingLookupError(
                "arabam.com bağlantıyı sıfırladı. Birkaç saniye bekleyip tekrar deneyin."
            )
        raise ListingLookupError("İlan sayfası okunamadı. Linki kontrol edip tekrar deneyin.")

    return parse_listing_page_text(url, page_text)
