"""
Figures and tables of the thesis, in thesis numbering, written to
output/thesis/figures and output/thesis/tables.

Inputs: data/cz_power_panel.csv, data/neighbour_prices_2025.csv, the prepared
dataset (prepare.py) and the scenario summaries (simulate.py). Values taken
from publications are quoted below with their source.

Black and white, Liberation Serif (falls back to DejaVu Serif).
"""
from decimal import ROUND_HALF_UP, Decimal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

import config as C
import heat

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "font.size": 10,
    "axes.edgecolor": "black",
    "axes.labelcolor": "black",
    "xtick.color": "black",
    "ytick.color": "black",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "mathtext.fontset": "stix",
})

FIG = C.FIG_DIR
TAB = C.TAB_DIR
WORK = C.WORK_DIR
W = 6.3          # inches, text width of the template

# ── published values ─────────────────────────────────────────────────────────
# IPCC (2021) AR6 WGI SPM, Table SPM.1: warming vs 1850–1900, best estimate
# (very likely range), for 2021–2040, 2041–2060, 2081–2100.
IPCC_SPM1 = {
    "SSP1-1.9": [(1.5, 1.2, 1.7), (1.6, 1.2, 2.0), (1.4, 1.0, 1.8)],
    "SSP1-2.6": [(1.5, 1.2, 1.8), (1.7, 1.3, 2.2), (1.8, 1.3, 2.4)],
    "SSP2-4.5": [(1.5, 1.2, 1.8), (2.0, 1.6, 2.5), (2.7, 2.1, 3.5)],
    "SSP3-7.0": [(1.5, 1.2, 1.8), (2.1, 1.7, 2.6), (3.6, 2.8, 4.6)],
    "SSP5-8.5": [(1.6, 1.3, 1.9), (2.4, 1.9, 3.0), (4.4, 3.3, 5.7)],
}
WMO_2024 = 1.55                                    # WMO (2025)
# Annual average EUA price, EUR/t: Nissen et al. (2025, EEA ETC CM 2025/06)
# for 2021–2024, ESMA (2026) for 2025.
EUA_AVG = {2021: 54.15, 2022: 80.18, 2023: 83.60, 2024: 64.76, 2025: 74.0}
# CDR.fyi and OPIS (2025) DACCS survey, USD/t; converted at 0.88 EUR/USD as
# in the text (670 USD ≈ 590 EUR).
USD_EUR = 0.88
DACCS_USD = {"Supplier break-even 2025": 670, "Buyer “good value” 2025": 458,
             "Supplier break-even 2030 (expected)": 341}
# Smith et al. (2024, ch. 7): removals in 2023, MtCO2/yr.
CDR_2023 = {"Conventional (forests, land)": 2010, "Biochar": 0.79, "BECCS": 0.51,
            "Enhanced rock weathering": 0.03, "DACCS": 0.004}

GEN_GROUPS = {
    "Nuclear": ["entsoe_gen_nuclear"],
    "Lignite": ["entsoe_gen_fossil_brown_coal_lignite"],
    "Other fossil": ["entsoe_gen_fossil_hard_coal", "entsoe_gen_fossil_gas",
                     "entsoe_gen_fossil_coal-derived_gas", "entsoe_gen_fossil_oil"],
    "Hydro": ["entsoe_gen_hydro_pumped_storage",
              "entsoe_gen_hydro_run-of-river_and_poundage",
              "entsoe_gen_hydro_water_reservoir"],
    "Biomass, waste, other": ["entsoe_gen_biomass", "entsoe_gen_waste",
                              "entsoe_gen_other", "entsoe_gen_other_renewable"],
    "Wind": ["entsoe_gen_wind_onshore"],
    "Solar": ["entsoe_gen_solar"],
}
GREYS = ["0.15", "0.35", "0.5", "0.65", "0.78", "0.88", "white"]
HATCH = ["", "", "", "", "", "..", "///"]


def load_panel():
    df = pd.read_csv(C.PANEL_CSV, parse_dates=["datetime"],
                     float_precision="round_trip").set_index("datetime")
    loc = df.index.tz_localize("UTC").tz_convert("Europe/Prague")
    df["year"], df["month"], df["hour"] = loc.year, loc.month, loc.hour
    return df


# ── chapter 2 ────────────────────────────────────────────────────────────────
def fig_ipcc():
    fig, ax = plt.subplots(figsize=(W, 3.0))
    periods = ["2021–2040", "2041–2060", "2081–2100"]
    markers = ["o", "s", "^", "D", "v"]
    n = len(IPCC_SPM1)
    for k, (ssp, vals) in enumerate(IPCC_SPM1.items()):
        x = np.arange(3) + (k - (n - 1) / 2) * 0.14
        b = np.array([v[0] for v in vals])
        lo = b - np.array([v[1] for v in vals])
        hi = np.array([v[2] for v in vals]) - b
        ax.errorbar(x, b, yerr=[lo, hi], fmt=markers[k], color="black",
                    mfc="white" if k % 2 else "black", ms=5, capsize=2, lw=0.8,
                    label=ssp)
    ax.axhline(1.5, color="black", lw=0.6, ls=":")
    ax.axhline(WMO_2024, color="0.4", lw=0.8, ls="--")
    ax.text(0.5, WMO_2024 + 0.07, "2024 observed\n(1.55 °C)", ha="center",
            va="bottom", fontsize=7.5, color="0.3", linespacing=1.1)
    ax.text(1.5, 1.5 - 0.07, "1.5 °C\n(Paris goal)", ha="center", va="top",
            fontsize=7.5, color="0.3", linespacing=1.1)
    ax.set_xticks(range(3), periods)
    ax.set_ylabel("Warming vs 1850–1900 (°C)")
    ax.set_xlim(-0.45, 2.45)
    ax.set_ylim(0.8, 6)
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.13), fontsize=8,
              handletextpad=0.3, columnspacing=1.0)
    fig.savefig(FIG / "fig01_projected_global_warming_in_the_ipcc_ar6.png")
    plt.close(fig)


