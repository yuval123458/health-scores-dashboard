import React, { useMemo, useState } from "react";
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

const tierColor = (tier) => {
  if (tier === "Green") return "text-green-600 font-semibold";
  if (tier === "Yellow") return "text-yellow-600 font-semibold";
  if (tier === "Red") return "text-red-600 font-semibold";
  return "";
};

const DataTable = ({ customers, onRowClick }) => {
  const [globalFilter, setGlobalFilter] = useState("");

  const columns = useMemo(
    () => [
      { accessorKey: "name", header: "Customer Name" },
      { accessorKey: "segment", header: "Segment" },
      { accessorKey: "plan", header: "Plan" },
      { accessorKey: "health_score", header: "Health Score" },
      {
        accessorKey: "health_tier",
        header: "Health Tier",
        cell: (info) => (
          <span className={tierColor(info.getValue())}>
            {info.getValue() ?? "N/A"}
          </span>
        ),
      },
      {
        id: "last_activity",
        header: "Last Activity",
        cell: (info) => {
          const row = info.row.original;
          const value =
            row && row.last_activity_at
              ? row.last_activity_at
              : "-";
          return value;
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: customers,
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

  if (!customers) {
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
          placeholder="Search customer name..."
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
            <tr
              key={row.id}
              className="hover:bg-gray-100 cursor-pointer"
              onClick={() => onRowClick && onRowClick(row.original)}
            >
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
