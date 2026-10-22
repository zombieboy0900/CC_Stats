import numpy as np
import pandas as pd
import scipy.stats as st
from cc_stats.paths import ANALYSIS_CSV, results_dir
from cc_stats.units import from_argv
import statsmodels.stats.proportion as proportion
from statsmodels.stats.multitest import multipletests
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)

# Does having one seizure type (or LGS) before surgery change whether another
# type disappears? For each target type B and condition A: among patients who
# had B before surgery and whose post-op types were recorded, the share in
# whom B disappeared, with A vs without A. Types and conditions are the unit's
# pair_groups (cc_stats.units; for types the five core groups; the unit is
# named on the command line).
analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
unit = from_argv(analysis)
CONDITIONS = unit.pair_groups + ['lgs']
RESULTS = results_dir(f'4_combinations/{unit.name}')


def rate(left, n):
    if n == 0:
        return np.nan, np.nan, np.nan
    lo, hi = proportion.proportion_confint(count = left, nobs = n, alpha = 0.05, method = 'wilson')
    return left / n, lo, hi


rows = []
for target in unit.pair_groups:
    had_target = analysis[analysis[unit.pre(target)] == 1].dropna(subset = [unit.post(target)])
    left = had_target[unit.post(target)] == 0
    for condition in CONDITIONS:
        if condition == target:
            continue
        column = condition if condition == 'lgs' else unit.pre(condition)
        known = had_target[column].notna()
        with_a = (had_target[column] == 1) & known
        without_a = (had_target[column] == 0) & known
        row = {'target': target, 'condition': condition}
        for label, mask in (('with', with_a), ('without', without_a)):
            n, k = int(mask.sum()), int((left & mask).sum())
            r, lo, hi = rate(k, n)
            row.update({f'n_{label}': n, f'left_{label}': k, f'rate_{label}': r,
                        f'lo_{label}': lo, f'hi_{label}': hi})
        row['difference'] = row['rate_with'] - row['rate_without']
        row['p'] = st.fisher_exact([[row['left_with'], row['n_with'] - row['left_with']],
                                    [row['left_without'], row['n_without'] - row['left_without']]])[1]
        rows.append(row)

results = pd.DataFrame(rows)
# Holm across every pair tested: with this many comparisons, some will look
# striking by chance.
results['p_holm'] = multipletests(results['p'], method = 'holm')[1]
results = results.round(3)
print(results[['target', 'condition', 'left_with', 'n_with', 'rate_with', 'left_without', 'n_without',
               'rate_without', 'difference', 'p', 'p_holm']].sort_values('p').to_string(index = False))
results.to_csv(RESULTS / 'conditional_disappearance.csv', index = False)
