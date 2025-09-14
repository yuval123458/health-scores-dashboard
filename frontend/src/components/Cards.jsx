import React from "react";
import StatCard from "./StatCard";
import { FaUsers } from "react-icons/fa";

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
    </>
  );
};

export default Cards;