def _box(ax, x, y, w, h, text, head=None, fs=9, fill="white", lw=1.2, ls="-", hh=0.075):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.015",
                                fc=fill, ec="black", lw=lw, ls=ls))
    if head:
        ax.add_patch(FancyBboxPatch((x, y + h - hh), w, hh,
                                    boxstyle="round,pad=0.01,rounding_size=0.015",
                                    fc="0.85", ec="black", lw=lw))
        ax.text(x + w / 2, y + h - hh / 2, head, ha="center", va="center",
                fontsize=fs, weight="bold")
        ax.text(x + w / 2, y + (h - hh) / 2, text, ha="center", va="center",
                fontsize=fs - 0.5, linespacing=1.25)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                linespacing=1.25)


def _arrow(ax, x0, y0, x1, y1, text=None, side="above", lw=1.3, ls="-"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=lw, ls=ls,
                                mutation_scale=12))
    if text:
        dy = 0.03 if side == "above" else -0.03
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + dy, text, ha="center",
                va="bottom" if side == "above" else "top", fontsize=8, style="italic")


def _canvas(h):
    fig = plt.figure(figsize=(W, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def fig_daccs_schema():
    fig, ax = _canvas(4.0)
    bw, bh, y = 0.19, 0.29, 0.37
    xs = [0.02, 0.27, 0.52, 0.77]
    heads = ["1  Capture", "2  Regeneration", "3  Compression", "4  Storage"]
    body = ["Fans push air\nthrough a filter\n(sorbent) that\nbinds CO\u2082",
            "Full filter is\nheated to about\n100 °C and\nreleases pure CO\u2082",
            "CO\u2082 is\ncompressed for\ntransport by\npipeline or ship",
            "CO\u2082 is injected\ninto deep rock\nformations and\nstays there"]
    for x, hd, b in zip(xs, heads, body):
        _box(ax, x, y, bw, bh, b, head=hd)
    for k in range(3):
        _arrow(ax, xs[k] + bw + 0.01, y + bh * 0.4, xs[k + 1] - 0.01, y + bh * 0.4)
    ax.text(xs[0] + bw / 2, y - 0.035, "air in (0.04 % CO\u2082),\nair out with less CO\u2082",
            ha="center", va="top", fontsize=8, style="italic", linespacing=1.3)
    # energy inputs per tonne captured (working values of the thesis)
    top = y + bh + 0.012
    _box(ax, 0.02, 0.885, 0.69, 0.09, "Electricity \u2248 0.5 MWh per tonne "
         "(fans, vacuum pump, compression)", fs=8.5, fill="0.93")
    _box(ax, 0.27, 0.75, 0.19, 0.09, "Heat \u2248 1.7 MWh\nper tonne", fs=8.5, fill="0.93")
    _arrow(ax, xs[0] + bw / 2, 0.875, xs[0] + bw / 2, top, lw=1)
    _arrow(ax, xs[2] + bw / 2, 0.875, xs[2] + bw / 2, top, lw=1)
    _arrow(ax, xs[1] + bw / 2, 0.74, xs[1] + bw / 2, top, lw=1)
    # economics row
    _box(ax, 0.02, 0.015, 0.46, 0.2,
         "capital (CAPEX, the largest item)\nelectricity, heat, maintenance\n"
         "transport and storage", head="Costs", fs=8.5)
    _box(ax, 0.52, 0.015, 0.46, 0.2,
         "removal credit for each tonne stored,\nminus the emissions of the\n"
         "electricity and heat used (net tonne)", head="Revenue", fs=8.5)
    fig.savefig(FIG / "fig02_how_a_solid_sorbent_daccs_plant_works.png")
    plt.close(fig)


def fig_genmix(df):
    d = df[df.year.isin([2024, 2025]) & df.month.between(4, 8)]
    prof = pd.DataFrame({k: d[v].clip(lower=0).sum(axis=1).groupby(d.hour).mean() / 1000
                         for k, v in GEN_GROUPS.items()})
    load = d["entsoe_load_Actual Load"].groupby(d.hour).mean() / 1000
    negshare = (d.ote_price_eur_mwh < 0).groupby(d.hour).mean() * 100
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(W, 4.6), sharex=True,
                                 gridspec_kw={"height_ratios": [2.2, 1]})
    bottom = np.zeros(24)
    for (k, col), g, h in zip(prof.items(), GREYS, HATCH):
        a1.bar(prof.index, col.values, bottom=bottom, width=0.9, color=g,
               edgecolor="black", lw=0.3, hatch=h, label=k)
        bottom += col.values
    a1.plot(load.index, load.values, color="black", lw=1.5, marker="o", ms=2.5,
            label="Load")
    a1.set_ylabel("Mean output (GW)")
    a1.legend(ncol=4, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, 1.22))
    a2.bar(negshare.index, negshare.values, width=0.7, color="0.3")
    a2.set_ylabel("Hours with\nprice < 0 (%)")
    a2.set_xlabel("Hour of day (local time)")
    a2.set_xticks(range(0, 24, 2))
    fig.savefig(FIG / "fig04_czech_generation_mix_and_negative_prices_by.png")
    plt.close(fig)


