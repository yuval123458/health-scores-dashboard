import React, { useEffect, useState } from "react";
import Cards from "./Cards";
import Charts from "./Charts";
import DataTable from "./DataTable";

const Dashboard = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerHealth, setCustomerHealth] = useState(null);

  useEffect(() => {
  fetch(`${import.meta.env.VITE_API_URL}/api/customers`)
    .then((res) => res.json())
      .then((data) => setCustomers(data))
      .catch((err) => console.error("failed to fetch customers table:", err))
      .finally(() => setLoading(false));
  }, []);

  const handleRowClick = (customer) => {
    setSelectedCustomer(customer);
    fetch(`/api/customers/${customer.id}/health`)
      .then((res) => res.json())
      .then((data) => setCustomerHealth(data))
      .catch((err) => console.error("failed to fetch customer health:", err));
  };

  if (loading) return <div>Loading...</div>;

  const summary = {
    total: customers.length,
    green: customers.filter((c) => c.health_tier === "Green").length,
    yellow: customers.filter((c) => c.health_tier === "Yellow").length,
    red: customers.filter((c) => c.health_tier === "Red").length,
  };

  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Cards summary={summary} />
      </div>
      <Charts customers={customers} />
      <DataTable customers={customers} onRowClick={handleRowClick} />
      {selectedCustomer && customerHealth && (
        <div className="mt-4 p-4 bg-gray-100 rounded">
          <h2 className="font-bold mb-2">
            {customerHealth.name} Health Details
          </h2>
          {/* Render health breakdown here */}
          <pre>{JSON.stringify(customerHealth, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
