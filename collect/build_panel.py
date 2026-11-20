"""
Merge the raw downloads (collect/download.py) into the files in data/:

  data/cz_power_panel.csv            hourly panel 2020-2025
  data/forecasts_cz_de.csv           day-ahead forecasts 2023-2025
  data/neighbour_prices_2025.csv     day-ahead prices of CZ and its neighbours

Index: naive UTC, hourly. Local timestamps of OTE and ČEPS are converted from
Europe/Prague, 15-minute data are averaged to hourly means.

Usage
  python collect/build_panel.py
"""
import logging
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
DATA = ROOT / "data"
PANEL_START, PANEL_END = "2020-01-01 00:00", "2025-12-31 23:00"
FORECAST_START = "2023-01-01 00:00"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("build_panel")


def read(path, skip_rows=0, source_tz=None):
    """CSV with a datetime index -> naive UTC index. Naive timestamps are
    local time in `source_tz` (or UTC when None); the repeated autumn DST hour
    appears twice in file order and is resolved by `ambiguous="infer"`."""
    if not path.exists():
        log.warning(f"  missing {path.relative_to(ROOT)}")
        return pd.DataFrame()
    df = pd.read_csv(path, index_col=0,
                     skiprows=range(1, skip_rows + 1) if skip_rows else None)
    try:
        idx = pd.to_datetime(df.index, errors="coerce")
    except ValueError:                       # mixed +01:00 / +02:00 offsets
        idx = pd.to_datetime(df.index, errors="coerce", utc=True)
    df, idx = df[idx.notna()].copy(), idx[idx.notna()]
    if idx.tz is None and source_tz:
        try:
            idx = idx.tz_localize(source_tz, ambiguous="infer", nonexistent="NaT")
        except Exception:
            idx = idx.tz_localize(source_tz, ambiguous="NaT", nonexistent="NaT")
        df, idx = df[idx.notna()], idx[idx.notna()]
    elif idx.tz is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert("UTC").tz_localize(None)
    df = df.apply(pd.to_numeric, errors="coerce").sort_index()
    return df[~df.index.duplicated(keep="first")]


def clean(name, chars="()[]"):
    name = name.lower().replace(" ", "_").replace("/", "_")
    for ch in chars:
        name = name.replace(ch, "")
    return name.rstrip("_")


def load_ote():
    df = read(RAW / "ote" / "cz_dam_ote.csv", source_tz="Europe/Prague")
    if df.empty:
        return df
    return df.rename(columns={"price_eur_mwh": "ote_price_eur_mwh"}).resample("h").mean()


def load_entsoe():
    d = RAW / "entsoe"
    parts = []
    for f, col in [("cz_da_prices.csv", "entsoe_cz_da_eur_mwh"),
                   ("de_da_prices.csv", "entsoe_de_da_eur_mwh")]:
        df = read(d / f)
        if not df.empty:
            df.columns = [col]
            parts.append(df)
    load = read(d / "cz_load.csv")
    if not load.empty:
        load.columns = [f"entsoe_load_{c}" for c in load.columns]
        parts.append(load)
    gen = read(d / "cz_generation.csv")
    if not gen.empty:
        gen.columns = [f"entsoe_gen_{clean(c, '')}".replace("_pondage", "_poundage")
                       for c in gen.columns]
        parts.append(gen[sorted(gen.columns)].resample("h").mean())
    return pd.concat(parts, axis=1).resample("h").mean() if parts else pd.DataFrame()


def load_ceps():
    files = {"cz_imbalance_price.csv": "ceps_imbalance",
             "cz_crossborder_flows.csv": "ceps_xborder",
             "cz_load.csv": "ceps_load",
             "cz_generation_mix.csv": "ceps_gen",
             "cz_renewable_generation.csv": "ceps_res"}
    parts = []
    for f, prefix in files.items():
        df = read(RAW / "ceps" / f, source_tz="Europe/Prague")
        if df.empty:
            continue
        df.columns = [f"{prefix}_{clean(c)}" for c in df.columns]
        parts.append(df.resample("h").mean())
    return pd.concat(parts, axis=1) if parts else pd.DataFrame()


def load_era5():
    parts = [read(f) for f in sorted((RAW / "era5").glob("era5_cz_????.csv"))]
    parts = [p for p in parts if not p.empty]
    if not parts:
        log.warning("  no ERA5 data, era5_* columns stay empty")
        return pd.DataFrame(columns=["era5_u100", "era5_v100", "era5_t2m", "era5_ssrd",
                                     "era5_wind_speed_100m"])
    df = pd.concat(parts).sort_index()
    df = df[~df.index.duplicated()]
    df.columns = [f"era5_{c}" for c in df.columns]
    return df.resample("h").mean()


def build_panel():
    log.info("panel")
    ote, entsoe, ceps, era5 = load_ote(), load_entsoe(), load_ceps(), load_era5()
    if entsoe.empty:
        raise SystemExit("no ENTSO-E data in raw/entsoe, run collect/download.py first")
    idx = pd.date_range(PANEL_START, PANEL_END, freq="h", name="datetime")
    panel = pd.concat([ote.reindex(idx), entsoe.reindex(idx), ceps.reindex(idx),
                       era5.reindex(idx)], axis=1)
    # OTE and ENTSO-E publish the same coupled CZ price. From 2025 the OTE
    # report is not used (15-minute products from 1 Oct 2025), so the column
    # holds the ENTSO-E price there.
    if "ote_price_eur_mwh" not in panel:
        panel.insert(0, "ote_price_eur_mwh", float("nan"))
        panel.insert(1, "volume_mwh", float("nan"))
    late = panel.index >= "2025-01-01"
    panel.loc[late, "ote_price_eur_mwh"] = panel.loc[late, "entsoe_cz_da_eur_mwh"]
    panel.to_csv(DATA / "cz_power_panel.csv")
    log.info(f"  {panel.shape[0]:,} rows x {panel.shape[1]} columns -> data/cz_power_panel.csv")


def build_forecasts():
    log.info("forecasts")
    fc = read(RAW / "entsoe" / "forecasts_cz_de.csv")
    if fc.empty:
        return
    idx = pd.date_range(FORECAST_START, PANEL_END, freq="h", name="datetime")
    fc.reindex(idx).round(2).to_csv(DATA / "forecasts_cz_de.csv")
    log.info(f"  {len(idx):,} rows -> data/forecasts_cz_de.csv")


def build_neighbours():
    log.info("neighbour prices")
    pr = read(RAW / "entsoe" / "neighbour_prices_2025.csv")
    if pr.empty:
        return
    idx = pd.date_range("2025-01-01 00:00", PANEL_END, freq="h", name="datetime")
    pr.reindex(idx).round(2).to_csv(DATA / "neighbour_prices_2025.csv")
    log.info(f"  {len(idx):,} rows -> data/neighbour_prices_2025.csv")


if __name__ == "__main__":
    build_panel()
    build_forecasts()
    build_neighbours()
