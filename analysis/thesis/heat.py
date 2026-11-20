"""
Emission factor of delivered heat, tCO2 per MWh of heat, under the
allocation conventions used for cogeneration (CHP):

energy      fuel split in proportion to energy output
exergy      fuel split in proportion to exergy, heat weighted by its Carnot
            factor 1 - T0/Th
power_loss  heat carries the fuel a reference condensing plant would have
            saved: F_heat = F - E / eta_ref_el
by_product  heat carries nothing

Fuel combustion factors are IPCC 2006 defaults per MWh of fuel input; for
municipal waste only the fossil share of carbon is charged.
"""
from __future__ import annotations

import pandas as pd

MJ_PER_MWH = 3600.0

# IPCC (2006, Vol. 2: Energy) default combustion factors, kg CO2 per GJ of fuel
# (net CV).
# Converted to tCO2 per MWh of fuel input.
IPCC_KG_PER_GJ = {
    "lignite": 101.0,
    "hard_coal": 94.6,
    "natural_gas": 56.1,
    "municipal_waste": 91.7,     # total carbon; fossil fraction applied below
    "biomass": 112.0,            # biogenic — zeroed under the thesis convention
    "nuclear": 0.0,
}
FOSSIL_FRACTION = {              # share of carbon that is fossil
    "municipal_waste": 0.50,     # EU average for MSW; national values vary
    "biomass": 0.0,              # treated as neutral
}

# Representative plant configurations (working assumptions of the thesis).
# eta_el and eta_th are annual-average efficiencies on fuel input; heat_c is
# the delivery temperature in Celsius.
PLANTS = [
    # name,           fuel,              eta_el, eta_th, heat_c, kind
    ("lignite_chp",   "lignite",           0.30,  0.45,   95.0, "chp"),
    ("hard_coal_chp", "hard_coal",         0.32,  0.44,   95.0, "chp"),
    ("gas_chp",       "natural_gas",       0.40,  0.42,   90.0, "chp"),
    ("gas_boiler",    "natural_gas",       0.00,  0.92,   90.0, "boiler"),
    ("coal_boiler",   "lignite",           0.00,  0.85,   95.0, "boiler"),
    ("waste_chp",     "municipal_waste",   0.20,  0.55,   95.0, "chp"),
    ("biomass_chp",   "biomass",           0.25,  0.50,   95.0, "chp"),
    ("nuclear",       "nuclear",           0.33,  0.00,  120.0, "nuclear"),
]

# Reference condensing efficiencies for the power-loss method (EU harmonised
# reference values for separate electricity production, order of magnitude).
ETA_REF_EL = {"lignite": 0.40, "hard_coal": 0.44,
              "natural_gas": 0.53, "municipal_waste": 0.25, "biomass": 0.33}

T0_C = 10.0        # annual mean ambient temperature, Czechia


def fuel_factor(fuel: str) -> float:
    """tCO2 per MWh of fuel input, fossil carbon only."""
    kg_per_gj = IPCC_KG_PER_GJ[fuel] * FOSSIL_FRACTION.get(fuel, 1.0)
    return kg_per_gj * (MJ_PER_MWH / 1000.0) / 1000.0      # kg/GJ -> t/MWh


def carnot(heat_c: float, t0_c: float = T0_C) -> float:
    """Carnot quality factor of heat delivered at heat_c."""
    th, t0 = heat_c + 273.15, t0_c + 273.15
    return 1.0 - t0 / th


def factors(fuel, eta_el, eta_th, heat_c, kind) -> dict[str, float]:
    """tCO2 per MWh of delivered heat under each allocation convention."""
    ef_fuel = fuel_factor(fuel)
    out = {}

    if eta_th <= 0:                       # electricity-only: no heat product
        return {k: float("nan") for k in
                ("energy", "exergy", "power_loss", "by_product")}

    if kind == "boiler" or eta_el <= 0:   # all fuel serves heat
        v = ef_fuel / eta_th
        return {"energy": v, "exergy": v, "power_loss": v, "by_product": 0.0}

    # --- cogeneration: one fuel, two products -------------------------------
    # energy allocation
    share_e = eta_th / (eta_el + eta_th)
    out["energy"] = ef_fuel * share_e / eta_th

    # exergy allocation: heat weighted by its Carnot factor, power by 1.0
    x_heat = eta_th * carnot(heat_c)
    share_x = x_heat / (eta_el + x_heat)
    out["exergy"] = ef_fuel * share_x / eta_th

    # power-loss: heat carries the fuel not needed by a reference condensing set
    eta_ref = ETA_REF_EL.get(fuel, 0.40)
    fuel_to_heat = max(1.0 - eta_el / eta_ref, 0.0)
    out["power_loss"] = ef_fuel * fuel_to_heat / eta_th

    out["by_product"] = 0.0
    return out


def table() -> pd.DataFrame:
    rows = []
    for name, fuel, eta_el, eta_th, heat_c, kind in PLANTS:
        f = factors(fuel, eta_el, eta_th, heat_c, kind)
        rows.append({"configuration": name, "fuel": fuel, "kind": kind,
                     "eta_el": eta_el, "eta_th": eta_th, "heat_c": heat_c,
                     "ef_fuel_t_per_mwh": fuel_factor(fuel),
                     **{f"ef_heat_{k}": v for k, v in f.items()}})
    return pd.DataFrame(rows)
