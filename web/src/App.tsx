import { useEffect, useMemo, useState } from "react";
import { api, type BusinessSummary, type Position, type WhatIf } from "./api";
import Curve from "./Curve";
import { day, gbp, pct } from "./format";

type Tab = "cashradar" | "taxshield" | "actionflow";

export default function App() {
  const [list, setList] = useState<BusinessSummary[]>([]);
  const [key, setKey] = useState("dan");
  const [asOf, setAsOf] = useState("");
  const [confidence, setConfidence] = useState(0.8);
  const [pos, setPos] = useState<Position | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("actionflow");
  const [amount, setAmount] = useState(1000);
  const [whatIf, setWhatIf] = useState<WhatIf | null>(null);

  useEffect(() => { api.businesses().then((r) => { setList(r.businesses); }).catch((e) => setErr(String(e))); }, []);
  const current = useMemo(() => list.find((b) => b.key === key), [list, key]);
  useEffect(() => { if (current) setAsOf(current.default_as_of); }, [current]);
  useEffect(() => {
    if (!asOf) return;
    setErr(null);
    api.position(key, asOf, confidence).then(setPos).catch((e) => setErr(String(e)));
    setWhatIf(null);
  }, [key, asOf, confidence]);

  const runWhatIf = () => api.whatIf(key, asOf, amount).then(setWhatIf).catch((e) => setErr(String(e)));

  return (
    <div className="page">
      <header className="top">
        <div className="brand"><span className="mark">C</span> CLARIVANCE <span className="ai">AI</span></div>
        <div className="controls">
          <label>Business
            <select value={key} onChange={(e) => setKey(e.target.value)}>
              {list.map((b) => <option key={b.key} value={b.key}>{b.name} · {b.trade}</option>)}
            </select>
          </label>
          <label>As of
            <input type="date" value={asOf} min={current?.trading_since} onChange={(e) => e.target.value && setAsOf(e.target.value)} />
          </label>
          <label>Reserve confidence
            <select value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}>
              {[0.7, 0.8, 0.9].map((c) => <option key={c} value={c}>{pct(c)}</option>)}
            </select>
          </label>
        </div>
      </header>

      <div className="banner">Prototype on synthetic data. Every figure is an estimate, not tax advice.</div>
      {err && <div className="error">{err}</div>}
      {!pos ? <div className="loading">Working out the year…</div> : (
        <main>
          <section className="hero card">
            <div>
              <div className="eyebrow">Safe to spend today · {day(pos.business.as_of)}</div>
              <div className={`big ${pos.headline.safe_to_spend_today < 0 ? "neg" : ""}`}>{gbp(pos.headline.safe_to_spend_today)}</div>
              <div className="sub">
                {gbp(pos.headline.cash_at_bank)} in the bank, less {gbp(pos.headline.tax_pot_should_hold)} that belongs to HMRC.
              </div>
              {pos.headline.reserve_change && <div className="change">{pos.headline.reserve_change}</div>}
            </div>
            <div className="who">
              <strong>{pos.business.name}, {pos.business.trade.toLowerCase()}</strong>
              <span>{pos.business.notes[0]}</span>
              <span>{pos.business.history_months} months of history</span>
            </div>
          </section>

          <section className="card">
            <div className="cardhead">
              <h2>Cash after tax, next 52 weeks</h2>
              <span className="legend"><i className="line" /> safe to spend ({pct(pos.taxshield.confidence)} confidence) <i className="band" /> likely range (10–90%) <i className="gold" /> HMRC payment</span>
            </div>
            <Curve data={pos.curve} payments={pos.taxshield.payments} confidence={pos.taxshield.confidence} />
          </section>

          <nav className="tabs">
            {([["actionflow", "ActionFlow · this week"], ["taxshield", "TaxShield · tax and reserve"], ["cashradar", "CashRadar · forecast"]] as [Tab, string][])
              .map(([t, label]) => <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{label}</button>)}
          </nav>

          {tab === "actionflow" && (
            <section className="card">
              {pos.actionflow.length === 0 ? <p className="muted">Nothing needs doing this week.</p> :
                <ol className="actions">{pos.actionflow.map((a, i) => <li key={i}><span className="tag">{a.module}</span>{a.text}</li>)}</ol>}
            </section>
          )}

          {tab === "taxshield" && (
            <section className="grid">
              <div className="card">
                <h3>This year's bill ({pos.cashradar.tax_year})</h3>
                <dl className="kv">
                  <dt>Expected</dt><dd>{gbp(pos.taxshield.expected_bill)}</dd>
                  <dt>Reserved for ({pct(pos.taxshield.confidence)} confidence)</dt><dd>{gbp(pos.taxshield.reserve_bill)}</dd>
                  <dt>Likely range</dt><dd>{gbp(pos.taxshield.bill_range.p10)} to {gbp(pos.taxshield.bill_range.p90)}</dd>
                  <dt>A single-forecast tool would reserve</dt><dd>{gbp(pos.taxshield.single_forecast_bill)}</dd>
                  <dt>Tax on income received so far</dt><dd>{gbp(pos.taxshield.tax_on_income_so_far)}</dd>
                  <dt>Already paid for this year</dt><dd>{gbp(pos.taxshield.already_paid_for_year)}</dd>
                  {pos.taxshield.last_year_balance_owed > 0 && <><dt>Still owed for last year</dt><dd>{gbp(pos.taxshield.last_year_balance_owed)}</dd></>}
                </dl>
              </div>
              <div className="card">
                <h3>The next £1,000</h3>
                <p className="stat">{gbp(pos.taxshield.rate_on_next_1000)} <span>of it is tax</span></p>
                <p className="muted">Chance of finishing above £50,270: {pct(pos.taxshield.chance_over["50270"])} · above £100,000: {pct(pos.taxshield.chance_over["100000"])}</p>
                <div className="whatif">
                  <label>What if I receive another
                    <input type="number" min={1} step={100} value={amount} onChange={(e) => setAmount(Number(e.target.value))} />
                  </label>
                  <button onClick={runWhatIf}>Work it out</button>
                </div>
                {whatIf && <p>{gbp(whatIf.amount)}: about <strong>{gbp(whatIf.tax_on_it)}</strong> is tax ({pct(whatIf.effective_rate)}), you keep {gbp(whatIf.keep)}.</p>}
              </div>
              <div className="card">
                <h3>HMRC payments coming up</h3>
                {pos.taxshield.payments.length === 0 ? <p className="muted">None in the next 52 weeks.</p> :
                  <table><tbody>{pos.taxshield.payments.map((p) => (
                    <tr key={p.due}><td>{day(p.due)}</td><td>{p.label}</td><td className="num">{gbp(p.expected)}</td></tr>))}</tbody></table>}
              </div>
              <div className="card wide">
                <h3>Recent money in, and the tax set aside for each</h3>
                <table>
                  <thead><tr><th>#</th><th>From</th><th className="num">Received</th><th className="num">Tax on it</th></tr></thead>
                  <tbody>{pos.taxshield.transactions.map((t) => (
                    <tr key={t.id}><td>{t.id}</td><td>{t.label}</td><td className="num">{gbp(t.amount)}</td><td className="num">{gbp(t.reconciled)}</td></tr>))}</tbody>
                </table>
              </div>
            </section>
          )}

          {tab === "cashradar" && (
            <section className="grid">
              <div className="card">
                <h3>Profit for {pos.cashradar.tax_year}</h3>
                <dl className="kv">
                  <dt>So far</dt><dd>{gbp(pos.cashradar.profit_so_far)}</dd>
                  <dt>Year-end, middle case</dt><dd>{gbp(pos.cashradar.year_end_profit.p50)}</dd>
                  <dt>Likely range</dt><dd>{gbp(pos.cashradar.year_end_profit.p10)} to {gbp(pos.cashradar.year_end_profit.p90)}</dd>
                </dl>
              </div>
              <div className="card">
                <h3>How your clients pay</h3>
                <table><tbody>{pos.cashradar.clients.map((c) => (
                  <tr key={c.client}><td>{c.client}</td><td className="num">usually {c.usually_pays_in} days</td></tr>))}</tbody></table>
              </div>
              <div className="card wide">
                <h3>Invoices waiting to be paid</h3>
                {pos.cashradar.outstanding_invoices.length === 0 ? <p className="muted">None.</p> :
                  <table>
                    <thead><tr><th>#</th><th>Client</th><th className="num">Amount</th><th className="num">Age</th><th className="num">Usually pays in</th><th className="num">Expected by</th></tr></thead>
                    <tbody>{pos.cashradar.outstanding_invoices.map((i) => (
                      <tr key={i.id} className={i.age_days > i.client_usually_pays_in ? "late" : ""}>
                        <td>{i.id}</td><td>{i.client}</td><td className="num">{gbp(i.amount)}</td><td className="num">{i.age_days} days</td>
                        <td className="num">{i.client_usually_pays_in} days</td><td className="num">{day(i.expected_by)}</td></tr>))}</tbody>
                  </table>}
              </div>
            </section>
          )}

          <footer>
            {pos.meta.label} Engine {pos.meta.engine} · rules {pos.meta.rules}{pos.meta.rules_signed_off ? "" : " (awaiting sign-off)"} · {pos.meta.forecast} · {pos.meta.simulations.toLocaleString("en-GB")} simulated years in {pos.meta.seconds}s
          </footer>
        </main>
      )}
    </div>
  );
}
