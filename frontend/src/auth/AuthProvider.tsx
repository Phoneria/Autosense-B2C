import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { authRequest, getMe } from "./api";
import type { User } from "./types";
import type { Billing } from "../types";
interface Auth { user: User | null; loading: boolean; error: string; reload: () => Promise<User | null>; logout: () => Promise<void>; setBilling: (billing: Billing) => void; }
const Context = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const reload = useCallback(async () => { const current = await getMe(); setUser(current); setError(""); return current; }, []);
  useEffect(() => { let active = true; getMe().then(current => { if (active) setUser(current); }).catch((e: Error) => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    const expire = () => { setUser(null); setError(""); };
    window.addEventListener("auth:expired", expire); window.addEventListener("auth:unverified", expire);
    return () => { active = false; window.removeEventListener("auth:expired", expire); window.removeEventListener("auth:unverified", expire); };
  }, []);
  useEffect(() => {
    if (!user) return;
    let active = true;
    let checking = false;
    const revalidate = async () => {
      if (document.visibilityState === "hidden" || checking) return;
      checking = true;
      try { const current = await getMe(); if (active) setUser(current); }
      catch { /* Temporary connectivity failures do not end a valid session. */ }
      finally { checking = false; }
    };
    const check = () => { void revalidate(); };
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", check);
    return () => { active = false; window.removeEventListener("focus", check); document.removeEventListener("visibilitychange", check); };
  }, [user?.id]);
  const setBilling = useCallback((billing: Billing) => { setUser(current => current ? { ...current, billing } : current); }, []);
  const logout = async () => { await authRequest("auth/session", undefined, "DELETE"); setUser(null); };
  return <Context.Provider value={{ user, loading, error, reload, logout, setBilling }}>{children}</Context.Provider>;
}
export function useAuth() { const value = useContext(Context); if (!value) throw new Error("AuthProvider gerekli"); return value; }
