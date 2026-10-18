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
  meta: { engine: string; rules: string; rules_signed_off: boolean; forecast: string; simulations: number; seconds: number; label: string };
};

export type WhatIf = { amount: number; tax_on_it: number; keep: number; effective_rate: number; chance_over_50270_after: number };

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}

export const api = {
  businesses: () => get<{ businesses: BusinessSummary[] }>("/api/businesses"),
  position: (key: string, asOf: string, confidence: number) =>
    get<Position>(`/api/businesses/${key}?as_of=${asOf}&confidence=${confidence}`),
  whatIf: (key: string, asOf: string, amount: number) =>
    get<WhatIf>(`/api/businesses/${key}/what-if?as_of=${asOf}&amount=${amount}`),
};