def fig_negative_hours(df):
    neg = df.ote_price_eur_mwh < 0
    yrs = list(range(2020, 2026))
    per_year = neg.groupby(df.year).sum().reindex(yrs)
    by_month = pd.crosstab(df.year[neg], df.month[neg]).reindex(columns=range(1, 13),
                                                              fill_value=0)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 2.8),
                                 gridspec_kw={"width_ratios": [1, 1.6]})
    a1.bar(per_year.index, per_year.values, color="0.4", edgecolor="black", lw=0.5)
    for x, v in per_year.items():
        a1.text(x, v + 6, f"{v}", ha="center", fontsize=8)
    a1.set_ylabel("Negative-price hours")
    a1.set_title("(a) per year", fontsize=10)
    a1.set_xticks(yrs, [str(y) for y in yrs], fontsize=8)
    a1.set_ylim(0, per_year.max() * 1.12)
    styles = {2023: ("0.6", ":", "s"), 2024: ("0.35", "--", "^"), 2025: ("black", "-", "o")}
    for y, (c, ls, m) in styles.items():
        a2.plot(range(1, 13), by_month.loc[y].values, color=c, ls=ls, marker=m, ms=4,
                lw=1.2, label=str(y), mfc="white" if y == 2023 else c)
    a2.set_xticks(range(1, 13), list("JFMAMJJASOND"))
    a2.set_title("(b) per month, 2023–2025", fontsize=10)
    a2.set_ylabel("Negative-price hours")
    a2.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig05_negative_price_hours_on_the_czech_day_ahead.png")
    plt.close(fig)


def fig_projection(df):
    cz = pd.read_csv(WORK / "sim_scenario_summary.csv")
    de = pd.read_csv(WORK / "sim_scenario_summary_joint_de.csv")
    labels = ["Today\n(2024 capacity)", "2030 low", "2030 central", "2030 high",
              "2035 central"]
    x = np.arange(len(cz))
    fig, ax = plt.subplots(figsize=(W, 3.3))
    for t, off, m, fc, lab in [(cz, -0.12, "o", "white", "Czech solar grows"),
                               (de, 0.12, "s", "black", "Czech and German solar grow")]:
        y = t.expected_negative_hours_per_year.values
        ax.errorbar(x + off, y, yerr=[y - t.negative_hours_p05, t.negative_hours_p95 - y],
                    fmt=m, color="black", mfc=fc, ms=6, capsize=3, lw=0.9, label=lab)
        lo, hi = t.negative_hours_p05.values, t.negative_hours_p95.values
        for xi, yi, l, h in zip(x + off, y, lo, hi):
            if off < 0:      # open circles: value under the lower whisker
                ax.text(xi, l - 10, f"{yi:.0f}", ha="center", va="top", fontsize=7.5)
            else:            # filled squares: value above the upper whisker
                ax.text(xi, h + 10, f"{yi:.0f}", ha="center", va="bottom", fontsize=7.5)
    observed = (df.ote_price_eur_mwh < 0).groupby(df.year).sum()
    for yr, ls in [(2024, ":"), (2025, "--")]:
        v = int(observed[yr])
        ax.axhline(v, color="0.5", lw=0.7, ls=ls, label=f"observed {yr} ({v} h)")
    ax.set_xticks(x, labels, fontsize=8.5)
    ax.set_ylabel("Negative-price hours per year")
    ax.set_ylim(150, 700)
    ax.set_xlim(-0.5, len(cz) - 0.5)
    h, l = ax.get_legend_handles_labels()
    order = [2, 3, 0, 1]
    ax.legend([h[i] for i in order], [l[i] for i in order], fontsize=8,
              loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    fig.savefig(FIG / "fig06_simulated_negative_price_hours_per_year_in.png")
    plt.close(fig)


def fig_eua_credits():
    fig, ax = plt.subplots(figsize=(W, 2.9))
    yrs = list(EUA_AVG)
    ax.bar(yrs, list(EUA_AVG.values()), color="0.55", edgecolor="black", lw=0.5,
           width=0.6, label="EU allowance (EUA), annual average")
    for y, v in EUA_AVG.items():
        ax.text(y, v + 12, f"{v:.0f}", ha="center", fontsize=8)
    styles = ["-", "--", ":"]
    for (lab, usd), ls in zip(DACCS_USD.items(), styles):
        v = usd * USD_EUR
        ax.axhline(v, color="black", lw=1.2, ls=ls, label=f"DACCS credit: {lab[0].lower() + lab[1:]}")
        ax.text(2025.58, v, f"{v:.0f}", fontsize=8, ha="left", va="center")
    ax.set_xticks(yrs)
    ax.set_xlim(2020.5, 2025.5)
    ax.set_ylim(0, 700)
    ax.set_ylabel("EUR per tonne of CO₂")
    ax.legend(fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.12), ncol=2, columnspacing=1.2, handlelength=2.5)
    fig.savefig(FIG / "fig07_eu_allowance_price_and_daccs_removal_credit.png")
    plt.close(fig)


