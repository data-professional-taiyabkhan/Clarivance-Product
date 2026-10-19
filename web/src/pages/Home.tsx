import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type Position } from "../api";
import { useAuth } from "../auth";
import Dashboard from "../components/Dashboard";

export default function Home() {
  const { me } = useAuth();
  const [pos, setPos] = useState<Position | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!me?.has_transactions) return;
    api.myPosition().then(setPos).catch((e: ApiError) => setErr(e.message));
  }, [me?.has_transactions]);

  if (!me?.has_transactions) {
    return (
      <section className="card onboarding">
        <h2>Let's get your figures</h2>
        <ol>
          <li className={me?.profile_done ? "done" : ""}><Link to="/app/profile">Fill in your tax profile</Link> (2 minutes: last year's bill and payments already made).</li>
          <li><Link to="/app/upload">Upload a bank statement</Link> as a CSV, ideally from 6 April last year to today.</li>
          <li>Check the categories, then come back here.</li>
        </ol>
      </section>
    );
  }
  if (err) return <div className="error">{err} <Link to="/app/upload">Upload a statement</Link></div>;
  if (!pos) return <div className="loading">Working out your year…</div>;
  return <Dashboard pos={pos} onWhatIf={api.myWhatIf} ownData />;
}
