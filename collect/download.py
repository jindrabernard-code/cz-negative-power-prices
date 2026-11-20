"""
Download the raw data behind data/cz_power_panel.csv, data/forecasts_cz_de.csv
and data/neighbour_prices_2025.csv into raw/.

Sources (full references in data/README.md)
  OTE      OTE, a.s., day-ahead market results, daily XLS reports, no key
           (2020-2024), https://www.ote-cr.cz/en/statistics/electricity/market-prices
  ENTSO-E  ENTSO-E Transparency Platform, https://transparency.entsoe.eu,
           via entsoe-py (ENTSOE_API_KEY): CZ and DE-LU day-ahead price, CZ load
           and generation per type, CZ and DE-LU day-ahead load/solar/wind
           forecasts, 2025 day-ahead prices of the neighbouring zones
  ČEPS     ČEPS, a.s., data portal https://www.ceps.cz/en/all-data, no key:
           load, generation mix, RES infeed, cross-border flows, imbalance price
  ERA5     Copernicus Climate Change Service, ERA5 hourly data on single levels,
           https://doi.org/10.24381/cds.adbb2d47 (CDS_API_KEY, optional)

Files that already exist are skipped, so an interrupted run can be resumed.
The OTE part fetches one report per day and takes about 20 minutes.

Usage
  python collect/download.py                    # all sources
  python collect/download.py ote ceps           # selected sources
  (sources: entsoe, forecasts, neighbours, ote, ceps, era5)
"""
import calendar
import io
import logging
import os
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("download")

START = pd.Timestamp("2020-01-01", tz="UTC")
END = pd.Timestamp("2026-01-01", tz="UTC")
# OTE changed its daily report with the move to 15-minute products
# (1 Oct 2025); 2025 prices are taken from ENTSO-E (see build_panel.py).
OTE_END = pd.Timestamp("2025-01-01", tz="UTC")
FORECAST_START = pd.Timestamp("2023-01-01", tz="UTC")

CZ = "10YCZ-CEPS-----N"
DE_LU = "10Y1001A1001A82H"
NEIGHBOUR_ZONES = ["CZ", "DE_LU", "AT", "SK", "PL"]
NEIGHBOUR_YEAR = 2025
CZ_BBOX = [52, 12, 48, 19]  # N, W, S, E


def entsoe_client():
    key = os.getenv("ENTSOE_API_KEY")
    if not key:
        raise SystemExit("ENTSOE_API_KEY is not set, see .env.example")
    from entsoe import EntsoePandasClient
    return EntsoePandasClient(api_key=key, timeout=90, retry_count=3, retry_delay=10)


def to_hourly_utc(obj):
    df = obj.to_frame() if isinstance(obj, pd.Series) else obj.copy()
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    df = df.resample("1h").mean()
    df.index = df.index.tz_localize(None)
    df.index.name = "datetime"
    return df


def monthly(fn, area, start, end, workers=6, **kwargs):
    """Query month by month in parallel; the platform is slow and large
    requests time out."""
    months = pd.date_range(start, end, freq="MS")

    def one(s):
        e = s + pd.offsets.MonthBegin(1)
        for attempt in range(1, 4):
            try:
                return fn(area, start=s, end=e, **kwargs)
            except Exception as exc:
                if "NoMatchingDataError" in type(exc).__name__:
                    return None
                log.warning(f"  {fn.__name__} {area} {s:%Y-%m} attempt {attempt}: {exc}")
                time.sleep(5 * attempt)
        return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        parts = list(ex.map(one, months[:-1]))
    missing = [f"{m:%Y-%m}" for m, p in zip(months[:-1], parts) if p is None]
    if missing:
        log.warning(f"  {fn.__name__} {area}: no data for {missing}")
    parts = [p for p in parts if p is not None]
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts)
    return out[~out.index.duplicated()].sort_index()


def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    log.info(f"  saved {len(df):,} rows -> {path.relative_to(ROOT)}")


