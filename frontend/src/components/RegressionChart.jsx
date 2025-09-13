import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const formatNumber = (value) => {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
  return value.toString();
};

const RegressionChart = ({ lineData }) => {
  return (
    <div className="bg-white p-4 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-2">
        Total jobs successfully indexed
      </h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={lineData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis
            domain={[0, "dataMax"]}
            tickCount={5}
            tickFormatter={formatNumber}
          />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="totalJobs" stroke="#4f46e5" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default RegressionChart;
