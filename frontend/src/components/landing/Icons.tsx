// Tanıtım sayfasındaki küçük çizgisel ikonlar (24×24, currentColor). Hepsi dekoratif.
import type { ReactNode } from "react";

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.7"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className="ld-icon">
      {children}
    </svg>
  );
}

/** İlan metni: satırlı belge */
export const IconDoc = () => <Icon><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 11h5M10 14h5M10 17h3" /></Icon>;
/** Senaryo: dallanan yol */
export const IconBranch = () => <Icon><circle cx="6" cy="6" r="2" /><circle cx="6" cy="18" r="2" /><circle cx="18" cy="9" r="2" /><path d="M6 8v8M6 12c0-3 3-3 6-3h4" /></Icon>;
/** Kronik sorun: anahtar */
export const IconWrench = () => <Icon><path d="M15 4a4 4 0 0 0-3.8 5.3L4 16.5 7.5 20l7.2-7.2A4 4 0 0 0 20 9l-2.5 2.5-3-3L17 6a4 4 0 0 0-2-2z" /></Icon>;
/** İlan fiyatı: etiket */
export const IconTag = () => <Icon><path d="M3 12V4h8l9 9-8 8z" /><circle cx="7.5" cy="8.5" r="1.3" /></Icon>;
/** Tahmin: aralık / yaklaşık */
export const IconRange = () => <Icon><path d="M4 12h16M4 8v8M20 8v8" /><path d="M9 10.5c1 .9 2 .9 3 0s2-.9 3 0" /></Icon>;
/** İlandan kalkan: dışarı çıkan ok */
export const IconExit = () => <Icon><path d="M10 4H5v16h5" /><path d="M14 8l4 4-4 4M18 12H9" /></Icon>;
/** Ekspertiz: büyüteç */
export const IconSearch = () => <Icon><circle cx="11" cy="11" r="6" /><path d="M20 20l-4.5-4.5" /></Icon>;
/** Galerici: bina/vitrin */
export const IconStore = () => <Icon><path d="M4 9l1.5-5h13L20 9" /><path d="M4 9h16v2a3 3 0 0 1-5.3 1.9A3 3 0 0 1 12 14a3 3 0 0 1-2.7-1.1A3 3 0 0 1 4 11z" /><path d="M5 14v6h14v-6" /></Icon>;
/** Bireysel alıcı: kişi */
export const IconUser = () => <Icon><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></Icon>;
/** Onay işareti */
export const IconCheck = () => <Icon><path d="M5 12.5l4.5 4.5L19 7" /></Icon>;
