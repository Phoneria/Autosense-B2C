import { createContext, useContext } from "react";

/** Kilitli bölümlerdeki "yükselt" düğmeleri planı doğrudan değiştirmez:
 *  kullanıcıyı Profil sayfasına götürüp onay kutusunu açar. */
export const PlanChangeContext = createContext<(plan: "pro" | "premium") => void>(() => {});
export const useRequestPlan = () => useContext(PlanChangeContext);
