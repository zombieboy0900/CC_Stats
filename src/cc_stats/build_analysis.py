"""Builds the curated analysis dataset, cc_analysis.csv, from cc_patients.csv.

cc_patients.csv is the faithful record and makes no analytic decisions. This
is the layer that does: it applies the project's fixed outcome definitions, so
every analysis in analysis/ - Python and R - reads one file and agrees on what
"improved" means. To change a definition, edit the constants below and
rebuild; the codebook descriptions are written from the same constants.

One row per patient, all of them. Nothing is dropped and missing stays
missing: each analysis filters to the columns it actually uses, so a patient
missing post-op seizure types still counts in a model that never looks at
them.

Rebuild with `pixi run build-analysis`, which reruns build-dataset first.
"""

import pandas as pd

from cc_stats import build_dataset
from cc_stats.paths import ANALYSIS_CSV, CODEBOOK_CSV, PATIENTS_CSV, UNITS_CSV

ENGEL_IMPROVED_MAX = 3  # Engel I-III
ILAE_IMPROVED_MAX = 4   # ILAE 1-4
DROP_FREE = -100        # drop_sz_reduction_pct of -100: no drop seizures left
CORE_TYPES = ['atonic', 'absence', 'btc', 'tonic', 'myoclonic']

# Time since surgery (and follow-up time) are deliberately not here: the
# project doesn't analyse them. Both stay in cc_patients.csv.
PATIENT_COLUMNS = ['sex', 'age_at_cc', 'lgs', 'engel_class', 'ilae', 'drop_sz_reduction_pct']

_ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV'}

DESCRIPTIONS = {
    'engel_improved': f'Engel outcome, dichotomised. 1 = Engel class I-{_ROMAN[ENGEL_IMPROVED_MAX]} '
                      f'(engel_class <= {ENGEL_IMPROVED_MAX}), 0 = worse, NA = no Engel '
                      f'recorded.',
    'ilae_improved': f'ILAE outcome, dichotomised. 1 = ILAE 1-{ILAE_IMPROVED_MAX} '
                     f'(ilae <= {ILAE_IMPROVED_MAX}), 0 = worse, NA = no ILAE recorded.',
    'n_types_5': f'How many of the {len(CORE_TYPES)} core seizure-type groups '
                 f'({", ".join(CORE_TYPES)}) the patient had before surgery. NA = '
                 f'no pre-op seizure-type data, not 0.',
    'drop_free': f'Drop seizures gone at 6 months. 1 = drop_sz_reduction_pct of {DROP_FREE}, '
                 f'0 = any less reduction, NA = not recorded (whether NA means no drop seizures '
                 f'before surgery or not recorded is an open question for the data owner).',
}


def _describe(name):
    return DESCRIPTIONS.get(name) or build_dataset._describe(name)


def _improved(score, cutoff):
    """1/0 for score <= cutoff, NA where the score is missing. A bare
    comparison would make every missing score False - i.e. 'not improved'."""
    return (score <= cutoff).astype('Int64').mask(score.isna())


def build():
    patients = pd.read_csv(PATIENTS_CSV, index_col='subject_id')

    # Every group column, found by prefix rather than listed, so a group added
    # in custom_groups.py arrives here with no edit.
    # The per-code indicators come along the same way.
    group_columns = [c for c in patients.columns if c.startswith(('has_', 'had_post_', 'pre_code_', 'post_code_'))]

    analysis = patients[PATIENT_COLUMNS + group_columns].copy()
    integer_columns = ['lgs', 'engel_class', 'ilae'] + group_columns
    analysis[integer_columns] = analysis[integer_columns].astype('Int64')

    analysis.insert(analysis.columns.get_loc('ilae') + 1, 'engel_improved',
                    _improved(analysis['engel_class'], ENGEL_IMPROVED_MAX))
    analysis.insert(analysis.columns.get_loc('engel_improved') + 1, 'ilae_improved',
                    _improved(analysis['ilae'], ILAE_IMPROVED_MAX))

    # min_count: NA unless every core type is recorded. A plain sum skips NA
    # and would give a patient with no seizure-type data 0 types.
    core = analysis[[f'has_{t}' for t in CORE_TYPES]]
    analysis.insert(analysis.columns.get_loc('ilae_improved') + 1, 'n_types_5',
                    core.sum(axis=1, min_count=len(CORE_TYPES)))

    drop = analysis['drop_sz_reduction_pct']
    analysis.insert(analysis.columns.get_loc('drop_sz_reduction_pct') + 1, 'drop_free',
                    (drop == DROP_FREE).astype('Int64').mask(drop.isna()))
    return analysis


def check(analysis):
    """Rules that must hold on every rebuild, whatever the sample size."""
    assert analysis.index.is_unique, 'duplicate subject_id'
    for t in CORE_TYPES:
        assert f'has_{t}' in analysis.columns, f'core type {t!r} is not a registered group'
    assert analysis['engel_improved'].isna().equals(analysis['engel_class'].isna())
    assert analysis['ilae_improved'].isna().equals(analysis['ilae'].isna())
    core = analysis[[f'has_{t}' for t in CORE_TYPES]]
    assert analysis['n_types_5'].isna().equals(core.isna().any(axis=1))
    assert analysis['drop_free'].isna().equals(analysis['drop_sz_reduction_pct'].isna())
    assert (analysis['drop_sz_reduction_pct'].dropna() >= DROP_FREE).all(), 'drop seizures reduced by over 100%'


def main():
    analysis = build()
    check(analysis)
    analysis.to_csv(ANALYSIS_CSV)
    from cc_stats import units  # imports CORE_TYPES from here
    units.table(analysis).to_csv(UNITS_CSV, index=False)

    # Replace this file's entries in the shared codebook, keeping the rest.
    codebook = pd.read_csv(CODEBOOK_CSV)
    codebook = codebook[codebook['file'] != ANALYSIS_CSV.name]
    rows = build_dataset.codebook_rows(ANALYSIS_CSV, analysis.reset_index(), _describe)
    pd.concat([codebook, pd.DataFrame(rows)], ignore_index=True).to_csv(CODEBOOK_CSV, index=False)

    print(f'  {ANALYSIS_CSV}: {len(analysis)} patients x {len(analysis.columns)} columns')
    for col in ('engel_improved', 'ilae_improved'):
        counts = analysis[col].value_counts(dropna=False)
        print(f'  {col}: {counts.get(1, 0)} improved, {counts.get(0, 0)} not, '
              f'{analysis[col].isna().sum()} missing')
    print(f'  n_types_5: {analysis["n_types_5"].isna().sum()} missing')
    print(f'  {UNITS_CSV.name}: the groups each unit (types, codes) analyses')


if __name__ == '__main__':
    main()
