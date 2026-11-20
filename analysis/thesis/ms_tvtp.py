"""
ms_tvtp.py — Markov-switching regression with time-varying transition
probabilities (Diebold, Lee and Weinbach 1994; Filardo 1994).

Model, for regimes k = 0..K-1:

    y_t | S_t = k  ~  N( x_t' β_k , σ_k² )
    Pr(S_t = j | S_{t-1} = i, w_t) = exp(γ_ij' w̃_t) / Σ_l exp(γ_il' w̃_t),
    w̃_t = (1, w_t')',  γ_{i,K-1} ≡ 0  (last destination is the reference)

x_t holds the mean regressors (a constant first), w_t the TVTP covariates.
The parameterisation — reference category, [from, to] orientation — is the one
statsmodels uses for `MarkovRegression(..., exog_tvtp=...)`, which lets the
filter be validated against statsmodels on the *time-varying* case, not only
on the homogeneous special case (see `statsmodels_loglike`).

Missing observations of y are handled inside the filter: the update step is
skipped (density ≡ 1), so the chain keeps its hourly clock instead of being
spliced together by `dropna`.

The module is estimation machinery only; regimes.py drives it.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import norm

try:
    from numba import njit
except ImportError:      # pragma: no cover - numba is expected to be installed
    def njit(*a, **k):
        def deco(f):
            return f
        return deco(a[0]) if a and callable(a[0]) else deco


# ── parameter vector ──────────────────────────────────────────────────────────

@dataclass
class Spec:
    K: int          # regimes
    m: int          # mean regressors incl. constant
    q: int          # TVTP covariates excl. intercept

    @property
    def n_params(self) -> int:
        return self.K * self.m + self.K + self.K * (self.K - 1) * (self.q + 1)


def unpack(theta, spec: Spec):
    """theta → beta[K, m], sigma[K], gamma[K(from), K-1(to), q+1]."""
    K, m, q = spec.K, spec.m, spec.q
    i = 0
    beta = theta[i:i + K * m].reshape(K, m); i += K * m
    sigma = np.exp(theta[i:i + K]); i += K
    gamma = theta[i:].reshape(K, K - 1, q + 1)
    return beta, sigma, gamma


def pack(beta, sigma, gamma):
    return np.concatenate([np.ravel(beta), np.log(sigma), np.ravel(gamma)])


def param_names(spec: Spec, x_names, w_names):
    names = [f"beta[{k}].{x}" for k in range(spec.K) for x in x_names]
    names += [f"log_sigma[{k}]" for k in range(spec.K)]
    names += [f"gamma[{i}->{j}].{w}" for i in range(spec.K) for j in range(spec.K - 1)
              for w in ["const"] + list(w_names)]
    return names


# ── transition matrices and filter ───────────────────────────────────────────

def transition_matrices(gamma, W):
    """P[t, i, j] = Pr(S_t = j | S_{t-1} = i) for covariate rows W[t] (no intercept)."""
    K = gamma.shape[0]
    T = W.shape[0]
    Wt = np.column_stack([np.ones(T), W])                     # (T, q+1)
    logits = np.zeros((T, K, K))
    logits[:, :, :-1] = np.einsum("ijq,tq->tij", gamma, Wt)
    logits -= logsumexp(logits, axis=2, keepdims=True)
    return np.exp(logits)


@njit(cache=True)
def _filter_core(dens, P, xi0):
    """Scaled Hamilton filter; rows of `dens` equal to 1 are missing observations."""
    T, K = dens.shape
    xi_filt = np.empty((T, K))
    xi_pred = np.empty((T, K))
    loglik = 0.0
    xi = xi0.copy()
    for t in range(T):
        xp = xi @ P[t]
        num = xp * dens[t]
        s = num.sum()
        loglik += np.log(s)
        xi = num / s
        xi_pred[t] = xp
        xi_filt[t] = xi
    return loglik, xi_filt, xi_pred


def regime_means(beta, X):
    return X @ beta.T                                         # (T, K)


def densities(y, X, beta, sigma):
    mean = regime_means(beta, X)
    dens = np.exp(-0.5 * ((y[:, None] - mean) / sigma[None, :]) ** 2) \
        / (np.sqrt(2 * np.pi) * sigma[None, :])
    dens = np.maximum(dens, 1e-300)
    dens[~np.isfinite(y)] = 1.0                               # missing y: no update
    return dens


def hamilton_filter(theta, spec, y, X, W, xi0=None):
    beta, sigma, gamma = unpack(theta, spec)
    P = transition_matrices(gamma, W)
    dens = densities(y, X, beta, sigma)
    if xi0 is None:
        xi0 = np.full(spec.K, 1.0 / spec.K)
    ll, xf, xp = _filter_core(np.ascontiguousarray(dens), np.ascontiguousarray(P),
                              np.ascontiguousarray(xi0, dtype=np.float64))
    return ll, xf, xp, P


def kim_smoother(xi_filt, xi_pred, P):
    T, K = xi_filt.shape
    xs = np.empty((T, K))
    xs[-1] = xi_filt[-1]
    for t in range(T - 2, -1, -1):
        ratio = xs[t + 1] / np.maximum(xi_pred[t + 1], 1e-300)
        xs[t] = xi_filt[t] * (P[t + 1] @ ratio)
    return xs


# ── estimation ───────────────────────────────────────────────────────────────

def negloglik(theta, spec, y, X, W):
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        ll, *_ = hamilton_filter(theta, spec, y, X, W)
    return -ll if np.isfinite(ll) else 1e12


def fit(theta0, spec, y, X, W, maxiter=2000, fixed_zero=None):
    """L-BFGS-B. `fixed_zero` = boolean mask of parameters pinned at 0
    (used for the nested homogeneous model, γ_slopes = 0)."""
    free = np.ones(len(theta0), bool) if fixed_zero is None else ~fixed_zero
    base = np.where(free, theta0, 0.0)

    def f(th_free):
        th = base.copy(); th[free] = th_free
        return negloglik(th, spec, y, X, W)

    res = minimize(f, theta0[free], method="L-BFGS-B",
                   options={"maxiter": maxiter, "maxfun": 50000})
    theta = base.copy(); theta[free] = res.x
    return theta, -res.fun, res


def slope_mask(spec):
    """True at the TVTP slope coefficients (γ on covariates, not intercepts)."""
    mask = np.zeros(spec.n_params, bool)
    g0 = spec.K * spec.m + spec.K
    g = np.zeros((spec.K, spec.K - 1, spec.q + 1), bool)
    g[:, :, 1:] = True
    mask[g0:] = g.ravel()
    return mask


def relabel(theta, spec, order_by="const"):
    """Permute regimes so that regime 0 has the lowest intercept (surplus)
    and K-1 the highest (spike). γ is re-derived exactly from the permuted
    transition logits, which are linear in w̃."""
    beta, sigma, gamma = unpack(theta, spec)
    if order_by == "implied_mean":       # MS-AR(1): c_k / (1 − φ_k), φ in column 1
        key = beta[:, 0] / np.maximum(1.0 - beta[:, 1], 1e-6)
    else:
        key = beta[:, 0]
    order = np.argsort(key)
    beta, sigma = beta[order], sigma[order]
    # logits for destination j relative to the reference (old last) regime
    q1 = spec.q + 1
    full = np.zeros((spec.K, spec.K, q1))
    full[:, :-1, :] = gamma
    full = full[np.ix_(order, order, np.arange(q1))]
    full = full - full[:, [-1], :]                            # new reference = new last
    return pack(beta, sigma, full[:, :-1, :]), order


def numerical_hessian(f, theta, rel_step=1e-4):
    """Central-difference Hessian of a scalar function."""
    n = len(theta)
    h = rel_step * np.maximum(np.abs(theta), 1.0)
    H = np.empty((n, n))
    f0 = f(theta)
    for i in range(n):
        ei = np.zeros(n); ei[i] = h[i]
        H[i, i] = (f(theta + ei) - 2 * f0 + f(theta - ei)) / h[i] ** 2
        for j in range(i):
            ej = np.zeros(n); ej[j] = h[j]
            H[i, j] = H[j, i] = (f(theta + ei + ej) - f(theta + ei - ej)
                                 - f(theta - ei + ej) + f(theta - ei - ej)) / (4 * h[i] * h[j])
    return H


def invert_information(H):
    """(H⁻¹, used_pinv, condition number). pinv is a fallback only; the
    caller reports when it was needed."""
    cond = float(np.linalg.cond(H))
    try:
        return np.linalg.inv(H), False, cond
    except np.linalg.LinAlgError:
        return np.linalg.pinv(H), True, cond


def covariance(theta, spec, y, X, W):
    """Inverse of the numerical Hessian of −loglik (observed information)."""
    H = numerical_hessian(lambda th: negloglik(th, spec, y, X, W), theta)
    cov, _, _ = invert_information(H)
    return cov, H


def score_obs(theta, spec, y, X, W, rel_step=1e-5):
    """Per-observation scores ∂ log f(y_t | F_{t-1})/∂θ, central differences
    (T × n). Missing y contribute zero."""
    n = len(theta)
    h = rel_step * np.maximum(np.abs(theta), 1.0)
    G = np.empty((len(y), n))
    for i in range(n):
        e = np.zeros(n); e[i] = h[i]
        G[:, i] = (loglik_obs(theta + e, spec, y, X, W)
                   - loglik_obs(theta - e, spec, y, X, W)) / (2 * h[i])
    return G


def sandwich_covariance(theta, spec, y, X, W, H, lags):
    """Quasi-ML (Huber–White) covariance H⁻¹ J H⁻¹ with a Newey–West
    (Bartlett) estimate of the long-run score covariance J. Robust to the
    within-regime serial correlation and non-normality that the
    observed-information SEs assume away."""
    G = score_obs(theta, spec, y, X, W)
    J = G.T @ G
    for l in range(1, lags + 1):
        w = 1.0 - l / (lags + 1.0)
        Gl = G[l:].T @ G[:-l]
        J += w * (Gl + Gl.T)
    Hinv, _, _ = invert_information(H)
    return Hinv @ J @ Hinv


# ── derived quantities ───────────────────────────────────────────────────────

def entry_marginal_effects(theta, cov, spec, w_point, dest=0, step=1e-5):
    """∂Pr(S_t=dest | S_{t-1}=i)/∂w at w_point for every origin i and covariate,
    with delta-method standard errors (numerical gradient in θ)."""
    def me(th):
        _, _, gamma = unpack(th, spec)
        out = np.empty((spec.K, spec.q))
        for c in range(spec.q):
            wp = np.array(w_point, float); wm = wp.copy()
            wp[c] += step; wm[c] -= step
            Pp = transition_matrices(gamma, wp[None, :])[0]
            Pm = transition_matrices(gamma, wm[None, :])[0]
            out[:, c] = (Pp[:, dest] - Pm[:, dest]) / (2 * step)
        return out.ravel()

    val = me(theta)
    G = np.empty((len(val), len(theta)))
    for k in range(len(theta)):
        e = np.zeros(len(theta)); e[k] = 1e-5 * max(abs(theta[k]), 1.0)
        G[:, k] = (me(theta + e) - me(theta - e)) / (2 * e[k])
    se = np.sqrt(np.maximum(np.einsum("ik,kl,il->i", G, cov, G), 0.0))
    return val.reshape(spec.K, spec.q), se.reshape(spec.K, spec.q)


def prob_below(xi, beta, sigma, X, threshold):
    """Pr(y_t < threshold) = Σ_k ξ_tk Φ((threshold − x_t'β_k)/σ_k)."""
    mean = regime_means(beta, X)
    thr = np.broadcast_to(np.asarray(threshold, float), (len(X),))
    return (xi * norm.cdf((thr[:, None] - mean) / sigma[None, :])).sum(axis=1)


def day_ahead_predictions(theta, spec, y, X, W, day_id, xi0=None):
    """Regime probabilities for every hour of day D formed from information
    available at the day-ahead auction: the filtered state at the last hour of
    D−1 is propagated through the hours of D with the TVTP matrices of the
    (pre-determined) covariates. No price of day D enters its own forecast."""
    ll, xf, xp, P = hamilton_filter(theta, spec, y, X, W, xi0)
    T, K = xf.shape
    out = np.empty((T, K))
    xi = np.full(K, 1.0 / K) if xi0 is None else np.asarray(xi0, float)
    day_id = np.asarray(day_id)
    t = 0
    while t < T:
        d = day_id[t]
        while t < T and day_id[t] == d:
            xi = xi @ P[t]
            out[t] = xi
            t += 1
        xi = xf[t - 1]                       # end of day D: condition on its prices
    return out


def stationary_dist(P):
    K = P.shape[0]
    A = np.vstack([P.T - np.eye(K), np.ones(K)])
    b = np.zeros(K + 1); b[-1] = 1.0
    return np.linalg.lstsq(A, b, rcond=None)[0]


def rcm(xi_smooth):
    """Regime classification measure, product form: 100 · K^K · mean_t Π_k p_kt.

    K^K is the normalisation that maps uniform probabilities (1/K each) to 100
    and certainty to 0; for K = 2 it reduces to Ang and Bekaert's (2002)
    400 · mean p(1−p). (K² would cap the uniform case at 100·K²/K^K.)"""
    K = xi_smooth.shape[1]
    return float(100.0 * K ** K * np.mean(np.prod(xi_smooth, axis=1)))


def rcm_quadratic(xi_smooth):
    """Quadratic RCM (Baele 2005): 100·(1 − K/(K−1)·mean_t Σ_k (p_kt − 1/K)²).

    0 = certainty, 100 = uniform. Unlike the product form it does not drop
    to 0 whenever one regime has zero probability, so for K = 3 it still
    registers a 50/50 split between the other two."""
    K = xi_smooth.shape[1]
    dev = ((xi_smooth - 1.0 / K) ** 2).sum(axis=1)
    return float(100.0 * (1.0 - K / (K - 1.0) * dev.mean()))


# ── statsmodels cross-check on the TVTP case ─────────────────────────────────

def pit_residuals(theta, spec, y, X, W):
    """Generalised (probability-integral-transform) residuals
    z_t = Φ⁻¹(Σ_k ξ_{t|t-1,k} Φ((y_t − μ_tk)/σ_k)); i.i.d. N(0,1) under a
    correctly specified model, so their ACF is the residual diagnostic."""
    beta, sigma, _ = unpack(theta, spec)
    _, _, xp, _ = hamilton_filter(theta, spec, y, X, W)
    mu = regime_means(beta, X)
    with np.errstate(invalid="ignore"):
        u = (xp * norm.cdf((y[:, None] - mu) / sigma[None, :])).sum(axis=1)
    z = norm.ppf(np.clip(u, 1e-12, 1 - 1e-12))
    z[~np.isfinite(y)] = np.nan
    return z


def loglik_obs(theta, spec, y, X, W):
    """Per-observation log-likelihood contributions log f(y_t | F_{t-1})."""
    beta, sigma, _ = unpack(theta, spec)
    _, _, xp, _ = hamilton_filter(theta, spec, y, X, W)
    return np.log((xp * densities(y, X, beta, sigma)).sum(axis=1))


def statsmodels_loglike(theta, spec, y, X, W):
    """Per-observation log-likelihood of the same parameters evaluated by
    statsmodels' MarkovRegression with exog_tvtp and a uniform known
    initialisation. The two filters treat the very first observation
    differently (initialisation convention); from t = 1 on the contributions
    are identical, so the cross-check compares Σ_{t≥1}."""
    import statsmodels.api as sm

    beta, sigma, gamma = unpack(theta, spec)
    ok = np.isfinite(y)
    if not ok.all():
        raise ValueError("statsmodels cross-check requires complete y")
    exog = X[:, 1:] if spec.m > 1 else None
    Wt = np.column_stack([np.ones(len(W)), W])
    mod = sm.tsa.MarkovRegression(y, k_regimes=spec.K, trend="c", exog=exog,
                                  switching_variance=True, exog_tvtp=Wt)
    mod.initialize_known(np.full(spec.K, 1.0 / spec.K))
    names = mod.param_names
    val = {}
    for i in range(spec.K):                     # from
        for j in range(spec.K - 1):             # to
            for c in range(spec.q + 1):
                val[f"p[{i}->{j}].tvtp{c}"] = gamma[i, j, c]
    for k in range(spec.K):
        val[f"const[{k}]"] = beta[k, 0]
        for c in range(1, spec.m):
            val[f"x{c}[{k}]"] = beta[k, c]
        val[f"sigma2[{k}]"] = sigma[k] ** 2
    params = np.array([val[n] for n in names])
    return np.asarray(mod.filter(params).llf_obs)
