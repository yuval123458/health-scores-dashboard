import React, { useEffect, useState } from "react";
import Cards from "./Cards";
import Charts from "./Charts";
import DataTable from "./DataTable";

const Dashboard = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/api/customers")
      .then((res) => res.json())
      .then((data) => setCustomers(data))
      .catch((err) => console.error("Failed to fetch customers:", err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;

  // Example: Compute summary stats for Cards
  const summary = {
    total: customers.length,
    green: customers.filter((c) => c.health_tier === "Green").length,
    yellow: customers.filter((c) => c.health_tier === "Yellow").length,
    red: customers.filter((c) => c.health_tier === "Red").length,
  };

  // Example: Prepare data for charts/tables as needed
  // You may need to adjust this based on your Charts/DataTable components

  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Cards summary={summary} />
      </div>
      <Charts customers={customers} />
      <DataTable customers={customers} />
    </div>
  );
};

export default Dashboard;
