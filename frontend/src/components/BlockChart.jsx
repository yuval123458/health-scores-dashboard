import React from "react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from "recharts";

const BlockChart = ({ countryData }) => {
  return (
    <div className="bg-white p-4 rounded-xl shadow">
      <h2 className="text-lg font-semibold mb-2">Deals by Country</h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={countryData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="value" fill="#16a34a" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default BlockChart;
