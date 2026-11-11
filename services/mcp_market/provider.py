from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import yfinance as yf
from pydantic import BaseModel, Field

from packages.shared_schemas.schemas import CandlestickPoint, Citation, IndicatorSeries, utc_now_iso
from services.mcp_market.indicators import compute_indicators


class QuoteData(BaseModel):
    ticker: str
    price: float
    previous_close: float
    change: float
    change_pct: float
    volume: int
    market_cap: float | None = None
    currency: str = "USD"
    citation: Citation


class OHLCVData(BaseModel):
    ticker: str
    period: str
    interval: str
    candles: list[CandlestickPoint] = Field(default_factory=list)
    citation: Citation


class TechnicalAnalysisData(BaseModel):
    ticker: str
    period: str
    interval: str
    candles: list[CandlestickPoint] = Field(default_factory=list)
    indicators: list[IndicatorSeries] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    citation: Citation


class MarketDataProvider(Protocol):
    def get_quote(self, ticker: str) -> QuoteData: ...
    def get_ohlcv(self, ticker: str, period: str = "6mo", interval: str = "1d") -> OHLCVData: ...
    def get_technical_indicators(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
        indicators: list[str] | None = None,
    ) -> TechnicalAnalysisData: ...


_FIXTURE_SEEDS: dict[str, dict[str, float]] = {
    "AAPL": {"base": 212.0, "drift": 0.0008, "vol": 0.015, "mcap": 3.25e12, "base_vol": 48_000_000},
    "MSFT": {"base": 418.0, "drift": 0.0009, "vol": 0.014, "mcap": 3.10e12, "base_vol": 22_000_000},
    "NVDA": {"base": 124.0, "drift": 0.0016, "vol": 0.026, "mcap": 3.05e12, "base_vol": 210_000_000},
    "GOOGL": {"base": 176.0, "drift": 0.0007, "vol": 0.016, "mcap": 2.18e12, "base_vol": 26_000_000},
    "AMZN": {"base": 195.0, "drift": 0.0008, "vol": 0.018, "mcap": 2.04e12, "base_vol": 39_000_000},
    "TSLA": {"base": 248.0, "drift": 0.0005, "vol": 0.032, "mcap": 7.90e11, "base_vol": 88_000_000},
    "SPY": {"base": 565.0, "drift": 0.0004, "vol": 0.009, "mcap": 5.60e11, "base_vol": 62_000_000},
}


class FixtureMarketProvider:
    """Deterministic fixture market data provider for offline dev, tests, and fallback."""

    def _generate_candles(self, ticker: str, period: str) -> list[CandlestickPoint]:
        t = ticker.upper()
        seed_cfg = _FIXTURE_SEEDS.get(
            t,
            {
                "base": 100.0 + (sum(ord(ch) for ch in t) % 150),
                "drift": 0.0006,
                "vol": 0.018,
                "mcap": 5.0e10,
                "base_vol": 12_000_000,
            },
        )
        bar_counts = {"1mo": 22, "3mo": 64, "6mo": 126, "1y": 252, "2y": 504}
        n_bars = bar_counts.get(period, 126)

        # Deterministic pseudo-random wave based on ticker characters
        phase = (sum(ord(ch) * (i + 1) for i, ch in enumerate(t)) % 97) / 10.0
        price = seed_cfg["base"] * 0.9
        start_date = datetime(2026, 5, 1, tzinfo=timezone.utc)
        candles: list[CandlestickPoint] = []

        day_idx = 0
        while len(candles) < n_bars:
            dt = start_date + timedelta(days=day_idx)
            day_idx += 1
            if dt.weekday() >= 5:
                continue
            i = len(candles)
            wave = math.sin(i * 0.22 + phase) * seed_cfg["vol"] + math.cos(i * 0.09 + phase) * (seed_cfg["vol"] * 0.5)
            ret = seed_cfg["drift"] + wave * 0.65
            open_p = price
            close_p = max(1.0, open_p * (1.0 + ret))
            spread = max(0.15, abs(close_p - open_p) + open_p * seed_cfg["vol"] * 0.45)
            high_p = max(open_p, close_p) + spread * 0.45
            low_p = max(0.5, min(open_p, close_p) - spread * 0.4)
            vol = int(seed_cfg["base_vol"] * (1.0 + 0.35 * abs(math.sin(i * 0.4 + phase))))
            candles.append(
                CandlestickPoint(
                    time=dt.strftime("%Y-%m-%d"),
                    open=round(open_p, 2),
                    high=round(high_p, 2),
                    low=round(low_p, 2),
                    close=round(close_p, 2),
                    volume=float(vol),
                )
            )
            price = close_p
        return candles

    def get_quote(self, ticker: str) -> QuoteData:
        t = ticker.upper()
        candles = self._generate_candles(t, "1mo")
        latest = candles[-1]
        prev = candles[-2] if len(candles) >= 2 else latest
        change = round(latest.close - prev.close, 2)
        change_pct = round((change / prev.close) * 100.0, 2) if prev.close else 0.0
        mcap = _FIXTURE_SEEDS.get(t, {}).get("mcap", 7.5e10)
        return QuoteData(
            ticker=t,
            price=latest.close,
            previous_close=prev.close,
            change=change,
            change_pct=change_pct,
            volume=int(latest.volume),
            market_cap=mcap,
            citation=Citation(
                source="Market Data Fixture (Offline Demo)",
                label=f"{t} quote snapshot",
                retrieved_at=utc_now_iso(),
            ),
        )

    def get_ohlcv(self, ticker: str, period: str = "6mo", interval: str = "1d") -> OHLCVData:
        t = ticker.upper()
        candles = self._generate_candles(t, period)
        return OHLCVData(
            ticker=t,
            period=period,
            interval=interval,
            candles=candles,
            citation=Citation(
                source="Market Data Fixture (Offline Demo)",
                label=f"{t} OHLCV ({period}, {interval})",
                retrieved_at=utc_now_iso(),
            ),
        )

    def get_technical_indicators(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
        indicators: list[str] | None = None,
    ) -> TechnicalAnalysisData:
        ohlcv = self.get_ohlcv(ticker, period=period, interval=interval)
        ind_series, summary = compute_indicators(ohlcv.candles, indicators)
        return TechnicalAnalysisData(
            ticker=ohlcv.ticker,
            period=period,
            interval=interval,
            candles=ohlcv.candles,
            indicators=ind_series,
            summary=summary,
            citation=ohlcv.citation,
        )


