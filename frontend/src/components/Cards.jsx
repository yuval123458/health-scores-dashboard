import React from "react";
import StatCard from "./StatCard";
import { FaUsers, FaArrowUp, FaArrowDown, FaExclamationTriangle, FaMoneyBillWave, FaHeartbeat } from "react-icons/fa";

const Cards = ({ summary }) => {
  return (
    <>
      <StatCard
        title="Total Customers"
        value={summary.total}
        icon={<FaUsers />}
      />
      <StatCard
        title="Green Tier"
        value={summary.green}
        icon={<span className="text-green-500">🟢</span>}
      />
      <StatCard
        title="Yellow Tier"
        value={summary.yellow}
        icon={<span className="text-yellow-500">🟡</span>}
      />
      <StatCard
        title="Red Tier"
        value={summary.red}
        icon={<span className="text-red-500">🔴</span>}
      />
       {/* <StatCard
        title="At Risk"
        value={summary.at_risk_count}
        icon={<FaExclamationTriangle className="text-red-500" />}
      />
      <StatCard
        title="Newly At Risk (7d)"
        value={summary.newly_at_risk_7d}
        icon={<FaExclamationTriangle className="text-yellow-500" />} 
      /> */}
      <StatCard 
        title="Improving (30d)"
        value={summary.improving_30d}
        icon={<FaArrowUp className="text-green-500" />}
      />
      <StatCard
        title="Declining (30d)"
        value={summary.declining_30d}
        icon={<FaArrowDown className="text-red-500" />}
      />
      <StatCard
        title="Late Invoices (30d)"
        value={`${summary.pct_late_invoices_30d}%`}
        icon={<FaMoneyBillWave className="text-yellow-700" />}
      />
      <StatCard
        title="Avg Health Score"
        value={summary.avg_health_score}
        icon={<FaHeartbeat className="text-pink-500" />}
      />
    </>
  );
};

export default Cards;
