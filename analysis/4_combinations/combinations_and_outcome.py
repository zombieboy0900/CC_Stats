import numpy as np
import pandas as pd
import scipy.stats as st
from cc_stats.outcomes import OUTCOMES
from cc_stats.paths import ANALYSIS_CSV, results_dir
from cc_stats.units import from_argv
import statsmodels.stats.proportion as proportion
from statsmodels.stats.multitest import multipletests
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)

# Does a feature go with improvement differently depending on what else the
# patient has? For each feature A and context B (the unit's pair_groups - for
# types the five core groups - and LGS; the unit is named on the command line): among patients who had B before surgery, the share improved with A vs
# without A. Every result is computed for both outcomes (cc_stats.outcomes)
# and carries an `outcome` column; Holm corrects within an outcome.
# conditional_disappearance.py asks the same of disappearance.
analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
unit = from_argv(analysis)
FEATURES = unit.pair_groups + ['lgs']
RESULTS = results_dir(f'4_combinations/{unit.name}')
columns = {f: f if f == 'lgs' else unit.pre(f) for f in FEATURES}


def rate(k, n):
    if n == 0:
        return np.nan, np.nan, np.nan
    lo, hi = proportion.proportion_confint(count = k, nobs = n, alpha = 0.05, method = 'wilson')
    return k / n, lo, hi


rows = []
for outcome, o in OUTCOMES.items():
    # Patients with the outcome, LGS and every group recorded
    cohort = analysis.dropna(subset = [o['improved']] + list(columns.values()))
    improved = cohort[o['improved']] == 1
    print(f'{outcome}: {len(cohort)} patients, {int((~improved).sum())} not improved')
    results = []
    for context in FEATURES:
        among = cohort[columns[context]] == 1
        for feature in FEATURES:
            if feature == context:
                continue
            row = {'outcome': outcome, 'feature': feature, 'context': context}
            for label, has in (('with', 1), ('without', 0)):
                mask = among & (cohort[columns[feature]] == has)
                n, k = int(mask.sum()), int((improved & mask).sum())
                r, lo, hi = rate(k, n)
                row.update({f'n_{label}': n, f'improved_{label}': k, f'rate_{label}': r,
                            f'lo_{label}': lo, f'hi_{label}': hi})
            row['difference'] = row['rate_with'] - row['rate_without']
            row['p'] = st.fisher_exact([[row['improved_with'], row['n_with'] - row['improved_with']],
                                        [row['improved_without'], row['n_without'] - row['improved_without']]])[1]
            results.append(row)
    results = pd.DataFrame(results)
    # Holm across every pair for this outcome: 30 comparisons (types) on few
    # non-improvers will throw up striking differences by chance.
    results['p_holm'] = multipletests(results['p'], method = 'holm')[1]
    rows.append(results)

results = pd.concat(rows).round(3)
print(results[['outcome', 'feature', 'context', 'improved_with', 'n_with', 'rate_with', 'improved_without',
               'n_without', 'rate_without', 'difference', 'p', 'p_holm']]
      .sort_values(['outcome', 'p']).groupby('outcome').head(8).to_string(index = False))
results.to_csv(RESULTS / 'combinations_and_outcome.csv', index = False)
