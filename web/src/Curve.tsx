import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Band, Payment } from "./api";
import { gbp, shortDay } from "./format";

export default function Curve({ data, payments, confidence }: { data: Band[]; payments: Payment[]; confidence: number }) {
  const rows = data.map((d) => ({ ...d, band: [d.p10, d.p90] as [number, number] }));
  const weekFor = (iso: string) => rows.find((r) => r.week_ending >= iso)?.week_ending;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={rows} margin={{ top: 16, right: 12, bottom: 0, left: 8 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="week_ending" tickFormatter={shortDay} minTickGap={40} tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={(v) => gbp(v)} width={72} tick={{ fill: "var(--muted)", fontSize: 12 }} axisLine={false} tickLine={false} />
        <Tooltip
          formatter={(v: number | [number, number], name) =>
            Array.isArray(v) ? [`${gbp(v[0])} to ${gbp(v[1])}`, "Likely range"] : [gbp(v), name === "safe" ? `Safe to spend (${Math.round(confidence * 100)}% confidence)` : String(name)]}
          labelFormatter={(l) => `Week ending ${shortDay(String(l))}`}
          contentStyle={{ borderRadius: 10, border: "1px solid var(--line)", background: "var(--card)", color: "var(--ink)" }}
        />
        <Area dataKey="band" stroke="none" fill="var(--teal)" fillOpacity={0.16} isAnimationActive={false} />
        <ReferenceLine y={0} stroke="var(--muted)" strokeDasharray="4 4" />
        {payments.map((p) => {
          const w = weekFor(p.due);
          return w ? (
            <ReferenceLine key={p.due} x={w} stroke="var(--gold)" strokeWidth={1.5}
              label={{ value: `HMRC ${shortDay(p.due)}`, position: "insideTopRight", fill: "var(--gold-ink)", fontSize: 11 }} />
          ) : null;
        })}
        <Line dataKey="safe" stroke="var(--navy-line)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