class YFinanceMarketProvider:
    """Live yfinance market data provider with TTL caching and optional fixture fallback."""

    def __init__(self, mode: str = "auto", cache_ttl_seconds: int = 120) -> None:
        self.mode = mode
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}
        self._fallback = FixtureMarketProvider()

    def _get_cached(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def _set_cached(self, key: str, value: Any) -> None:
        self._cache[key] = (time.time(), value)

    def get_quote(self, ticker: str) -> QuoteData:
        t = ticker.upper()
        if self.mode == "fixture":
            return self._fallback.get_quote(t)
        cache_key = f"quote:{t}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            tk = yf.Ticker(t)
            hist = tk.history(period="5d", interval="1d", auto_adjust=False)
            if hist is None or hist.empty:
                raise ValueError(f"No history returned for {t}")
            latest_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else latest_close
            latest_vol = int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0
            change = round(latest_close - prev_close, 2)
            change_pct = round((change / prev_close) * 100.0, 2) if prev_close else 0.0
            info = getattr(tk, "fast_info", None)
            mcap = float(info.get("marketCap")) if info and info.get("marketCap") else None
            quote = QuoteData(
                ticker=t,
                price=round(latest_close, 2),
                previous_close=round(prev_close, 2),
                change=change,
                change_pct=change_pct,
                volume=latest_vol,
                market_cap=mcap,
                citation=Citation(
                    source="Yahoo Finance (yfinance)",
                    label=f"{t} quote",
                    url=f"https://finance.yahoo.com/quote/{t}",
                    retrieved_at=utc_now_iso(),
                ),
            )
            self._set_cached(cache_key, quote)
            return quote
        except Exception:
            if self.mode == "auto":
                return self._fallback.get_quote(t)
            raise

    def get_ohlcv(self, ticker: str, period: str = "6mo", interval: str = "1d") -> OHLCVData:
        t = ticker.upper()
        if self.mode == "fixture":
            return self._fallback.get_ohlcv(t, period=period, interval=interval)
        cache_key = f"ohlcv:{t}:{period}:{interval}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            tk = yf.Ticker(t)
            hist = tk.history(period=period, interval=interval, auto_adjust=False)
            if hist is None or hist.empty:
                raise ValueError(f"Empty OHLCV history for {t}")
            candles: list[CandlestickPoint] = []
            for idx, row in hist.iterrows():
                time_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                candles.append(
                    CandlestickPoint(
                        time=time_str,
                        open=round(float(row["Open"]), 2),
                        high=round(float(row["High"]), 2),
                        low=round(float(row["Low"]), 2),
                        close=round(float(row["Close"]), 2),
                        volume=float(row.get("Volume", 0.0) or 0.0),
                    )
                )
            data = OHLCVData(
                ticker=t,
                period=period,
                interval=interval,
                candles=candles,
                citation=Citation(
                    source="Yahoo Finance (yfinance)",
                    label=f"{t} OHLCV ({period}, {interval})",
                    url=f"https://finance.yahoo.com/quote/{t}",
                    retrieved_at=utc_now_iso(),
                ),
            )
            self._set_cached(cache_key, data)
            return data
        except Exception:
            if self.mode == "auto":
                return self._fallback.get_ohlcv(t, period=period, interval=interval)
            raise

    def get_technical_indicators(
        self,
        ticker: str,
        period: str = "6mo",
        interval: str = "1d",
        indicators: list[str] | None = None,
    ) -> TechnicalAnalysisData:
        ohlcv = self.get_ohlcv(ticker, period=period, interval=interval)
        ind_series, summary = compute_indicators(ohlcv.candles, indicators)
        return TechnicalAnalysisData(
            ticker=ohlcv.ticker,
            period=period,
            interval=interval,
            candles=ohlcv.candles,
            indicators=ind_series,
            summary=summary,
            citation=ohlcv.citation,
        )
