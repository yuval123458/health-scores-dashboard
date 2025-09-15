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

const RegressionChart = ({ lineData }) => {
  // Gather all points for average calculation
  const allPoints = [];
  lineData.forEach((customer) => {
    customer.data.forEach((point) => {
      allPoints.push({
        date: point.x,
        score: point.y,
      });
    });
  });

  // Calculate average health score per date
  const avgByDate = {};
  allPoints.forEach((pt) => {
    if (!avgByDate[pt.date]) avgByDate[pt.date] = [];
    avgByDate[pt.date].push(pt.score);
  });
  const avgLine = Object.entries(avgByDate).map(([date, scores]) => ({
    date,
    y: scores.reduce((a, b) => a + b, 0) / scores.length,
  }));

  return (
    <div className="bg-white p-4 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-2">
        Average Health Score Trend
      </h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={avgLine}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis domain={[0, 100]} />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey="y"
            name="Average Health Score"
            stroke="#000"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default RegressionChart;
