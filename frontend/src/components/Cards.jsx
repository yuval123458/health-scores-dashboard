import React from "react";
import StatCard from "./StatCard";
import { FaUsers, FaArrowUp, FaArrowDown, FaExclamationTriangle, FaMoneyBillWave, FaHeartbeat } from "react-icons/fa";

const Cards = ({ summary, benchmarks, legacy_peek }) => {
  return (
    <>
      <StatCard
        title="Total Customers"
        value={summary?.total}
        icon={<FaUsers />}
      />
      <StatCard
        title="Green Tier"
        value={summary?.green}
        icon={<span className="text-green-500">🟢</span>}
      />
      <StatCard
        title="Yellow Tier"
        value={summary?.yellow}
        icon={<span className="text-yellow-500">🟡</span>}
      />
      <StatCard
        title="Red Tier"
        value={summary?.red}
        icon={<span className="text-red-500">🔴</span>}
      />
      <StatCard
        title="Avg Health Score"
        value={summary?.avg_health_score}
        icon={<FaHeartbeat className="text-pink-500" />}
      />
      <StatCard
        title="Late Invoices (30d)"
        value={summary?.pct_late_invoices_30d !== undefined ? `${summary.pct_late_invoices_30d}%` : ""}
        icon={<FaMoneyBillWave className="text-yellow-700" />}
      />
      {/* Benchmarks */}
      <StatCard
        title="Median Logins (30d)"
        value={benchmarks?.median_E_per_30d}
        icon={<FaArrowUp className="text-blue-500" />}
      />
      <StatCard
        title="Median Adoption (60d)"
        value={benchmarks?.median_A_per_60d}
        icon={<FaArrowUp className="text-purple-500" />}
      />
      <StatCard
        title="Median Finance Harm"
        value={benchmarks?.median_F_harm}
        icon={<FaMoneyBillWave className="text-green-500" />}
      />

      <StatCard
        title="Avg Logins (30d)"
        value={legacy_peek?.avg_logins_30d}
        icon={<FaArrowUp className="text-blue-500" />}
      />
      <StatCard
        title="Avg Adoption (60d)"
        value={legacy_peek?.avg_adoption_distinct_features_60d}
        icon={<FaArrowUp className="text-purple-500" />}
      />
      <StatCard
        title="Avg Tickets (30d)"
        value={legacy_peek?.avg_tickets_30d}
        icon={<FaArrowDown className="text-orange-500" />}
      />
    </>
  );
};

export default Cards;
