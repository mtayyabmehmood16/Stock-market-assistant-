"use client";

import React, { useEffect, useState } from "react";
import { Activity, CheckCircle2, Clock, AlertTriangle, RefreshCw } from "lucide-react";
import type { AnalysisResponse, JobRecord } from "@/types/analysis";

interface Props {
  apiBase: string;
  activeJobId?: string | null;
  onSelectResult: (result: AnalysisResponse) => void;
}

export function JobTracker({ apiBase, activeJobId, onSelectResult }: Props) {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${apiBase}/api/jobs`);
      if (resp.ok) {
        const data: JobRecord[] = await resp.json();
        setJobs(data);
      }
    } catch {
      // ignore transient network errors
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [activeJobId]);

  useEffect(() => {
    if (!activeJobId) return;
    const es = new EventSource(`${apiBase}/api/jobs/${activeJobId}/stream`);
    es.addEventListener("progress", (evt) => {
      const updated: JobRecord = JSON.parse((evt as MessageEvent).data);
      setJobs((prev) => {
        const exists = prev.some((j) => j.job_id === updated.job_id);
        return exists
          ? prev.map((j) => (j.job_id === updated.job_id ? updated : j))
          : [updated, ...prev];
      });
      if (updated.status === "SUCCESS" || updated.status === "FAILURE") {
        es.close();
      }
    });
    es.onerror = () => es.close();
    return () => es.close();
  }, [activeJobId, apiBase]);

  return (
    <aside className="flex h-full flex-col rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-sky-400" />
          <h3 className="text-sm font-semibold text-slate-100">Background Jobs (Celery)</h3>
        </div>
        <button
          type="button"
          onClick={fetchJobs}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
          title="Refresh jobs"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 p-4 text-center text-xs text-slate-500">
          No background jobs yet. Ask for a &ldquo;deep Monte Carlo &amp; peer analysis&rdquo; to trigger a Celery worker.
        </div>
      ) : (
        <div className="space-y-2.5 overflow-y-auto pr-1">
          {jobs.map((job) => (
            <div key={job.job_id} className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-slate-100">{job.tickers.join(", ")}</span>
                <span className="flex items-center gap-1 rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-300">
                  {job.status === "SUCCESS" ? (
                    <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                  ) : job.status === "FAILURE" ? (
                    <AlertTriangle className="h-3 w-3 text-rose-400" />
                  ) : (
                    <Clock className="h-3 w-3 text-sky-400" />
                  )}
                  {job.status}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">{job.message}</p>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full transition-all ${
                    job.status === "FAILURE" ? "bg-rose-500" : "bg-sky-500"
                  }`}
                  style={{ width: `${job.progress}%` }}
                />
              </div>
              <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
                <span>
                  {job.progress}% · Retries: {job.retries}
                </span>
                {job.result && (
                  <button
                    type="button"
                    onClick={() => onSelectResult(job.result!)}
                    className="font-medium text-sky-400 hover:text-sky-300"
                  >
                    Load Report →
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
