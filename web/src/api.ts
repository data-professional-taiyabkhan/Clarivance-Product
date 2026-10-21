export type Band = { week_ending: string; safe: number; p10: number; p50: number; p90: number; cash_p50: number };
export type Payment = { due: string; label: string; expected: number; at_confidence: number };
export type Action = { kind: string; module: string; text: string };
export type BusinessSummary = { key: string; name: string; trade: string; description: string; default_as_of: string; trading_since: string };

export type Position = {
  business: { key: string; name: string; trade: string; as_of: string; trading_since: string; notes: string[]; history_months: number };
  headline: { safe_to_spend_today: number; cash_at_bank: number; tax_pot_should_hold: number; reserve_change: string | null };
  cashradar: {
    tax_year: string; year_end: string; profit_so_far: number;
    year_end_profit: { p10: number; p50: number; p90: number };
    outstanding_invoices: { id: string; client: string; amount: number; age_days: number; client_usually_pays_in: number; expected_by: string }[];
    clients: { client: string; usually_pays_in: number; invoices_seen: number }[];
  };
  taxshield: {
    expected_bill: number; reserve_bill: number; confidence: number; bill_range: { p10: number; p90: number };
    single_forecast_bill: number; tax_on_income_so_far: number; already_paid_for_year: number; hold_now: number;
    last_year_balance_owed: number; rate_on_next_1000: number; chance_over: Record<string, number>;
    payments: Payment[];
    transactions: { id: string; label: string; amount: number; attributed: number; reconciled: number }[];
  };
  curve: Band[];
  actionflow: Action[];
  warnings?: string[];
  meta: { engine: string; rules: string; rules_signed_off: boolean; forecast: string; simulations: number; seconds: number; label: string };
};

export type WhatIf = { amount: number; tax_on_it: number; keep: number; effective_rate: number; chance_over_50270_after: number };
export type Me = { authenticated: boolean; email?: string; name?: string; profile_done?: boolean; has_transactions?: boolean };
export type Profile = {
  name: string; business_name: string; trade: string; business_type: string; trading_since: string; last_year_bill: number;
  paid_towards_this_year: number; last_year_balance_owed: number; cash_override: number | null; confidence: number; profile_done: boolean;
};
export type Txn = { id: number; day: string; description: string; amount: number; balance: number | null; category: string; client: string; user_edited: boolean };
export type TxnPage = { transactions: Txn[]; total: number; page: number; pages: number; categories: Record<string, string>; summary: Record<string, { count: number; total: number }> };
export type Statement = { id: number; filename: string; rows: number; imported: number; duplicates: number; first_day: string; last_day: string; business_only: boolean; uploaded_at: string };
export type OpenInvoice = { id: number; client: string; reference: string; issued: string; amount: number };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function csrf(): string {
  return document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1] ?? "";
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (method !== "GET") headers["X-CSRFToken"] = csrf();
  if (init.body && typeof init.body === "string") headers["Content-Type"] = "application/json";
  const r = await fetch(path, { ...init, headers, credentials: "same-origin" });
  const text = await r.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!r.ok) {
    const msg = (data as { error?: string } | null)?.error ?? (r.status === 403 ? "Your session expired. Refresh the page." : `Something went wrong (${r.status}).`);
    throw new ApiError(r.status, msg);
  }
  return data as T;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const api = {
  // demo
  businesses: () => call<{ businesses: BusinessSummary[] }>("/api/businesses"),
  position: (key: string, asOf: string, confidence: number) => call<Position>(`/api/businesses/${key}?as_of=${asOf}&confidence=${confidence}`),
  whatIf: (key: string, asOf: string, amount: number) => call<WhatIf>(`/api/businesses/${key}/what-if?as_of=${asOf}&amount=${amount}`),
  // accounts
  csrf: () => call<{ ok: boolean; invite_required: boolean }>("/api/auth/csrf"),
  me: () => call<Me>("/api/auth/me"),
  register: (d: { email: string; password: string; name: string; invite_code: string; accept_terms: boolean }) => call<Me>("/api/auth/register", json("POST", d)),
  login: (email: string, password: string) => call<Me>("/api/auth/login", json("POST", { email, password })),
  logout: () => call<Me>("/api/auth/logout", { method: "POST" }),
  // my data
  myPosition: (confidence?: number) => call<Position>(`/api/me/position${confidence ? `?confidence=${confidence}` : ""}`),
  myWhatIf: (amount: number) => call<WhatIf>(`/api/me/what-if?amount=${amount}`),
  profile: () => call<Profile>("/api/me/profile"),
  saveProfile: (p: Partial<Profile>) => call<Profile>("/api/me/profile", json("PUT", p)),
  statements: () => call<{ statements: Statement[] }>("/api/me/statements"),
  upload: (file: File, businessOnly: boolean) => {
    const fd = new FormData(); fd.append("file", file); fd.append("business_only", String(businessOnly));
    return call<{ imported: number; duplicates: number; rows: number; first_day: string; last_day: string }>("/api/me/statements", { method: "POST", body: fd });
  },
  loadSample: () => call<{ imported: number; duplicates: number; rows: number; first_day: string; last_day: string }>("/api/me/statements/sample", { method: "POST" }),
  deleteStatement: (id: number) => call<{ deleted: boolean }>(`/api/me/statements/${id}`, { method: "DELETE" }),
  transactions: (params: { category?: string; q?: string; page?: number }) => {
    const s = new URLSearchParams(); Object.entries(params).forEach(([k, v]) => v && s.set(k, String(v)));
    return call<TxnPage>(`/api/me/transactions?${s}`);
  },
  setCategory: (id: number, category: string, applyToSimilar: boolean) =>
    call<{ updated: number }>(`/api/me/transactions/${id}`, json("PATCH", { category, apply_to_similar: applyToSimilar })),
  recategorise: () => call<{ changed: number }>("/api/me/transactions/recategorise", { method: "POST" }),
  invoices: () => call<{ invoices: OpenInvoice[] }>("/api/me/invoices"),
  addInvoice: (d: { client: string; reference: string; issued: string; amount: number }) => call<{ invoices: OpenInvoice[] }>("/api/me/invoices", json("POST", d)),
  deleteInvoice: (id: number) => call<{ deleted: boolean }>(`/api/me/invoices/${id}`, { method: "DELETE" }),
  deleteAccount: (password: string) => call<{ deleted: boolean }>("/api/me/delete", json("DELETE", { password })),
};
