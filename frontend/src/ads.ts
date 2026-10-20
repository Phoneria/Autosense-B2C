// Ödüllü reklam (Google Ad Manager / GPT "rewarded"). Backend bir işlem için
// 402 + code="ad_required" döndüğünde http.ts burayı çağırır; reklam sonucu
// sunucuya bildirilir, sonra istek tekrarlanır. Bkz. backend/search/ad_gate.py.
//
// Reklam yüklenemezse (envanter yok, reklam engelleyici, hata) kullanıcı
// engellenmez: sonuç "no_fill"/"error" olarak bildirilir ve işlem devam eder.
// Çerez bildiriminde "Kabul et" seçilmediyse kişiselleştirilmemiş reklam istenir.
import { personalizedAdsAllowed } from "./pages/PublicPages";

export type AdOutcome = "completed" | "no_fill" | "error" | "dismissed";
export interface AdInfo { ad_unit_path?: string; action?: string }

type Googletag = {
  cmd: Array<() => void>;
  pubads: () => {
    setPrivacySettings: (settings: { nonPersonalizedAds?: boolean }) => void;
    addEventListener: (name: string, cb: (event: any) => void) => void;
    removeEventListener?: (name: string, cb: (event: any) => void) => void;
  };
  defineOutOfPageSlot: (path: string, format: unknown) => any | null;
  destroySlots: (slots: any[]) => boolean;
  display: (slot: any) => void;
  enableServices: () => void;
  enums: { OutOfPageFormat: { REWARDED: unknown } };
};

const GPT_SRC = "https://securepubads.g.doubleclick.net/tag/js/gpt.js";
const LOAD_TIMEOUT_MS = 8000;
let gptLoading: Promise<Googletag> | null = null;

function loadGpt(): Promise<Googletag> {
  if (gptLoading) return gptLoading;
  gptLoading = new Promise<Googletag>((resolve, reject) => {
    const w = window as unknown as { googletag?: Googletag };
    w.googletag = w.googletag || ({ cmd: [] } as unknown as Googletag);
    const script = document.createElement("script");
    script.src = GPT_SRC;
    script.async = true;
    script.onload = () => resolve(w.googletag as Googletag);
    script.onerror = () => { gptLoading = null; reject(new Error("gpt")); };
    document.head.appendChild(script);
  });
  return gptLoading;
}

function overlay(text: string, button?: { label: string; onClick: () => void }) {
  const box = document.createElement("div");
  box.className = "ad-gate-overlay";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-live", "polite");
  const card = document.createElement("div");
  card.className = "ad-gate-card";
  const p = document.createElement("p");
  p.textContent = text;
  card.appendChild(p);
  if (button) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "primary-button";
    b.textContent = button.label;
    b.onclick = button.onClick;
    card.appendChild(b);
  }
  box.appendChild(card);
  document.body.appendChild(box);
  return () => box.remove();
}

/** Ödüllü reklamı oynatır ve sonucunu döndürür. Asla hata fırlatmaz. */
export async function playRewardedAd(info: AdInfo): Promise<AdOutcome> {
  const path = info.ad_unit_path || "";
  if (!path) return "no_fill";
  const close = overlay("Sonucunuz hazırlanıyor. Kısa bir reklamdan sonra devam edeceksiniz…");
  try {
    const googletag = await loadGpt();
    return await new Promise<AdOutcome>((resolve) => {
      let slot: any = null;
      let granted = false;
      let done = false;
      const finish = (outcome: AdOutcome) => {
        if (done) return;
        done = true;
        window.clearTimeout(timer);
        try { if (slot) googletag.destroySlots([slot]); } catch { /* yoksay */ }
        resolve(outcome);
      };
      const timer = window.setTimeout(() => finish("no_fill"), LOAD_TIMEOUT_MS);
      googletag.cmd.push(() => {
        slot = googletag.defineOutOfPageSlot(path, googletag.enums.OutOfPageFormat.REWARDED);
        if (!slot) { finish("no_fill"); return; }    // tarayıcı/sayfa bu formatı desteklemiyor
        slot.addService(googletag.pubads());
        const pubads = googletag.pubads();
        pubads.setPrivacySettings({ nonPersonalizedAds: !personalizedAdsAllowed() });
        pubads.addEventListener("rewardedSlotReady", (e: any) => {
          if (e.slot !== slot) return;
          window.clearTimeout(timer);
          e.makeRewardedVisible();
        });
        pubads.addEventListener("rewardedSlotGranted", (e: any) => {
          if (e.slot === slot) granted = true;
        });
        pubads.addEventListener("rewardedSlotClosed", (e: any) => {
          if (e.slot === slot) finish(granted ? "completed" : "dismissed");
        });
        pubads.addEventListener("slotRenderEnded", (e: any) => {
          if (e.slot === slot && e.isEmpty) finish("no_fill");
        });
        googletag.enableServices();
        googletag.display(slot);
      });
    });
  } catch {
    return "error";
  } finally {
    close();
  }
}

/** Reklam yarıda kapatıldığında kullanıcıya tekrar deneme şansı verir. */
export function askRetry(): Promise<boolean> {
  return new Promise((resolve) => {
    const close = overlay("Devam etmek için reklamı sonuna kadar izlemeniz gerekiyor.", {
      label: "Reklamı tekrar izle",
      onClick: () => { close(); resolve(true); },
    });
    // Arka plana tıklayınca vazgeç.
    const el = document.querySelector(".ad-gate-overlay:last-of-type");
    el?.addEventListener("click", (ev) => { if (ev.target === el) { close(); resolve(false); } });
  });
}