# ── ENTSO-E ─────────────────────────────────────────────────────────────────
def collect_entsoe():
    out = RAW / "entsoe"
    client = entsoe_client()
    jobs = {
        "cz_da_prices.csv": lambda: monthly(client.query_day_ahead_prices, CZ, START, END)
        .rename("price_eur_mwh"),
        "de_da_prices.csv": lambda: monthly(client.query_day_ahead_prices, DE_LU, START, END)
        .rename("price_eur_mwh"),
        "cz_load.csv": lambda: monthly(client.query_load, CZ, START, END),
        "cz_generation.csv": lambda: generation(client),
    }
    for name, job in jobs.items():
        if (out / name).exists():
            log.info(f"  {name} exists, skipped")
            continue
        log.info(f"ENTSO-E {name}")
        save(to_hourly_utc(job()), out / name)


def generation(client):
    g = monthly(client.query_generation, CZ, START, END)
    if isinstance(g.columns, pd.MultiIndex):
        # keep generation, drop the pumped-storage consumption column
        g = g.loc[:, [c for c in g.columns if c[1] == "Actual Aggregated"]]
        g.columns = [c[0] for c in g.columns]
    return g


def collect_forecasts():
    path = RAW / "entsoe" / "forecasts_cz_de.csv"
    if path.exists():
        log.info("  forecasts exist, skipped")
        return
    client = entsoe_client()
    cols = {}
    for cc, area in {"cz": CZ, "de": DE_LU}.items():
        log.info(f"ENTSO-E {cc.upper()} load forecast")
        load = to_hourly_utc(monthly(client.query_load_forecast, area, FORECAST_START, END))
        cols[f"{cc}_load_fc_mw"] = load.iloc[:, 0]
        log.info(f"ENTSO-E {cc.upper()} wind and solar forecast")
        res = to_hourly_utc(monthly(client.query_wind_and_solar_forecast, area,
                                    FORECAST_START, END))
        for src, short in {"Solar": "solar", "Wind Onshore": "wind_onshore",
                           "Wind Offshore": "wind_offshore"}.items():
            if src in res.columns:
                cols[f"{cc}_{short}_fc_mw"] = res[src]
    out = pd.DataFrame(cols).rename(columns={"cz_wind_onshore_fc_mw": "cz_wind_fc_mw"})
    save(out, path)


def collect_neighbours():
    path = RAW / "entsoe" / f"neighbour_prices_{NEIGHBOUR_YEAR}.csv"
    if path.exists():
        log.info("  neighbour prices exist, skipped")
        return
    from entsoe.mappings import Area
    client = entsoe_client()
    s = pd.Timestamp(f"{NEIGHBOUR_YEAR}-01-01", tz="UTC")
    e = pd.Timestamp(f"{NEIGHBOUR_YEAR + 1}-01-01", tz="UTC")
    cols = {}
    for z in NEIGHBOUR_ZONES:
        log.info(f"ENTSO-E day-ahead price {z} {NEIGHBOUR_YEAR}")
        cols[z] = to_hourly_utc(monthly(client.query_day_ahead_prices, Area[z].code, s, e)).iloc[:, 0]
    save(pd.DataFrame(cols), path)


# ── OTE ─────────────────────────────────────────────────────────────────────
def ote_hour_to_utc(dates, hours):
    """OTE numbers the hours of a day 1..N (23 or 25 on DST days); hour h
    starts h-1 elapsed hours after local midnight."""
    midnight = pd.to_datetime(dates).dt.tz_localize("Europe/Prague").dt.tz_convert("UTC")
    return midnight + pd.to_timedelta(hours.astype(int) - 1, unit="h")


