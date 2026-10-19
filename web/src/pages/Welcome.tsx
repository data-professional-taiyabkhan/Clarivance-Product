import { Link } from "react-router-dom";

export default function Welcome() {
  return (
    <div className="welcome">
      <section className="card hero-welcome">
        <div className="eyebrow">Clarivance pilot</div>
        <h1>Know what's safe to spend, after tax.</h1>
        <p className="lead">Upload a CSV statement from your business bank account. Clarivance works out your tax for the year as a range,
          tells you how much of your balance belongs to HMRC, and shows your cash after tax for the next 52 weeks.</p>
        <div className="ctas">
          <Link className="btn" to="/register">Join the pilot</Link>
          <Link className="btn ghost" to="/signin">Sign in</Link>
          <Link className="btn ghost" to="/demo">See a demo business</Link>
        </div>
      </section>
      <section className="grid three">
        <div className="card"><h3>1. Upload a statement</h3><p className="muted">Export a CSV from online banking (Monzo, Starling, Lloyds, Barclays, NatWest, HSBC and more). No bank login is shared.</p></div>
        <div className="card"><h3>2. Check the categories</h3><p className="muted">We sort income, costs, drawings and HMRC payments. Correct anything once and similar payments follow.</p></div>
        <div className="card"><h3>3. See your position</h3><p className="muted">Safe to spend today, the tax pot you should hold, upcoming HMRC payments and up to three actions for the week.</p></div>
      </section>
      <p className="muted small">For sole traders in England, Wales and Northern Ireland. Figures are estimates, not tax advice. Pilot software.</p>
    </div>
  );
}
