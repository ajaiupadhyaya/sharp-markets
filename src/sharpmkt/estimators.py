"""Small estimators with cluster-robust (sandwich) covariance, written out so the plan can say
exactly what is computed.

- `ols`: least squares.
- `logit`: binary logistic regression by Newton's method.
- `pool`: a logarithmic opinion pool over the three outcomes of a match,
      P(o) proportional to exp(sum_k beta_k * log p_k(o)),
  fitted by maximum likelihood; beta_k is the weight on source k's log probability. With two
  sources (Betfair, venue), beta_venue = 0 means Betfair encompasses the venue.

Each returns (params, covariance). Covariance is the CR1 sandwich over clusters:
    V = c * H^-1 (sum_g s_g s_g') H^-1,   c = G / (G - 1)
where s_g is the summed score of cluster g and H the (negative) Hessian.
"""

import numpy as np
import polars as pl


def _cluster_meat(scores: np.ndarray, cl: np.ndarray) -> tuple[np.ndarray, int]:
    k = scores.shape[1]
    df = pl.DataFrame({"c": cl, **{f"s{j}": scores[:, j] for j in range(k)}})
    s = df.group_by("c").agg(pl.all().sum()).drop("c").to_numpy()
    return s.T @ s, s.shape[0]


def _sandwich(bread: np.ndarray, scores: np.ndarray, cl: np.ndarray) -> np.ndarray:
    meat, g = _cluster_meat(scores, cl)
    inv = np.linalg.inv(bread)
    return g / (g - 1) * inv @ meat @ inv


def ols(x: np.ndarray, y: np.ndarray, cl: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    xtx = x.T @ x
    b = np.linalg.solve(xtx, x.T @ y)
    e = y - x @ b
    return b, _sandwich(xtx, x * e[:, None], cl)


def logit(x: np.ndarray, y: np.ndarray, cl: np.ndarray,
          iters: int = 50) -> tuple[np.ndarray, np.ndarray]:
    b = np.zeros(x.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-x @ b))
        h = (x * (p * (1 - p))[:, None]).T @ x
        step = np.linalg.solve(h, x.T @ (y - p))
        b += step
        if np.abs(step).max() < 1e-10:
            break
    p = 1 / (1 + np.exp(-x @ b))
    h = (x * (p * (1 - p))[:, None]).T @ x
    return b, _sandwich(h, x * (y - p)[:, None], cl)


def pool(logp: list[np.ndarray], result: np.ndarray, cl: np.ndarray,
         iters: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """logp: one (n, 3) array of log probabilities per source; result: index 0..2 per match."""
    xs = np.stack(logp, axis=2)  # (n, 3 outcomes, k sources)
    n, _, k = xs.shape
    b = np.ones(k) / k
    rows = np.arange(n)
    for _ in range(iters):
        u = xs @ b
        u -= u.max(axis=1, keepdims=True)
        pi = np.exp(u)
        pi /= pi.sum(axis=1, keepdims=True)
        xbar = (pi[:, :, None] * xs).sum(axis=1)
        g = xs[rows, result] - xbar
        dev = xs - xbar[:, None, :]
        h = np.einsum("no,nok,nol->kl", pi, dev, dev)
        step = np.linalg.solve(h, g.sum(axis=0))
        b += step
        if np.abs(step).max() < 1e-10:
            break
    return b, _sandwich(h, g, cl)
