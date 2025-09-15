import React, { useEffect, useState } from "react";
import Cards from "./Cards";
import Charts from "./Charts";
import DataTable from "./DataTable";
import EventForm from "./EventForm";

const Dashboard = () => {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [customerHealth, setCustomerHealth] = useState(null);
  const [summary, setSummary] = useState(null); // <-- new

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL}/api/customers`)
      .then((res) => res.json())
      .then((data) => setCustomers(data))
      .catch((err) => console.error("failed to fetch customers table:", err))
      .finally(() => setLoading(false));

    // Fetch KPI summary
    fetch(`${import.meta.env.VITE_API_URL}/api/dashboard/summary`)
      .then((res) => res.json())
      .then((data) => setSummary(data))
      .catch((err) => console.error("failed to fetch dashboard summary:", err));
  }, []);

  const handleRowClick = (customer) => {
    setSelectedCustomer(customer);
    fetch(`${import.meta.env.VITE_API_URL}/api/customers/${customer.id}/health`)
      .then((res) => res.json())
      .then((data) => setCustomerHealth(data))
      .catch((err) => console.error("failed to fetch customer health:", err));
  };

  if (loading || !summary) return <div>Loading...</div>;

  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <Cards summary={summary} />
      </div>
      <Charts customers={customers} />
      <DataTable customers={customers} onRowClick={handleRowClick} />
      <EventForm customers={customers} />
      {selectedCustomer && customerHealth && (
        <div className="mt-4 p-4 bg-gray-100 rounded">
          <h2 className="font-bold mb-2">
            {customerHealth.name} Health Details
          </h2>
          <pre>{JSON.stringify(customerHealth, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
