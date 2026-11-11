from __future__ import annotations

import math
from typing import Any


def _pick_metric(row: dict[str, Any], aliases: tuple[str, ...]) -> float | None:
    for key in aliases:
        if key in row and row[key] is not None:
            try:
                val = float(row[key])
                if not (math.isnan(val) or math.isinf(val)):
                    return val
            except (TypeError, ValueError):
                continue
    lower_map = {k.lower(): v for k, v in row.items()}
    for key in aliases:
        if key.lower() in lower_map and lower_map[key.lower()] is not None:
            try:
                val = float(lower_map[key.lower()])
                if not (math.isnan(val) or math.isinf(val)):
                    return val
            except (TypeError, ValueError):
                continue
    return None


def _fmt_money(val: float | None) -> str:
    if val is None:
        return "N/A"
    av = abs(val)
    if av >= 1e12:
        return f"${val / 1e12:.2f}T"
    if av >= 1e9:
        return f"${val / 1e9:.2f}B"
    if av >= 1e6:
        return f"${val / 1e6:.2f}M"
    return f"${val:,.2f}"


def compute_fundamental_reasoning(
    ticker: str,
    statements: dict[str, dict[str, dict[str, float | None]]],
    valuation: dict[str, Any],
) -> dict[str, Any]:
    """Derive exact multi-year financial ratios, cash conversion, leverage, and valuation insights."""
    income = statements.get("income", {})
    balance = statements.get("balance", {})
    cashflow = statements.get("cashflow", {})

    inc_years = sorted(income.keys())
    bal_years = sorted(balance.keys())
    cf_years = sorted(cashflow.keys())

    facts: dict[str, Any] = {"ticker": ticker}
    bullets: list[str] = []

    # 1. Revenue & Earnings multi-year trajectory + margin expansion/compression
    if len(inc_years) >= 2:
        y0, y1 = inc_years[0], inc_years[-1]
        n_periods = max(1, len(inc_years) - 1)
        rev0 = _pick_metric(income[y0], ("Total Revenue", "Revenue"))
        rev1 = _pick_metric(income[y1], ("Total Revenue", "Revenue"))
        ni0 = _pick_metric(income[y0], ("Net Income", "Net Income Common Stockholders"))
        ni1 = _pick_metric(income[y1], ("Net Income", "Net Income Common Stockholders"))
        op0 = _pick_metric(income[y0], ("Operating Income", "EBIT"))
        op1 = _pick_metric(income[y1], ("Operating Income", "EBIT"))

        if rev0 and rev1 and rev0 > 0 and rev1 > 0:
            rev_cagr_pct = ((rev1 / rev0) ** (1.0 / n_periods) - 1.0) * 100.0
            facts["revenue_cagr_pct"] = round(rev_cagr_pct, 2)
            facts["revenue_span"] = f"{y0}->{y1}"
            bullets.append(
                f"**Revenue Trajectory ({y0}→{y1}):** Grew from {_fmt_money(rev0)} to {_fmt_money(rev1)} "
                f"(`{rev_cagr_pct:+.2f}%` annualized CAGR)."
            )

        if op0 is not None and op1 is not None and rev0 and rev1 and rev0 > 0 and rev1 > 0:
            op_m0 = (op0 / rev0) * 100.0
            op_m1 = (op1 / rev1) * 100.0
            op_delta_bps = round((op_m1 - op_m0) * 100.0)
            facts["operating_margin_start_pct"] = round(op_m0, 2)
            facts["operating_margin_end_pct"] = round(op_m1, 2)
            facts["operating_margin_delta_bps"] = op_delta_bps
            direction = "expanded" if op_delta_bps >= 0 else "compressed"
            bullets.append(
                f"**Operating Leverage:** Operating margin {direction} from `{op_m0:.1f}%` ({y0}) to "
                f"`{op_m1:.1f}%` ({y1}) (`{op_delta_bps:+d} bps`)."
            )

        if ni0 and ni1 and ni0 > 0 and ni1 > 0:
            ni_cagr_pct = ((ni1 / ni0) ** (1.0 / n_periods) - 1.0) * 100.0
            facts["net_income_cagr_pct"] = round(ni_cagr_pct, 2)

    # 2. Cash Flow Quality (FCF Conversion)
    if cf_years and inc_years:
        cf_latest = cashflow[cf_years[-1]]
        inc_latest = income[inc_years[-1]]
        fcf = _pick_metric(cf_latest, ("Free Cash Flow",))
        if fcf is None:
            ocf = _pick_metric(cf_latest, ("Operating Cash Flow", "Total Cash From Operating Activities"))
            capex = _pick_metric(cf_latest, ("Capital Expenditure", "Capital Expenditures"))
            if ocf is not None and capex is not None:
                fcf = ocf - abs(capex)
        ni_latest = _pick_metric(inc_latest, ("Net Income", "Net Income Common Stockholders"))
        if fcf is not None:
            facts["latest_fcf"] = fcf
            if ni_latest and ni_latest > 0:
                fcf_conv_pct = (fcf / ni_latest) * 100.0
                facts["fcf_conversion_pct"] = round(fcf_conv_pct, 1)
                quality_label = "high earnings cash quality (>=90%)" if fcf_conv_pct >= 90 else "moderate/capex-heavy cash conversion"
                bullets.append(
                    f"**Cash Conversion:** Latest Free Cash Flow of {_fmt_money(fcf)} equals `{fcf_conv_pct:.1f}%` "
                    f"of Net Income ({quality_label})."
                )
            mcap = valuation.get("market_cap")
            if mcap and float(mcap) > 0:
                fcf_yield_pct = (fcf / float(mcap)) * 100.0
                facts["fcf_yield_pct"] = round(fcf_yield_pct, 2)

    # 3. Balance Sheet Solvency & Net Cash / Debt
    if bal_years:
        bal_latest = balance[bal_years[-1]]
        cash = _pick_metric(bal_latest, ("Cash & Equivalents", "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"))
        debt = _pick_metric(bal_latest, ("Total Debt", "Long Term Debt"))
        equity = _pick_metric(bal_latest, ("Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"))
        if cash is not None and debt is not None:
            net_cash = cash - debt
            facts["net_cash"] = net_cash
            pos_label = "net cash" if net_cash >= 0 else "net debt"
            bullets.append(
                f"**Balance Sheet Position ({bal_years[-1]}):** Cash {_fmt_money(cash)} vs. Debt {_fmt_money(debt)} "
                f"→ `{pos_label}` of {_fmt_money(abs(net_cash))}."
            )
        if debt is not None and equity and equity > 0:
            d_to_e = debt / equity
            facts["debt_to_equity"] = round(d_to_e, 2)

    # 4. Valuation & Implied Earnings Expectations
    pe_t = valuation.get("pe_trailing")
    pe_f = valuation.get("pe_forward")
    rev_g = valuation.get("revenue_growth_pct")
    if pe_t and pe_f and pe_f > 0:
        implied_eps_growth_pct = ((pe_t / pe_f) - 1.0) * 100.0
        facts["implied_forward_eps_growth_pct"] = round(implied_eps_growth_pct, 1)
        bullets.append(
            f"**Valuation & Growth Implication:** Forward P/E (`{pe_f:.1f}x`) vs. Trailing P/E (`{pe_t:.1f}x`) "
            f"prices in roughly `{implied_eps_growth_pct:+.1f}%` forward EPS growth"
            + (f" (against `{rev_g:.1f}%` YoY revenue growth)." if rev_g is not None else ".")
        )

    return {"facts": facts, "bullets": bullets}


