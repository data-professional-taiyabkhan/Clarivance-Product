import { useCallback, useEffect, useState } from "react";
import { api, type TxnPage } from "../api";
import { gbp, day } from "../format";

export default function Transactions() {
  const [data, setData] = useState<TxnPage | null>(null);
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [similar, setSimilar] = useState(true);
  const [note, setNote] = useState<string | null>(null);
  const load = useCallback(() => api.transactions({ category, q, page }).then(setData), [category, q, page]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);

  const change = async (id: number, cat: string) => {
    const r = await api.setCategory(id, cat, similar);
    setNote(r.updated > 1 ? `Updated ${r.updated} transactions from the same payee.` : "Updated.");
    load();
  };
  const recheck = async () => {
    const r = await api.recategorise();
    setNote(r.changed ? `Re-checked: ${r.changed} transactions moved to a better category. Your own corrections were kept.` : "Re-checked: nothing needed changing.");
    load();
  };
  if (!data) return <div className="loading">Loading…</div>;
  return (
    <section className="card">
      <div className="cardhead">
        <h2>Check your transactions</h2>
        <span className="small muted">The forecast uses these categories. Fix anything that's wrong.</span>
      </div>
      <div className="chips">
        <button className={category === "" ? "on" : ""} onClick={() => { setCategory(""); setPage(1); }}>All</button>
        {Object.entries(data.categories).map(([k, label]) => (
          <button key={k} className={category === k ? "on" : ""} onClick={() => { setCategory(k); setPage(1); }}>
            {label.split(" (")[0]} <span>{data.summary[k]?.count ?? 0}</span>
          </button>))}
      </div>
      <div className="filters">
        <input placeholder="Search description or payee" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <label className="check"><input type="checkbox" checked={similar} onChange={(e) => setSimilar(e.target.checked)} /><span>Apply changes to other payments from the same payee</span></label>
        <button className="ghostbtn" onClick={recheck} title="Uses your profile name to spot money you moved in or out yourself">Re-check automatic categories</button>
      </div>
      {note && <p className="ok">{note}</p>}
      <div className="tablewrap">
        <table>
          <thead><tr><th>Date</th><th>Description</th><th className="num">Amount</th><th>Category</th></tr></thead>
          <tbody>{data.transactions.map((t) => (
            <tr key={t.id}>
              <td className="nowrap">{day(t.day)}</td>
              <td>{t.description}<div className="small muted">{t.client}</div></td>
              <td className={`num ${t.amount > 0 ? "pos" : ""}`}>{gbp(t.amount, 2)}</td>
              <td><select value={t.category} onChange={(e) => change(t.id, e.target.value)}>
                {Object.entries(data.categories).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </select>{t.user_edited && <span className="small muted"> ✓</span>}</td>
            </tr>))}</tbody>
        </table>
      </div>
      {data.pages > 1 && <div className="pager">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {data.pages}</span>
        <button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
      </div>}
    </section>
  );
}
