"""Descriptive statistics, tests and figures of the Czech day-ahead price.

Writes CSV tables to output/tables and PNG figures to output/figures.
Hour-of-day axes are local time. Tests marked "training window" use the
post-crisis hours before HOLDOUT_START.
"""
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.graphics.gofplots import qqplot
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.tsa.stattools import acf, adfuller, kpss

from prepare import HOLDOUT_START, OUT_DIR, PRICE, SUBPERIODS, TRAIN_PERIOD, load_prepared

TAB_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"
NEG = "price_lt0"


def training_window(df):
    a, b = SUBPERIODS[TRAIN_PERIOD]
    d = df.loc[a:b]
    return d[d.index < pd.Timestamp(HOLDOUT_START)]


def save_fig(fig, name):
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    plt.close(fig)


# ── tables ───────────────────────────────────────────────────────────────────

def table_by_year(df):
    g = df.groupby("year")
    tab = pd.DataFrame({
        "mean": g[PRICE].mean(),
        "std": g[PRICE].std(),
        "min": g[PRICE].min(),
        "p25": g[PRICE].quantile(0.25),
        "median": g[PRICE].median(),
        "p75": g[PRICE].quantile(0.75),
        "max": g[PRICE].max(),
        "neg_hours": g[NEG].sum(),
        "neg_share_pct": 100 * g[NEG].mean(),
        "lt20_hours": g["price_lt20"].sum(),
        "max_solar_mw": g["solar_mw"].max(),
        "mean_resload_mw": g["residual_load_mw"].mean(),
    }).round(2)
    # the last UTC hour falls into the next local year
    tab = tab[g.size() > 24]
    tab.to_csv(TAB_DIR / "price_by_year.csv")
    return tab


def table_neg_month_hour(df):
    pivot = df.pivot_table(index="month", columns="hour", values=NEG, aggfunc="sum")
    pivot.to_csv(TAB_DIR / "neg_by_month_hour.csv")
    return pivot


def table_block_lengths(df):
    """Lengths of runs of consecutive negative-price hours."""
    s = df[NEG].fillna(0).astype(int)
    run_id = (s != s.shift()).cumsum()
    runs = s.groupby(run_id).agg(["first", "size"])
    runs = runs.loc[runs["first"] == 1, "size"]
    tab = runs.value_counts().sort_index().rename("count").rename_axis("block_length").to_frame()
    tab["share_pct"] = (100 * tab["count"] / tab["count"].sum()).round(1)
    tab.to_csv(TAB_DIR / "neg_block_lengths.csv")
    return tab


def table_correlations(df):
    rows = {"corr_cz_de_price": df[[PRICE, "entsoe_de_da_eur_mwh"]].corr().iloc[0, 1]}
    for sp in list(SUBPERIODS) + [None]:
        d = df if sp is None else df[df["subperiod"] == sp]
        rows[f"corr_price_resload_{sp or 'full'}"] = d[[PRICE, "residual_load_mw"]].corr().iloc[0, 1]
    tab = pd.Series(rows, name="value").round(4).to_frame()
    tab.to_csv(TAB_DIR / "correlations.csv")
    return tab


def table_moments(df):
    rows = []
    for var in (PRICE, "price_deseason", "residual_load_mw"):
        for sp in list(SUBPERIODS) + ["full"]:
            x = (df if sp == "full" else df[df["subperiod"] == sp])[var].dropna()
            jb = stats.jarque_bera(x)
            rows.append({"variable": var, "subperiod": sp, "n": len(x),
                         "mean": x.mean(), "median": x.median(), "sd": x.std(),
                         "iqr": x.quantile(.75) - x.quantile(.25),
                         "skewness": stats.skew(x), "excess_kurtosis": stats.kurtosis(x),
                         "jarque_bera": jb.statistic, "jb_p": jb.pvalue})
    tab = pd.DataFrame(rows).set_index(["variable", "subperiod"]).round(3)
    tab.to_csv(TAB_DIR / "moments.csv")
    return tab