def synthesize_cross_domain_insight(
    ticker: str,
    tech_summary: dict[str, Any] | None,
    fund_facts: dict[str, Any] | None,
    valuation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine technical regime, valuation, and fundamental quality into one grounded synthesis."""
    if not tech_summary or not fund_facts:
        return {"alignment": "single-domain", "summary": ""}

    trend = str(tech_summary.get("trend", "mixed / consolidating"))
    rsi = tech_summary.get("rsi_14")
    vol_ratio = tech_summary.get("volume_ratio")
    op_delta = fund_facts.get("operating_margin_delta_bps")
    fcf_conv = fund_facts.get("fcf_conversion_pct")
    pe_f = (valuation or {}).get("pe_forward")
    roe = (valuation or {}).get("roe_pct")

    fund_strength = 0
    if op_delta is not None and op_delta > 0:
        fund_strength += 1
    if fcf_conv is not None and fcf_conv >= 85:
        fund_strength += 1
    if roe is not None and roe >= 15:
        fund_strength += 1

    tech_bullish = trend == "bullish"
    tech_bearish = trend == "bearish"

    if fund_strength >= 2 and tech_bullish:
        alignment = "convergent_bullish"
        stance = "Fundamentals and technicals are aligned positively (margin/cash strength confirmed by upward price trend)"
    elif fund_strength >= 2 and tech_bearish:
        alignment = "fundamental_strong_technical_weak"
        stance = "Divergence detected: strong historical fundamentals & cash generation, but bearish short-term price trend"
    elif fund_strength <= 1 and tech_bullish:
        alignment = "momentum_ahead_of_fundamentals"
        stance = "Technical momentum is bullish, while fundamental margin/cash metrics are mixed — monitor valuation risk"
    else:
        alignment = "mixed_neutral"
        stance = "Both technical signals and fundamental growth/valuation indicators are mixed/consolidating"

    notes = [stance]
    if rsi is not None:
        if rsi >= 70:
            notes.append(f"RSI(14) at `{rsi}` signals near-term overbought conditions")
        elif rsi <= 30:
            notes.append(f"RSI(14) at `{rsi}` signals near-term oversold conditions")
    if vol_ratio is not None and vol_ratio >= 1.3:
        notes.append(f"Volume is elevated at `{vol_ratio}x` 20-day average, confirming active participation")
    if pe_f is not None:
        notes.append(f"Forward P/E stands at `{pe_f:.1f}x`")

    return {
        "alignment": alignment,
        "summary": f"### Cross-Domain Synthesis ({ticker})\n- " + "; ".join(notes) + ".",
    }
