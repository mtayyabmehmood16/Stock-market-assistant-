"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, Info } from "lucide-react";
import type { Assumption, Citation } from "@/types/analysis";

interface Props {
  citations: Citation[];
  assumptions: Assumption[];
  toolsUsed: string[];
  disclaimer: string;
}

export function CitationsDrawer({ citations, assumptions, toolsUsed, disclaimer }: Props) {
  const [open, setOpen] = useState(false);

  if (citations.length === 0 && assumptions.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-800/90 bg-slate-950/70 px-4 py-2.5 text-xs">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between text-left text-slate-300 hover:text-white"
      >
        <span className="flex items-center gap-2 font-medium">
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          Sources ({citations.length}) · Assumptions ({assumptions.length}) · Tools ({toolsUsed.join(", ")})
        </span>
        <span className="text-[11px] text-sky-400">{open ? "Hide" : "Inspect"}</span>
      </button>

      {open && (
        <div className="mt-3 grid gap-3 border-t border-slate-800 pt-3 md:grid-cols-2">
          <div>
            <h5 className="mb-1.5 font-semibold uppercase tracking-wider text-slate-400">
              Data Sources & Timestamps
            </h5>
            <ul className="space-y-1.5 text-slate-300">
              {citations.map((c, idx) => (
                <li key={idx} className="flex items-start justify-between gap-2 rounded bg-slate-900/70 p-2">
                  <div>
                    <div className="font-medium text-slate-200">{c.label}</div>
                    <div className="text-[11px] text-slate-400">
                      {c.source} · {new Date(c.retrieved_at).toLocaleString()}
                    </div>
                  </div>
                  {c.url && (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sky-400 hover:text-sky-300"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h5 className="mb-1.5 font-semibold uppercase tracking-wider text-slate-400">
              Model Assumptions
            </h5>
            <ul className="space-y-1.5 text-slate-300">
              {assumptions.map((a, idx) => (
                <li key={idx} className="rounded bg-slate-900/70 p-2">
                  <div className="flex justify-between gap-2">
                    <span className="font-medium text-slate-200">{a.key}</span>
                    <span className="text-sky-300">{a.value}</span>
                  </div>
                  {a.rationale && <div className="mt-0.5 text-[11px] text-slate-400">{a.rationale}</div>}
                </li>
              ))}
            </ul>
          </div>

          <div className="md:col-span-2 flex items-start gap-2 rounded bg-slate-900/50 p-2 text-[11px] text-slate-400">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
            <span>{disclaimer}</span>
          </div>
        </div>
      )}
    </div>
  );
}
