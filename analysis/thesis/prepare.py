"""
Prepared dataset for the regime model and the figures.

  residual load      load - solar - wind (ČEPS), and the day-ahead forecast
                     residual load of CZ and DE-LU
  surplus            1{price < 0}
  price_deseason     price minus an annual Fourier + day-type profile, fitted
                     per subperiod (in the estimation subperiod on the
                     training window only)
  calendar           local time (Europe/Prague)
"""
import numpy as np
import pandas as pd

import config as C


# ── helpers ───────────────────────────────────────────────────────────────────

def czech_holidays(years) -> set:
    """Fixed-date Czech public holidays + Easter Monday / Good Friday."""
    fixed = [(1, 1), (5, 1), (5, 8), (7, 5), (7, 6), (9, 28),
             (10, 28), (11, 17), (12, 24), (12, 25), (12, 26)]

    def easter_sunday(y):  # Anonymous Gregorian algorithm
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
        for m, d in fixed:
            out.add(pd.Timestamp(y, m, d).date())
        es = easter_sunday(y)
        out.add((es + pd.Timedelta(days=1)).date())   # Easter Monday
        out.add((es - pd.Timedelta(days=2)).date())   # Good Friday
    return out


def add_calendar(df: pd.DataFrame) -> pd.DataFrame:
    """Calendar features on the local (Europe/Prague) clock.

    The panel index is naive UTC. A UTC calendar shifts every hour dummy by
    one hour between winter and summer time and assigns 22:00–23:59 UTC to
    the wrong local day (wrong weekday, wrong holiday)."""
    local = df.index.tz_localize("UTC").tz_convert(C.LOCAL_TZ)
    df["hour_utc"] = df.index.hour
    df["hour"] = local.hour
    df["month"] = local.month
    df["year"] = local.year
    df["doy"] = local.dayofyear
    df["local_date"] = local.date
    hol = czech_holidays(sorted(set(local.year)))
    is_hol = pd.Series(local.date, index=df.index).isin(hol)
    df["daytype"] = np.where(is_hol | (local.dayofweek >= 5), "weekend_holiday", "workday")
    return df


def label_subperiods(df: pd.DataFrame) -> pd.DataFrame:
    df["subperiod"] = pd.NA
    for name, (a, b) in C.SUBPERIODS.items():
        df.loc[a:b, "subperiod"] = name
    return df


def seasonal_design(g: pd.DataFrame, diurnal: bool) -> pd.DataFrame:
    """Design matrix of the deterministic seasonal component."""
    if diurnal:
        X_parts = [pd.get_dummies(g["hour"].astype(str) + "_" + g["daytype"], dtype=float)]
    else:
        X_parts = [pd.get_dummies(g["daytype"], dtype=float)]
    for k in range(1, C.N_FOURIER_ANNUAL + 1):
        X_parts.append(pd.DataFrame({
            f"sin{k}": np.sin(2 * np.pi * k * g["doy"] / 365.25),
            f"cos{k}": np.cos(2 * np.pi * k * g["doy"] / 365.25),
        }, index=g.index))
    return pd.concat(X_parts, axis=1)


def fit_seasonal_component(df: pd.DataFrame, price_col: str,
                           diurnal: bool = None) -> pd.Series:
    """OLS seasonal profile fitted separately within each subperiod (crisis
    break, §3.3). In the estimation subperiod only hours before HOLDOUT_START
    enter the fit (no look-ahead into the out-of-sample window)."""
    diurnal = C.DESEASON_DIURNAL if diurnal is None else diurnal
    fhat = pd.Series(np.nan, index=df.index)
    h0 = pd.Timestamp(C.HOLDOUT_START)
    for sp, g in df.groupby("subperiod", observed=True):
        y = g[price_col]
        ok = y.notna()
        if sp == C.ESTIMATION_PERIOD:
            ok &= g.index < h0
        X = seasonal_design(g, diurnal)
        beta, *_ = np.linalg.lstsq(X[ok].values, y[ok].values, rcond=None)
        fhat.loc[g.index] = X.values @ beta
    return fhat


