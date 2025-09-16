import React, { useMemo } from "react";
import RegressionChart from "./RegressionChart";
import BlockChart from "./BlockChart";

const Charts = ({ customers, summary }) => {

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

    const segmentData = useMemo(() => {
    const counts = {};
    customers.forEach((c) => {
      const segment = c.segment || "Unknown";
      counts[segment] = (counts[segment] || 0) + 1;
    });
    return Object.entries(counts).map(([segment, count]) => ({
      segment,
      count,
    }));
  }, [customers]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
      <RegressionChart customers={customers} summary={summary} />
      <BlockChart segmentData={segmentData} />
    </div>
  );
};

export default Charts;
