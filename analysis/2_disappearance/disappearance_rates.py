import pandas as pd
from cc_stats.paths import ANALYSIS_CSV, results_dir
from cc_stats.units import from_argv
import statsmodels.stats.proportion as proportion
pd.set_option('display.max_columns', None)


analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
# Types or codes: the unit named on the command line (cc_stats.units)
unit = from_argv(analysis)

rows = []
for type in unit.groups:
    # Patients who had the type before surgery and whose post-op types were recorded
    post = analysis.loc[analysis[unit.pre(type)] == 1, unit.post(type)].dropna()
    total = len(post)
    left = int((post == 0).sum())
    lo, hi = proportion.proportion_confint(count = left, nobs = total, alpha = 0.05, method = 'wilson')
    rows.append({'type': type, 'n': total, 'left': left, 'rate_left': left / total, 'lo': lo, 'hi': hi})

rates = pd.DataFrame(rows).sort_values('rate_left', ascending = False).round(3)
print(rates.to_string(index = False))
rates.to_csv(results_dir(f'2_disappearance/{unit.name}') / 'disappearance_rates.csv', index = False)
