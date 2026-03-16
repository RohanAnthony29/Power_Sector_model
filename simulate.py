"""
PJM Resource Adequacy Stress Test - Core Simulation Engine
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ──────────────────────────────────────────────────────────────
# Generator Fleet
# ──────────────────────────────────────────────────────────────
GENERATOR_FLEET = {
    "nuclear":       {"capacity_gw": 32.0, "outage_rate": 0.05, "type": "firm",      "cost_mwh": 30,  "co2_lb_mwh": 0},
    "gas_cc":        {"capacity_gw": 55.0, "outage_rate": 0.06, "type": "firm",      "cost_mwh": 55,  "co2_lb_mwh": 800},
    "gas_peaker":    {"capacity_gw": 25.0, "outage_rate": 0.10, "type": "firm",      "cost_mwh": 120, "co2_lb_mwh": 1100},
    "coal":          {"capacity_gw": 18.0, "outage_rate": 0.08, "type": "firm",      "cost_mwh": 45,  "co2_lb_mwh": 2100},
    "wind":          {"capacity_gw": 30.0, "outage_rate": 0.02, "type": "variable",  "cost_mwh": 25,  "co2_lb_mwh": 0},
    "solar":         {"capacity_gw": 22.0, "outage_rate": 0.01, "type": "variable",  "cost_mwh": 20,  "co2_lb_mwh": 0},
    "battery_4h":    {"capacity_gw": 8.0,  "outage_rate": 0.03, "type": "storage",   "cost_mwh": 150, "co2_lb_mwh": 0},
}

# ──────────────────────────────────────────────────────────────
# Candidate Expansion Resources
# ──────────────────────────────────────────────────────────────
EXPANSION_OPTIONS = {
    "new_gas_peaker":       {"capacity_gw": 5.0, "annualized_cost_m": 180,  "type": "firm",          "co2_direction": "up"},
    "new_battery_4h":       {"capacity_gw": 5.0, "annualized_cost_m": 220,  "type": "storage_short", "co2_direction": "neutral"},
    "long_duration_storage":{"capacity_gw": 5.0, "annualized_cost_m": 300,  "type": "storage_long",  "co2_direction": "neutral"},
    "new_nuclear_smr":      {"capacity_gw": 3.0, "annualized_cost_m": 420,  "type": "clean_firm",    "co2_direction": "down"},
    "geothermal":           {"capacity_gw": 2.0, "annualized_cost_m": 280,  "type": "clean_firm",    "co2_direction": "down"},
    "tx_import":            {"capacity_gw": 4.0, "annualized_cost_m": 160,  "type": "firm",          "co2_direction": "neutral"},
    "demand_response":      {"capacity_gw": 6.0, "annualized_cost_m": 90,   "type": "demand_flex",   "co2_direction": "neutral"},
}

# ──────────────────────────────────────────────────────────────
# Load Profile Generator
# ──────────────────────────────────────────────────────────────

def generate_baseline_load(year: int = 2024, weather: str = "normal") -> pd.Series:
    """Synthetic 8760-hour baseline load for PJM-like system (~150 GW peak)."""
    np.random.seed(42)
    hours = np.arange(8760)
    day_of_year = hours // 24
    hour_of_day = hours % 24

    # Seasonal component
    seasonal = 140 + 25 * np.sin((day_of_year - 172) * 2 * np.pi / 365)

    # Diurnal pattern
    diurnal = (
        10 * np.sin((hour_of_day - 6) * np.pi / 12) +
        5 * np.sin((hour_of_day - 14) * np.pi / 6)
    )
    diurnal = np.where(hour_of_day < 6, diurnal - 8, diurnal)

    # Weather stress multiplier
    if weather == "summer_extreme":
        # Heat dome: amplify summer peak by 12%
        peak_mask = (day_of_year >= 150) & (day_of_year <= 240)
        seasonal = np.where(peak_mask, seasonal * 1.12, seasonal)
    elif weather == "winter_extreme":
        # Cold snap: amplify winter by 10%
        winter_mask = (day_of_year <= 60) | (day_of_year >= 330)
        seasonal = np.where(winter_mask, seasonal * 1.10, seasonal)

    noise = np.random.normal(0, 1.5, 8760)
    load = seasonal + diurnal + noise
    idx = pd.date_range(f"{year}-01-01", periods=8760, freq="h")
    return pd.Series(np.maximum(load, 80), index=idx, name="baseline_gw")


def generate_dc_load(
    scenario: str = "medium",
    flexible: bool = False
) -> pd.Series:
    """
    Add data center load on top of baseline.
    DC scenarios: low=+8 GW, medium=+20 GW, high=+40 GW (by 2030).
    flat 24/7 profile with slight flexibility option.
    When flexible=True, shift 15% from peak (14-20) to off-peak, conserving total energy.
    """
    np.random.seed(7)
    dc_peak = {"low": 8.0, "medium": 20.0, "high": 40.0}[scenario]
    hours = np.arange(8760)

    if flexible:
        # Demand response: shift ~15% of load away from peak hours (14-20, 7 hours)
        # to off-peak hours (17 hours) while conserving total energy.
        # Shift amount: 0.15 * dc_peak = 6 GW from 7 peak hours to 17 off-peak hours
        # Off-peak increase: (6 * 7) / 17 = 2.47 GW, so factor = 1 + 2.47/dc_peak
        hour_of_day = hours % 24
        off_peak_increase = (0.15 * dc_peak * 7) / 17  # Energy-conserving calculation
        off_peak_factor = 1 + (off_peak_increase / dc_peak)
        flex_factor = np.where((hour_of_day >= 14) & (hour_of_day <= 20), 0.85, off_peak_factor)
        dc = dc_peak * flex_factor
    else:
        dc = np.full(8760, dc_peak)

    noise = np.random.normal(0, dc_peak * 0.02, 8760)
    idx = pd.date_range("2024-01-01", periods=8760, freq="h")
    return pd.Series(np.maximum(dc + noise, 0), index=idx, name="dc_load_gw")


# ──────────────────────────────────────────────────────────────
# Available Capacity Calculator
# ──────────────────────────────────────────────────────────────

def compute_available_capacity(
    load_series: pd.Series,
    extra_firm_gw: float = 0.0,
    extra_dr_gw: float = 0.0,
    outage_stress: str = "normal"
) -> pd.Series:
    """
    Hourly available generation capacity accounting for:
    - Firm plant outages
    - Variable renewable CF profiles
    - Battery storage (4-hour discharge availability)
    - Demand response (65% capacity credit during peak hours 14-20)
    """
    np.random.seed(99)
    hours = len(load_series)
    hour_of_day = np.arange(hours) % 24
    day_of_year = np.arange(hours) // 24

    outage_mult = 1.15 if outage_stress == "high" else 1.0

    # Firm capacity
    firm_cap = sum(
        v["capacity_gw"] * (1 - v["outage_rate"] * outage_mult)
        for v in GENERATOR_FLEET.values()
        if v["type"] == "firm"
    ) + extra_firm_gw

    # Solar CF (peaks midday, summer)
    solar_cf = np.clip(
        0.45 * np.sin(np.maximum(hour_of_day - 6, 0) * np.pi / 12) *
        (0.7 + 0.3 * np.sin((day_of_year - 80) * 2 * np.pi / 365)),
        0, 1
    )
    solar_cap = GENERATOR_FLEET["solar"]["capacity_gw"] * solar_cf

    # Wind CF (higher at night, higher in spring/fall)
    wind_cf = np.clip(
        0.38 + 0.15 * np.cos(hour_of_day * np.pi / 12) +
        0.08 * np.cos((day_of_year - 100) * 2 * np.pi / 365) +
        np.random.normal(0, 0.05, hours),
        0.02, 0.85
    )
    wind_cap = GENERATOR_FLEET["wind"]["capacity_gw"] * wind_cf

    # Battery: available ~4h discharge, tracks peak need
    battery_avail = GENERATOR_FLEET["battery_4h"]["capacity_gw"] * 0.85

    # Demand response: 65% capacity credit during peak hours (14-20)
    # More realistic for responsive DR that can reduce demand within 10-30 minutes
    dr_cap = np.where((hour_of_day >= 14) & (hour_of_day <= 20), extra_dr_gw * 0.65, 0)

    total = firm_cap + solar_cap + wind_cap + battery_avail + dr_cap
    return pd.Series(total, index=load_series.index, name="avail_cap_gw")


# ──────────────────────────────────────────────────────────────
# Reliability Metrics
# ──────────────────────────────────────────────────────────────

def compute_reliability(
    load: pd.Series,
    avail_cap: pd.Series
) -> Dict:
    gap = avail_cap - load
    shortage = gap[gap < 0]

    peak_load = load.max()
    peak_cap = avail_cap[load.idxmax()]
    reserve_margin = (avail_cap.mean() - load.mean()) / load.mean() * 100

    return {
        "peak_load_gw":        round(peak_load, 1),
        "peak_avail_cap_gw":   round(peak_cap, 1),
        "reserve_margin_pct":  round(reserve_margin, 1),
        "shortage_hours":      len(shortage),
        "total_unserved_gwh":  round(abs(shortage.sum()), 1),
        "max_shortfall_gw":    round(abs(shortage.min()) if len(shortage) else 0, 1),
        "capacity_gap_gw":     round(max(0, peak_load - avail_cap.min()), 1),
    }


# ──────────────────────────────────────────────────────────────
# Full Scenario Runner
# ──────────────────────────────────────────────────────────────

def run_scenario(
    dc_growth: str = "medium",
    weather: str = "normal",
    flexible_dc: bool = False,
    outage_stress: str = "normal",
    extra_firm_gw: float = 0.0,
    extra_dr_gw: float = 0.0
) -> Tuple[pd.Series, pd.Series, Dict]:
    baseline = generate_baseline_load(weather=weather)
    dc = generate_dc_load(scenario=dc_growth, flexible=flexible_dc)
    total_load = baseline + dc
    avail = compute_available_capacity(total_load, extra_firm_gw, extra_dr_gw, outage_stress)
    metrics = compute_reliability(total_load, avail)
    return total_load, avail, metrics


# ──────────────────────────────────────────────────────────────
# Capacity Expansion Scoring
# ──────────────────────────────────────────────────────────────

def score_expansion_options(
    baseline_metrics: Dict,
    dc_growth: str = "high",
    weather: str = "summer_extreme"
) -> pd.DataFrame:
    rows = []
    base_shortage = baseline_metrics["shortage_hours"]
    base_unserved = baseline_metrics["total_unserved_gwh"]

    for name, opt in EXPANSION_OPTIONS.items():
        _, _, m = run_scenario(
            dc_growth=dc_growth,
            weather=weather,
            flexible_dc=(opt["type"] == "demand_flex"),
            extra_firm_gw=opt["capacity_gw"] if opt["type"] in ("firm", "clean_firm", "storage_long") else 0,
            extra_dr_gw=opt["capacity_gw"] if opt["type"] == "demand_flex" else 0,
        )
        shortage_reduction = max(0, base_shortage - m["shortage_hours"])
        unserved_reduction = max(0, base_unserved - m["total_unserved_gwh"])
        cost = opt["annualized_cost_m"]
        
        # Scoring: prioritize unserved energy reduction, with shortage hours as tiebreaker
        # Demand response typically reduces unserved energy but may not reduce shortage hours
        # So we use a weighted score combining both metrics
        if opt["type"] == "demand_flex":
            # For DR: weight unserved reduction (primary) + shortage reduction (secondary)
            score = (unserved_reduction / max(base_unserved, 1) + 
                    shortage_reduction / max(base_shortage, 1) * 0.3) / max(cost, 1) * 10000
        else:
            # For other resources: use shortage reduction (shortage_hours is primary metric)
            score = (shortage_reduction / max(cost, 1)) * 1000

        rows.append({
            "resource":              name,
            "capacity_gw":           opt["capacity_gw"],
            "annualized_cost_m$":    cost,
            "type":                  opt["type"],
            "shortage_hours_after":  m["shortage_hours"],
            "shortage_reduction":    shortage_reduction,
            "unserved_gwh_reduction":round(unserved_reduction, 1),
            "reserve_margin_pct":    m["reserve_margin_pct"],
            "reliability_score":     round(score, 2),
            "co2_direction":         opt["co2_direction"],
        })

    return pd.DataFrame(rows).sort_values("reliability_score", ascending=False)


# ──────────────────────────────────────────────────────────────
# Full Scenario Grid
# ──────────────────────────────────────────────────────────────

def run_scenario_grid() -> pd.DataFrame:
    dc_scenarios   = ["low", "medium", "high"]
    weather_cases  = ["normal", "summer_extreme", "winter_extreme"]
    flex_options   = [False, True]
    rows = []

    for dc in dc_scenarios:
        for wx in weather_cases:
            for flex in flex_options:
                _, _, m = run_scenario(dc_growth=dc, weather=wx, flexible_dc=flex)
                rows.append({
                    "dc_growth":   dc,
                    "weather":     wx,
                    "flexible_dc": flex,
                    **m
                })

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────
# Main: Regenerate CSVs
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run baseline scenario to get metrics
    baseline_load, baseline_avail, baseline_metrics = run_scenario(
        dc_growth="high",
        weather="summer_extreme",
        flexible_dc=False
    )
    
    # Generate expansion options scores
    expansion_scores = score_expansion_options(
        baseline_metrics=baseline_metrics,
        dc_growth="high",
        weather="summer_extreme"
    )
    
    # Export to CSV
    expansion_scores.to_csv("expansion_options.csv", index=False)
    print("✓ Regenerated expansion_options.csv")
    print("\nExpansion Options Summary:")
    print(expansion_scores[["resource", "capacity_gw", "shortage_reduction", "reliability_score"]])
    
    # Generate scenario grid
    grid = run_scenario_grid()
    grid.to_csv("scenario_grid.csv", index=False)
    print("\n✓ Regenerated scenario_grid.csv")
    print(f"Grid size: {len(grid)} scenarios")
