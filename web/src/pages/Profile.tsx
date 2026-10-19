import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type Profile as P } from "../api";
import { useAuth } from "../auth";
import { pct } from "../format";

export default function Profile() {
  const { refresh, setMe } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [p, setP] = useState<P | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pw, setPw] = useState("");
  useEffect(() => { api.profile().then(setP); }, []);
  if (!p) return <div className="loading">Loading…</div>;
  const num = (k: keyof P) => (e: React.ChangeEvent<HTMLInputElement>) => setP({ ...p, [k]: e.target.value === "" ? null : Number(e.target.value) });
  const txt = (k: keyof P) => (e: React.ChangeEvent<HTMLInputElement>) => setP({ ...p, [k]: e.target.value });

  const save = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    try {
      setP(await api.saveProfile({ ...p, last_year_bill: p.last_year_bill ?? 0, paid_towards_this_year: p.paid_towards_this_year ?? 0, last_year_balance_owed: p.last_year_balance_owed ?? 0 }));
      await refresh(); setMsg("Saved."); if (params.get("welcome")) nav("/app/upload");
    } catch (x) { setErr((x as Error).message); }
  };
  const del = async () => {
    if (!confirm("Delete your account and every statement and transaction? This can't be undone.")) return;
    try { await api.deleteAccount(pw); setMe({ authenticated: false }); nav("/"); } catch (x) { setErr((x as Error).message); }
  };

  return (
    <section className="grid">
      <form className="card form" onSubmit={save}>
        <h2>{params.get("welcome") ? "Welcome. First, your tax profile" : "Your tax profile"}</h2>
        <p className="muted">These answers set your payments on account. If you're not sure, your last Self Assessment calculation (SA302) or HMRC online account has them.</p>
        <label>Your name<input value={p.name} onChange={txt("name")} /></label>
        <label>Business name<input value={p.business_name} onChange={txt("business_name")} /></label>
        <label>What you do<input placeholder="e.g. Electrician" value={p.trade} onChange={txt("trade")} /></label>
        <label>Self-employed since<input type="date" required value={p.trading_since} onChange={txt("trading_since")} /></label>
        <label>Last year's Self Assessment bill (£) <span className="hint">income tax + Class 4 NI for 2025-26; 0 if this is your first year</span>
          <input type="number" min="0" step="0.01" value={p.last_year_bill ?? ""} onChange={num("last_year_bill")} /></label>
        <label>Payments on account already made for 2026-27 (£) <span className="hint">usually paid 31 January and 31 July</span>
          <input type="number" min="0" step="0.01" value={p.paid_towards_this_year ?? ""} onChange={num("paid_towards_this_year")} /></label>
        <label>Balancing payment still owed for last year (£) <span className="hint">due 31 January; 0 if paid</span>
          <input type="number" min="0" step="0.01" value={p.last_year_balance_owed ?? ""} onChange={num("last_year_balance_owed")} /></label>
        <label>Current bank balance (£) <span className="hint">only if your statement has no balance column</span>
          <input type="number" step="0.01" value={p.cash_override ?? ""} onChange={num("cash_override")} /></label>
        <label>How cautious should your tax pot be?
          <select value={p.confidence} onChange={(e) => setP({ ...p, confidence: Number(e.target.value) })}>
            {[0.7, 0.8, 0.9].map((c) => <option key={c} value={c}>{pct(c)} of likely outcomes covered{c === 0.8 ? " (recommended)" : ""}</option>)}
          </select></label>
        {err && <p className="errtext">{err}</p>}
        {msg && <p className="ok">{msg}</p>}
        <button>Save{params.get("welcome") ? " and upload a statement" : ""}</button>
      </form>
      <div className="card">
        <h3>Your data</h3>
        <p className="muted">Download everything we hold about you, or delete your account and all your statements and transactions.</p>
        <p><a className="btn ghost" href="/api/me/export">Download my data</a></p>
        <label>Password to confirm deletion<input type="password" value={pw} onChange={(e) => setPw(e.target.value)} /></label>
        <button className="danger" disabled={!pw} onClick={del}>Delete my account</button>
      </div>
    </section>
  );
}
