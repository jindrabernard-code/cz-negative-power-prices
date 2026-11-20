"""
Simulate hourly price paths from the estimated model under the solar
scenarios and count negative-price hours per year.

  * calendar and seasonal price component of the base year 2024;
  * each path gets its own parameter draw θ_i ~ N(θ̂, V̂) and one weather year
    (2023-2025 day-ahead forecasts laid onto the 2024 calendar, CZ solar
    rescaled to the 2024 energy);
  * scenarios scale the Czech solar forecast (config.SOLAR_SCENARIOS); the
    joint variant also scales DE-LU solar (config.DE_SOLAR_SCENARIOS);
  * path i uses the same θ_i, weather year and random numbers in every
    scenario.

Output: output/thesis/work/sim_scenario_summary.csv
        output/thesis/work/sim_scenario_summary_joint_de.csv
"""
import numpy as np
import pandas as pd

import config as C
import ms_tvtp as M
from prepare import load_prepared

BASE_YEAR = 2024


def load_model(fname="tvtp_params.npz"):
    f = np.load(C.MOD_DIR / fname, allow_pickle=False)
    mod = {k: f[k] for k in f.files}
    mod["spec"] = M.Spec(K=int(f["K"]), m=int(f["m"]), q=int(f["q"]))
    for k in ("z_cols", "x_names", "w_names"):
        mod[k] = [str(c) for c in f[k]]
    mod["z_source"] = str(f["z_source"])
    return mod


def scenario_z(base, factor, mod, de_factor=1.0):
    """Standardised conditioning variables under the solar factors."""
    if mod["z_source"].startswith("day-ahead"):
        raw = {"z_cz": base["cz_load_fc_mw"] - factor * base["cz_solar_fc_mw"]
                       - base["cz_wind_fc_mw"],
               "z_de": base["resload_fc_de_mw"]
                       - (de_factor - 1.0) * base["de_solar_fc_mw"]}
    else:
        rl = (base["ceps_load_zatížení_mw"] - factor * base["ceps_res_fve_mw"]
              - base["ceps_res_vte_mw"])
        raw = {"z_cz": rl.shift(1)}
    Z = pd.DataFrame(raw, index=base.index).ffill().bfill()
    for c, m, s in zip(mod["z_cols"], mod["z_mean"], mod["z_std"]):
        Z[c] = (Z[c] - m) / s
    return Z[mod["z_cols"]]


def draw_thetas(mod, n, rng):
    theta, cov = mod["theta"], mod.get("cov")
    if not C.SIM_PARAM_UNCERTAINTY or cov is None or not np.all(np.isfinite(cov)):
        return np.repeat(theta[None, :], n, axis=0)
    cov = 0.5 * (cov + cov.T)
    w, V = np.linalg.eigh(cov)
    L = V * np.sqrt(np.clip(w, 0.0, None))
    return theta[None, :] + rng.standard_normal((n, len(theta))) @ L.T


@M.njit(cache=True)
def _draw_chain(cumP, u, s0):
    """Inverse-CDF draw of one regime path from cumulative transition rows."""
    T, K = cumP.shape[0], cumP.shape[1]
    reg = np.empty(T, dtype=np.int8)
    s = s0
    for t in range(T):
        k = 0
        for j in range(K):
            if u[t] > cumP[t, s, j]:
                k += 1
        s = min(k, K - 1)
        reg[t] = s
    return reg


def simulate_paths(X_by_path, W_by_path, thetas, spec, u, eps):
    n, T = u.shape
    K = spec.K
    regimes = np.empty((n, T), dtype=np.int8)
    prices = np.empty((n, T))
    for i in range(n):
        beta, sigma, gamma = M.unpack(thetas[i], spec)
        cumP = M.transition_matrices(gamma, W_by_path[i]).cumsum(axis=2)
        reg = _draw_chain(np.ascontiguousarray(cumP), u[i], i % K)
        mean = M.regime_means(beta, X_by_path[i])
        regimes[i] = reg
        prices[i] = mean[np.arange(T), reg] + sigma[reg] * eps[i]
    return regimes, prices


def conditioning_cols(mod):
    if mod["z_source"].startswith("day-ahead"):
        return ["cz_load_fc_mw", "cz_solar_fc_mw", "cz_wind_fc_mw",
                "resload_fc_de_mw", "de_solar_fc_mw"], "cz_solar_fc_mw"
    return ["ceps_load_zatížení_mw", "ceps_res_fve_mw", "ceps_res_vte_mw"], "ceps_res_fve_mw"


