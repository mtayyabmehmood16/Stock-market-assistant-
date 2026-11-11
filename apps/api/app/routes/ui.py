from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])

HTML_PAGE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AlphaPulse AI — Stock Market Assistant</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lightweight-charts@4.2.1/dist/lightweight-charts.standalone.production.js"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <div class="mx-auto max-w-7xl px-4 py-5 flex flex-col min-h-screen">
    <header class="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
      <div>
        <h1 class="text-lg font-bold text-white">AlphaPulse AI Stock Market Assistant</h1>
        <p class="text-xs text-slate-400">MCP Market &amp; SEC EDGAR Data · Isolated Python Sandbox · Celery Workers</p>
      </div>
      <div class="flex items-center gap-3 text-xs">
        <a href="/docs" class="rounded-lg border border-slate-700 px-3 py-1.5 text-sky-400 hover:bg-slate-900">API Docs (/docs)</a>
        <span class="rounded-full border border-emerald-700/50 bg-emerald-950/50 px-3 py-1 text-emerald-300">FastAPI Live</span>
      </div>
    </header>

    <div class="grid flex-1 gap-5 lg:grid-cols-[1fr_320px]">
      <main class="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
        <div id="messages" class="flex-1 space-y-4 overflow-y-auto pr-1">
          <div id="welcome" class="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <h2 class="text-sm font-semibold text-sky-300 mb-2">Try a Stock Research Prompt</h2>
            <p class="text-xs text-slate-400 mb-3">Ask for candlestick charts &amp; technical indicators, SEC fundamentals, multi-stock Python comparisons, DCF what-if scenarios, or background Monte Carlo jobs.</p>
            <div class="flex flex-wrap gap-2" id="quickPrompts"></div>
          </div>
        </div>

        <form id="chatForm" class="mt-4 flex gap-2 border-t border-slate-800 pt-3">
          <input id="queryInput" type="text" placeholder="Ask about any ticker (e.g., 'Compare AAPL vs NVDA' or 'What-if DCF for MSFT')..."
            class="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-500 focus:outline-none" />
          <button id="sendBtn" type="submit"
            class="rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50">Analyze</button>
        </form>
      </main>

      <aside class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-slate-100">Background Jobs (Celery)</h3>
          <button onclick="loadJobs()" class="text-xs text-sky-400 hover:text-sky-300">Refresh</button>
        </div>
        <div id="jobsList" class="space-y-2.5 text-xs text-slate-400">Loading...</div>
      </aside>
    </div>
  </div>

  <script>
    const PROMPTS = [
      "Show AAPL technical candlestick chart, RSI, MACD, and volume",
      "Analyze MSFT fundamentals, financial statements, and valuation",
      "Compare AAPL vs MSFT vs NVDA over 6 months in Python",
      "Run a what-if DCF valuation for NVDA with growth 18% and WACC 9.5%",
      "Run a deep background Monte Carlo and peer analysis for AAPL and MSFT"
    ];
    let conversationId = null;

    const qp = document.getElementById("quickPrompts");
    PROMPTS.forEach((p) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-left text-xs text-slate-200 hover:border-sky-500";
      btn.textContent = p;
      btn.onclick = () => sendQuery(p);
      qp.appendChild(btn);
    });

    function esc(s) {
      return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function renderChart(container, chartSpec) {
      const wrap = document.createElement("div");
      wrap.className = "rounded-xl border border-slate-800 bg-slate-900/80 p-4";
      wrap.innerHTML = `<div class="mb-2"><h4 class="text-sm font-semibold text-slate-100">${esc(chartSpec.title)}</h4>${chartSpec.subtitle ? `<p class="text-xs text-slate-400">${esc(chartSpec.subtitle)}</p>` : ""}</div>`;
      const chartDiv = document.createElement("div");
      chartDiv.style.height = "300px";
      wrap.appendChild(chartDiv);
      container.appendChild(wrap);

      const chart = LightweightCharts.createChart(chartDiv, {
        layout: { background: { type: "solid", color: "#0f172a" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
        width: chartDiv.clientWidth || 720,
        height: 300,
      });

      if (chartSpec.chart_type === "candlestick" && chartSpec.candlesticks?.length) {
        const cs = chart.addCandlestickSeries({ upColor: "#22c55e", downColor: "#ef4444", borderVisible: false, wickUpColor: "#22c55e", wickDownColor: "#ef4444" });
        cs.setData(chartSpec.candlesticks.map(c => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })));
        const vol = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
        vol.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        vol.setData(chartSpec.candlesticks.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)" })));
      }

      (chartSpec.series || []).filter(s => s.pane === "overlay").forEach(s => {
        const line = chart.addLineSeries({ color: s.color || "#38bdf8", lineWidth: 2, title: s.name });
        line.setData((s.points || []).filter(p => p.value !== null && p.value !== undefined));
      });
      chart.timeScale().fitContent();
    }

    function renderTable(container, tbl) {
      const wrap = document.createElement("div");
      wrap.className = "rounded-xl border border-slate-800 bg-slate-900/80 p-4 overflow-x-auto";
      const ths = tbl.columns.map(c => `<th class="px-3 py-2 text-left font-medium text-slate-400 border-b border-slate-800">${esc(c)}</th>`).join("");
      const trs = tbl.rows.map(r => `<tr class="hover:bg-slate-800/40">${r.map((cell, i) => `<td class="px-3 py-2 border-b border-slate-800/60 ${i===0 ? "font-medium text-slate-200" : "text-slate-300"}">${cell === null ? "—" : esc(cell)}</td>`).join("")}</tr>`).join("");
      wrap.innerHTML = `<h4 class="text-sm font-semibold text-slate-100 mb-2">${esc(tbl.title)}</h4><table class="w-full text-xs"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
      container.appendChild(wrap);
    }

    function renderResponse(data) {
      const box = document.getElementById("messages");
      const wrap = document.createElement("div");
      wrap.className = "space-y-3";
      const msg = document.createElement("div");
      msg.className = "rounded-2xl border border-slate-800 bg-slate-900/90 p-4 text-sm whitespace-pre-wrap text-slate-200";
      msg.textContent = data.narrative;
      wrap.appendChild(msg);
      (data.charts || []).forEach(c => renderChart(wrap, c));
      (data.tables || []).forEach(t => renderTable(wrap, t));

      const meta = document.createElement("details");
      meta.className = "rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-2 text-xs text-slate-300";
      meta.innerHTML = `<summary class="cursor-pointer font-medium">Sources (${(data.citations||[]).length}) · Assumptions (${(data.assumptions||[]).length}) · Tools (${(data.tools_used||[]).join(", ")})</summary>
        <div class="mt-2 space-y-1 text-[11px] text-slate-400">
          ${(data.citations||[]).map(c => `<div>• <b>${esc(c.label)}</b> — ${esc(c.source)} (${esc(c.retrieved_at)})</div>`).join("")}
          ${(data.assumptions||[]).map(a => `<div>• <b>${esc(a.key)}:</b> ${esc(a.value)} (${esc(a.rationale || "")})</div>`).join("")}
          <div class="pt-1 text-amber-300/80">${esc(data.disclaimer)}</div>
        </div>`;
      wrap.appendChild(meta);
      box.appendChild(wrap);
      box.scrollTop = box.scrollHeight;
    }

    async function sendQuery(text) {
      const q = text.trim();
      if (!q) return;
      document.getElementById("welcome")?.remove();
      const box = document.getElementById("messages");
      const u = document.createElement("div");
      u.className = "flex justify-end";
      u.innerHTML = `<div class="rounded-2xl bg-sky-600 px-4 py-2.5 text-sm text-white max-w-2xl">${esc(q)}</div>`;
      box.appendChild(u);

      document.getElementById("queryInput").value = "";
      document.getElementById("sendBtn").disabled = true;
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q, conversation_id: conversationId }),
        });
        const data = await res.json();
        conversationId = data.conversation_id;
        renderResponse(data);
        loadJobs();
      } catch (e) {
        const err = document.createElement("div");
        err.className = "rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-200";
        err.textContent = "Request failed: " + e;
        box.appendChild(err);
      } finally {
        document.getElementById("sendBtn").disabled = false;
      }
    }

    async function loadJobs() {
      const list = document.getElementById("jobsList");
      try {
        const res = await fetch("/api/jobs");
        const jobs = await res.json();
        if (!jobs.length) {
          list.innerHTML = `<div class="rounded-xl border border-dashed border-slate-800 p-3 text-center">No jobs yet.</div>`;
          return;
        }
        list.innerHTML = "";
        jobs.forEach(j => {
          const card = document.createElement("div");
          card.className = "rounded-xl border border-slate-800 bg-slate-950/70 p-3 space-y-1";
          card.innerHTML = `<div class="flex justify-between font-semibold text-slate-200"><span>${esc(j.tickers.join(", "))}</span><span>${esc(j.status)}</span></div>
            <div class="text-[11px] text-slate-400">${esc(j.message)}</div>
            <div class="h-1.5 rounded-full bg-slate-800 overflow-hidden"><div class="h-full bg-sky-500" style="width:${j.progress}%"></div></div>`;
          if (j.result) {
            const btn = document.createElement("button");
            btn.className = "text-[11px] font-medium text-sky-400 hover:text-sky-300 mt-1";
            btn.textContent = "Load Report ->";
            btn.onclick = () => renderResponse(j.result);
            card.appendChild(btn);
          }
          list.appendChild(card);
        });
      } catch {
        list.textContent = "Failed to load jobs.";
      }
    }

    document.getElementById("chatForm").onsubmit = (e) => {
      e.preventDefault();
      sendQuery(document.getElementById("queryInput").value);
    };
    loadJobs();
  </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(content=HTML_PAGE)
