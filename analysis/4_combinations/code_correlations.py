import pandas as pd

from cc_stats.paths import ANALYSIS_CSV, DATASET, results_dir

# Which seizure codes occur together before surgery: the phi coefficient
# (Pearson's r on 0/1) for every pair of codes with at least MIN_N patients,
# with the number who have both. Rarer codes give unstable correlations. LGS is
# included as one more row, coded 'LGS'. Patients: everyone with pre-op types
# recorded. Reads the per-code counts from 0_cohort/code_counts.py's output.
print(f'dataset {DATASET}')
MIN_N = 5
analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
codes = pd.read_csv(results_dir('0_cohort/codes') / 'code_counts.csv', keep_default_na = False)
pre = analysis[analysis.filter(like = 'pre_code_').notna().all(axis = 1)]

common = codes.loc[codes['n_pre'] >= MIN_N, 'code'].tolist()
present = pd.concat({code: pre[f'pre_code_{code:02d}'].eq(1).astype(int) for code in common}, axis = 1)
# LGS alongside the codes, for the patients it is recorded for (corr() and
# the counts below skip the rest pairwise)
present['LGS'] = pre['lgs']
common = common + ['LGS']
phi = present.corr()
together = present.fillna(0).T @ present.fillna(0)
pairs = [{'code_a': a, 'code_b': b, 'n_a': int(together.loc[a, a]), 'n_b': int(together.loc[b, b]),
          'n_both': int(together.loc[a, b]), 'phi': phi.loc[a, b]}
         for i, a in enumerate(common) for b in common[i + 1:]]
pairs = pd.DataFrame(pairs).round(3)
print(f'{len(common)} codes with at least {MIN_N} patients; strongest pairs:')
print(pairs.reindex(pairs['phi'].abs().sort_values(ascending = False).index).head(10).to_string(index = False))
pairs.to_csv(results_dir('4_combinations/codes') / 'code_correlations.csv', index = False)