def fig_cdr_methods():
    fig, ax = plt.subplots(figsize=(W, 2.4))
    names = list(CDR_2023)[::-1]
    vals = [CDR_2023[n] for n in names]
    cols = ["black" if n == "DACCS" else ("0.8" if n.startswith("Conv") else "0.5")
            for n in names]
    ax.barh(names, vals, color=cols, edgecolor="black", lw=0.5)
    ax.set_xscale("log")
    ax.set_xlim(0.001, 1e4)
    for n, v in zip(names, vals):
        s = f"{v:,.0f}" if v >= 10 else (f"{v:.2f}" if v >= 0.01 else f"{v:.3f}")
        ax.text(v * 1.3, n, s, va="center", fontsize=8)
    ax.set_xlabel("CO₂ removed in 2023 (MtCO₂ per year, logarithmic scale)")
    fig.savefig(FIG / "fig08_carbon_dioxide_removal_by_method_in_2023.png")
    plt.close(fig)


# ── chapter 4 schemas ────────────────────────────────────────────────────────
def _flow(name, h, rows, side=None, side_title=None):
    """Vertical flow of boxes; side = list of (row index, text) alternatives."""
    fig, ax = _canvas(h)
    n = len(rows)
    gap = 0.055
    top = 0.94 if side_title else 0.99
    bh = (top - 0.025 - (n - 1) * gap) / n
    x, w = (0.02, 0.56) if side else (0.2, 0.6)
    ys = [top - (k + 1) * bh - k * gap for k in range(n)]
    for k, (head, text) in enumerate(rows):
        _box(ax, x, ys[k], w, bh, text, head=head, fs=8.5, hh=0.33 * bh)
        if k:
            _arrow(ax, x + w / 2, ys[k - 1] - 0.01, x + w / 2, ys[k] + bh + 0.012)
    if side:
        if side_title:
            ax.text(0.8, 0.99, side_title, ha="center", va="top", fontsize=8.5,
                    weight="bold")
        for k, text in side:
            _box(ax, 0.64, ys[k], 0.34, bh, text, fs=8, ls="--", lw=1)
            _arrow(ax, 0.63, ys[k] + bh / 2, x + w + 0.012, ys[k] + bh / 2, lw=0.9, ls="--")
    fig.savefig(FIG / name)
    plt.close(fig)


def fig_layer_schemas():
    _flow("fig12_layer_a_steps_of_the_econometric_analysis.png", 5.8, [
        ("Data", "hourly day-ahead price, forecast residual load (CZ, DE-LU)\n"
                 "estimation: April 2023 – June 2024"),
        ("1  Deseasonalisation (4.2.1)", "remove day-type and annual cycles\n"
                                       "keep the daily profile"),
        ("2  Benchmark: logit (4.2.2)", "probability of a surplus hour from\n"
                                        "forecast residual load and the calendar"),
        ("3  Core model: MS-TVTP (4.2.3)", "3 hidden regimes (surplus / normal / spike)\n"
                                           "transitions driven by residual load"),
        ("4  Validation (4.2.3)", "regimes match the midday solar block?\n"
                                  "day-ahead forecasts in the 2025 test year"),
        ("5  Projection (4.2.4)", "solar infeed scaled to 2030 and 2035\n"
                                  "→ price paths for Layer B"),
    ], side=[(2, "climatology benchmark\n(frequency by hour × month)"),
             (3, "MS-AR(1)\nmean-regression MS\nconstant transition probabilities\n2 regimes"),
             (4, "Brier score, log loss, AUC\nDiebold–Mariano test"),
             (5, "Czech solar only\nor Czech and German solar")],
          side_title="Alternatives and checks")
    _flow("fig13_layer_b_steps_of_the_operating_analysis.png", 4.5, [
        ("Inputs", "price paths simulated from Layer A\nplant parameters, credit price π"),
        ("1  Plant model (4.3.1)", "energy use, costs, minimum up- and down-times"),
        ("2  Run-or-not rule (4.3.2)", "run in hour t if the price is below\n"
                                       "the reservation price $p^{*}_{t}$"),
        ("3  Operation over the year (4.3.3)", "threshold rule (used for all economic results)"),
        ("4  Simulation (4.3.4)", "distribution of the capacity factor,\n"
                                  "tonnes captured and electricity cost → Layer C"),
    ], side=[(2, "heat at fixed tariff (base)\nheat indexed to power price\nheat pump"),
             (3, "minimum-run optimum\n(dynamic programming)\nbaseload operation"),
             (4, "check against the realised\n2025 prices")],
          side_title="Alternatives and benchmarks")
    _flow("fig14_layer_c_steps_of_the_economic_analysis.png", 4.5, [
        ("Inputs", "operation from Layer B, costs (CAPEX, WACC,\n"
                   "lifetime, O&M, heat, transport and storage)"),
        ("1  Carbon accounting (4.4.3)", "net tonnes = captured tonnes minus emissions\n"
                                         "of the electricity and heat used"),
        ("2  Cost per tonne, LCOC (4.4.1)", "annual costs ÷ net tonnes removed"),
        ("3  Break-even (4.4.2)", "credit price π* at which LCOC(π*) = π*"),
        ("4  Comparison", "with removal-credit prices (Section 2.6)\n→ answer to RQ4"),
    ], side=[(1, "average grid intensity (base)\nmarginal intensity, CRCF rules\n"
                 "heat allocation conventions"),
             (3, "2030/2035 scenarios, energy use,\nCAPEX, WACC, heat price,\n"
                 "transport and storage, net vs gross")],
          side_title="Alternatives and sensitivities")