def table_stationarity(df):
    """ADF (H0: unit root) and KPSS (H0: level stationarity), training window."""
    d = training_window(df)
    rows = []
    for var in (PRICE, "price_deseason", "residual_load_mw"):
        x = d[var].interpolate().dropna().values
        adf = adfuller(x, maxlag=168, autolag="AIC")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # KPSS p-values are bounded by its lookup table
            kp = kpss(x, regression="c", nlags=168)
        rows.append({"variable": var, "adf_stat": adf[0], "adf_p": adf[1], "adf_lags": adf[2],
                     "kpss_stat": kp[0], "kpss_p_bounded": kp[1]})
    tab = pd.DataFrame(rows).set_index("variable").round(4)
    tab.to_csv(TAB_DIR / "stationarity.csv")
    return tab


def table_dependence(df):
    """Autocorrelation, Ljung-Box and ARCH-LM tests, training window."""
    d = training_window(df)
    rows = []
    for var in (PRICE, "price_deseason"):
        x = d[var].interpolate().dropna()
        r = acf(x, nlags=168)
        lb = acorr_ljungbox(x, lags=[24, 168])
        arch = het_arch(x - x.mean(), nlags=24)
        rows.append({"variable": var, "acf_lag1": r[1], "acf_lag24": r[24], "acf_lag168": r[168],
                     "ljung_box_Q24": lb["lb_stat"].iloc[0], "lb24_p": lb["lb_pvalue"].iloc[0],
                     "ljung_box_Q168": lb["lb_stat"].iloc[1], "lb168_p": lb["lb_pvalue"].iloc[1],
                     "arch_lm24": arch[0], "arch_lm24_p": arch[1]})
    tab = pd.DataFrame(rows).set_index("variable").round(4)
    tab.to_csv(TAB_DIR / "dependence.csv")
    return tab


def table_corr_matrix(df):
    """Correlations of candidate regressors, training window."""
    cols = {PRICE: "price_cz", "entsoe_de_da_eur_mwh": "price_de",
            "residual_load_mw": "resload_cz", "ceps_load_zatížení_mw": "load_cz",
            "solar_mw": "solar_cz", "ceps_res_vte_mw": "wind_cz", "era5_t2m": "temp",
            "resload_fc_cz_mw": "resload_fc_cz", "resload_fc_de_mw": "resload_fc_de"}
    cm = training_window(df)[list(cols)].rename(columns=cols).corr()
    cm.round(3).to_csv(TAB_DIR / "corr_matrix.csv")
    return cm


# ── figures ──────────────────────────────────────────────────────────────────

def fig_price_timeseries(df):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(df.index, df[PRICE], lw=0.25, color="steelblue")
    neg = df[df[NEG] == 1]
    ax.scatter(neg.index, neg[PRICE], s=2, color="crimson", zorder=3,
               label=f"negative hours (n={len(neg)})")
    for a, _ in SUBPERIODS.values():
        ax.axvline(pd.Timestamp(a), color="grey", ls="--", lw=0.7)
    ax.set_ylabel("EUR/MWh")
    ax.set_title("Czech day-ahead price")
    ax.legend(loc="upper right")
    save_fig(fig, "price_timeseries.png")


def fig_neg_heatmap(pivot):
    fig, ax = plt.subplots(figsize=(10, 5))
    im = ax.imshow(pivot.values, aspect="auto", cmap="Reds")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_xlabel("hour (local time)")
    ax.set_ylabel("month")
    ax.set_title("Negative-price hours by month and hour")
    fig.colorbar(im, label="hours")
    save_fig(fig, "neg_heatmap.png")


def fig_duration_curves(df):
    fig, ax = plt.subplots(figsize=(8, 5))
    for y, g in df.groupby("year"):
        p = g[PRICE].dropna().sort_values(ascending=False).values
        if len(p) > 24:
            ax.plot(np.linspace(0, 100, len(p)), p, lw=1.2, label=str(y))
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xlabel("% of hours")
    ax.set_ylabel("EUR/MWh")
    ax.set_ylim(-150, 500)
    ax.set_title("Price-duration curves by year")
    ax.legend()
    save_fig(fig, "duration_curves.png")


def fig_solar_vs_neg(tab_year):
    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.bar(tab_year.index, tab_year["neg_hours"], color="crimson", alpha=0.7)
    ax1.set_ylabel("negative hours per year", color="crimson")
    ax2 = ax1.twinx()
    ax2.plot(tab_year.index, tab_year["max_solar_mw"], "o-", color="darkorange")
    ax2.set_ylabel("max hourly solar infeed [MW]", color="darkorange")
    ax1.set_title("Negative-price hours and peak solar infeed")
    save_fig(fig, "solar_vs_neg.png")


