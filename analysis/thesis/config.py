"""Settings of the thesis pipeline (analysis/thesis/run.py)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL_CSV = ROOT / "data" / "cz_power_panel.csv"
FORECAST_CSV = ROOT / "data" / "forecasts_cz_de.csv"
NEIGHBOUR_CSV = ROOT / "data" / "neighbour_prices_2025.csv"

OUT_DIR = ROOT / "output" / "thesis"
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"
WORK_DIR = OUT_DIR / "work"
MOD_DIR = WORK_DIR
PREPARED_CSV = WORK_DIR / "prepared_dataset.csv"
for d in (FIG_DIR, TAB_DIR, WORK_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── sample ───────────────────────────────────────────────────────────────────
LOCAL_TZ = "Europe/Prague"
SAMPLE_START = "2020-01-01"
SAMPLE_END = "2025-12-31"
SUBPERIODS = {
    "pre_crisis": ("2020-01-01", "2021-06-30"),
    "crisis": ("2021-07-01", "2023-03-31"),
    "post_crisis": ("2023-04-01", "2025-12-31"),
}
ESTIMATION_PERIOD = "post_crisis"
HOLDOUT_START = "2024-07-01"            # parameters use hours before this only

# ── surplus hours and deseasonalisation ─────────────────────────────────────
SURPLUS_THRESHOLD_EUR = 0.0
SURPLUS_THRESHOLD_VARIANTS = [5.0, 20.0]
N_FOURIER_ANNUAL = 3
DESEASON_DIURNAL = False                # regimes classify price levels

# ── Markov-switching model with time-varying transition probabilities ───────
MS_N_REGIMES = 3                        # surplus / normal / spike
MS_MAX_ITER = 2000
MS_SEED = 42
MS_TVTP_COVARIATES = ["z_cz", "z_de"]   # standardised day-ahead forecast residual load
MS_MEAN_REGRESSORS = []                 # constant regime means
SANDWICH_HAC_LAGS = 48

# ── simulation ───────────────────────────────────────────────────────────────
N_SIM_PATHS = 200
SIM_SEED = 123
SIM_PARAM_UNCERTAINTY = True            # θ_i ~ N(θ̂, V̂_sandwich) per path
SIM_WEATHER_YEARS = [2023, 2024, 2025]
# Czech solar infeed relative to 2024. The updated National Energy and Climate
# Plan foresees about 10 GW of PV by 2030 (MPO, 2024); installed capacity at
# the end of 2024 was roughly 4 GW (author's estimate from the peak ČEPS solar
# infeed, thesis Section 3.2).
SOLAR_SCENARIOS = {
    "today": 1.0,
    "necp_2030_low": 1.6,
    "necp_2030_central": 2.1,
    "necp_2030_high": 2.6,
    "necp_2035_central": 3.0,
}
# DE-LU solar paired with each scenario in the joint variant. § 4 No. 3 EEG 2023
# (Deutscher Bundestag, 2022) sets 215 GW of PV for 2030 and 309 GW for 2035;
# 99.3 GW were installed at the end of 2024 (Bundesnetzagentur, 2025), so
# 215 / 99.3 = 2.17 and 309 / 99.3 = 3.1. The 2030 central factor continues the
# 2024 build rate of 16.2 GW per year (Bundesnetzagentur, 2025):
# (99.3 + 6 x 16.2) / 99.3 = 2.0; the low factor 1.8 assumes a slower build-out.
DE_SOLAR_SCENARIOS = {
    "today": 1.0,
    "necp_2030_low": 1.8,
    "necp_2030_central": 2.0,
    "necp_2030_high": 2.17,
    "necp_2035_central": 3.1,
}

# ── emission factors, tCO2 per MWh of electricity ───────────────────────────
# Direct (combustion) emissions per MWh as used in the thesis model (Table 6);
# biomass is counted as zero.
EMISSION_FACTORS = {
    "entsoe_gen_fossil_brown_coal_lignite": 1.06,
    "entsoe_gen_fossil_hard_coal": 0.87,
    "entsoe_gen_fossil_gas": 0.36,
    "entsoe_gen_fossil_coal-derived_gas": 1.40,
    "entsoe_gen_fossil_oil": 0.65,
    "entsoe_gen_waste": 0.26,
    "entsoe_gen_biomass": 0.0,
    "entsoe_gen_nuclear": 0.0,
    "entsoe_gen_solar": 0.0,
    "entsoe_gen_wind_onshore": 0.0,
    "entsoe_gen_hydro_pumped_storage": 0.0,
    "entsoe_gen_hydro_run-of-river_and_poundage": 0.0,
    "entsoe_gen_hydro_water_reservoir": 0.0,
    "entsoe_gen_other": 0.30,
    "entsoe_gen_other_renewable": 0.0,
}
