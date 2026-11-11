"use client";

import React, { useMemo, useState } from "react";
import type { TableSpec } from "@/types/analysis";

interface Props {
  table: TableSpec;
}

export function DataTableCard({ table }: Props) {
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [asc, setAsc] = useState(true);

  const sortedRows = useMemo(() => {
    if (sortCol === null) return table.rows;
    return [...table.rows].sort((a, b) => {
      const av = String(a[sortCol] ?? "");
      const bv = String(b[sortCol] ?? "");
      const an = Number(av.replace(/[^0-9.-]/g, ""));
      const bn = Number(bv.replace(/[^0-9.-]/g, ""));
      if (!Number.isNaN(an) && !Number.isNaN(bn) && av !== "" && bv !== "") {
        return asc ? an - bn : bn - an;
      }
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    });
  }, [table.rows, sortCol, asc]);

  const handleSort = (idx: number) => {
    if (sortCol === idx) {
      setAsc(!asc);
    } else {
      setSortCol(idx);
      setAsc(true);
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="mb-2.5 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-100">{table.title}</h4>
        <span className="text-[11px] text-slate-500">{table.rows.length} rows</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400">
              {table.columns.map((col, idx) => (
                <th
                  key={col}
                  onClick={() => handleSort(idx)}
                  className="cursor-pointer select-none px-3 py-2 font-medium hover:text-slate-200"
                >
                  {col} {sortCol === idx ? (asc ? "↑" : "↓") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {sortedRows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-slate-800/40">
                {row.map((cell, cIdx) => (
                  <td
                    key={cIdx}
                    className={`px-3 py-2 ${cIdx === 0 ? "font-medium text-slate-200" : "text-slate-300"}`}
                  >
                    {cell === null || cell === undefined ? "—" : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
