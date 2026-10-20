// Kaydırdıkça beliriş: kök içindeki [data-reveal] öğeleri ekrana girince "rv-in" sınıfını alır.
// JS yoksa, IntersectionObserver desteklenmiyorsa veya kullanıcı azaltılmış hareket istiyorsa
// içerik hiç gizlenmez (kök "rv-on" sınıfını almaz).
import { useLayoutEffect, useRef, useState } from "react";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

function canAnimate(): boolean {
  return typeof IntersectionObserver !== "undefined" && !prefersReducedMotion();
}

export function useScrollReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  // İlk boyamadan önce çalışır; böylece içerik bir an görünüp kaybolmaz.
  useLayoutEffect(() => {
    const root = ref.current;
    if (!root || !canAnimate()) return;
    const items = Array.from(root.querySelectorAll<HTMLElement>("[data-reveal]"));
    root.classList.add("rv-on");
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          e.target.classList.add("rv-in");
          io.unobserve(e.target);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
    items.forEach((el) => io.observe(el));
    return () => {
      io.disconnect();
      root.classList.remove("rv-on");
      items.forEach((el) => el.classList.remove("rv-in"));
    };
  }, []);
  return ref;
}

/** Ekrana girince 0'dan hedef sayıya sayar. Ekran okuyucu her zaman son değeri okur. */
export function CountUp({ to, prefix = "", suffix = "", duration = 1200 }: { to: number; prefix?: string; suffix?: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [value, setValue] = useState(to);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !canAnimate()) return;
    let frame = 0;
    setValue(0);
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry?.isIntersecting) return;
        io.disconnect();
        const start = performance.now();
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / duration);
          setValue(Math.round(to * (1 - Math.pow(1 - t, 3))));
          if (t < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(frame); setValue(to); };
  }, [to, duration]);
  return (
    <>
      <span ref={ref} className="rv-count" aria-hidden="true">{prefix}{value}{suffix}</span>
      <span className="sr-only">{prefix}{to}{suffix}</span>
    </>
  );
}
