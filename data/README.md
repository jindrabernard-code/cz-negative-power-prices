# Data

| File | Rows | Period (UTC) | Content |
|---|---|---|---|
| `cz_power_panel.csv` | 52,608 | 2020-01-01 00:00 to 2025-12-31 23:00 | Czech prices, load, generation, cross-border flows, weather |
| `forecasts_cz_de.csv` | 26,304 | 2023-01-01 00:00 to 2025-12-31 23:00 | Day-ahead load, solar and wind forecasts for CZ and DE-LU |
| `neighbour_prices_2025.csv` | 8,760 | 2025-01-01 00:00 to 2025-12-31 23:00 | Day-ahead prices of CZ, DE-LU, AT, SK and PL (ENTSO-E) |

## Conventions

- Index `datetime` is naive UTC, hourly and continuous. Local time is Europe/Prague.
- 15-minute source data are averaged to hourly means.
- Prices in EUR/MWh, except the ČEPS imbalance price (CZK/MWh). Power in MW.
- Cross-border flows: positive = flow into CZ (import).
- Missing values are empty cells.
- `cz_power_panel.csv` uses CRLF line endings. Read it with
  `pd.read_csv(path, index_col=0, parse_dates=True, float_precision="round_trip")`.

## Columns of `cz_power_panel.csv`

| Prefix | Source | Columns |
|---|---|---|
| `ote_price_eur_mwh`, `volume_mwh` | OTE | Day-ahead price and traded volume |
| `entsoe_cz_da_eur_mwh`, `entsoe_de_da_eur_mwh` | ENTSO-E | CZ and DE-LU day-ahead price |
| `entsoe_load_Actual Load` | ENTSO-E | Actual load |
| `entsoe_gen_*` | ENTSO-E | Generation per production type |
| `ceps_imbalance_*` | ČEPS | Estimated imbalance price |
| `ceps_load_*` | ČEPS | Load, with (`zatížení_s_čerpáním`) and without (`zatížení`) pumping |
| `ceps_gen_*_mw` | ČEPS | Generation mix: `je` nuclear, `pe` steam, `ppe` CCGT/industrial, `ve` hydro, `pve` pumped storage (negative = pumping), `ae` alternative, `ze` unused, `vte` wind, `fve` solar |
| `ceps_res_vte_mw`, `ceps_res_fve_mw` | ČEPS | Wind and solar from the separate RES feed |
| `ceps_xborder_<tso>_<skutečnost/plán>_mw` | ČEPS | Physical (`skutečnost`) and scheduled (`plán`) flows per border: `pse` PL, `seps` SK, `apg` AT, `tennet` and `50hzt` DE, `ceps` total |
| `era5_*` | ERA5 | Mean over 48–52°N, 12–19°E: `u100`, `v100`, `wind_speed_100m` (m/s), `t2m` (K), `ssrd` (J/m² per hour) |

## Notes

- 2025: `ote_price_eur_mwh` holds the ENTSO-E CZ day-ahead price (OTE changed its report
  format with the move to 15-minute products on 1 Oct 2025). `volume_mwh` and `era5_*`
  are empty in 2025.
- The two ČEPS solar series agree except for two hours: `ceps_res_fve_mw` is corrupt on
  2025-06-30 18:00 (22,678 MW) and `ceps_gen_fve_mw` is zero on 2024-07-08 11:00.
- Several quantities appear in two sources (OTE and ENTSO-E price, ČEPS and ENTSO-E load
  and generation). Levels differ by metering scope. Use one series per quantity.
- ENTSO-E publishes no day-ahead wind forecast for the Czech area.

## Sources

- OTE, a.s., day-ahead market results, [ote-cr.cz](https://www.ote-cr.cz)
- ENTSO-E Transparency Platform, [transparency.entsoe.eu](https://transparency.entsoe.eu)
- ČEPS, a.s., [ceps.cz/en/all-data](https://www.ceps.cz/en/all-data)
- Copernicus Climate Change Service, ERA5 hourly data on single levels