# ── tables ───────────────────────────────────────────────────────────────────
def table_grid_ef(df):
    d = df[df.year == 2024]
    rows = []
    for k, cols in GEN_GROUPS.items():
        gen = d[cols].clip(lower=0).sum().sum()
        efs = sorted({C.EMISSION_FACTORS.get(c, 0.0) for c in cols})
        rows.append({"source": k, "ef_min": efs[0], "ef_max": efs[-1], "gen_twh": gen / 1e6})
    t = pd.DataFrame(rows)
    t["share_pct"] = 100 * t.gen_twh / t.gen_twh.sum()
    allc = [c for v in GEN_GROUPS.values() for c in v]
    g = d[allc].clip(lower=0)
    emis = sum(g[c] * C.EMISSION_FACTORS.get(c, 0.0) for c in allc).sum()
    t.loc[len(t)] = {"source": "Generation-weighted average", "ef_min": emis / g.sum().sum(),
                     "ef_max": emis / g.sum().sum(), "gen_twh": g.sum().sum() / 1e6,
                     "share_pct": 100.0}
    t.round(3).to_csv(WORK / "theory_grid_ef_2024.csv", index=False)

    def ef(lo, hi, avg=False):
        if avg:
            return f"{lo:.3f}"
        f = lambda x: "0" if x == 0 else f"{x:.2f}"
        return f(lo) if lo == hi else f"{f(lo)}–{f(hi)}"
    out = pd.DataFrame({
        "Source": t.source,
        "Emission factor (tCO₂/MWh)": [ef(r.ef_min, r.ef_max, r.source.startswith("Generation"))
                                       for r in t.itertuples()],
        "Generation (TWh)": t.gen_twh.round(1),
        "Share (%)": t.share_pct.round(1)})
    out.to_csv(TAB / "tab06_emission_factors_and_generation_shares_of.csv", index=False)
    return t


def table_heat_ef():
    h = heat.table()
    labels = {"lignite_chp": "Lignite CHP", "hard_coal_chp": "Hard coal CHP",
              "gas_chp": "Gas CHP", "waste_chp": "Waste incineration CHP",
              "gas_boiler": "Gas boiler", "coal_boiler": "Lignite boiler"}
    h = h.set_index("configuration").loc[list(labels)]
    out = pd.DataFrame({
        "Heat source": [labels[c] for c in h.index],
        "η el": h.eta_el.map("{:.2f}".format).values,
        "η th": h.eta_th.map("{:.2f}".format).values,
        "Fuel factor (tCO₂/MWh fuel)": h.ef_fuel_t_per_mwh.round(4).map(lambda v: round(v, 3)).values,
        "Energy": h.ef_heat_energy.round(4).map(lambda v: round(v, 3)).values,
        "Exergy": h.ef_heat_exergy.round(4).map(lambda v: round(v, 3)).values,
        "Power-loss": h.ef_heat_power_loss.round(4).map(lambda v: round(v, 3)).values})
    out.to_csv(TAB / "tab07_emission_factor_of_delivered_heat_by.csv", index=False)
    return out


# ── merit order and two example hours (§2.2) ────────────────────────────────
# Hour A: the lowest Czech price of 2024 (Sunday 12 May 2024, 13:00 local).
# Hour B: an ordinary winter weekday evening (Wednesday 17 January 2024, 18:00).
HOUR_A = pd.Timestamp("2024-05-12 13:00", tz="Europe/Prague")
HOUR_B = pd.Timestamp("2024-01-17 18:00", tz="Europe/Prague")
TWO_HOUR_ROWS = ["Solar", "Wind", "Hydro", "Nuclear", "Lignite", "Other fossil",
                 "Biomass, waste, other"]


def _hour(df, ts):
    return df.loc[ts.tz_convert("UTC").tz_localize(None)]


