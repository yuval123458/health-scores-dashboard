import React, { useState, useMemo } from "react";

const EVENT_TYPES = [
  "login",
  "feature_use",
  "ticket_opened",
  "invoice_paid",
];

const DEVICE_OPTIONS = [
  "windows", "linux", "ios", "mac"
];
const REGION_OPTIONS = [
  "eu-west", "ap-south", "us-east"
];
const FEATURE_OPTIONS = [
  "admin", "dashboards", "reports", "alerts", "integrations"
];
const SEVERITY_OPTIONS = [
  "low", "medium", "high"
];

const EventForm = ({ customers }) => {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [type, setType] = useState("");
  const [date, setDate] = useState("");
  // metadata is always an object now
  const [metadata, setMetadata] = useState({});
  const [status, setStatus] = useState(null);

  const filtered = useMemo(() =>
    customers.filter(c =>
      c.name.toLowerCase().includes(search.toLowerCase())
    ), [search, customers]
  );

  // Reset metadata when type changes
  React.useEffect(() => {
    setMetadata({});
  }, [type]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selected || !type || !date) {
      setStatus("Please fill all required fields.");
      return;
    }
    let meta = metadata;
    // Convert days_late to int if present
    if (type === "invoice_paid" && meta.days_late !== undefined) {
      meta = { ...meta, days_late: Number(meta.days_late) };
    }
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/customers/${selected.id}/events`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            type,
            occurred_at: date,
            metadata_json: meta,
          }),
        }
      );
      if (res.ok) {
        setStatus("Event posted successfully!");
        setType("");
        setDate("");
        setMetadata({});
      } else {
        setStatus("Failed to post event.");
      }
    } catch {
      setStatus("Error posting event.");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white p-6 rounded shadow max-w-lg mx-auto mt-8">
      <h2 className="font-bold text-lg mb-4">Post Customer Event</h2>
      <div className="mb-3">
        <label className="block mb-1 font-semibold">Search Customer</label>
        <input
          type="text"
          className="border px-3 py-1 rounded w-full"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Type customer name..."
        />
        {search && (
          <ul className="border rounded mt-1 max-h-32 overflow-y-auto bg-white">
            {filtered.slice(0, 5).map(c => (
              <li
                key={c.id}
                className={`px-3 py-1 cursor-pointer hover:bg-gray-100 ${selected && selected.id === c.id ? "bg-gray-200" : ""}`}
                onClick={() => { setSelected(c); setSearch(c.name); }}
              >
                {c.name}
              </li>
            ))}
            {filtered.length === 0 && <li className="px-3 py-1 text-gray-400">No results</li>}
          </ul>
        )}
      </div>
      <div className="mb-3">
        <label className="block mb-1 font-semibold">Event Type</label>
        <select
          className="border px-3 py-1 rounded w-full"
          value={type}
          onChange={e => setType(e.target.value)}
        >
          <option value="">Select type...</option>
          {EVENT_TYPES.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>
      <div className="mb-3">
        <label className="block mb-1 font-semibold">Date</label>
        <input
          type="datetime-local"
          className="border px-3 py-1 rounded w-full"
          value={date}
          onChange={e => setDate(e.target.value)}
        />
      </div>

      {/* Structured metadata fields */}
      {type === "login" && (
        <div className="mb-3 flex gap-2">
          <div>
            <label className="block mb-1 font-semibold">Device</label>
            <select
              className="border px-3 py-1 rounded"
              value={metadata.device || ""}
              onChange={e => setMetadata(m => ({ ...m, device: e.target.value }))}
            >
              <option value="">Select device...</option>
              {DEVICE_OPTIONS.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block mb-1 font-semibold">Region</label>
            <select
              className="border px-3 py-1 rounded"
              value={metadata.region || ""}
              onChange={e => setMetadata(m => ({ ...m, region: e.target.value }))}
            >
              <option value="">Select region...</option>
              {REGION_OPTIONS.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
        </div>
      )}
      {type === "feature_use" && (
        <div className="mb-3">
          <label className="block mb-1 font-semibold">Feature</label>
          <select
            className="border px-3 py-1 rounded w-full"
            value={metadata.feature || ""}
            onChange={e => setMetadata(m => ({ ...m, feature: e.target.value }))}
          >
            <option value="">Select feature...</option>
            {FEATURE_OPTIONS.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
      )}
      {type === "ticket_opened" && (
        <div className="mb-3">
          <label className="block mb-1 font-semibold">Severity</label>
          <select
            className="border px-3 py-1 rounded w-full"
            value={metadata.severity || ""}
            onChange={e => setMetadata(m => ({ ...m, severity: e.target.value }))}
          >
            <option value="">Select severity...</option>
            {SEVERITY_OPTIONS.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </div>
      )}
      {type === "invoice_paid" && (
        <div className="mb-3 flex gap-2">
          <div>
            <label className="block mb-1 font-semibold">Paid On Time</label>
            <select
              className="border px-3 py-1 rounded"
              value={
                metadata.paid_on_time === undefined
                  ? ""
                  : metadata.paid_on_time
                  ? "true"
                  : "false"
              }
              onChange={e =>
                setMetadata(m => ({
                  ...m,
                  paid_on_time: e.target.value === "true"
                }))
              }
            >
              <option value="">Select...</option>
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          </div>
          <div>
            <label className="block mb-1 font-semibold">Days Late</label>
            <input
              type="number"
              className="border px-3 py-1 rounded"
              value={metadata.days_late ?? ""}
              onChange={e =>
                setMetadata(m => ({
                  ...m,
                  days_late: e.target.value
                }))
              }
              min={0}
            />
          </div>
        </div>
      )}

      {/* Show JSON preview for debugging */}
      {type && (
        <div className="mb-3">
          <label className="block mb-1 font-semibold">Metadata Preview</label>
          <pre className="bg-gray-100 rounded p-2 text-xs">
            {JSON.stringify(metadata, null, 2)}
          </pre>
        </div>
      )}

      <button
        type="submit"
        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
      >
        Post Event
      </button>
      {status && <div className="mt-3 text-sm">{status}</div>}
    </form>
  );
};

export default EventForm;