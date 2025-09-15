import { useEffect, useMemo, useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  Line, ReferenceLine, ResponsiveContainer
} from "recharts";

function ols(xs, ys) {
  const n = xs.length || 1;
  const mean = a => a.reduce((s,v)=>s+v,0)/n;
  const x̄ = mean(xs), ȳ = mean(ys);
  let num=0, den=0, sst=0, sse=0;
  for (let i=0;i<xs.length;i++){ const dx=xs[i]-x̄, dy=ys[i]-ȳ; num+=dx*dy; den+=dx*dx; sst+=dy*dy; }
  const slope = den===0?0:num/den;
  const intercept = ȳ - slope*x̄;
  for (let i=0;i<xs.length;i++){ const yhat=slope*xs[i]+intercept; const e=ys[i]-yhat; sse+=e*e; }
  const r2 = sst===0?0:Math.max(0, Math.min(1, 1 - sse/sst));
  return { slope, intercept, r2 };
}

const X_OPTIONS = [
  { key: "logins_30d", label: "Logins (30d)",  domain: [0, 40] },
  { key: "key_features_60d", label: "Key features (60d)",  domain: [0, 6] },
  { key: "tickets_30d", label: "Tickets (30d)", domain: [0, 10] },
  { key: "invoice_days_late", label: "Invoice days late",  domain: [0, 30] },
  { key: "days_since_last_activity", label: "Days since last activity", domain: [0, 90] },
];

const daysSince = (d) => {
  if (!d) return 999;
  const t = Date.parse(String(d));
  return Number.isFinite(t) ? Math.max(0, Math.round((Date.now()-t)/(1000*60*60*24))) : 999;
};

function TierTooltip({ active, payload, xLabel }) {
  if (!active || !payload || !payload.length) return null;
  const item = payload.find(p => p.name !== "Trend");
  if (!item) return null;
  const d = item.payload; // { tier, x, y, count }
  return (
    <div style={{ background: "white", border: "1px solid #e5e7eb", borderRadius: 6, padding: 8, boxShadow: "0 2px 6px rgba(0,0,0,0.08)", fontSize: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{d.tier} <span style={{ color:"#6b7280" }}>({d.count} customers)</span></div>
      <div>{xLabel}: <b>{Math.round(d.x)}</b></div>
      <div>Avg health: <b>{Math.round(d.y)}</b></div>
    </div>
  );
}

export default function RegressionChartTier() {
  const [rows, setRows] = useState([]);
  const [xKey, setXKey] = useState("logins_30d");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await fetch(`${import.meta.env.VITE_API_URL}/api/customers`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const js = await r.json();
        if (!alive) return;
        const mapped = js.map((c) => {
          const m = c.metrics || {};
          const features = Number(m.adoption_distinct_features_60d ?? 0);
          const daysLate = Number(m.last_invoice_days_late ?? (m.last_invoice === "invoice_late" ? 1 : 0));
          return {
            id: c.id,
            tier: c.health_tier,                         
            health_score: Number(c.health_score ?? 0),
            logins_30d: Number(m.logins_30d ?? 0),
            key_features_60d: features,
            tickets_30d: Number(m.tickets_30d ?? 0),
            invoice_days_late: daysLate,
            days_since_last_activity: Number(daysSince(m.last_activity_at)),
          };
        });
        setRows(mapped); setLoading(false);
      } catch (e) { if (alive) { setErr(String(e)); setLoading(false); } }
    })();
    return () => { alive = false; };
  }, []);

  const { green, yellow, red, trend, stats, xLabel, xDomain, hint } = useMemo(() => {
    const opt = X_OPTIONS.find(o => o.key === xKey) || {};
    const xLabel = opt.label || xKey;
    const xDomain = opt.domain || ["auto","auto"];
    const hint = opt.hint;

    const tiers = ["Green","Yellow","Red"];
    const groups = tiers.map(t => {
      const g = rows.filter(r => r.tier === t);
      if (!g.length) return null;
      const mean = arr => arr.reduce((s,v)=>s+v,0) / arr.length;
      return {
        tier: t,
        x: mean(g.map(r => Number(r[xKey] || 0))),
        y: mean(g.map(r => Number(r.health_score || 0))),
        count: g.length,
      };
    }).filter(Boolean);

    const green = groups.filter(g => g.tier === "Green");
    const yellow = groups.filter(g => g.tier === "Yellow");
    const red    = groups.filter(g => g.tier === "Red");

    const xs = groups.map(p => p.x);
    const ys = groups.map(p => p.y);
    const { slope, intercept, r2 } = ols(xs, ys);
    const [minX, maxX] = Array.isArray(xDomain) ? xDomain : [Math.min(...xs,0), Math.max(...xs,1)];
    const trend = [
      { x: minX, y: Math.max(0, Math.min(100, slope*minX + intercept)) },
      { x: maxX, y: Math.max(0, Math.min(100, slope*maxX + intercept)) },
    ];

    return { green, yellow, red, trend, stats: { slope, r2 }, xLabel, xDomain, hint };
  }, [rows, xKey]);

  if (loading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (err) return <div className="p-4 text-sm text-red-600">{err}</div>;

  return (
    <div className="w-full h-[420px] bg-white rounded-xl shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold">Health vs. {xLabel} (tier averages)</h3>
          <div className="text-xs text-gray-500">{hint}</div>
          <div className="text-xs mt-1">slope: <b>{stats.slope.toFixed(3)}</b> &nbsp; R²: <b>{stats.r2.toFixed(3)}</b></div>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-600">X-axis</label>
          <select value={xKey} onChange={(e)=>setXKey(e.target.value)} className="border rounded px-2 py-1 text-sm">
            {X_OPTIONS.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <ResponsiveContainer width="100%" height="85%">
        {/* extra bottom margin so legend sits below the axis */}
        <ScatterChart margin={{ top: 10, right: 20, bottom: 56, left: 10 }}>
          <CartesianGrid />
          <XAxis
            type="number"
            dataKey="x"
            name={xLabel}
            domain={xDomain}
            allowDecimals={false}
            tickFormatter={(v)=>Math.round(v)}
            tickCount={6}
            label={{ value: xLabel, position: "insideBottom", offset: -10 }}
            tickMargin={8}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="Health Score"
            domain={[0,100]}
            allowDecimals={false}
            tickCount={6}
            label={{ value: "Health Score", angle: -90, position: "insideLeft" }}
          />

          <ReferenceLine y={60} stroke="#f59e0b" strokeDasharray="3 3" />
          <ReferenceLine y={80} stroke="#22c55e" strokeDasharray="3 3" />


          <Legend
            verticalAlign="top"
            align="center"
            wrapperStyle={{ paddingTop: 6 }}
          />

          <Scatter name="Green"  data={green}  fill="#22c55e" />
          <Scatter name="Yellow" data={yellow} fill="#eab308" />
          <Scatter name="Red"    data={red}    fill="#ef4444" />

          <Line
            dataKey="y"
            data={trend}
            dot={false}
            stroke="#111827"
            strokeDasharray="4 2"
            name="Trend"
            legendType="none"    
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
