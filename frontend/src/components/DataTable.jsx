import React, { useEffect, useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  flexRender,
} from "@tanstack/react-table";
import { FaSpinner } from "react-icons/fa";
import "./DataTable.css";

const DataTable = () => {
  const [data, setData] = useState([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTopDeals = async () => {
      try {
        const res = await fetch("http://localhost:5001/api/deals/top-deals");
        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error("failed to fetch top deals:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchTopDeals();
  }, []);

  const columns = useMemo(
    () => [
      {
        accessorKey: "transactionSourceName",
        header: "Source",
      },
      {
        accessorKey: "country_code",
        header: "Country",
      },
      {
        accessorKey: "totalJobs",
        header: "Total Jobs",
      },
      {
        accessorKey: "failedJobs",
        header: "Failed Jobs",
      },
      {
        accessorKey: "recordCount",
        header: "Records",
      },
      {
        accessorKey: "timestamp",
        header: "Timestamp",
        cell: (info) =>
          new Date(info.getValue()).toLocaleDateString("en-GB", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
          }),
      },
    ],
    []
  );

  const table = useReactTable({
    data,
    columns,
    state: {
      globalFilter,
    },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  if (loading) {
    return (
      <div className="flex justify-center items-center py-10">
        <FaSpinner className="animate-spin text-2xl text-blue-500" />
      </div>
    );
  }

  return (
    <div className="mt-8 bg-white p-4 shadow rounded-xl">
      <div className="mb-4 flex justify-between">
        <input
          type="text"
          placeholder="Search source name..."
          value={globalFilter ?? ""}
          onChange={(e) => setGlobalFilter(e.target.value)}
          className="border rounded px-3 py-1 w-64"
        />
      </div>

      <table className="min-w-full border">
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  className="border-b px-4 py-2 cursor-pointer"
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                  {{
                    asc: " 🔼",
                    desc: " 🔽",
                  }[header.column.getIsSorted()] ?? ""}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-gray-100">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="border px-4 py-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-4 flex justify-between items-center">
        <div>
          Page {table.getState().pagination.pageIndex + 1} of{" "}
          {table.getPageCount()}
        </div>
        <div className="space-x-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
          >
            Prev
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default DataTable;