def fig_price_vs_resload(df):
    d = df[[PRICE, "residual_load_mw", "subperiod"]].dropna()
    fig, ax = plt.subplots(figsize=(8, 5))
    for sp, g in d.groupby("subperiod", observed=True):
        m = g.groupby(pd.qcut(g["residual_load_mw"], 30), observed=True).mean(numeric_only=True)
        ax.plot(m["residual_load_mw"], m[PRICE], "o-", ms=3, label=sp)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_xlabel("residual load [MW]")
    ax.set_ylabel("mean price [EUR/MWh]")
    ax.set_title("Price vs residual load (30 quantile bins)")
    ax.legend()
    save_fig(fig, "price_vs_resload.png")


def fig_diurnal(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True)
    for y, g in df.groupby("year"):
        if len(g) > 24:
            axes[0].plot(g.groupby("hour")[PRICE].mean(), label=str(y))
            axes[1].plot(g.groupby("hour")["solar_mw"].mean(), label=str(y))
    axes[0].set(title="mean diurnal price", ylabel="EUR/MWh")
    axes[1].set(title="mean diurnal solar infeed", ylabel="MW")
    for ax in axes:
        ax.set_xlabel("hour (local time)")
        ax.legend(fontsize=7)
    save_fig(fig, "diurnal_profiles.png")


def fig_distribution(df):
    d = training_window(df)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for row, var in enumerate((PRICE, "price_deseason")):
        x = d[var].dropna()
        axes[row, 0].hist(x, bins=120, density=True, color="steelblue", alpha=0.8)
        xs = np.linspace(x.min(), x.max(), 300)
        axes[row, 0].plot(xs, stats.norm.pdf(xs, x.mean(), x.std()), "k--", lw=1,
                          label="normal, same mean and sd")
        axes[row, 0].set_title(var)
        axes[row, 0].legend(fontsize=8)
        qqplot(x, line="s", ax=axes[row, 1], markersize=1.5)
        axes[row, 1].set_title(f"{var}, normal Q-Q")
    fig.suptitle("Price distribution, training window")
    save_fig(fig, "distribution.png")


def fig_acf(df):
    d = training_window(df)
    fig, ax = plt.subplots(figsize=(10, 4))
    for var in (PRICE, "price_deseason"):
        ax.plot(range(169), acf(d[var].interpolate().dropna(), nlags=168), label=var)
    for lag in range(24, 169, 24):
        ax.axvline(lag, color="grey", lw=0.5, ls=":")
    ax.set(xlabel="lag [hours]", ylabel="autocorrelation", title="ACF, training window")
    ax.legend()
    save_fig(fig, "acf.png")


def fig_rolling(df):
    r = df[PRICE].rolling(24 * 30, min_periods=24 * 20)
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df.index, r.mean(), label="30-day rolling mean")
    ax.plot(df.index, r.std(), label="30-day rolling sd")
    for a, _ in SUBPERIODS.values():
        ax.axvline(pd.Timestamp(a), color="grey", ls="--", lw=0.7)
    ax.axvline(pd.Timestamp(HOLDOUT_START), color="crimson", ls=":", lw=1, label="holdout start")
    ax.set_ylabel("EUR/MWh")
    ax.set_title("Rolling level and volatility of the day-ahead price")
    ax.legend()
    save_fig(fig, "rolling.png")


def main():
    TAB_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = load_prepared()

    tab_year = table_by_year(df)
    print(tab_year)
    pivot = table_neg_month_hour(df)
    table_block_lengths(df)
    table_correlations(df)
    table_moments(df)
    table_stationarity(df)
    table_dependence(df)
    table_corr_matrix(df)

    fig_price_timeseries(df)
    fig_neg_heatmap(pivot)
    fig_duration_curves(df)
    fig_solar_vs_neg(tab_year)
    fig_price_vs_resload(df)
    fig_diurnal(df)
    fig_distribution(df)
    fig_acf(df)
    fig_rolling(df)
    print(f"tables -> {TAB_DIR}\nfigures -> {FIG_DIR}")


if __name__ == "__main__":
    main()
