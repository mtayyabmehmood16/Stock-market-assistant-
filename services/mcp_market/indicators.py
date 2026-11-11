from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from packages.shared_schemas.schemas import CandlestickPoint, IndicatorSeries, LinePoint


def compute_indicators(
    candles: list[CandlestickPoint],
    requested: list[str] | None = None,
) -> tuple[list[IndicatorSeries], dict[str, Any]]:
    """Compute technical indicators and a structured trend summary from OHLCV candles."""
    if not candles:
        return [], {"trend": "neutral", "signals": []}

    req = {item.lower() for item in (requested or ["sma_20", "sma_50", "ema_20", "rsi_14", "macd", "bb_20"])}
    df = pd.DataFrame([c.model_dump() for c in candles])
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)
    times = df["time"].tolist()

    def to_line_points(series: pd.Series) -> list[LinePoint]:
        points: list[LinePoint] = []
        for t, val in zip(times, series.tolist()):
            if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                points.append(LinePoint(time=t, value=None))
            else:
                points.append(LinePoint(time=t, value=round(float(val), 4)))
        return points

    series_list: list[IndicatorSeries] = []
    summary_metrics: dict[str, Any] = {}

    sma_20 = close.rolling(window=20).mean()
    sma_50 = close.rolling(window=50).mean()
    ema_20 = close.ewm(span=20, adjust=False).mean()

    if "sma_20" in req or "sma" in req:
        series_list.append(
            IndicatorSeries(name="SMA 20", pane="overlay", color="#38bdf8", points=to_line_points(sma_20))
        )
    if "sma_50" in req or "sma" in req:
        series_list.append(
            IndicatorSeries(name="SMA 50", pane="overlay", color="#f59e0b", points=to_line_points(sma_50))
        )
    if "ema_20" in req or "ema" in req:
        series_list.append(
            IndicatorSeries(name="EMA 20", pane="overlay", color="#a78bfa", points=to_line_points(ema_20))
        )

    if "bb_20" in req or "bollinger" in req:
        std_20 = close.rolling(window=20).std()
        bb_upper = sma_20 + 2.0 * std_20
        bb_lower = sma_20 - 2.0 * std_20
        series_list.append(
            IndicatorSeries(name="BB Upper (20,2)", pane="overlay", color="#94a3b8", points=to_line_points(bb_upper))
        )
        series_list.append(
            IndicatorSeries(name="BB Lower (20,2)", pane="overlay", color="#94a3b8", points=to_line_points(bb_lower))
        )

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi_14 = 100.0 - (100.0 / (1.0 + rs))
    rsi_14 = rsi_14.fillna(50.0)

    if "rsi_14" in req or "rsi" in req:
        series_list.append(
            IndicatorSeries(name="RSI 14", pane="oscillator", color="#22c55e", points=to_line_points(rsi_14))
        )

    # MACD (12, 26, 9)
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()

    if "macd" in req:
        series_list.append(
            IndicatorSeries(name="MACD (12,26)", pane="oscillator", color="#06b6d4", points=to_line_points(macd_line))
        )
        series_list.append(
            IndicatorSeries(name="MACD Signal (9)", pane="oscillator", color="#f97316", points=to_line_points(macd_signal))
        )

    # ATR 14
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_14 = tr.rolling(window=14).mean()

    # Latest metrics & trend classification
    latest_close = float(close.iloc[-1])
    first_close = float(close.iloc[0])
    period_return_pct = ((latest_close / first_close) - 1.0) * 100.0 if first_close else 0.0
    latest_sma20 = float(sma_20.iloc[-1]) if not math.isnan(sma_20.iloc[-1]) else None
    latest_sma50 = float(sma_50.iloc[-1]) if not math.isnan(sma_50.iloc[-1]) else None
    latest_rsi = float(rsi_14.iloc[-1]) if not math.isnan(rsi_14.iloc[-1]) else None
    latest_macd = float(macd_line.iloc[-1]) if not math.isnan(macd_line.iloc[-1]) else None
    latest_signal = float(macd_signal.iloc[-1]) if not math.isnan(macd_signal.iloc[-1]) else None
    latest_atr = float(atr_14.iloc[-1]) if not math.isnan(atr_14.iloc[-1]) else None
    avg_vol_20 = float(volume.tail(20).mean()) if len(volume) else 0.0
    latest_vol = float(volume.iloc[-1]) if len(volume) else 0.0

    signals: list[str] = []
    bull_score = 0
    if latest_sma20 is not None:
        if latest_close > latest_sma20:
            bull_score += 1
            signals.append("Price above SMA 20 (short-term bullish)")
        else:
            bull_score -= 1
            signals.append("Price below SMA 20 (short-term bearish)")
    if latest_sma20 is not None and latest_sma50 is not None:
        if latest_sma20 > latest_sma50:
            bull_score += 1
            signals.append("SMA 20 above SMA 50 (positive medium-term trend)")
        else:
            bull_score -= 1
            signals.append("SMA 20 below SMA 50 (negative medium-term trend)")
    if latest_macd is not None and latest_signal is not None:
        if latest_macd > latest_signal:
            bull_score += 1
            signals.append("MACD above Signal line (bullish momentum)")
        else:
            bull_score -= 1
            signals.append("MACD below Signal line (bearish momentum)")
    if latest_rsi is not None:
        if latest_rsi >= 70:
            signals.append(f"RSI 14 at {latest_rsi:.1f} (overbought zone >= 70)")
        elif latest_rsi <= 30:
            signals.append(f"RSI 14 at {latest_rsi:.1f} (oversold zone <= 30)")
        else:
            signals.append(f"RSI 14 at {latest_rsi:.1f} (neutral momentum)")

    if bull_score >= 2:
        trend = "bullish"
    elif bull_score <= -2:
        trend = "bearish"
    else:
        trend = "mixed / consolidating"

    summary_metrics = {
        "latest_close": round(latest_close, 2),
        "period_return_pct": round(period_return_pct, 2),
        "sma_20": round(latest_sma20, 2) if latest_sma20 is not None else None,
        "sma_50": round(latest_sma50, 2) if latest_sma50 is not None else None,
        "rsi_14": round(latest_rsi, 2) if latest_rsi is not None else None,
        "macd": round(latest_macd, 4) if latest_macd is not None else None,
        "macd_signal": round(latest_signal, 4) if latest_signal is not None else None,
        "atr_14": round(latest_atr, 2) if latest_atr is not None else None,
        "latest_volume": int(latest_vol),
        "avg_volume_20d": int(avg_vol_20),
        "volume_ratio": round(latest_vol / avg_vol_20, 2) if avg_vol_20 > 0 else None,
        "trend": trend,
        "signals": signals,
    }
    return series_list, summary_metrics
