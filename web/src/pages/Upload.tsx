import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Statement } from "../api";
import { useAuth } from "../auth";
import { day } from "../format";

const TEMPLATE = "Date,Description,Amount,Balance\n01/09/2026,Hartley Builders INV 1043,2600.00,8600.00\n03/09/2026,Screwfix,-212.40,8387.60\n";

export default function Upload() {
  const { refresh } = useAuth();
  const [list, setList] = useState<Statement[]>([]);
  const [businessOnly, setBusinessOnly] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const load = () => api.statements().then((r) => setList(r.statements));
  useEffect(() => { load(); }, []);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await api.upload(file, businessOnly);
      setMsg(`Imported ${r.imported} transactions from ${day(r.first_day)} to ${day(r.last_day)}${r.duplicates ? ` (${r.duplicates} already uploaded, skipped)` : ""}.`);
      await load(); await refresh();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); if (input.current) input.current.value = ""; }
  };
  const remove = async (id: number) => {
    if (!confirm("Delete this statement and its transactions?")) return;
    await api.deleteStatement(id); await load(); await refresh();
  };
  const sample = async () => {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await api.loadSample();
      setMsg(r.imported ? `Loaded the sample statement: ${r.imported} invented transactions.` : "The sample statement is already loaded.");
      await load(); await refresh();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const template = URL.createObjectURL(new Blob([TEMPLATE], { type: "text/csv" }));

  return (
    <section className="grid">
      <div className="card">
        <h2>Upload a bank statement</h2>
        <p className="muted">In your online banking, export transactions as <strong>CSV</strong>. Cover this tax year from 6 April; 12 to 24 months gives a better forecast. Uploading overlapping dates is fine: duplicates are skipped.</p>
        <label className="check">
          <input type="checkbox" checked={businessOnly} onChange={(e) => setBusinessOnly(e.target.checked)} />
          <span>This account is used only for the business (spending is treated as business costs unless it looks personal)</span>
        </label>
        <div className={`drop ${busy ? "busy" : ""}`} onClick={() => input.current?.click()}
          onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); onFile(e.dataTransfer.files[0]); }}>
          {busy ? "Reading your statement…" : "Drop a CSV here, or click to choose a file"}
          <input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => onFile(e.target.files?.[0])} />
        </div>
        {msg && <p className="ok">{msg} <Link to="/app/transactions">Check the categories →</Link></p>}
        {err && <p className="errtext">{err}</p>}
        <p className="small"><button className="ghostbtn" onClick={sample} disabled={busy}>No statement to hand? Use sample data</button></p>
        <p className="small muted">Works with Monzo, Starling, Lloyds, Halifax, Barclays, NatWest, HSBC, Nationwide, Revolut, Tide and most others.
          If yours doesn't read, use <a href={template} download="clarivance-template.csv">this template</a>.</p>
      </div>
      <div className="card">
        <h3>Your statements</h3>
        {list.length === 0 ? <p className="muted">None yet.</p> :
          <table><tbody>{list.map((s) => (
            <tr key={s.id}><td>{s.filename}<div className="small muted">{day(s.first_day)} to {day(s.last_day)} · {s.imported} new{s.duplicates ? `, ${s.duplicates} duplicates` : ""}</div></td>
              <td className="num"><button className="link" onClick={() => remove(s.id)}>Delete</button></td></tr>))}</tbody></table>}
      </div>
    </section>
  );
}
