"""Build the analysis dataset from data/cz_power_panel.csv.

Adds calendar features (local time), crisis subperiods, residual load,
negative-price indicators and a deseasonalised price.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANEL_CSV = ROOT / "data" / "cz_power_panel.csv"
FORECAST_CSV = ROOT / "data" / "forecasts_cz_de.csv"
OUT_DIR = ROOT / "output"
PREPARED_CSV = OUT_DIR / "prepared.csv"

PRICE = "ote_price_eur_mwh"
LOCAL_TZ = "Europe/Prague"
SAMPLE_START, SAMPLE_END = "2020-01-01", "2025-12-31"
SUBPERIODS = {
    "pre_crisis": ("2020-01-01", "2021-06-30"),
    "crisis": ("2021-07-01", "2023-03-31"),
    "post_crisis": ("2023-04-01", "2025-12-31"),
}
# The seasonal profile of the post-crisis period is fitted on hours before
# HOLDOUT_START only, so later hours do not enter their own deseasonalisation.
TRAIN_PERIOD = "post_crisis"
HOLDOUT_START = "2024-07-01"
THRESHOLDS = [0.0, 5.0, 20.0]       # EUR/MWh, "price below threshold" indicators
N_FOURIER = 3                       # sin/cos pairs of the annual cycle
SOLAR_CAP_MW = 10_000               # above any plausible Czech PV infeed


def czech_holidays(years) -> set:
    """Fixed-date public holidays plus Good Friday and Easter Monday."""
    fixed = [(1, 1), (5, 1), (5, 8), (7, 5), (7, 6), (9, 28),
             (10, 28), (11, 17), (12, 24), (12, 25), (12, 26)]

    def easter_sunday(y):  # anonymous Gregorian algorithm
        a, b, c = y % 19, y // 100, y % 100
        d, e = b // 4, b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i, k = c // 4, c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        return pd.Timestamp(y, month, day)

    out = set()
    for y in years:
        out.update(pd.Timestamp(y, m, d).date() for m, d in fixed)
        es = easter_sunday(y)
        out.add((es + pd.Timedelta(days=1)).date())
        out.add((es - pd.Timedelta(days=2)).date())
    return out


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    """Hour, month, year and day type on the local clock (the market trades local days)."""
    local = df.index.tz_localize("UTC").tz_convert(LOCAL_TZ)
    df["hour"] = local.hour
    df["month"] = local.month
    df["year"] = local.year
    df["doy"] = local.dayofyear
    hol = czech_holidays(sorted(set(local.year)))
    is_hol = pd.Series(local.date, index=df.index).isin(hol)
    df["daytype"] = np.where(is_hol | (local.dayofweek >= 5), "weekend_holiday", "workday")
    return df


def add_subperiods(df: pd.DataFrame) -> pd.DataFrame:
    df["subperiod"] = pd.NA
    for name, (a, b) in SUBPERIODS.items():
        df.loc[a:b, "subperiod"] = name
    return df


def seasonal_component(df: pd.DataFrame, col: str) -> pd.Series:
    """OLS on day type and annual Fourier terms, fitted per subperiod."""
    fhat = pd.Series(np.nan, index=df.index)
    for sp, g in df.groupby("subperiod", observed=True):
        X = [pd.get_dummies(g["daytype"], dtype=float)]
        for k in range(1, N_FOURIER + 1):
            w = 2 * np.pi * k * g["doy"] / 365.25
            X.append(pd.DataFrame({f"sin{k}": np.sin(w), f"cos{k}": np.cos(w)}, index=g.index))
        X = pd.concat(X, axis=1)
        ok = g[col].notna()
        if sp == TRAIN_PERIOD:
            ok &= g.index < pd.Timestamp(HOLDOUT_START)
        beta, *_ = np.linalg.lstsq(X[ok].values, g.loc[ok, col].values, rcond=None)
        fhat.loc[g.index] = X.values @ beta
    return fhat


def add_forecast_residual_load(df: pd.DataFrame) -> pd.DataFrame:
    """Day-ahead forecast residual load for CZ and DE-LU, in MW."""
    fc = pd.read_csv(FORECAST_CSV, index_col=0, parse_dates=True)
    df = df.join(fc, how="left")
    # No CZ wind forecast is published, realised ČEPS wind is used instead.
    df["resload_fc_cz_mw"] = df["cz_load_fc_mw"] - df["cz_solar_fc_mw"] - df["ceps_res_vte_mw"]
    de_wind = df["de_wind_onshore_fc_mw"] + df["de_wind_offshore_fc_mw"].fillna(0)
    df["resload_fc_de_mw"] = df["de_load_fc_mw"] - df["de_solar_fc_mw"] - de_wind
    return df


def prepare() -> pd.DataFrame:
    df = pd.read_csv(PANEL_CSV, index_col=0, parse_dates=True, float_precision="round_trip")
    df = df.loc[SAMPLE_START:SAMPLE_END]
    df = add_subperiods(add_calendar(df))

    bad = df["ceps_res_fve_mw"] > SOLAR_CAP_MW
    df.loc[bad, "ceps_res_fve_mw"] = df.loc[bad, "ceps_gen_fve_mw"]
    df["solar_mw"] = df["ceps_res_fve_mw"]
    df["residual_load_mw"] = (df["ceps_load_zatížení_mw"]
                              - df["ceps_res_fve_mw"] - df["ceps_res_vte_mw"])
    df = add_forecast_residual_load(df)

    p = df[PRICE]
    for thr in THRESHOLDS:
        df[f"price_lt{int(thr)}"] = (p < thr).astype(float).where(p.notna())
    df["price_deseason"] = p - seasonal_component(df, PRICE)

    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(PREPARED_CSV)
    print(f"{len(df):,} rows x {df.shape[1]} columns -> {PREPARED_CSV}")
    return df


def load_prepared() -> pd.DataFrame:
    if not PREPARED_CSV.exists():
        return prepare()
    return pd.read_csv(PREPARED_CSV, index_col=0, parse_dates=True)


if __name__ == "__main__":
    prepare()
