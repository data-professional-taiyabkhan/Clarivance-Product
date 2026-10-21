import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api";
import { AuthProvider, useAuth } from "./auth";
import { Register, SignIn } from "./pages/Auth";
import Demo from "./pages/Demo";
import Home from "./pages/Home";
import Invoices from "./pages/Invoices";
import Profile from "./pages/Profile";
import Transactions from "./pages/Transactions";
import Upload from "./pages/Upload";
import Welcome from "./pages/Welcome";

function Shell() {
  const { me, setMe } = useAuth();
  const nav = useNavigate();
  const out = async () => { await api.logout(); setMe({ authenticated: false }); nav("/"); };
  return (
    <div className="page">
      <header className="top">
        <Link to={me?.authenticated ? "/app" : "/"} className="brand"><span className="mark">C</span> CLARIVANCE <span className="ai">AI</span><span className="pill">Pilot</span></Link>
        <nav className="mainnav">
          {me?.authenticated ? <>
            <NavLink to="/app" end>Dashboard</NavLink>
            <NavLink to="/app/upload">Upload</NavLink>
            <NavLink to="/app/transactions">Transactions</NavLink>
            <NavLink to="/app/invoices">Invoices</NavLink>
            <NavLink to="/app/profile">Profile</NavLink>
            <button className="link" onClick={out}>Sign out</button>
          </> : <>
            <NavLink to="/demo">Demo</NavLink>
            <NavLink to="/signin">Sign in</NavLink>
            <Link className="btn small" to="/register">Join the pilot</Link>
          </>}
        </nav>
      </header>
      <Outlet />
    </div>
  );
}

function Waking() {
  const [slow, setSlow] = useState(false);
  useEffect(() => { const t = setTimeout(() => setSlow(true), 4000); return () => clearTimeout(t); }, []);
  return <div className="loading">{slow ? "Waking up the server. The first visit after a quiet spell can take up to a minute…" : "Loading…"}</div>;
}

function RequireAuth() {
  const { me } = useAuth();
  if (!me) return <Waking />;
  return me.authenticated ? <Outlet /> : <Navigate to="/signin" replace />;
}

function Root() {
  const { me } = useAuth();
  if (!me) return <Waking />;
  return me.authenticated ? <Navigate to="/app" replace /> : <Welcome />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<Root />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/register" element={<Register />} />
          <Route path="/demo" element={<Demo />} />
          <Route element={<RequireAuth />}>
            <Route path="/app" element={<Home />} />
            <Route path="/app/upload" element={<Upload />} />
            <Route path="/app/transactions" element={<Transactions />} />
            <Route path="/app/invoices" element={<Invoices />} />
            <Route path="/app/profile" element={<Profile />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
