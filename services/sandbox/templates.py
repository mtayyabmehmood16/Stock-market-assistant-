from __future__ import annotations

STOCK_COMPARISON_SCRIPT = """
import math
import numpy as np

series_map = inputs["series"]
metrics = []
normalized_series = {}

for ticker, candles in series_map.items():
    closes = np.array([float(c["close"]) for c in candles], dtype=float)
    times = [c["time"] for c in candles]
    if len(closes) < 2:
        continue
    daily_ret = np.diff(closes) / closes[:-1]
    total_return_pct = ((closes[-1] / closes[0]) - 1.0) * 100.0
    ann_vol_pct = float(np.std(daily_ret, ddof=1) * math.sqrt(252) * 100.0) if len(daily_ret) > 1 else 0.0
    ann_ret_pct = float(np.mean(daily_ret) * 252 * 100.0)
    sharpe = round(ann_ret_pct / ann_vol_pct, 2) if ann_vol_pct > 0 else 0.0
    running_max = np.maximum.accumulate(closes)
    drawdowns = (closes / running_max) - 1.0
    max_dd_pct = float(np.min(drawdowns) * 100.0)

    norm_vals = [round(float((c / closes[0]) * 100.0), 2) for c in closes]
    normalized_series[ticker] = [{"time": t, "value": v} for t, v in zip(times, norm_vals)]

    metrics.append({
        "ticker": ticker,
        "start_price": round(float(closes[0]), 2),
        "end_price": round(float(closes[-1]), 2),
        "total_return_pct": round(total_return_pct, 2),
        "annualized_vol_pct": round(ann_vol_pct, 2),
        "sharpe_proxy": sharpe,
        "max_drawdown_pct": round(max_dd_pct, 2),
    })

result = {
    "metrics": metrics,
    "normalized_series": normalized_series,
}
"""

DCF_WHAT_IF_SCRIPT = """
base_fcf = float(inputs["base_fcf"])
shares_outstanding = float(inputs.get("shares_outstanding", 1.0))
net_cash = float(inputs.get("net_cash", 0.0))
growth_rate = float(inputs.get("fcf_growth_rate", 0.12))
wacc = float(inputs.get("wacc", 0.09))
terminal_growth = float(inputs.get("terminal_growth", 0.03))
years = int(inputs.get("years", 5))
current_price = float(inputs.get("current_price", 0.0))

def calc_dcf(g_rate, disc_rate, term_g):
    if disc_rate <= term_g:
        return None
    pv_fcfs = 0.0
    fcf = base_fcf
    yearly = []
    for y in range(1, years + 1):
        fcf = fcf * (1.0 + g_rate)
        pv = fcf / ((1.0 + disc_rate) ** y)
        pv_fcfs += pv
        yearly.append({"year": y, "projected_fcf": round(fcf, 2), "pv_fcf": round(pv, 2)})
    terminal_fcf = fcf * (1.0 + term_g)
    tv = terminal_fcf / (disc_rate - term_g)
    pv_tv = tv / ((1.0 + disc_rate) ** years)
    ev = pv_fcfs + pv_tv
    equity_val = ev + net_cash
    intrinsic_per_share = equity_val / shares_outstanding if shares_outstanding > 0 else equity_val
    return round(intrinsic_per_share, 2), yearly, round(ev, 2), round(pv_tv / ev * 100.0, 1) if ev else 0.0

base_calc = calc_dcf(growth_rate, wacc, terminal_growth)
intrinsic_price, yearly_projection, enterprise_value, tv_share_pct = base_calc

wacc_grid = [round(wacc + d, 4) for d in (-0.015, -0.0075, 0.0, 0.0075, 0.015)]
tg_grid = [round(terminal_growth + d, 4) for d in (-0.01, -0.005, 0.0, 0.005, 0.01)]
sensitivity = []
for w in wacc_grid:
    row = {"wacc_pct": round(w * 100, 2)}
    for tg in tg_grid:
        calc = calc_dcf(growth_rate, w, tg)
        row[f"tg_{round(tg*100, 2)}%"] = calc[0] if calc else None
    sensitivity.append(row)

upside_pct = round(((intrinsic_price / current_price) - 1.0) * 100.0, 2) if current_price > 0 else None

result = {
    "intrinsic_value_per_share": intrinsic_price,
    "current_price": round(current_price, 2),
    "implied_upside_pct": upside_pct,
    "enterprise_value": enterprise_value,
    "terminal_value_share_pct": tv_share_pct,
    "yearly_projection": yearly_projection,
    "sensitivity_matrix": sensitivity,
}
"""

MONTE_CARLO_SCRIPT = """
import math
import numpy as np

closes = np.array([float(x) for x in inputs["closes"]], dtype=float)
horizon_days = int(inputs.get("horizon_days", 90))
n_paths = int(inputs.get("n_paths", 2000))
seed = int(inputs.get("seed", 42))

returns = np.diff(np.log(closes))
mu = float(np.mean(returns))
sigma = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.015
last_price = float(closes[-1])

rng = np.random.default_rng(seed)
shocks = rng.normal(loc=mu, scale=sigma, size=(n_paths, horizon_days))
log_paths = np.cumsum(shocks, axis=1)
price_paths = last_price * np.exp(log_paths)

p10 = np.percentile(price_paths, 10, axis=0)
p50 = np.percentile(price_paths, 50, axis=0)
p90 = np.percentile(price_paths, 90, axis=0)
prob_above = float(np.mean(price_paths[:, -1] > last_price) * 100.0)

result = {
    "last_price": round(last_price, 2),
    "horizon_days": horizon_days,
    "n_paths": n_paths,
    "daily_drift": round(mu, 6),
    "daily_volatility": round(sigma, 6),
    "terminal_p10": round(float(p10[-1]), 2),
    "terminal_p50": round(float(p50[-1]), 2),
    "terminal_p90": round(float(p90[-1]), 2),
    "prob_positive_return_pct": round(prob_above, 2),
    "cone": {
        "p10": [round(float(v), 2) for v in p10[::5]],
        "p50": [round(float(v), 2) for v in p50[::5]],
        "p90": [round(float(v), 2) for v in p90[::5]],
    },
}
"""
