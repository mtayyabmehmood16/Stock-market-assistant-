"use client";

import React, { useState } from "react";
import { Send, Sparkles, TrendingUp, Cpu } from "lucide-react";
import type { AnalysisResponse } from "@/types/analysis";
import { CandlestickChart } from "./CandlestickChart";
import { DataTableCard } from "./DataTableCard";
import { CitationsDrawer } from "./CitationsDrawer";
import { JobTracker } from "./JobTracker";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: AnalysisResponse;
}

const QUICK_PROMPTS = [
  "Show AAPL technical candlestick chart, RSI, MACD, and volume",
  "Analyze MSFT fundamentals, financial statements, and valuation",
  "Compare AAPL vs MSFT vs NVDA over 6 months in Python",
  "Run a what-if DCF valuation for NVDA with growth 18% and WACC 9.5%",
  "Run a deep background Monte Carlo and peer analysis for AAPL and MSFT",
];

export function ChatWorkspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const sendQuery = async (queryText: string) => {
    const q = queryText.trim();
    if (!q || loading) return;

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", text: q };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, conversation_id: conversationId }),
      });
      if (!resp.ok) {
        throw new Error(`API error (${resp.status})`);
      }
      const data: AnalysisResponse = await resp.json();
      setConversationId(data.conversation_id);
      if (data.job_id) setActiveJobId(data.job_id);
      setMessages((prev) => [
        ...prev,
        { id: data.message_id, role: "assistant", text: data.narrative, response: data },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          text: `Failed to reach API at ${API_BASE}. Make sure FastAPI is running (${String(err)}).`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadJobResult = (result: AnalysisResponse) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `job-load-${Date.now()}`,
        role: "assistant",
        text: result.narrative,
        response: result,
      },
    ]);
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-5">
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/15 text-sky-400">
            <TrendingUp className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white">
              AlphaPulse AI Stock Market Assistant
            </h1>
            <p className="text-xs text-slate-400">
              MCP Market &amp; SEC EDGAR Data · Isolated Python Sandbox · Celery Async Workers
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs text-slate-300">
          <Cpu className="h-3.5 w-3.5 text-emerald-400" />
          <span>AI Harness Ready</span>
        </div>
      </header>

      <div className="grid flex-1 gap-5 lg:grid-cols-[1fr_320px]">
        <main className="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex-1 space-y-5 overflow-y-auto pr-1">
            {messages.length === 0 && (
              <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-6">
                <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-sky-300">
                  <Sparkles className="h-4 w-4" />
                  Try a Stock Research Prompt
                </div>
                <p className="mb-4 text-xs text-slate-400">
                  Ask for candlestick charts &amp; technical indicators, SEC financial statements &amp;
                  valuation, multi-stock Python comparisons, DCF what-if scenarios, or deep background
                  Monte Carlo jobs.
                </p>
                <div className="flex flex-wrap gap-2">
                  {QUICK_PROMPTS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => sendQuery(p)}
                      className="rounded-xl border border-slate-700/80 bg-slate-950/70 px-3 py-2 text-left text-xs text-slate-200 transition hover:border-sky-500/60 hover:bg-slate-800"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex flex-col gap-3 ${
                  msg.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-sky-600 text-white"
                      : "w-full max-w-none border border-slate-800 bg-slate-900/90 text-slate-200"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{msg.text}</div>
                </div>

                {msg.response && (
                  <div className="w-full space-y-4">
                    {msg.response.charts.map((chart) => (
                      <CandlestickChart key={chart.id} chart={chart} />
                    ))}
                    {msg.response.tables.map((table) => (
                      <DataTableCard key={table.id} table={table} />
                    ))}
                    <CitationsDrawer
                      citations={msg.response.citations}
                      assumptions={msg.response.assumptions}
                      toolsUsed={msg.response.tools_used}
                      disclaimer={msg.response.disclaimer}
                    />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3 text-xs text-sky-300">
                Running AI harness: querying MCP data sources &amp; Python sandbox...
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendQuery(input);
            }}
            className="mt-4 flex items-center gap-2 border-t border-slate-800 pt-3"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about any ticker (e.g., 'Compare AAPL vs NVDA' or 'What-if DCF for MSFT')..."
              className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="flex items-center gap-1.5 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-500 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              Analyze
            </button>
          </form>
        </main>

        <JobTracker
          apiBase={API_BASE}
          activeJobId={activeJobId}
          onSelectResult={handleLoadJobResult}
        />
      </div>
    </div>
  );
}
