# PJM Data Center Load Growth & Resource Adequacy Stress Test

## Problem Statement

Hyperscale data center construction is accelerating across the PJM interconnection footprint — Northern Virginia, Western Pennsylvania, Ohio, and the Mid-Atlantic corridor. Unlike residential or commercial load, data centers consume power 24/7 at near-constant levels, eliminating the overnight recovery window that historically allowed the grid to replenish reserves. This project quantifies how that shift erodes reliability and evaluates which resource portfolios most cost-effectively restore it.

## Research Question

> Which resource portfolios best preserve reliability under rising data center load growth while balancing cost and cleaner firm capacity options?

## Methodology

- **Hourly load simulation**: 8,760-hour synthetic PJM-like load profiles calibrated to ~150 GW summer peak
- **Data center scenarios**: +8 GW (low), +20 GW (medium), +40 GW (high) flat 24/7 additions
- **Generator fleet**: Nuclear, gas CC, gas peakers, coal, wind, solar, 4-hour battery — with outage-adjusted availability
- **Weather stress cases**: Normal, Summer Extreme (heat dome +12%), Winter Extreme (cold snap +10%)
- **Resource adequacy metrics**: Shortage hours, reserve margin, unserved energy, capacity gap
- **Capacity expansion scoring**: 7 candidate portfolios ranked by reliability improvement per dollar

## Key Findings

### 1. Flat Load Eliminates Night-Time Relief
Baseline residential/commercial load falls 15–25% overnight, allowing thermal plants to refuel and return to service. DC load does not. Under **high growth (40 GW)**, the overnight margin drops to near-zero — structurally raising planning reserve requirements by 8–12 GW.

### 2. Reserve Margins Turn Deeply Negative
| Scenario | Reserve Margin | Shortage Hours |
|---|---|---|
| Low DC / Normal | −3.0% | 4,837 hrs |
| Medium DC / Summer Extreme | −12.8% | 6,669 hrs |
| High DC / Summer Extreme | −22.4% | **8,251 hrs** |

PJM's target is ≥ +15%. All DC scenarios breach it.

### 3. Short-Duration Battery Is Insufficient
4-hour BESS reduces scarcity during transient peaks but cannot address multi-day heat domes or polar vortex events. Under high DC growth, battery-only additions reduce shortage hours by only ~361 hrs (4.4%).

### 4. Demand Response is the Highest-Value First Step
Flexible DC demand response (15% peak shift) achieves a reliability score of **12.78** — 2.3× better than the next best option — at only $90M/yr. This reflects the structural advantage of deferring DC load during the 14:00–20:00 peak window.

### 5. Clean Firm Outperforms Gas Peakers at Scale
For extreme scenarios, SMR and geothermal additions reduce shortage hours by 600–630 hrs while eliminating CO₂ increases. New gas peakers reduce shortage by only 291 hrs due to overlapping outage correlation with peak demand periods.

## Repository Structure

```
pjm_stress_test/
├── src/
│   └── simulate.py          # Core simulation engine
├── data/
│   ├── scenario_grid.csv    # Full 18-scenario results matrix
│   ├── expansion_options.csv # Capacity expansion scorecard
│   └── hourly_*.csv         # 8,760-hour load/capacity profiles
├── outputs/
│   └── dashboard.html       # Interactive scenario explorer
├── notebooks/
│   └── analysis.ipynb       # Full analysis notebook
└── README.md
```

## Tech Stack
- Python 3.12 · Pandas · NumPy · SciPy
- Chart.js (dashboard visualization)
- PuLP / SciPy (optimization hooks)

## Data Notes & Sources

The standard data in this repository is **synthetic**, generated mathematically in Python rather than pulled row-by-row from a live production feed. However, it is **heavily calibrated** to replicate real-world published statistics from the PJM interconnection:

- **Base Load Profiles**: Modeled to replicate the 2019–2023 PJM summer peak ~150 GW, using sinusoidal shaping for diurnal and seasonal cycles.
- **Generator Fleet Performance**: Sourced from the [PJM 2023 State of the Market Report](https://www.monitoringanalytics.com/reports/PJM_State_of_the_Market/2023.shtml) (outage characteristics and fuel mix).
- **External Real Data API**: For users wishing to replace this synthetic engine with true historical data, a script `fetch_real_data.py` is included that queries load data via the `gridstatus` Python package. 
  - Real load data origins: [PJM Data Miner 2](https://dataminer2.pjm.com/feed/hrl_load_metered) (requires free API key).
  - Alternative origin: [EIA Open Data API](https://www.eIA.gov/opendata/) (US Energy Information Administration). This is a research-grade scenario model, not a production power system simulator.

---
*Not affiliated with PJM Interconnection LLC.*
