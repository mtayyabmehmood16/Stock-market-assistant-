"use client";

import React, { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi } from "lightweight-charts";
import type { ChartSpec } from "@/types/analysis";

interface Props {
  chart: ChartSpec;
}

export function CandlestickChart({ chart }: Props) {
  const mainContainerRef = useRef<HTMLDivElement | null>(null);
  const oscContainerRef = useRef<HTMLDivElement | null>(null);

  const overlaySeries = chart.series.filter((s) => s.pane === "overlay");
  const oscSeries = chart.series.filter((s) => s.pane === "oscillator");

  const [enabledSeries, setEnabledSeries] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    chart.series.forEach((s) => {
      initial[s.name] = true;
    });
    return initial;
  });

  useEffect(() => {
    const container = mainContainerRef.current;
    if (!container) return;

    const mainChart: IChartApi = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: "#0f172a" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      width: container.clientWidth,
      height: 320,
      timeScale: { borderColor: "#334155" },
      rightPriceScale: { borderColor: "#334155" },
    });

    if (chart.chart_type === "candlestick" && chart.candlesticks.length > 0) {
      const candleSeries = mainChart.addCandlestickSeries({
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderVisible: false,
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
      });
      candleSeries.setData(
        chart.candlesticks.map((c) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
      );

      const volumeSeries = mainChart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(
        chart.candlesticks.map((c) => ({
          time: c.time,
          value: c.volume,
          color: c.close >= c.open ? "rgba(34, 197, 94, 0.35)" : "rgba(239, 68, 68, 0.35)",
        }))
      );
    }

    overlaySeries.forEach((s) => {
      if (!enabledSeries[s.name]) return;
      const line = mainChart.addLineSeries({
        color: s.color,
        lineWidth: 2,
        title: s.name,
      });
      line.setData(
        s.points
          .filter((p): p is { time: string; value: number } => p.value !== null && p.value !== undefined)
          .map((p) => ({ time: p.time, value: p.value }))
      );
    });

    mainChart.timeScale().fitContent();

    let oscChart: IChartApi | null = null;
    const oscContainer = oscContainerRef.current;
    const activeOsc = oscSeries.filter((s) => enabledSeries[s.name]);
    if (oscContainer && activeOsc.length > 0) {
      oscChart = createChart(oscContainer, {
        layout: {
          background: { type: ColorType.Solid, color: "#0f172a" },
          textColor: "#94a3b8",
        },
        grid: {
          vertLines: { color: "#1e293b" },
          horzLines: { color: "#1e293b" },
        },
        width: oscContainer.clientWidth,
        height: 140,
        timeScale: { borderColor: "#334155" },
        rightPriceScale: { borderColor: "#334155" },
      });
      activeOsc.forEach((s) => {
        const line = oscChart!.addLineSeries({
          color: s.color,
          lineWidth: 2,
          title: s.name,
        });
        line.setData(
          s.points
            .filter((p): p is { time: string; value: number } => p.value !== null && p.value !== undefined)
            .map((p) => ({ time: p.time, value: p.value }))
        );
      });
      oscChart.timeScale().fitContent();
    }

    const handleResize = () => {
      if (mainContainerRef.current) {
        mainChart.applyOptions({ width: mainContainerRef.current.clientWidth });
      }
      if (oscContainerRef.current && oscChart) {
        oscChart.applyOptions({ width: oscContainerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      mainChart.remove();
      oscChart?.remove();
    };
  }, [chart, enabledSeries, overlaySeries, oscSeries]);

  const toggleSeries = (name: string) => {
    setEnabledSeries((prev) => ({ ...prev, [name]: !prev[name] }));
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-slate-100">{chart.title}</h4>
          {chart.subtitle && <p className="text-xs text-slate-400">{chart.subtitle}</p>}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {chart.series.map((s) => (
            <button
              key={s.name}
              type="button"
              onClick={() => toggleSeries(s.name)}
              className={`rounded-md border px-2 py-0.5 text-xs font-medium transition ${
                enabledSeries[s.name]
                  ? "border-slate-600 bg-slate-800 text-slate-100"
                  : "border-slate-800 bg-slate-950 text-slate-500"
              }`}
            >
              <span
                className="mr-1.5 inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: s.color }}
              />
              {s.name}
            </button>
          ))}
        </div>
      </div>
      <div ref={mainContainerRef} className="w-full overflow-hidden rounded-lg" />
      {oscSeries.length > 0 && (
        <div className="mt-2">
          <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Oscillators (RSI / MACD)
          </div>
          <div ref={oscContainerRef} className="w-full overflow-hidden rounded-lg" />
        </div>
      )}
    </div>
  );
}
