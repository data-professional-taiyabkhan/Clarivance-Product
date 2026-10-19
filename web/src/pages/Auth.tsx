import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";

export function SignIn() {
  const { setMe } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { setMe(await api.login(email, password)); nav("/app"); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="authbox card">
      <h1>Sign in</h1>
      <form onSubmit={submit}>
        <label>Email<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {err && <p className="errtext">{err}</p>}
        <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="muted">New to the pilot? <Link to="/register">Create an account</Link></p>
    </div>
  );
}

export function Register() {
  const { setMe, inviteRequired } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", password: "", invite_code: "", accept_terms: false });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { setMe(await api.register(f)); nav("/app/profile?welcome=1"); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="authbox card">
      <h1>Join the pilot</h1>
      <p className="muted">Upload a bank statement and see what's safe to spend after tax. No bank login needed.</p>
      <form onSubmit={submit}>
        <label>Your name<input autoComplete="name" value={f.name} onChange={set("name")} /></label>
        <label>Email<input type="email" autoComplete="email" required value={f.email} onChange={set("email")} /></label>
        <label>Password <span className="hint">(at least 10 characters)</span>
          <input type="password" autoComplete="new-password" required minLength={10} value={f.password} onChange={set("password")} /></label>
        {inviteRequired && <label>Invite code<input required value={f.invite_code} onChange={set("invite_code")} /></label>}
        <label className="check">
          <input type="checkbox" checked={f.accept_terms} onChange={set("accept_terms")} />
          <span>I understand this is a pilot. Clarivance stores the statements I upload to calculate my figures, I can delete my data at any
            time, and the figures are estimates, not tax advice. <a href="https://clarivanceai.co.uk/privacy" target="_blank" rel="noreferrer">Privacy policy</a></span>
        </label>
        {err && <p className="errtext">{err}</p>}
        <button disabled={busy || !f.accept_terms}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <p className="muted">Already have an account? <Link to="/signin">Sign in</Link></p>
    </div>
  );
}
