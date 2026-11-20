# Negative electricity prices in the Czech Republic

Hourly data and descriptive analysis of the Czech day-ahead electricity market, 2020–2025.

## Usage

```sh
pip install -r requirements.txt
python analysis/prepare.py
python analysis/descriptives.py
```

Tables and figures are written to `output/`.

## Thesis figures and tables

```sh
python analysis/thesis/run.py
```

Recomputes all 14 figures and 7 tables of the thesis from `data/` and writes them to
`output/thesis/` under the same file names as in `thesis/`, which holds the copies
printed in the thesis. The run estimates the Markov-switching model and simulates the
solar scenarios, which takes a few minutes.

## Downloading the data again

`data/` can be rebuilt from the original sources:

```sh
cp .env.example .env              # add your ENTSO-E key (CDS key optional)
python collect/download.py        # raw downloads -> raw/
python collect/build_panel.py     # raw/ -> data/
python analysis/thesis/run.py
```

| Source | Key | Data |
|---|---|---|
| OTE | none | day-ahead price and volume 2020–2024 |
| ENTSO-E | `ENTSOE_API_KEY` | day-ahead prices, load, generation per type, day-ahead forecasts |
| ČEPS | none | load, generation mix, solar and wind infeed, cross-border flows, imbalance price |
| ERA5 | `CDS_API_KEY` (optional) | `era5_*` weather columns, not used by the thesis figures |

Downloads are resumable: existing files in `raw/` are skipped, so delete a file to fetch it
again. Sources can be selected, e.g. `python collect/download.py ote ceps`. The OTE part
fetches one report per day and takes about 20 minutes. Published values can be revised
by the sources, so a fresh download may differ slightly from the files in `data/`.
