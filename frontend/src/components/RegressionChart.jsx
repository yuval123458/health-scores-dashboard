import React, { useState, useEffect, useMemo } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from "recharts";

const METRICS = [
  { key: "logins",           label: "Logins per Month" },
  { key: "features",         label: "Distinct Features per Month" },
  { key: "tickets_weighted", label: "Weighted Tickets per Month" },
  { key: "invoices",         label: "Invoices per Month" },
  { key: "late_invoices",    label: "Late Invoices per Month" },
];

// tiny OLS on index-based x
function fitLine(values) {
  const n = values.length;
  if (n < 2) return { slope: 0, intercept: values[0] ?? 0 };
  const xs = [...Array(n)].map((_, i) => i);
  const mean = a => a.reduce((s, v) => s + v, 0) / n;
  const x̄ = mean(xs), ȳ = mean(values);
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - x̄, dy = values[i] - ȳ;
    num += dx * dy; den += dx * dx;
  }
  const slope = den === 0 ? 0 : num / den;
  return { slope, intercept: ȳ - slope * x̄ };
}

const getLastNMonths = (series, n = 3) => {
  if (!series || !series.length) return [];
  return series.slice(-n);
};

export default function RegressionChart({ customers }) {
  const [customerId, setCustomerId] = useState("");
  const [metric, setMetric] = useState(METRICS[0].key);
  const [seriesByMetric, setSeriesByMetric] = useState(null); // { logins:[{month,value}], ... }
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!customerId) { setSeriesByMetric(null); return; }
    setLoading(true);
    fetch(`${import.meta.env.VITE_API_URL}/api/customers/${customerId}/health`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => setSeriesByMetric(d?.series ?? null))
      .catch(() => setSeriesByMetric(null))
      .finally(() => setLoading(false));
  }, [customerId]);

  const raw = seriesByMetric?.[metric] ?? [];
  const chartData = useMemo(() => (
    getLastNMonths(raw, 3).map((pt, i) => ({
      x: i,
      month: pt.month,
      value: Number(pt.value ?? 0)
    }))
  ), [raw]);

  return (
    <div className="w-full bg-white rounded-xl shadow p-4">
      <div className="flex gap-4 mb-3">
        <label className="text-sm text-gray-600">
          <select
            className="border rounded px-2 py-1 ml-2"
            value={customerId}
            onChange={e => setCustomerId(e.target.value)}
          >
            <option value="">— Select —</option>
            {customers.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="text-sm text-gray-600">
          Metric{" "}
          <select
            className="border rounded px-2 py-1 ml-2"
            value={metric}
            onChange={e => setMetric(e.target.value)}
            disabled={!seriesByMetric}
          >
            {METRICS.map(m => (
              <option key={m.key} value={m.key}>{m.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="w-full h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
          >
            <CartesianGrid />
            <XAxis
              dataKey="month"
              label={{ value: "Month", position: "insideBottom", offset: 0 }}
              tick={{ fontSize: 12 }}

            />
            <YAxis
              label={{
                value: METRICS.find(m => m.key === metric)?.label,
                angle: -90,
                dy: 50,
                position: "insideLeft",
                offset: 40
              }}
              allowDecimals
            />
            <Tooltip />
            <Line type="monotone" dataKey="value" name="Actual" stroke="#2563eb" dot={{ r: 3 }} connectNulls />
            {chartData.length >= 2 && (
              <Line type="linear" dataKey="fit" name="Trend" stroke="#ef4444" dot={false} isAnimationActive={false} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {!customerId && <div className="text-sm text-gray-500 mt-2">Pick a customer to load data.</div>}
      {customerId && loading && <div className="text-sm text-gray-500 mt-2">Loading…</div>}
      {customerId && !loading && chartData.length === 0 && (
        <div className="text-sm text-gray-500 mt-2">No data for this metric.</div>
      )}
    </div>
  );
}
