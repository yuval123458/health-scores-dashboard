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
  const allPoints = [];
  lineData.forEach((customer) => {
    customer.data.forEach((point) => {
      allPoints.push({
        name: customer.name,
        date: point.x,
        score: point.y,
      });
    });
  });

  return (
    <div className="bg-white p-4 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-2">
        Customer Health Score Trends
      </h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            type="category"
            allowDuplicatedCategory={false}
            tickFormatter={(date) =>
              typeof date === "string"
                ? date.slice(0, 10)
                : date
            }
          />
          <YAxis
            domain={[0, 100]}
            tickCount={5}
            tickFormatter={formatNumber}
            label={{ value: "Health Score", angle: -90, position: "insideLeft" }}
          />
          <Tooltip />
          <Legend />
          {lineData.map((customer, idx) => (
            <Line
              key={customer.name}
              data={customer.data}
              dataKey="y"
              name={customer.name}
              dot={false}
              stroke={`hsl(${(idx * 60) % 360}, 70%, 50%)`}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default RegressionChart;
