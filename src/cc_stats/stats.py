"""Statistics shared by more than one analysis notebook."""

import numpy as np
from scipy.stats import norm


def hodges_lehmann(x, y, conf=0.95):
    """Hodges-Lehmann estimate of the shift between x and y, with its CI.

    The estimate is the median of every pairwise difference x_i - y_j, e.g.
    the typical age gap between an improved and a not-improved patient. It
    is the estimate that goes with the Mann-Whitney test: the CI excludes 0
    when the test is significant at the same level.

    The CI is the large-sample order-statistic interval of Hollander & Wolfe
    (Nonparametric Statistical Methods, section 4.3). Returns
    (estimate, lower, upper); the bounds are NaN when a group is too small
    for an interval at this level.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m, n = len(x), len(y)
    if m == 0 or n == 0:
        return np.nan, np.nan, np.nan

    diffs = np.sort(np.subtract.outer(x, y).ravel())
    estimate = float(np.median(diffs))

    z = norm.ppf(1 - (1 - conf) / 2)
    c = int(round(m * n / 2 - z * np.sqrt(m * n * (m + n + 1) / 12)))
    if c < 1:
        return estimate, np.nan, np.nan
    return estimate, float(diffs[c - 1]), float(diffs[m * n - c])