def table_two_hours(df):
    rows = {}
    for lab, ts in [("A", HOUR_A), ("B", HOUR_B)]:
        r = _hour(df, ts)
        gen = {k: float(r[v].clip(lower=0).sum()) for k, v in GEN_GROUPS.items()}
        col = {k: gen[k] for k in TWO_HOUR_ROWS}
        col["Total generation"] = sum(gen.values())
        col["Net physical import"] = float(r["ceps_xborder_ceps_skutečnost_mw"])
        col["Pumped-storage pumping"] = float(r["ceps_load_zatížení_s_čerpáním_mw"]
                                              - r["ceps_load_zatížení_mw"])
        col["Load"] = float(r["entsoe_load_Actual Load"])
        col["CZ day-ahead price (EUR/MWh)"] = float(r["ote_price_eur_mwh"])
        col["DE day-ahead price (EUR/MWh)"] = float(r["entsoe_de_da_eur_mwh"])
        rows[lab] = col
    tab = pd.DataFrame(rows)
    tab.round(2).to_csv(WORK / "theory_two_hours.csv")
    out = tab.astype(object)
    for r in out.index:
        out.loc[r] = (tab.loc[r].round(1) if "price" in r
                      else tab.loc[r].round(0).astype(int)).values
    out.columns = [f"{ts:%A} {ts.day} {ts:%B}, {ts:%H:%M}" for ts in (HOUR_A, HOUR_B)]
    out.to_csv(TAB / "tab01_generation_cross_border_flows_and_price_in.csv")
    return tab


def fig_merit_order(df, two):
    """Schematic merit order: widths from 2024 data, heights only show the order."""
    d = df[df.year == 2024]
    out = {k: d[v].clip(lower=0).sum(axis=1) for k, v in GEN_GROUPS.items()}
    lig_min = out["Lignite"].min()
    blocks = [  # (label, width GW, schematic bid, hatch, fill)
        ("Solar", out["Solar"].max(), -3.0, "///", "white"),
        ("Wind", out["Wind"].max(), -2.0, "..", "0.9"),
        ("Nuclear", out["Nuclear"].max(), -0.6, "", "0.35"),
        ("Lignite,\nminimum load", lig_min, -0.3, "xx", "0.6"),
        ("Hydro", out["Hydro"].max(), 1.0, "", "0.8"),
        ("Biomass,\nwaste", out["Biomass, waste, other"].max(), 2.0, "", "0.9"),
        ("Lignite", out["Lignite"].max() - lig_min, 4.0, "", "0.6"),
        ("Gas, hard\ncoal, oil", out["Other fossil"].max(), 6.5, "", "0.45"),
    ]
    fig, ax = plt.subplots(figsize=(W, 3.6))
    x = 0.0
    for lab, w, h, ha, fc in blocks:
        w = w / 1000
        ax.bar(x, h, width=w, align="edge", color=fc, edgecolor="black", lw=0.6,
               hatch=ha)
        ty = h + 0.25 if h > 0 else 0.25
        if lab.startswith("Lignite,"):
            ax.annotate(lab.replace("\n", " "), xy=(x + w / 2, -0.15),
                        xytext=(x + w / 2 + 0.5, -2.4), fontsize=7.2, ha="left",
                        arrowprops=dict(arrowstyle="-", lw=0.6, color="black"))
        else:
            ax.text(x + w / 2, ty, lab, ha="center", va="bottom", fontsize=7.2,
                    linespacing=1.0)
        x += w
    ax.axhline(0, color="black", lw=0.8)
    for key, ls, name in [("A", "-", "Hour A"), ("B", "--", "Hour B")]:
        q = two.loc["Total generation", key] / 1000
        pr = two.loc["CZ day-ahead price (EUR/MWh)", key]
        ax.plot([q + 0.35, q - 0.35], [-4.2, 7.6], color="black", lw=1.4, ls=ls)
        ax.text(q + 0.2, 7.7, f"{name}\n{pr:+.0f} EUR/MWh".replace("-", "\u2212"), ha="center",
                va="bottom", fontsize=7.5, linespacing=1.05)
    ax.set_xlim(0, x)
    ax.set_ylim(-4.5, 9.3)
    ax.set_yticks([0], ["0"])
    ax.set_ylabel("Bid price (schematic)")
    ax.set_xlabel("Cumulative capacity offered (GW)")
    ax.text(3.1, -0.9, "bids below zero:\nsupport schemes,\nmust-run, costly restarts",
            fontsize=7, va="top", color="0.2")
    fig.savefig(FIG / "fig03_schematic_merit_order_of_the_czech_zone_in.png")
    plt.close(fig)


# ── neighbouring zones (§3.4): price coupling and physical flows, 2025 ───────
BORDERS = {"DE": ["tennet", "50hzt"], "AT": ["apg"], "SK": ["seps"], "PL": ["pse"]}  # table order
PRICE_ZONE = {"DE": "DE_LU", "AT": "AT", "SK": "SK", "PL": "PL"}