def grid_emission_intensity(df: pd.DataFrame) -> pd.Series:
    """Generation-weighted average CO2 intensity of CZ generation [tCO2/MWh]."""
    cols = [c for c in C.EMISSION_FACTORS if c in df.columns]
    gen = df[cols].clip(lower=0)
    emis = sum(gen[c] * C.EMISSION_FACTORS[c] for c in cols)
    total = gen.sum(axis=1)
    return (emis / total.replace(0, np.nan)).rename("grid_intensity_t_per_mwh")


def add_forecasts(df: pd.DataFrame) -> pd.DataFrame:
    """Merge the ENTSO-E day-ahead forecasts (collect_forecasts.py) and build
    forecast residual loads for CZ and DE-LU, in MW."""
    if not C.FORECAST_CSV.exists():
        print(f"  note: {C.FORECAST_CSV.name} not found, forecast covariates "
              f"unavailable")
        return df
    fc = pd.read_csv(C.FORECAST_CSV, index_col=0, parse_dates=True)
    df = df.join(fc, how="left")
    # ENTSO-E publishes no day-ahead wind forecast for CZ. Czech wind averages
    # 74 MW (≈1 % of load), so realised ČEPS wind stands in for it.
    if "cz_wind_fc_mw" not in df:
        df["cz_wind_fc_mw"] = df["ceps_res_vte_mw"]
    df["resload_fc_cz_mw"] = (df["cz_load_fc_mw"] - df["cz_solar_fc_mw"]
                              - df["cz_wind_fc_mw"])
    de_wind = df["de_wind_onshore_fc_mw"] + df["de_wind_offshore_fc_mw"].fillna(0)
    df["resload_fc_de_mw"] = df["de_load_fc_mw"] - df["de_solar_fc_mw"] - de_wind
    return df


# ── main ─────────────────────────────────────────────────────────────────────

def prepare() -> pd.DataFrame:
    df = pd.read_csv(C.PANEL_CSV, index_col=0, parse_dates=True,
                     float_precision="round_trip")
    df = df.loc[C.SAMPLE_START:C.SAMPLE_END]

    df = add_calendar(df)
    df = label_subperiods(df)

    # ČEPS publishes solar twice (generation mix and RES infeed); they agree to
    # the MW except for single corrupt hours of the RES series (22,678 MW on
    # 2025-06-30 18:00, ~7× the installed capacity). Where the two differ by
    # more than 1 GW the generation-mix value is used.
    bad = (df["ceps_res_fve_mw"] - df["ceps_gen_fve_mw"]).abs() > 1000
    df.loc[bad, "ceps_res_fve_mw"] = df.loc[bad, "ceps_gen_fve_mw"]

    # residual load (ČEPS series)
    df["residual_load_mw"] = (df["ceps_load_zatížení_mw"]
                              - df["ceps_res_fve_mw"] - df["ceps_res_vte_mw"])
    df["solar_mw"] = df["ceps_res_fve_mw"]

    # day-ahead forecasts (known before the auction)
    df = add_forecasts(df)

    # surplus indicators (missing price → missing indicator, not 0)
    p = df["ote_price_eur_mwh"]
    df["surplus"] = (p < C.SURPLUS_THRESHOLD_EUR).astype(float).where(p.notna())
    for thr in C.SURPLUS_THRESHOLD_VARIANTS:
        df[f"surplus_lt{int(thr)}"] = (p < thr).astype(float).where(p.notna())

    df["price_seasonal"] = fit_seasonal_component(df, "ote_price_eur_mwh")
    df["price_deseason"] = p - df["price_seasonal"]

    # hourly grid emission intensity
    df["grid_intensity_t_per_mwh"] = grid_emission_intensity(df)

    df.to_csv(C.PREPARED_CSV)
    print(f"prepared dataset: {df.shape[0]:,} rows x {df.shape[1]} cols -> {C.PREPARED_CSV}")
    return df


def load_prepared() -> pd.DataFrame:
    """Rebuilds the dataset if missing."""
    if not C.PREPARED_CSV.exists():
        return prepare()
    return pd.read_csv(C.PREPARED_CSV, index_col=0, parse_dates=True)


if __name__ == "__main__":
    prepare()
