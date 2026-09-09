"""Kural/anahtar-kelime tabanlı ilan açıklaması kalite skoru.

LLM DEĞİL -- Galeri/llm_analiz.py'deki LLM tabanlı yaklaşımın aksine, bu
modül sadece metin içinde belirli ifadelerin geçip geçmediğine, uzunluğa ve
basit yazım kalıplarına (TAMAMI BÜYÜK HARF, aşırı ünlem) bakan saf Python.
Dış bağımlılık yok, "Galerimi Analiz Et" akışında her ilan açıklaması için
çağrılır (bkz. Backend/search/tasks.py run_galeri_tekil_analiz).

score_description() döndürdüğü skor 1-10 arası, ayrıca hangi sinyallerin
bulunduğu (positives/negatives) ve somut iyileştirme önerileri (suggestions)
de dönüyor.
"""

from __future__ import annotations

import re

# ── Kelime listeleri ─────────────────────────────────────────────────────────

GUVEN_KELIMELERI = [
    "hasarsız", "hasar kaydı yok", "boyasız", "orjinal", "orijinal",
    "garantili", "garanti", "takas olur", "takasa açık", "bakımlı",
    "bakımları yetkili serviste", "kaza kaydı yok", "değişensiz",
    "değişeni yok", "tramer kaydı", "tramersiz", "ekspertiz raporlu",
    "ekspertizli", "sıfır ayarında", "ilk sahibinden", "tek sahibinden",
    "km si gerçek", "gerçek km", "kredi imkanı", "senetli", "bakımları tam",
    "değişen yok", "boyalı değil",
]

CTA_KELIMELERI = [
    "detaylı bilgi için", "bilgi için arayınız", "arayabilirsiniz",
    "whatsapp", "watsapp", "cep telefonu", "irtibat", "iletişime geçebilirsiniz",
    "randevu için", "test sürüşü",
]

KIRMIZI_BAYRAK_KELIMELERI = [
    "acil satılık", "acil", "pişman olmazsınız", "kelepir", "fırsat kaçmaz",
    "bugüne özel", "acil nakit ihtiyacı", "acil param lazım", "kaçmaz fırsat",
    "tek fiyat", "pazarlık yok kesin",
]

_PHONE_RE = re.compile(r"\b0?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b")


def _count_hits(text_lower: str, keywords: list[str]) -> list[str]:
    return [kw for kw in keywords if kw in text_lower]


def _caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    upper = [c for c in letters if c.isupper()]
    return len(upper) / len(letters)


def score_description(description: str) -> dict:
    """Returns {"score": int(1-10), "positives": [...], "negatives": [...], "suggestions": [...]}"""
    text = (description or "").strip()
    positives: list[str] = []
    negatives: list[str] = []
    suggestions: list[str] = []

    # ── Boş açıklama: erken çık ──────────────────────────────────────────
    if not text:
        return {
            "score": 1,
            "positives": [],
            "negatives": ["Açıklama tamamen boş."],
            "suggestions": [
                "İlana en az birkaç cümlelik bir açıklama ekleyin: bakım durumu, "
                "hasar/tramer bilgisi, donanım ve neden bu aracın tercih edilmesi "
                "gerektiği gibi bilgiler alıcı güvenini artırır.",
            ],
        }

    text_lower = text.lower()
    length = len(text)

    # ── 1) Uzunluk / bilgi yoğunluğu -- taban puan ───────────────────────
    item_markers = len(re.findall(r"[,•\-–\n]", text))
    if length < 50:
        base = 2
        negatives.append("Açıklama çok kısa (50 karakterden az).")
        suggestions.append("Açıklamayı genişletin: km, bakım, hasar durumu, donanım gibi somut bilgiler ekleyin.")
    elif length < 150:
        base = 4
    else:
        base = 6
        if item_markers >= 4:
            base = 7
            positives.append("Açıklama detaylı ve bilgi yoğun.")

    score = base

    # ── 2) Güven/satış artırıcı kelimeler ────────────────────────────────
    guven_hits = _count_hits(text_lower, GUVEN_KELIMELERI)
    if guven_hits:
        bonus = min(2, len(guven_hits))
        score += bonus
        positives.append(f"Güven verici ifadeler kullanılmış: {', '.join(guven_hits[:5])}.")
    else:
        suggestions.append(
            "\"Hasarsız\", \"garantili\", \"bakımlı\", \"kaza kaydı yok\" gibi güven verici "
            "ifadeler ekleyin."
        )

    # ── 3) İletişim/CTA ifadeleri ────────────────────────────────────────
    cta_hits = _count_hits(text_lower, CTA_KELIMELERI)
    phone_matches = _PHONE_RE.findall(text)
    if cta_hits:
        score += 1
        positives.append("İletişime teşvik eden bir ifade var.")
    elif not phone_matches:
        suggestions.append("\"Detaylı bilgi için arayabilirsiniz\" gibi bir iletişim çağrısı ekleyin.")

    if len(phone_matches) >= 3:
        # Aynı numaranın/numaraların 3+ kez tekrarı spam sinyali.
        score -= 1
        negatives.append("Telefon numarası metinde aşırı tekrar ediyor (spam görünümü).")
        suggestions.append("Telefon numarasını açıklama içinde tekrar tekrar yazmak yerine bir kez belirtin.")

    # ── 4) Kırmızı bayrak ifadeler + yazım kalitesi ──────────────────────
    red_hits = _count_hits(text_lower, KIRMIZI_BAYRAK_KELIMELERI)
    if red_hits:
        score -= min(3, len(red_hits))
        negatives.append(f"Güven azaltıcı/klişe ifadeler var: {', '.join(red_hits[:5])}.")
        suggestions.append("\"Acil\", \"kelepir\", \"fırsat kaçmaz\" gibi klişe ifadeler yerine somut bilgi verin.")

    caps_ratio = _caps_ratio(text)
    if caps_ratio > 0.6 and length >= 20:
        score -= 2
        negatives.append("Açıklamanın büyük bölümü BÜYÜK HARFLE yazılmış.")
        suggestions.append("Büyük harfle yazmak yerine normal cümle yapısı kullanın; okunabilirliği artırır.")

    exclaim_count = text.count("!") + text.count("?")
    if exclaim_count >= 5:
        score -= 1
        negatives.append("Aşırı sayıda ünlem/soru işareti kullanılmış.")

    score = max(1, min(10, round(score)))

    if not suggestions and score >= 8:
        suggestions.append("Açıklama iyi durumda; küçük güncellemelerle (güncel km, yeni bakım kaydı) tazelenebilir.")

    return {
        "score": score,
        "positives": positives,
        "negatives": negatives,
        "suggestions": suggestions,
    }