def ote_day(d):
    url = (f"https://www.ote-cr.cz/pubweb/attachments/01/{d.year}/month{d.month:02d}"
           f"/day{d.day:02d}/DT_{d.day:02d}_{d.month:02d}_{d.year}_CZ.xls")
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=30)
            break
        except requests.RequestException:
            time.sleep(3 * attempt)
    else:
        return []
    if r.status_code != 200 or not r.content:
        return []
    raw = pd.read_excel(io.BytesIO(r.content), header=None)
    # the hourly table starts below the "Hodina" header (its position moved in 2024)
    head = next((i for i, row in raw.iterrows() if str(row.iloc[0]).strip() == "Hodina"), None)
    if head is None:
        return []
    rows = []
    for _, row in raw.iloc[head + 2: head + 27].iterrows():
        try:
            h = int(float(row.iloc[0]))
        except (TypeError, ValueError):
            continue
        if 1 <= h <= 25:
            rows.append({"date": d.isoformat(), "hour": h,
                         "price_eur_mwh": float(row.iloc[1]),
                         "volume_mwh": float(row.iloc[2])})
    return rows


def collect_ote():
    path = RAW / "ote" / "cz_dam_ote.csv"
    if path.exists():
        log.info("  OTE exists, skipped")
        return
    days = pd.date_range(START.tz_localize(None), OTE_END.tz_localize(None),
                         inclusive="left").date
    log.info(f"OTE: {len(days)} daily reports")
    records, failed = [], []
    for k, d in enumerate(days, 1):
        rows = ote_day(d)
        if not rows:
            failed.append(d.isoformat())
        records += rows
        time.sleep(0.3)
        if k % 200 == 0:
            log.info(f"  {k}/{len(days)} days")
    if failed:
        log.warning(f"  OTE: no report for {len(failed)} days, e.g. {failed[:5]}")
    df = pd.DataFrame(records)
    df["datetime"] = ote_hour_to_utc(df["date"], df["hour"])
    save(df.drop(columns=["date", "hour"]).set_index("datetime").sort_index(), path)


# ── ČEPS ────────────────────────────────────────────────────────────────────
CEPS_DATASETS = {
    "cz_imbalance_price": ("OdhadovanaCenaOdchylky", "QH"),
    "cz_crossborder_flows": ("CrossborderPowerFlows", "HR"),
    "cz_load": ("Load", "HR"),
    "cz_generation_mix": ("Generation", "HR"),
    "cz_renewable_generation": ("GenerationRES", "HR"),
}


def ceps_fetch(method, dfrom, dto, agg):
    r = requests.get("https://www.ceps.cz/downloads/graph",
                     params={"method": method, "format": "csv", "date_from": dfrom,
                             "date_to": dto, "agregation": agg},
                     headers={"Referer": "https://www.ceps.cz/en/all-data"}, timeout=180)
    if r.status_code != 200 or len(r.content) < 500:
        return None
    lines = r.content.decode("utf-8-sig", errors="replace").splitlines()
    names = [c.strip() for c in lines[2].split(";")]
    df = pd.read_csv(io.StringIO("\n".join(lines[3:])), sep=";", header=None,
                     on_bad_lines="skip")
    if df.empty:
        return None
    df.columns = range(len(df.columns))
    first = str(df.iloc[0, 0]).strip()
    if " " in first and len(first) >= 13:          # hourly: "DD.MM.YYYY HH:MM"
        df[0] = pd.to_datetime(df[0], format="%d.%m.%Y %H:%M", errors="coerce")
        df = df.dropna(subset=[0]).set_index(0)
        data_cols = [c for c in names[1:] if c]
    else:                                          # 15-min: date, "HH:MM-HH:MM"
        df["datetime"] = (pd.to_datetime(df[0], format="%d.%m.%Y", errors="coerce")
                          + df[1].str[:5].apply(
                              lambda x: pd.Timedelta(hours=int(x[:2]), minutes=int(x[3:5]))
                              if isinstance(x, str) and len(x) >= 5 else pd.NaT))
        df = df.dropna(subset=["datetime"]).set_index("datetime").drop(columns=[0, 1])
        data_cols = [c for c in names[2:] if c]
    df = df.rename(columns=dict(zip(df.columns, data_cols)))
    df = df[[c for c in df.columns if isinstance(c, str) and c.strip()]]
    df.index.name = "datetime"
    # stable sort: the repeated autumn DST hour is listed CEST first, then CET
    return df.dropna(how="all").sort_index(kind="stable")