def table_neighbours(df, year=2025):
    """ENTSO-E day-ahead prices and ČEPS physical flows.
    ČEPS sign: positive = flow into the Czech zone."""
    pr = pd.read_csv(C.NEIGHBOUR_CSV, index_col=0, parse_dates=True)
    pr = pr[pr.index.year == year]
    cz_neg = pr["CZ"] < 0
    d = df[df.year == year]
    neg = d.ote_price_eur_mwh < 0
    rows = {}
    for b, cols in BORDERS.items():
        f = sum(d[f"ceps_xborder_{c}_skutečnost_mw"] for c in cols)
        z = pr[PRICE_ZONE[b]]
        rows[b] = {
            "price_corr": pr["CZ"].corr(z),
            "share_cz_neg_also_neg": (z[cz_neg] < 0).mean(),
            "import_twh": f.clip(lower=0).sum() / 1e6,
            "export_twh": (-f).clip(lower=0).sum() / 1e6,
            "net_import_twh": f.sum() / 1e6,
            "net_import_mw_all": f.mean(),
            "net_import_mw_neg": f[neg].mean(),
        }
    tab = pd.DataFrame(rows).T
    tab.round(3).to_csv(WORK / f"desc_neighbours_{year}.csv")
    out = pd.DataFrame({
        "Zone": ["Germany", "Austria", "Slovakia", "Poland"],
        "Price corr. with CZ": tab.price_corr.round(2).values,
        "Negative when CZ negative (%)": [round(100 * round(v, 3)) for v in tab.share_cz_neg_also_neg],
        "Import to CZ (TWh)": tab.import_twh.round(1).values,
        "Export from CZ (TWh)": tab.export_twh.round(1).values,
        "Net import (TWh)": tab.net_import_twh.round(1).values,
        "Mean net import, all hours (MW)": tab.net_import_mw_all.round(0).astype(int).values,
        "Mean net import, CZ negative hours (MW)": tab.net_import_mw_neg.round(0).astype(int).values,
    })
    out.to_csv(TAB / "tab05_neighbouring_zones_of_the_czech_republic_in.csv", index=False)
    return tab


# ── descriptive figures (§3.4) ───────────────────────────────────────────────
def _neg_blocks(df):
    neg = (df.ote_price_eur_mwh < 0).astype(int).values
    runs, n = [], 0
    for v in neg:
        if v:
            n += 1
        elif n:
            runs.append(n)
            n = 0
    if n:
        runs.append(n)
    return pd.Series(runs)


def fig_negative_blocks(df):
    runs = _neg_blocks(df)
    cnt = runs.value_counts().reindex(range(1, runs.max() + 1), fill_value=0)
    hrs = cnt * cnt.index
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, 2.6), sharex=True)
    a1.bar(cnt.index, cnt.values, color="0.45", edgecolor="black", lw=0.4)
    a1.set_title("(a) number of blocks", fontsize=10)
    a1.set_ylabel("Blocks")
    a2.bar(hrs.index, hrs.values, color="0.45", edgecolor="black", lw=0.4)
    a2.set_title("(b) negative-price hours in blocks", fontsize=10)
    a2.set_ylabel("Hours")
    for a in (a1, a2):
        a.set_xlabel("Block length (consecutive hours)")
        a.set_xticks([1, 5, 10, 15, int(runs.max())])
    fig.tight_layout()
    fig.savefig(FIG / "fig09_length_of_blocks_of_consecutive_negative.png")
    plt.close(fig)
    long_share = hrs[hrs.index >= 5].sum() / hrs.sum()
    print(f"blocks {len(runs)}, mean {runs.mean():.2f}, max {runs.max()}, "
          f"share of hours in blocks >= 5 h {long_share:.3f}")


def fig_price_resload():
    from prepare import load_prepared
    d = load_prepared()[["ote_price_eur_mwh", "residual_load_mw", "subperiod"]].dropna()
    names = {"pre_crisis": "(a) pre-crisis,\nJan 2020 – Jun 2021",
             "crisis": "(b) crisis,\nJul 2021 – Mar 2023",
             "post_crisis": "(c) post-crisis,\nApr 2023 – Dec 2025"}
    fig, axes = plt.subplots(1, 3, figsize=(W, 2.7), sharex=True)
    for ax, (sp, title) in zip(axes, names.items()):
        g = d[d.subperiod == sp]
        r = g.ote_price_eur_mwh.corr(g.residual_load_mw)
        ax.scatter(g.residual_load_mw / 1000, g.ote_price_eur_mwh, s=0.6,
                   color="black", alpha=0.12, lw=0, rasterized=True)
        ax.axhline(0, color="0.5", lw=0.6, ls=":")
        ax.set_title(f"{title}\nr = {r:.2f}", fontsize=8.5)
        ax.set_xlabel("Residual load (GW)")
    axes[0].set_ylabel("Day-ahead price (EUR/MWh)")
    fig.tight_layout()
    fig.savefig(FIG / "fig10_day_ahead_price_and_residual_load_by_sub.png")
    plt.close(fig)




# ── chapter 4: the three layers ─────────────────────────────────────────────
def fig_pipeline():
    fig = plt.figure(figsize=(8.6, 2.7))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    bw, y, h = 0.262, 0.13, 0.74
    xs = [0.012, 0.369, 0.726]
    heads = ["Layer A: Econometrics", "Layer B: Optimisation", "Layer C: Economics"]
    body = ["Markov-switching model of\nhourly Czech day-ahead prices\n"
            "(TVTP driven by CZ and DE\nforecast residual load)",
            "Operating policy of the DAC\nplant (run / idle each hour)\n"
            "on price paths simulated\nfrom the estimated model",
            "Endogenous capacity factor\n\u2192 levelised cost of carbon\n"
            "removal (LCOC)\n\u2192 break-even credit price"]
    for x, hd, b in zip(xs, heads, body):
        _box(ax, x, y, bw, h, b, head=hd, fs=13, lw=1.6, hh=0.17)
    for k, lab in enumerate(["price\npaths", "dispatch"]):
        x0, x1 = xs[k] + bw + 0.012, xs[k + 1] - 0.012
        _arrow(ax, x0, 0.4, x1, 0.4, lw=2)
        ax.text((x0 + x1) / 2, 0.47, lab, ha="center", va="bottom", fontsize=11.5,
                style="italic", linespacing=1.1)
    fig.savefig(FIG / "fig11_the_three_layer_pipeline_each_layer_uses_the.png")
    plt.close(fig)


