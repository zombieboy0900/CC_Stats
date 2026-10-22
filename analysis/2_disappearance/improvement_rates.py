import numpy as np
import pandas as pd
import scipy.stats as st
from cc_stats.outcomes import OUTCOMES
from cc_stats.paths import ANALYSIS_CSV, results_dir
from cc_stats.units import from_argv
import statsmodels.stats.proportion as proportion
from statsmodels.stats.multitest import multipletests
pd.set_option('display.max_columns', None)


def rate(outcome):
    """Improved count, n, rate and Wilson 95% CI for a 1/0 series."""
    n = len(outcome)
    improved = int(outcome.sum())
    if n == 0:
        return improved, n, np.nan, np.nan, np.nan
    lo, hi = proportion.proportion_confint(count = improved, nobs = n, alpha = 0.05, method = 'wilson')
    return improved, n, improved / n, lo, hi


analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
# Types or codes: the unit named on the command line (cc_stats.units)
unit = from_argv(analysis)

rows = []
for type in unit.groups:
    had_type = analysis[analysis[unit.pre(type)] == 1]
    for outcome_name, o in OUTCOMES.items():
        outcome = o['improved']
        # Overall rate needs only the outcome; the stayed/left split also needs post-op types
        overall = had_type[outcome].dropna()
        split = had_type.dropna(subset = [outcome, unit.post(type)])
        stayed = split.loc[split[unit.post(type)] == 1, outcome]
        left = split.loc[split[unit.post(type)] == 0, outcome]

        row = {'type': type, 'outcome': outcome_name}
        for group, values in [('all', overall), ('stayed', stayed), ('left', left)]:
            improved, n, r, lo, hi = rate(values)
            row.update({f'{group}_n': n, f'{group}_improved': improved,
                        f'{group}_rate': r, f'{group}_lo': lo, f'{group}_hi': hi})
        # Stayed vs left: Fisher's exact test
        row['p'] = st.fisher_exact([[row['left_improved'], row['left_n'] - row['left_improved']],
                                    [row['stayed_improved'], row['stayed_n'] - row['stayed_improved']]])[1]
        rows.append(row)

rates = pd.DataFrame(rows)
# Holm across the unit's groups, within each outcome
rates['p_holm'] = rates.groupby('outcome')['p'].transform(lambda p: multipletests(p, method = 'holm')[1])
rates = rates.round(3)
print(rates.to_string(index = False))
rates.to_csv(results_dir(f'2_disappearance/{unit.name}') / 'improvement_rates.csv', index = False)