def collect_ceps():
    for name, (method, agg) in CEPS_DATASETS.items():
        path = RAW / "ceps" / f"{name}.csv"
        if path.exists():
            log.info(f"  {name} exists, skipped")
            continue
        log.info(f"ČEPS {method}")
        parts = []
        for y in range(START.year, END.year):
            part = ceps_fetch(method, f"{y}-01-01T00:00", f"{y + 1}-01-01T00:00", agg)
            if part is None:
                log.warning(f"  {method} {y}: download failed")
            else:
                parts.append(part)
            time.sleep(0.5)
        if parts:
            save(pd.concat(parts), path)


# ── ERA5 ────────────────────────────────────────────────────────────────────
def collect_era5():
    key = os.getenv("CDS_API_KEY")
    if not key:
        log.warning("CDS_API_KEY is not set, ERA5 skipped (only the era5_* columns need it)")
        return
    import cdsapi
    out = RAW / "era5"
    out.mkdir(parents=True, exist_ok=True)
    c = cdsapi.Client(url=os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api"),
                      key=key, quiet=True)
    for y in range(START.year, END.year):
        for m in range(1, 13):
            f = out / f"era5_cz_{y}_{m:02d}.nc"
            if f.exists():
                continue
            log.info(f"ERA5 {y}-{m:02d}")
            c.retrieve("reanalysis-era5-single-levels", {
                "product_type": "reanalysis",
                "variable": ["100m_u_component_of_wind", "100m_v_component_of_wind",
                             "surface_solar_radiation_downwards", "2m_temperature"],
                "year": str(y), "month": f"{m:02d}",
                "day": [f"{d:02d}" for d in range(1, calendar.monthrange(y, m)[1] + 1)],
                "time": [f"{h:02d}:00" for h in range(24)],
                "area": CZ_BBOX, "format": "netcdf"}, str(f))
    era5_to_csv(out)


def era5_to_csv(folder):
    """Monthly CDS downloads (ZIP with NetCDF inside) -> one CSV per year,
    averaged over the bounding box."""
    import netCDF4
    import numpy as np

    def read(zf, name):
        ds = netCDF4.Dataset(name, memory=zf.read(name))
        t = netCDF4.num2date(ds["valid_time"][:], units=ds["valid_time"].units)
        idx = pd.DatetimeIndex([pd.Timestamp(str(x)) for x in t], name="valid_time")
        data = {v: ds[v][:].mean(axis=(1, 2)) for v in ds.variables if ds[v].ndim == 3}
        ds.close()
        return pd.DataFrame(data, index=idx)

    for y in sorted({p.stem.split("_")[2] for p in folder.glob("era5_cz_*_*.nc")}):
        parts = []
        for f in sorted(folder.glob(f"era5_cz_{y}_*.nc")):
            with zipfile.ZipFile(f) as zf:
                parts.append(pd.concat([read(zf, n) for n in zf.namelist()
                                        if n.endswith(".nc")], axis=1))
        df = pd.concat(parts).sort_index()
        df = df[~df.index.duplicated()]
        df["wind_speed_100m"] = np.sqrt(df["u100"] ** 2 + df["v100"] ** 2)
        save(df, folder / f"era5_cz_{y}.csv")


SOURCES = {"entsoe": collect_entsoe, "forecasts": collect_forecasts,
           "neighbours": collect_neighbours, "ote": collect_ote,
           "ceps": collect_ceps, "era5": collect_era5}

if __name__ == "__main__":
    chosen = sys.argv[1:] or list(SOURCES)
    for s in chosen:
        if s not in SOURCES:
            raise SystemExit(f"unknown source {s}, choose from {list(SOURCES)}")
    for s in chosen:
        SOURCES[s]()
