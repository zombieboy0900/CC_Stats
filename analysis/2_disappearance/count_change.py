import numpy as np
import pandas as pd
import scipy.stats as st
from cc_stats.outcomes import OUTCOMES
from cc_stats.paths import ANALYSIS_CSV, results_dir
from cc_stats.units import from_argv
import statsmodels.stats.proportion as proportion
pd.set_option('display.max_columns', None)

# Does losing more seizure types go with a better outcome? Counted over the
# unit's count_groups (cc_stats.units; the unit is named on the command line):
# for types the five core groups, so a patient has 0-5 before and 0-5 after.
# Every result is computed for both outcomes (cc_stats.outcomes) and carries
# an `outcome` column.
analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
unit = from_argv(analysis)
RESULTS = results_dir(f'2_disappearance/{unit.name}')
before_cols = [unit.pre(t) for t in unit.count_groups]
after_cols = [unit.post(t) for t in unit.count_groups]

# Patients with every group recorded before and after surgery
recorded = analysis.dropna(subset = before_cols + after_cols).copy()
recorded['n_before'] = recorded[before_cols].sum(axis = 1).astype(int)
recorded['n_after'] = recorded[after_cols].sum(axis = 1).astype(int)
recorded['net_loss'] = recorded['n_before'] - recorded['n_after']
# A patient can lose one group and gain another, so the net loss hides gains:
# count both directions separately as well.
gained = (recorded[before_cols].to_numpy() == 0) & (recorded[after_cols].to_numpy() == 1)
recorded['n_gained'] = gained.sum(axis = 1)
recorded['change'] = pd.cut(recorded['net_loss'], bins = [-np.inf, -1, 0, 1, np.inf],
                            labels = ['gained', 'no change', 'lost 1', 'lost 2+'])


# Spearman's rho with a 95% CI by the Fisher z transform, using the
# Bonett-Wright standard error for Spearman's rho.
def spearman_ci(x, y):
    rho, p = st.spearmanr(x, y)
    n = len(x)
    se = np.sqrt((1 + rho ** 2 / 2) / (n - 3))
    z = np.arctanh(rho)
    lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
    return rho, lo, hi, p


patients, correlations, by_change = [], [], []
for outcome, o in OUTCOMES.items():
    # ... and this outcome recorded
    cohort = recorded.dropna(subset = [o['scale']]).copy()
    cohort['outcome'] = outcome
    cohort['outcome_class'] = cohort[o['scale']].astype(int)
    cohort['improved'] = cohort[o['improved']].astype(int)
    print(f'{outcome}: {len(cohort)} patients with all {len(before_cols)} {unit.name} recorded before and after surgery, '
          f'{int((cohort["improved"] == 0).sum())} not improved')
    patients.append(cohort[['outcome', 'outcome_class', 'improved', 'n_before', 'n_after', 'net_loss',
                            'n_gained', 'change']])

    # Correlation of each count with the outcome class. Higher class is worse,
    # so a negative rho means "more of this, better outcome".
    for measure, label in [('n_before', 'types before'), ('n_after', 'types after'), ('net_loss', 'net loss')]:
        rho, lo, hi, p = spearman_ci(cohort[measure], cohort['outcome_class'])
        correlations.append({'outcome': outcome, 'measure': measure, 'label': label, 'n': len(cohort),
                             'rho': rho, 'lo': lo, 'hi': hi, 'p': p})

    # Improvement rate by change in type count
    for change, group in cohort.groupby('change', observed = False):
        n, improved = len(group), int(group['improved'].sum())
        lo, hi = proportion.proportion_confint(count = improved, nobs = n, alpha = 0.05, method = 'wilson') if n else (np.nan, np.nan)
        by_change.append({'outcome': outcome, 'change': change, 'n': n, 'improved': improved,
                          'rate': improved / n if n else np.nan, 'lo': lo, 'hi': hi})

# One row per patient per outcome, for the Firth models (count_change_firth.R)
pd.concat(patients).to_csv(RESULTS / 'count_change_by_patient.csv')

correlations = pd.DataFrame(correlations).round(3)
print('\nSpearman correlation with the outcome class (higher class = worse)')
print(correlations.to_string(index = False))
correlations.to_csv(RESULTS / 'count_correlations.csv', index = False)

by_change = pd.DataFrame(by_change).round(3)
print('\nImprovement by change in type count')
print(by_change.to_string(index = False))
by_change.to_csv(RESULTS / 'improvement_by_count_change.csv', index = False)
