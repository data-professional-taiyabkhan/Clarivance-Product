import { useEffect, useMemo, useState } from "react";
import { api, type BusinessSummary, type Position } from "../api";
import Dashboard from "../components/Dashboard";
import { pct } from "../format";

export default function Demo() {
  const [list, setList] = useState<BusinessSummary[]>([]);
  const [key, setKey] = useState("dan");
  const [asOf, setAsOf] = useState("");
  const [confidence, setConfidence] = useState(0.8);
  const [pos, setPos] = useState<Position | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { api.businesses().then((r) => setList(r.businesses)).catch((e) => setErr(e.message)); }, []);
  const current = useMemo(() => list.find((b) => b.key === key), [list, key]);
  useEffect(() => { if (current) setAsOf(current.default_as_of); }, [current]);
  useEffect(() => {
    if (!asOf) return;
    api.position(key, asOf, confidence).then((p) => { setPos(p); setErr(null); }).catch((e) => setErr(e.message));
  }, [key, asOf, confidence]);

  return (
    <>
      <div className="toolbar">
        <div className="banner">Demo businesses with invented data. Every figure is an estimate, not tax advice.</div>
        <div className="controls">
          <label>Business
            <select value={key} onChange={(e) => setKey(e.target.value)}>
              {list.map((b) => <option key={b.key} value={b.key}>{b.name} · {b.trade}</option>)}
            </select>
          </label>
          <label>As of<input type="date" value={asOf} min={current?.trading_since} onChange={(e) => e.target.value && setAsOf(e.target.value)} /></label>
          <label>Reserve confidence
            <select value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}>
              {[0.7, 0.8, 0.9].map((c) => <option key={c} value={c}>{pct(c)}</option>)}
            </select>
          </label>
        </div>
      </div>
      {err && <div className="error">{err}</div>}
      {!pos ? <div className="loading">Working out the year…</div> : <Dashboard pos={pos} onWhatIf={(n) => api.whatIf(key, asOf, n)} />}
    </>
  );
}