# ── chapter 3: price by year ────────────────────────────────────────────────
def table_price_by_year():
    from prepare import load_prepared
    d = load_prepared()
    d = d[d.year.between(2020, 2025)]
    g = d.groupby("year")
    p = g["ote_price_eur_mwh"]

    def r(x, n):
        """round half up on the 2-decimal value"""
        q = Decimal(1).scaleb(-n)
        return x.round(2).map(lambda v: float(Decimal(str(v)).quantize(q, ROUND_HALF_UP)))
    out = pd.DataFrame({
        "Mean": r(p.mean(), 1), "Std. dev.": r(p.std(), 1),
        "Min": r(p.min(), 1), "Max": r(p.max(), 1),
        "Hours < 0": g["surplus"].sum().astype(int),
        "Share < 0": r(100 * g["surplus"].mean(), 1),
        "Hours < 20": g["surplus_lt20"].sum().astype(int),
        "Max hourly PV infeed (MW)": r(g["solar_mw"].max(), 0).astype(int),
        "Mean residual load (MW)": r(g["residual_load_mw"].mean(), 0).astype(int),
    })
    out.index.name = "Year"
    out.to_csv(TAB / "tab04_czech_day_ahead_price_by_year_eur_mwh_and.csv")
    return out


# ── tables compiled from the literature and the data description ────────────
# Fuss et al. (2018, Table 2); CDR.fyi and OPIS (2025); European Union (2024);
# European Commission (2026).
CDR_METHODS = pd.DataFrame([
    ["Afforestation and reforestation",
     "biomass and soil, decades to centuries, reversible, forests saturate",
     "5–50", "—", "carbon farming"],
    ["Soil carbon sequestration", "soil, reversible when the practice stops, saturates",
     "0–100", "—", "carbon farming"],
    ["Biochar", "char in soil, decades to centuries", "30–120", "143 / 136",
     "permanent removal, methodology adopted 2026"],
    ["Enhanced weathering", "dissolved carbonate, months to geological time scales",
     "50–200", "272 / 252", "methodology under consideration"],
    ["BECCS (BioCCS)", "geological storage, permanent if storage is adequate",
     "100–200", "232 / 212", "permanent removal, methodology adopted 2026"],
    ["DACCS", "geological storage, permanent if storage is adequate", "100–300",
     "670 / 341", "permanent removal, methodology adopted 2026"],
], columns=["Method", "Storage and its permanence", "Cost, literature (US$/t)",
            "Supplier break-even 2025 / 2030 (US$/t)", "EU certification (CRCF)"])

DATA_SOURCES = pd.DataFrame([
    ["OTE, a.s. (Czech market operator; OTE, 2026)",
     "Day-ahead clearing prices and traded volumes", "hourly",
     "dependent variable (Layer A)"],
    ["ENTSO-E Transparency Platform (Hirth et al., 2018)",
     "CZ and DE day-ahead prices, actual load, generation per production type, "
     "day-ahead load, solar and wind forecasts (CZ, DE-LU)", "hourly / 15-min",
     "forecast residual load (regime and logit regressors), covariates, cross-check, "
     "market-coupling control, emission intensity"],
    ["ČEPS, a.s. (Czech transmission system operator; ČEPS, 2026)",
     "System load, generation mix by technology, wind and solar infeed, cross-border "
     "physical flows, imbalance prices", "hourly (imbalance 15-min)",
     "covariates, robustness"],
    ["ERA5 reanalysis (Hersbach et al., 2020)",
     "100 m wind components, 2 m temperature, surface solar radiation",
     "hourly, 0.25° grid", "weather robustness checks"],
], columns=["Source", "Datasets", "Native resolution", "Role in analysis"])


def tables_text():
    CDR_METHODS.to_csv(TAB / "tab02_carbon_removal_methods_compared_storage_cost.csv",
                       index=False)
    DATA_SOURCES.to_csv(TAB / "tab03_data_sources.csv", index=False)


def main():
    df = load_panel()
    fig_ipcc()
    fig_daccs_schema()
    two = table_two_hours(df)
    fig_merit_order(df, two)
    fig_genmix(df)
    fig_negative_hours(df)
    fig_projection(df)
    fig_eua_credits()
    fig_cdr_methods()
    fig_negative_blocks(df)
    fig_price_resload()
    fig_pipeline()
    fig_layer_schemas()
    tables_text()
    table_price_by_year()
    table_neighbours(df)
    table_grid_ef(df)
    table_heat_ef()
    print(f"figures -> {FIG.relative_to(C.ROOT)}, tables -> {TAB.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
