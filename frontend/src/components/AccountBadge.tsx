import { useEffect, useState } from "react";
import { fetchBilling } from "../api";
import { useAuth } from "../auth/AuthProvider";

function remaining(iso: string, now: number) {
  const ms = Math.max(0, new Date(iso).getTime() - now);
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return { ms, label: `${m}:${String(s).padStart(2, "0")}` };
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
  const empty = billing.total_credits === 0;
  return (
    <button type="button" className={`account-badge plan-${billing.plan}`} onClick={onOpen} title="Profil ve plan">
      <span className="account-plan">{billing.plan_name}</span>
      <span className={`account-credits${empty ? " empty" : ""}`}>
        <b>{billing.total_credits}</b> kredi
        {billing.extra_credits > 0 && <small>+{billing.extra_credits} ek</small>}
      </span>
      {billing.credits < billing.quota && left && (
        <span className="account-reset" title="Plan kredilerinin yenilenmesine kalan süre">↻ {left.label}</span>
      )}
    </button>
  );
}
