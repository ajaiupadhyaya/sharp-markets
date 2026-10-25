"""The clustered estimators recover known parameters on simulated data."""

import numpy as np
import pytest

from sharpmkt import estimators


def test_ols_matches_lstsq_and_iid_se_with_singletons():
    rng = np.random.default_rng(1)
    x = np.column_stack([np.ones(2000), rng.normal(size=2000)])
    y = x @ np.array([0.5, -2.0]) + rng.normal(size=2000)
    b, cov = estimators.ols(x, y, np.arange(2000))
    assert b == pytest.approx(np.linalg.lstsq(x, y, rcond=None)[0])
    assert np.sqrt(cov[1, 1]) == pytest.approx(1 / np.sqrt(2000), rel=0.1)


def test_logit_recovers_slope():
    rng = np.random.default_rng(2)
    z = rng.normal(size=20000)
    y = (rng.random(20000) < 1 / (1 + np.exp(-(0.3 + 1.2 * z)))).astype(float)
    b, cov = estimators.logit(np.column_stack([np.ones_like(z), z]), y, np.arange(20000) // 4)
    assert b == pytest.approx([0.3, 1.2], abs=0.06)
    assert 0 < np.sqrt(cov[1, 1]) < 0.05


def test_pool_recovers_weights():
    """True P(o) ~ exp(0.7 log p1 + 0.3 log p2): the pool should recover (0.7, 0.3)."""
    rng = np.random.default_rng(3)
    n = 20000
    p1 = rng.dirichlet([3, 2, 2], size=n)
    p2 = rng.dirichlet([2, 2, 3], size=n)
    u = 0.7 * np.log(p1) + 0.3 * np.log(p2)
    pt = np.exp(u) / np.exp(u).sum(axis=1, keepdims=True)
    res = np.array([rng.choice(3, p=row) for row in pt])
    b, cov = estimators.pool([np.log(p1), np.log(p2)], res, np.arange(n) // 5)
    assert b == pytest.approx([0.7, 0.3], abs=0.06)
    assert np.all(np.sqrt(np.diag(cov)) < 0.05)


def test_tost_power():
    from sharpmkt import power
    assert power.tost_power(1e-9) == pytest.approx(1.0)
    assert power.tost_power(1.0) == 0.0  # se far bigger than the margin
    # 2 * Phi(delta / se - z) - 1 at a true difference of 0
    from scipy import stats
    se = 0.0006
    want = 2 * stats.norm.cdf(0.002 / se - stats.norm.ppf(0.975)) - 1
    assert power.tost_power(se, alpha=0.025) == pytest.approx(want)
