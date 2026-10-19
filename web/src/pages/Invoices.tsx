import { useEffect, useState, type FormEvent } from "react";
import { api, type OpenInvoice } from "../api";
import { day, gbp } from "../format";

export default function Invoices() {
  const [list, setList] = useState<OpenInvoice[]>([]);
  const [f, setF] = useState({ client: "", reference: "", issued: "", amount: "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.invoices().then((r) => setList(r.invoices)); }, []);
  const add = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    try { setList((await api.addInvoice({ ...f, amount: Number(f.amount) })).invoices); setF({ client: "", reference: "", issued: "", amount: "" }); }
    catch (x) { setErr((x as Error).message); }
  };
  const remove = async (id: number) => { await api.deleteInvoice(id); setList((await api.invoices()).invoices); };
  return (
    <section className="grid">
      <div className="card">
        <h2>Invoices not yet paid</h2>
        <p className="muted">Your bank statement only shows money once it arrives. Add invoices you've sent but haven't been paid for, so the forecast and the "chase it" actions include them. Delete one once it's paid.</p>
        <form className="inline" onSubmit={add}>
          <label>Client<input required value={f.client} onChange={(e) => setF({ ...f, client: e.target.value })} /></label>
          <label>Reference<input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} /></label>
          <label>Date sent<input type="date" required value={f.issued} onChange={(e) => setF({ ...f, issued: e.target.value })} /></label>
          <label>Amount (£)<input type="number" min="0.01" step="0.01" required value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></label>
          <button>Add</button>
        </form>
        {err && <p className="errtext">{err}</p>}
      </div>
      <div className="card">
        <h3>Waiting to be paid</h3>
        {list.length === 0 ? <p className="muted">None.</p> :
          <table><tbody>{list.map((i) => (
            <tr key={i.id}><td>{i.client}{i.reference && <span className="small muted"> · {i.reference}</span>}<div className="small muted">sent {day(i.issued)}</div></td>
              <td className="num">{gbp(i.amount, 2)}</td><td className="num"><button className="link" onClick={() => remove(i.id)}>Paid / remove</button></td></tr>))}</tbody></table>}
      </div>
    </section>
  );
}
