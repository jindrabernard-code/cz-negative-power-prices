"""
Estimate the three-regime Markov-switching model of the deseasonalised Czech
day-ahead price with time-varying transition probabilities driven by the
standardised day-ahead forecast residual load of CZ and DE-LU.

Estimation window: post-crisis hours before HOLDOUT_START. Start values come
from the homogeneous model (statsmodels), the TVTP slopes from a small
deterministic multi-start. Standard errors: QML sandwich with HAC scores.

Output: output/thesis/work/tvtp_params.npz (used by simulate.py)
"""
import inspect
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

import config as C
import ms_tvtp as M
from prepare import load_prepared

K = C.MS_N_REGIMES
TVTP_SLOPE_STARTS = (0.0, -0.5, 0.5, -1.0)


def conditioning_frame(d: pd.DataFrame, train: pd.Series):
    """Standardised conditioning variables z_cz, z_de (training moments)."""
    have_fc = {"resload_fc_cz_mw", "resload_fc_de_mw"} <= set(d.columns) \
        and d.loc[train, "resload_fc_cz_mw"].notna().mean() > 0.95
    if have_fc:
        raw = {"z_cz": d["resload_fc_cz_mw"], "z_de": d["resload_fc_de_mw"]}
        source = "day-ahead forecast residual load (CZ, DE-LU), contemporaneous"
    else:
        raw = {"z_cz": d["residual_load_mw"].shift(1)}
        source = "realised CZ residual load, lagged one hour (forecasts unavailable)"
    Z = pd.DataFrame(raw, index=d.index).ffill().bfill()
    mom = {c: (Z.loc[train, c].mean(), Z.loc[train, c].std()) for c in Z}
    for c, (m, s) in mom.items():
        Z[c] = (Z[c] - m) / s
    return Z, mom, source


def design(Z: pd.DataFrame, names):
    names = [n for n in names if n in Z.columns]
    X = np.column_stack([np.ones(len(Z))] + [Z[n].values for n in names])
    return X, names


def _fit_kwargs():
    params = inspect.signature(sm.tsa.MarkovRegression.fit).parameters
    return {"rng": C.MS_SEED} if "rng" in params else {}


def homogeneous_start(y, X, k):
    """statsmodels homogeneous MarkovRegression -> start values."""
    ok = np.isfinite(y)
    exog = X[ok, 1:] if X.shape[1] > 1 else None
    mod = sm.tsa.MarkovRegression(y[ok], k_regimes=k, trend="c", exog=exog,
                                  switching_variance=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = mod.fit(search_reps=10, disp=False, **_fit_kwargs())
    pm = dict(zip(mod.param_names, res.params))
    beta = np.array([[pm[f"const[{j}]"]] + [pm[f"x{c}[{j}]"] for c in range(1, X.shape[1])]
                     for j in range(k)])
    sigma = np.sqrt([pm[f"sigma2[{j}]"] for j in range(k)])
    P = res.regime_transition[:, :, 0].T                   # [from, to]
    return beta, sigma, P, float(res.llf)


def fit_model(y, X, W, k, beta0, sigma0, P0):
    spec = M.Spec(K=k, m=X.shape[1], q=W.shape[1])
    g0 = np.log(np.maximum(P0[:, :-1], 1e-4) / np.maximum(P0[:, [-1]], 1e-4))
    best = None
    for s0 in TVTP_SLOPE_STARTS:
        gamma = np.zeros((k, k - 1, spec.q + 1))
        gamma[:, :, 0] = g0
        gamma[:, :, 1:] = s0
        th, ll, _ = M.fit(M.pack(beta0, sigma0, gamma), spec, y, X, W,
                          maxiter=C.MS_MAX_ITER)
        if best is None or ll > best[1]:
            best = (th, ll)
    th, _ = M.relabel(best[0], spec, order_by="const")
    return spec, th, M.hamilton_filter(th, spec, y, X, W)[0]


def main():
    np.random.seed(C.MS_SEED)
    df = load_prepared()
    a, b = C.SUBPERIODS[C.ESTIMATION_PERIOD]
    d = df.loc[a:b].copy()
    train = pd.Series(d.index < pd.Timestamp(C.HOLDOUT_START), index=d.index)

    Z, z_moments, z_source = conditioning_frame(d, train)
    X_all, x_names = design(Z, C.MS_MEAN_REGRESSORS)
    w_names = [c for c in C.MS_TVTP_COVARIATES if c in Z.columns]
    W_all = Z[w_names].values
    y_all = d["price_deseason"].values

    tr = train.values
    y, X, W = y_all[tr], X_all[tr], W_all[tr]
    print(f"estimation {d.index[tr][0]} - {d.index[tr][-1]} (n={tr.sum():,}); {z_source}")

    beta0, sig0, P0, _ = homogeneous_start(y, X, K)
    spec, theta, ll = fit_model(y, X, W, K, beta0, sig0, P0)
    _, H = M.covariance(theta, spec, y, X, W)
    cov = M.sandwich_covariance(theta, spec, y, X, W, H, C.SANDWICH_HAC_LAGS)
    beta, sigma, _ = M.unpack(theta, spec)
    print(f"log-likelihood {ll:.1f}")
    for k in range(K):
        print(f"  regime {k}: mean {beta[k, 0]:8.2f}  sd {sigma[k]:7.2f}")

    np.savez(C.MOD_DIR / "tvtp_params.npz", theta=theta, K=K, m=spec.m, q=spec.q, cov=cov,
             x_names=np.array(x_names, dtype=str), w_names=np.array(w_names),
             z_mean=np.array([z_moments[c][0] for c in Z.columns]),
             z_std=np.array([z_moments[c][1] for c in Z.columns]),
             z_train_min=Z.loc[train].min().values,
             z_train_max=Z.loc[train].max().values,
             z_cols=np.array(list(Z.columns)), z_source=z_source, loglik=ll)


if __name__ == "__main__":
    main()
