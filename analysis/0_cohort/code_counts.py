import pandas as pd
from cc_stats.build_analysis import CORE_TYPES
from cc_stats.cohort import Cohort
from cc_stats.ilae_taxonomy import label_sets, types
from cc_stats.paths import ANALYSIS_CSV, DATASET, results_dir
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 200)

# How many patients have each of the 37 ILAE 2017 seizure codes (2-38), before
# and after surgery, and which core group each code counts towards. Patients:
# everyone with pre-op seizure types recorded (post-op counts: everyone with
# post-op types recorded; left / stayed: everyone with both). Improvement by
# code is in 1_improvement/codes/, co-occurrence in
# 4_combinations/code_correlations.py.
RESULTS = results_dir('0_cohort/codes')

# The core groups as taxonomy leaves, as defined in cc_stats/custom_groups.py
# (and the curation document's "Defining seizure types" table). Checked below
# against the has_<group> columns every analysis uses.
CORE_LEAVES = {
    'atonic': ['atonic_f', 'atonic_m_g', 'myoclonic_atonic_m_g'],
    'btc': ['tonic_clonic_m_g', 'myoclonic_tonic_m_g', 'to_BTC_non', 'to_BTC_motor'],
    'tonic': ['tonic_m_g', 'tonic_f'],
    'absence': ['typical_ab', 'atypical_ab', 'myoclonic_ab', 'eyelid_myoclonia'],
    'myoclonic': ['myoclonic_m_g', 'myclonic_f'],
}
assert set(CORE_LEAVES) == set(CORE_TYPES)
core_group = {label: group for group, leaves in CORE_LEAVES.items() for leaf in leaves for label in label_sets[leaf]}


def onset(code):
    return ('generalized' if code <= 13 else 'focal' if code <= 33 else 'unknown' if code <= 36 else 'other')


cohort = Cohort.load_full(types, DATASET)
analysis = pd.read_csv(ANALYSIS_CSV, index_col = 'subject_id')
pre = cohort.pre_align[cohort.pre_recorded].reindex(columns = cohort.pre_align.columns)
post = cohort.post_align[cohort.post_recorded]
both = pre.index.intersection(post.index)
print(f'{len(pre)} patients with pre-op types recorded, {len(post)} with post-op, {len(both)} with both')


def has_code(frame, code):
    """1/0 per patient for this code; all 0 if the workbook has no column for it."""
    cols = cohort.label_to_columns.get(types[code], [])
    return frame[cols].eq(1).any(axis = 1) if cols else pd.Series(False, index = frame.index)


rows = []
for code, label in types.items():
    had_pre, had_post = has_code(pre, code), has_code(post, code)
    pre_both, post_both = had_pre.loc[both], had_post.loc[both]
    rows.append({
        'code': code, 'label': label, 'onset': onset(code), 'core_group': core_group.get(label, ''),
        'in_workbook': bool(cohort.label_to_columns.get(label)),
        'n_pre': int(had_pre.sum()), 'n_post': int(had_post.sum()),
        'n_left': int((pre_both & ~post_both).sum()), 'n_stayed': int((pre_both & post_both).sum()),
        'n_new_post': int((~pre_both & post_both).sum()),
    })
codes = pd.DataFrame(rows)
codes['pct_pre'] = (codes['n_pre'] / len(pre)).round(3)

# The union of a group's codes must be exactly that group's has_<group> column.
for group in CORE_TYPES:
    labels = [l for l, g in core_group.items() if g == group]
    members = pd.concat([has_code(pre, c) for c, l in types.items() if l in labels], axis = 1).any(axis = 1)
    expected = analysis.loc[members.index, f'has_{group}']
    assert (members.astype(int) == expected).all(), group

print(codes.to_string(index = False))
codes.to_csv(RESULTS / 'code_counts.csv', index = False)

# Codes per patient before surgery, for the distribution figure
per_patient = pd.concat([has_code(pre, c) for c in types], axis = 1).sum(axis = 1).rename('n_codes')
per_patient.index.name = 'subject_id'
per_patient.to_frame().to_csv(RESULTS / 'codes_per_patient.csv')
