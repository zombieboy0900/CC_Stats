import numpy as np
import pandas as pd
import scipy.stats as st
from cc_stats.build_analysis import CORE_TYPES
from cc_stats.outcomes import OUTCOMES
from cc_stats.paths import ANALYSIS_CSV, results_dir
import statsmodels.stats.proportion as proportion
from statsmodels.stats.multitest import multipletests
pd.set_option('display.width', 200)

# Drop seizures at 6 months: how they changed, who has the value recorded, and
# how the change relates to the Engel / ILAE outcome and to seizure type.
# drop_sz_reduction_pct is the percent change in drop seizures (-100 = gone,
# 0 = no change); drop_free is 1 for -100, 0 otherwise (build_analysis.py).
# Seizure types are the five core groups and LGS.
analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
RESULTS = results_dir('3_drop_seizures')
recorded = analysis.dropna(subset = ['drop_sz_reduction_pct'])
change = recorded['drop_sz_reduction_pct']
print(f'{len(recorded)} of {len(analysis)} patients with drop seizures recorded at 6 months')


def rate(k, n):
    if n == 0:
        return np.nan, np.nan, np.nan
    lo, hi = proportion.proportion_confint(count = k, nobs = n, alpha = 0.05, method = 'wilson')
    return k / n, lo, hi


# 1. Distribution of the recorded values (they are recorded in steps: -100, -95, -90, ...)
distribution = change.value_counts().sort_index().rename_axis('drop_sz_reduction_pct').reset_index(name = 'n')
distribution['share'] = distribution['n'] / len(recorded)
print(distribution.to_string(index = False))
distribution.round(3).to_csv(RESULTS / 'drop_distribution.csv', index = False)

# 2. Who has the value: recorded share in groups of patients, to show whether the
# recorded patients look like everyone else
groups = {'all patients': pd.Series(True, index = analysis.index)}
groups.update({f'{t}': analysis[f'has_{t}'] == 1 for t in CORE_TYPES})
groups['no atonic or tonic'] = (analysis['has_atonic'] == 0) & (analysis['has_tonic'] == 0)
groups['LGS'] = analysis['lgs'] == 1
groups['no LGS'] = analysis['lgs'] == 0
for o in OUTCOMES.values():
    groups[o['improved_label'] + ' (improved)'] = analysis[o['improved']] == 1
    groups[o['not_improved_label'] + ' (not improved)'] = analysis[o['improved']] == 0
coverage = pd.DataFrame([{'group': g, 'n': int(m.sum()), 'recorded': int((m & analysis['drop_sz_reduction_pct'].notna()).sum())}
                         for g, m in groups.items()])
coverage['share'] = coverage['recorded'] / coverage['n']
coverage.round(3).to_csv(RESULTS / 'drop_recorded.csv', index = False)

# 3. By outcome class, and the rank correlation of class (higher = worse) with
# the reduction (higher = better, -drop_sz_reduction_pct), so a negative rho
# means worse classes had less reduction.
by_class, correlations, by_improved = [], [], []
for outcome, o in OUTCOMES.items():
    d = recorded.dropna(subset = [o['scale']])
    for c, group in d.groupby(o['scale']):
        k, n = int(group['drop_free'].sum()), len(group)
        r, lo, hi = rate(k, n)
        by_class.append({'outcome': outcome, 'class': int(c), 'n': n, 'drop_free': k, 'rate': r, 'lo': lo, 'hi': hi,
                         'median_change': group['drop_sz_reduction_pct'].median()})
    rho, p = st.spearmanr(d[o['scale']], -d['drop_sz_reduction_pct'])
    correlations.append({'outcome': outcome, 'n': len(d), 'rho': rho, 'p': p})

    # 4. Improved vs not: drop-free rate (Fisher's exact test) and the whole
    # distribution (Mann-Whitney)
    row = {'outcome': outcome}
    for label, value in (('improved', 1), ('not_improved', 0)):
        group = d[d[o['improved']] == value]
        k, n = int(group['drop_free'].sum()), len(group)
        r, lo, hi = rate(k, n)
        row.update({f'n_{label}': n, f'drop_free_{label}': k, f'rate_{label}': r, f'lo_{label}': lo,
                    f'hi_{label}': hi, f'median_{label}': group['drop_sz_reduction_pct'].median()})
    row['p_fisher'] = st.fisher_exact([[row['drop_free_improved'], row['n_improved'] - row['drop_free_improved']],
                                       [row['drop_free_not_improved'], row['n_not_improved'] - row['drop_free_not_improved']]])[1]
    row['p_mann_whitney'] = st.mannwhitneyu(d.loc[d[o['improved']] == 1, 'drop_sz_reduction_pct'],
                                            d.loc[d[o['improved']] == 0, 'drop_sz_reduction_pct']).pvalue
    by_improved.append(row)

by_class = pd.DataFrame(by_class).round(3)
print(by_class.to_string(index = False))
by_class.to_csv(RESULTS / 'drop_by_class.csv', index = False)
pd.DataFrame(correlations).round(3).to_csv(RESULTS / 'drop_class_correlation.csv', index = False)
by_improved = pd.DataFrame(by_improved).round(3)
print(by_improved.to_string(index = False))
by_improved.to_csv(RESULTS / 'drop_by_improvement.csv', index = False)

# 5. By seizure type: drop-free with vs without each core type and LGS, among
# patients with pre-op seizure types recorded. Holm across the six.
features = {t: f'has_{t}' for t in CORE_TYPES} | {'lgs': 'lgs'}
typed = recorded.dropna(subset = list(features.values()))
rows = []
for feature, column in features.items():
    row = {'feature': feature}
    for label, value in (('with', 1), ('without', 0)):
        group = typed[typed[column] == value]
        k, n = int(group['drop_free'].sum()), len(group)
        r, lo, hi = rate(k, n)
        row.update({f'n_{label}': n, f'drop_free_{label}': k, f'rate_{label}': r, f'lo_{label}': lo, f'hi_{label}': hi,
                    f'median_{label}': group['drop_sz_reduction_pct'].median()})
    row['p'] = st.fisher_exact([[row['drop_free_with'], row['n_with'] - row['drop_free_with']],
                                [row['drop_free_without'], row['n_without'] - row['drop_free_without']]])[1]
    rows.append(row)
by_type = pd.DataFrame(rows)
by_type['p_holm'] = multipletests(by_type['p'], method = 'holm')[1]
by_type = by_type.round(3)
print(f'\n{len(typed)} patients with drop seizures and pre-op seizure types recorded')
print(by_type[['feature', 'drop_free_with', 'n_with', 'drop_free_without', 'n_without', 'p', 'p_holm']].to_string(index = False))
by_type.to_csv(RESULTS / 'drop_by_type.csv', index = False)