def base_frame(df, mod, year):
    need = ["price_seasonal"] + conditioning_cols(mod)[0]
    base = df[df["year"] == year].copy()
    base[need] = base[need].ffill().bfill()
    return base


def weather_on_base(df, mod, base, year):
    """Conditioning columns of `year` on the base-year calendar: whole days,
    shifted so weekdays match, solar rescaled to the base year's energy."""
    cols, solar = conditioning_cols(mod)
    if year == base.index[0].year:
        return base[cols]
    src = df[df["year"] == year][cols].ffill().bfill()
    nd_src, nd_base = len(src) // 24, len(base) // 24
    a = src.values[: nd_src * 24].reshape(nd_src, 24, len(cols))
    k = (base.index[0].dayofweek - src.index[0].dayofweek) % 7
    days = (k + np.arange(nd_base)) % nd_src
    out = pd.DataFrame(a[days].reshape(nd_base * 24, len(cols)),
                       index=base.index[: nd_base * 24], columns=cols)
    out = out.reindex(base.index).ffill()
    for c in (solar, "de_solar_fc_mw"):
        if c in out.columns:
            scale = base[c].sum() / max(out[c].sum(), 1e-9)
            if c == "de_solar_fc_mw" and "resload_fc_de_mw" in out.columns:
                out["resload_fc_de_mw"] -= (scale - 1.0) * out[c]
            out[c] *= scale
    return out


def path_inputs(weather_by_year, years_of_path, factor, mod, de_factor=1.0):
    cache = {}
    for y, wf in weather_by_year.items():
        Z = scenario_z(wf, factor, mod, de_factor)
        X = np.column_stack([np.ones(len(Z))] + [Z[c].values for c in mod["x_names"]])
        cache[y] = (X, Z[mod["w_names"]].values)
    return [cache[y][0] for y in years_of_path], [cache[y][1] for y in years_of_path]


def random_inputs(n, T, mod, years):
    """Common random numbers shared by every scenario."""
    rng = np.random.default_rng(C.SIM_SEED)
    thetas = draw_thetas(mod, n, rng)
    years_of_path = rng.permutation(np.resize(np.array(years), n))
    return thetas, years_of_path, rng.random((n, T)), rng.standard_normal((n, T))


def run_scenarios(df, mod, label, de_factors=None):
    base = base_frame(df, mod, BASE_YEAR)
    seasonal = base["price_seasonal"].values
    T = len(base)
    years = [y for y in C.SIM_WEATHER_YEARS if (df["year"] == y).any()]
    weather = {y: weather_on_base(df, mod, base, y) for y in years}
    thetas, years_of_path, u, eps = random_inputs(C.N_SIM_PATHS, T, mod, years)
    rows = []
    for name, factor in C.SOLAR_SCENARIOS.items():
        de_factor = 1.0 if de_factors is None else de_factors[name]
        X_by, W_by = path_inputs(weather, years_of_path, factor, mod, de_factor)
        _, p_des = simulate_paths(X_by, W_by, thetas, mod["spec"], u, eps)
        prices = (p_des + seasonal[None, :]).astype(np.float32)
        neg = (prices < 0).sum(axis=1).astype(float)
        rows.append({"scenario": name, "solar_factor": factor, "de_solar_factor": de_factor,
                     "expected_negative_hours_per_year": (prices < 0).mean() * T,
                     "negative_hours_p05": float(np.quantile(neg, 0.05)),
                     "negative_hours_p95": float(np.quantile(neg, 0.95)),
                     "mean_price": float(prices.mean())})
        print(f"  [{label}] {name:20s} {rows[-1]['expected_negative_hours_per_year']:6.0f} h "
              f"[{rows[-1]['negative_hours_p05']:.0f}, {rows[-1]['negative_hours_p95']:.0f}]")
    suffix = "" if label == "headline" else f"_{label}"
    tab = pd.DataFrame(rows).set_index("scenario").round(4)
    tab.to_csv(C.WORK_DIR / f"sim_scenario_summary{suffix}.csv")
    return tab


def main():
    df = load_prepared()
    run_scenarios(df, load_model(), "headline")
    run_scenarios(df, load_model(), "joint_de", de_factors=C.DE_SOLAR_SCENARIOS)


if __name__ == "__main__":
    main()
