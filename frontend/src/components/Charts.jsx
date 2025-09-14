import React, { useMemo } from "react";
import RegressionChart from "./RegressionChart";
import BlockChart from "./BlockChart";

const Charts = ({ customers }) => {
  const lineData = useMemo(() => {
    return customers.map((c) => ({
      name: c.name,
      data: Array.isArray(c.health_history)
        ? c.health_history.map((h) => ({
            x: h.date,
            y: h.score,
          }))
        : [],
    }));
  }, [customers]);

  const countryData = useMemo(() => {
    const counts = {};
    customers.forEach((c) => {
      const country = c.country || "Unknown";
      counts[country] = (counts[country] || 0) + 1;
    });
    return Object.entries(counts).map(([country, count]) => ({
      country,
      count,
    }));
  }, [customers]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
      <RegressionChart lineData={lineData} />
      <BlockChart countryData={countryData} />
    </div>
  );
};

export default Charts;
