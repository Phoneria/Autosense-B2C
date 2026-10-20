import { useEffect, useState } from "react";
import { fetchBilling } from "../api";
import { useAuth } from "../auth/AuthProvider";
import { isUnlimited, planLabel } from "../billingDisplay";

function remaining(iso: string, now: number) {
  const ms = Math.max(0, new Date(iso).getTime() - now);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return { ms, label: h > 0 ? `${h} sa ${m} dk` : `${m}:${String(s).padStart(2, "0")}` };
}

export default function AccountBadge({ onOpen }: { onOpen: () => void }) {
  const { user, setBilling } = useAuth();
  const billing = user?.billing;
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const left = billing ? remaining(billing.next_reset_at, now) : null;
  const due = !!left && left.ms === 0;

  useEffect(() => {
    if (!due) return;
    let active = true;
    const id = window.setTimeout(() => {
      fetchBilling().then((b) => { if (active) setBilling(b); }).catch(() => undefined);
    }, 800);
    return () => { active = false; window.clearTimeout(id); };
  }, [due, setBilling]);

  if (!billing) return null;
  const unlimited = isUnlimited(billing);
  const showCredits = !billing.open_access && !unlimited;
  const empty = showCredits && billing.total_credits === 0;
  return (
    <button type="button" className={`as-plan-badge plan-${billing.plan}`} onClick={onOpen}
      title="Hesap durumu ve plan" aria-label={`Hesap durumu: ${planLabel(billing.plan, billing.plan_name)} plan`}>
      <span className="as-plan-dot" aria-hidden="true" />
      <span className="as-plan-name">{planLabel(billing.plan, billing.plan_name)}</span>
      {unlimited && <span className="as-plan-credits is-unlimited">Sınırsız</span>}
      {showCredits && (
        <span className={`as-plan-credits${empty ? " empty" : ""}`}><b>{billing.total_credits}</b> kredi</span>
      )}
      {showCredits && billing.credits < billing.quota && left && (
        <span className="as-plan-reset" title="Günlük kredilerin yenilenmesine kalan süre">↻ {left.label}</span>
      )}
    </button>
  );
}
