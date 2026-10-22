"""Builds the shareable, R-ready analysis dataset for the CC seizure project.

Two files, deliberately relational rather than one wide table:

    cc_patients.csv       one row per patient (all of them), every patient-level
                          variable, plus three-state has_<group> indicators
    cc_seizure_types.csv  one row per (patient x seizure-type group), carrying
                          pre / post / stayed

Why two files and not the single long table they'd join into: only `stayed`
genuinely varies within a patient. Repeating age/sex/outcome down ~10 rows per
patient invites `polr(ilae ~ seizure_type + age)` on ten times as many rows as
there are patients, which silently narrows every CI. Join them in R when you
want the long view; model on cc_patients.csv.

Everything is registry-driven. Add a `_register_*()` to
`custom_groups.register_all()` and both files pick it up on the next run with
no edit here - see `custom_groups.analysis_groups()`.

The dataset records what is *known* and makes no analytic decisions. Missing
stays missing, so a collaborator's `drop_na()` yields the conservative cohort
and anything more inclusive has to be written on purpose. In particular every
seizure-type value is three-state (1 / 0 / NA), never a silent zero - see
data_loading.load_pre_post_full.
"""

import datetime as dt

import pandas as pd

from cc_stats import custom_groups
from cc_stats.cohort import Cohort
from cc_stats.data_loading import load_demographics, load_excluded_subjects
from cc_stats.ilae_taxonomy import types
from cc_stats.validate import raw_issues, with_status
from cc_stats.paths import (
    DATASET,
    ISSUE_STATUS_CSV,
    RAW_ISSUES_CSV,
    PATIENTS_CSV as PATIENT_FILE,
    SEIZURE_TYPES_CSV as LONG_FILE,
    CODEBOOK_CSV as CODEBOOK_FILE,
)

# The primary outcomes are the ones at the 6-month post-op note; the
# 2024-05-29 data-pull values are kept beside them as *_at_pull columns.
_AT_6MO = (' Assessed at the post-op neurology note at least 6 months after '
           'surgery; follow_up_years gives the actual interval.')

# Anything a reader could get wrong belongs here, not in a separate document
# that travels badly. Direction-of-better in particular: two of the three
# outcome scales run the opposite way to intuition.
DESCRIPTIONS = {
    'subject_id': 'Study subject identifier. Primary key; joins to '
                  'cc_seizure_types.csv.',
    'sex': 'Patient sex as recorded.',
    'age_at_cc': 'Age in years at corpus callosotomy.',
    'age_at_data_pull': 'Age in years on 2024-05-29, the date the *_at_pull '
                        'outcome columns were pulled. Missing for patients '
                        'operated on after it.',
    'time_since_surgery': 'Years between surgery and the 2024-05-29 data '
                          'pull (age_at_data_pull - age_at_cc). NOT the '
                          'follow-up of the primary outcome - that is '
                          'follow_up_years.',
    'follow_up_years': 'Years from surgery to the 6-month post-op note the '
                       'primary outcomes were assessed at (date of note - '
                       'date of surgery).',
    'lgs': 'Lennox-Gastaut syndrome. 1 = yes, 0 = no. CAUTION: the source has '
           'no third code, so 0 cannot be distinguished between "assessed, '
           'negative" and "never assessed".',
    'spasm': 'Infantile spasms. 1 = yes, 0 = no. Same 0-vs-not-assessed '
             'caveat as lgs. Note this is recorded independently of seizure '
             'code 38 in the classification workbook; the two can disagree.',
    'dravet': 'Dravet syndrome. 1 = yes, 0 = no. Same caveat as lgs.',
    'engel_raw': 'Engel outcome including the lettered subgrade, exactly as '
                 'recorded (e.g. IIIA). Descriptive use only.' + _AT_6MO,
    'engel_class': 'Engel Roman numeral only, 1-4. HIGHER IS WORSE. Letters '
                   'are dropped for modelling: only Class IV A/B/C is a clean '
                   'monotonic gradient, and Class I D is a different clinical '
                   'scenario rather than "worse". Class III is a subjective '
                   'judgement by the 1993 Engel paper\'s own account and '
                   'holds ~half this cohort.' + _AT_6MO,
    'ilae': 'ILAE outcome class, 1-6. HIGHER IS WORSE. Not evenly spaced: '
            '1-3 are absolute seizure-day counts, 4-6 are relative change '
            'from baseline (Wieser et al. 2001), so treat as ordinal, never '
            'as a continuous score.' + _AT_6MO,
    'drop_sz_reduction_pct': 'Percent change in drop seizures. NEGATIVE IS '
                             'BETTER: -100 = drop seizures eliminated, '
                             'positive = worsening. 0 is a real value (no '
                             'change) and is distinct from missing; the '
                             'source\'s "unknown" is NA here.' + _AT_6MO,
    'engel_raw_at_pull': 'engel_raw as of the 2024-05-29 data pull, the '
                         'outcome v1 used. Missing for later surgeries.',
    'engel_class_at_pull': 'engel_class as of the 2024-05-29 data pull.',
    'ilae_at_pull': 'ilae as of the 2024-05-29 data pull.',
    'drop_sz_reduction_pct_at_pull': 'drop_sz_reduction_pct as of the '
                                     '2024-05-29 data pull.',
    'seizure_type_record': 'Whether this patient has usable seizure-type data '
                           'and, if not, why. Machine-readable so the reason '
                           'survives without the codebook.',
    'n_types_pre': 'Count of distinct ILAE type codes recorded before '
                   'surgery. Counted over codes, not columns, so a code '
                   'appearing under two category prefixes counts once.',
    'n_types_post': 'Count of distinct ILAE type codes recorded after '
                    'surgery. 0 means recorded as having none (seizure-free '
                    'by type), NOT missing - missing is NA.',
    'data_quality_flag': 'Detected contradiction between the seizure-type '
                         'workbook and the outcome scales. NA = no '
                         'contradiction detected. These are open questions '
                         'for the data owner; nothing has been overridden.',
    'seizure_type': 'Registered seizure-type group name. See '
                    'custom_groups.py for each group\'s exact definition.',
    'pre': 'Patient had this seizure-type group before surgery. '
           '1 = yes, 0 = recorded as no, NA = not recorded.',
    'post': 'Patient had this seizure-type group after surgery. '
            '1 = yes, 0 = recorded as no, NA = not recorded.',
    'stayed': 'The type persisted through surgery. 1 = still present after, '
              '0 = no longer present. NA where the question does not apply '
              '(pre = 0, i.e. never had it) or either timepoint is '
              'unrecorded. Filter on pre == 1 for the analysable set.',
}

_STATUS_MEANINGS = {
    'complete': 'seizure-type data recorded at both timepoints',
    'post_not_recorded': 'pre-op types recorded, post-op row blank',
    'pre_not_recorded': 'post-op types recorded, pre-op row blank',
    'pre_and_post_not_recorded': 'in the workbook but both rows blank',
    'not_in_workbook': 'never appears in the classification workbook; these '
                       'patients are also missing age entirely',
    'excluded_miscoded': 'excluded for cause - miscoded prefix columns make '
                         'the label-to-column mapping ambiguous, so all '
                         'seizure-type values are NA',
}


def slug(group_name):
    """'Generalized BTC' -> 'generalized_btc'. Column names have to survive
    dplyr without backticks."""
    return group_name.strip().lower().replace(' ', '_')


def _record_status(cohort, index):
    """Why a subject's seizure-type data is or isn't usable. Machine-readable
    on purpose - the reason has to survive someone who never opens the
    codebook."""
    roster = set(cohort.pre_align.index)
    pre_rec = cohort.pre_recorded.reindex(index, fill_value=False)
    post_rec = cohort.post_recorded.reindex(index, fill_value=False)

    excluded = load_excluded_subjects()
    status = {}
    for subject in index:
        if subject in excluded:
            # Cells exist but the prefix columns are miscoded, so the
            # label->column mapping is ambiguous and the values are likely
            # wrong rather than merely uncertain. Values are NA'd; this flag
            # is how you find them again.
            status[subject] = 'excluded_miscoded'
        elif subject not in roster:
            status[subject] = 'not_in_workbook'
        elif pre_rec[subject] and post_rec[subject]:
            status[subject] = 'complete'
        elif pre_rec[subject]:
            status[subject] = 'post_not_recorded'
        elif post_rec[subject]:
            status[subject] = 'pre_not_recorded'
        else:
            status[subject] = 'pre_and_post_not_recorded'
    return pd.Series(status, name='seizure_type_record').reindex(index)


def _distinct_code_count(align, recorded, index):
    """How many distinct ILAE type codes a subject has at one timepoint.

    Counted over codes, not columns: the same code can appear under two
    category prefixes (GM_Type_5 / FM_Type_5), and counting columns would
    double it. NA wherever nothing was recorded - a plain .sum() would return
    0 for an all-NA row, which is the silent-zero bug in miniature."""
    counts = _by_code(align).sum(axis=1).astype('Int64').reindex(index)
    counts[~recorded.reindex(index, fill_value=False)] = pd.NA
    return counts


def _by_code(align):
    """One 1/0 column per ILAE type code (2-38), merging the category
    prefixes a code can appear under (GM_Type_5 / FM_Type_5). Codes the
    workbook has no column for are all 0."""
    codes = [int(col.split('_')[-1]) for col in align.columns]
    return align.T.groupby(codes).max().T.reindex(columns=list(types), fill_value=0)


def code_column(code, when):
    """pre_code_04 / post_code_04: the per-code indicators. A prefix of their
    own, so nothing that finds the type groups by has_ / had_post_ picks them up."""
    return f'{when}_code_{code:02d}'


def _quality_flags(patients):
    """Contradictions between the seizure-type workbook and the outcome
    scales. Written as rules rather than a hardcoded subject list so a
    refreshed data pull re-detects them (and stops flagging any that get
    corrected). These are questions for whoever entered the data, not
    corrections - nothing here is silently overridden."""
    flags = pd.Series(pd.NA, index=patients.index, dtype='object')

    # ILAE >= 3 or Engel class >= II both mean seizures continued. A post-op
    # row recording no seizure types at all therefore can't be right - one of
    # the two records is wrong. (ILAE 2 is auras-only, which is arguably
    # consistent with no types recorded, so it's deliberately not caught.)
    ongoing = ((patients['ilae'] >= 3) | (patients['engel_class'] >= 2)).fillna(False)
    none_recorded = (patients['n_types_post'] == 0).fillna(False)
    flags[none_recorded & ongoing] = 'no_postop_types_but_ongoing_seizures'

    # The mirror image: seizure types recorded post-op, but ILAE 1 means
    # completely seizure-free.
    some_recorded = (patients['n_types_post'] > 0).fillna(False)
    seizure_free = (patients['ilae'] == 1).fillna(False)
    flags[some_recorded & seizure_free] = 'postop_types_but_ilae_seizure_free'

    return flags


def build_patients(cohort, groups, demographics):
    """One row per patient, every one, nothing filtered."""
    index = demographics.index
    pre_rec = cohort.pre_recorded.reindex(index, fill_value=False)
    post_rec = cohort.post_recorded.reindex(index, fill_value=False)

    patients = pd.DataFrame(index=index)
    patients.index.name = 'subject_id'

    # Sex ships as a label, not 0/1: R factors it natively and a shared file
    # shouldn't need a codebook lookup to read a coefficient. load_demographics
    # maps it to 1/0 for the Python models, so map it back here.
    patients['sex'] = demographics['Sex'].map({1: 'Male', 0: 'Female'})
    patients['age_at_cc'] = demographics['Age']
    patients['age_at_data_pull'] = demographics['Age at Data Pull:5.29.24']
    patients['time_since_surgery'] = demographics['Time Since Surgery']

    patients['lgs'] = demographics['LGS'].astype('Int64')
    patients['spasm'] = demographics['Spasm'].astype('Int64')
    patients['dravet'] = demographics['Dravet'].astype('Int64')

    # engel_raw keeps the lettered subgrade; engel_class is the Roman numeral
    # only. The letters are deliberately dropped for modelling - only Class
    # IV's A/B/C is a clean monotonic gradient. See the codebook.
    patients['engel_raw'] = demographics['Engel:6mo']
    patients['engel_class'] = demographics['Engel Class:6mo'].astype('Int64')
    patients['ilae'] = demographics['ILAE:6mo'].astype('Int64')
    patients['drop_sz_reduction_pct'] = demographics['Drop Sz Reduction:6mo']

    # The 2024 data-pull outcomes, kept beside the primary ones so the two
    # definitions can be compared on the same patients.
    patients.insert(patients.columns.get_loc('time_since_surgery') + 1,
                    'follow_up_years', demographics['Follow-up:6mo'])
    patients['engel_raw_at_pull'] = demographics['Engel:5.29.24']
    patients['engel_class_at_pull'] = demographics['Engel Class:5.29.24'].astype('Int64')
    patients['ilae_at_pull'] = demographics['ILAE:5.29.24'].astype('Int64')
    patients['drop_sz_reduction_pct_at_pull'] = demographics['Drop Sz Reduction:5.29.24']

    patients['seizure_type_record'] = _record_status(cohort, index)
    patients['n_types_pre'] = _distinct_code_count(cohort.pre_align, pre_rec, index)
    patients['n_types_post'] = _distinct_code_count(cohort.post_align, post_rec, index)

    # Three-state group membership. The registry answers in sets of subject
    # IDs, which can't express "unknown" - a subject with no recorded row is
    # simply absent from every set, indistinguishable from one recorded as not
    # having the type. Masking with the recorded flags here is what restores
    # the distinction; nothing inside the registry does it for you.
    registry = cohort.groups.registry()
    for name in groups:
        pre_set, post_set = registry[name][0], registry[name][1]
        member_pre = pd.Series(index.isin(list(pre_set)), index=index, dtype='Int64')
        member_post = pd.Series(index.isin(list(post_set)), index=index, dtype='Int64')
        patients[f'has_{slug(name)}'] = member_pre.where(pre_rec, other=pd.NA)
        patients[f'had_post_{slug(name)}'] = member_post.where(post_rec, other=pd.NA)

    # The same three states for every individual ILAE code, for the analyses
    # run on codes as well as on the groups above.
    for when, align, rec in (('pre', cohort.pre_align, pre_rec), ('post', cohort.post_align, post_rec)):
        by_code = _by_code(align).reindex(index).astype('Int64')
        for code in types:
            patients[code_column(code, when)] = by_code[code].where(rec, other=pd.NA)

    patients.insert(patients.columns.get_loc('n_types_post') + 1,
                    'data_quality_flag', _quality_flags(patients))
    return patients


def build_long(cohort, groups, index):
    """One row per (patient x group). Every patient appears for every group,
    so an unmeasured patient is a visible NA row rather than a missing one."""
    pre_rec = cohort.pre_recorded.reindex(index, fill_value=False)
    post_rec = cohort.post_recorded.reindex(index, fill_value=False)
    registry = cohort.groups.registry()

    rows = []
    for name in groups:
        pre_set, post_set = registry[name][0], registry[name][1]
        for subject in index:
            has_pre = pd.NA if not pre_rec[subject] else int(subject in pre_set)
            has_post = pd.NA if not post_rec[subject] else int(subject in post_set)
            # "Stayed" is only meaningful for a type the patient actually had:
            # you can't keep what you never had. NA covers both "didn't have
            # it" and "don't know" - filter on pre == 1 to get the analysable
            # set, which is what any persistence rate needs anyway.
            if has_pre is pd.NA or has_post is pd.NA or has_pre == 0:
                stayed = pd.NA
            else:
                stayed = int(has_post == 1)
            rows.append({'subject_id': subject, 'seizure_type': name,
                         'pre': has_pre, 'post': has_post, 'stayed': stayed})

    long = pd.DataFrame(rows)
    for col in ('pre', 'post', 'stayed'):
        long[col] = long[col].astype('Int64')
    return long


def _describe(name):
    if name in DESCRIPTIONS:
        return DESCRIPTIONS[name]
    # has_<group> / had_post_<group> are generated per registered group, so
    # their descriptions have to be generated too or the codebook goes stale
    # the moment someone registers a new group.
    for prefix, when in (('has_', 'before'), ('had_post_', 'after')):
        if name.startswith(prefix):
            group = name[len(prefix):]
            return (f'Patient had the "{group}" seizure-type group {when} '
                    f'surgery. 1 = yes, 0 = recorded as no, NA = not '
                    f'recorded. Groups overlap by design - do not sum these '
                    f'to count seizure types, use n_types_{when[0:3]}.')
    for prefix, when in (('pre_code_', 'before'), ('post_code_', 'after')):
        if name.startswith(prefix):
            code = int(name[len(prefix):])
            return (f'Patient had ILAE 2017 seizure code {code} ({types[code]}) {when} '
                    f'surgery. 1 = yes, 0 = recorded as no, NA = not recorded.')
    return ''


def _summarise_values(series):
    values = series.dropna()
    if values.empty:
        return 'all missing'
    if series.dtype == object or values.nunique() <= 8:
        return '; '.join(str(v) for v in sorted(values.unique(), key=str))
    return f'{values.min()} to {values.max()}'


def codebook_rows(path, frame, describe=_describe):
    """Codebook entries for every column of one exported file. Shared with
    build_analysis, which documents cc_analysis.csv in the same codebook -
    pass `describe` to supply descriptions for columns this module doesn't
    know about."""
    rows = []
    for col in frame.columns:
        series = frame[col]
        rows.append({
            # .name, not the Path itself - the codebook ships alongside the
            # CSVs, so it must name them relatively. Absolute paths would leak
            # this machine's directory layout into the file a collaborator
            # reads.
            'file': path.name,
            'column': col,
            'dtype': str(series.dtype),
            'n_present': int(series.notna().sum()),
            'n_missing': int(series.isna().sum()),
            'values': _summarise_values(series),
            'description': describe(col),
        })
    return rows


def build_codebook(patients, long):
    """One row per column of each exported file, with its description and
    actual observed missingness. Generated from the built data, so it cannot
    disagree with what shipped."""
    rows = codebook_rows(PATIENT_FILE, patients.reset_index()) + codebook_rows(LONG_FILE, long)

    for status, meaning in _STATUS_MEANINGS.items():
        rows.append({
            'file': PATIENT_FILE.name, 'column': f'seizure_type_record = {status}',
            'dtype': 'value', 'n_present': int((patients['seizure_type_record'] == status).sum()),
            'n_missing': 0, 'values': '', 'description': meaning,
        })
    return pd.DataFrame(rows)


def build(dataset=DATASET):
    cohort = Cohort.load_full(types, dataset)
    custom_groups.register_all(cohort)
    groups = custom_groups.analysis_groups(cohort)
    demographics = load_demographics(dataset)

    # Every patient either file knows about. A subject with seizure types but
    # no demographics row arrives with NA demographics rather than not at
    # all - the same "missing stays visible" rule as everywhere else.
    unlisted = cohort.pre_align.index.difference(demographics.index)
    unlisted = sorted(unlisted, key=lambda s: int(s[1:]))
    demographics = demographics.reindex(demographics.index.append(pd.Index(unlisted)))

    patients = build_patients(cohort, groups, demographics)
    long = build_long(cohort, groups, demographics.index)
    return patients, long, groups


def main():
    patients, long, groups = build()
    codebook = build_codebook(patients, long)
    issues, fixed = with_status(raw_issues(quality_flags=patients['data_quality_flag']))

    PATIENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f'dataset {DATASET}')
    patients.to_csv(PATIENT_FILE)
    long.to_csv(LONG_FILE, index=False)
    codebook.to_csv(CODEBOOK_FILE, index=False)
    issues.to_csv(RAW_ISSUES_CSV, index=False)

    print(f'built {dt.date.today().isoformat()}')
    print(f'  {PATIENT_FILE}: {len(patients)} patients x {len(patients.columns)} columns')
    print(f'  {LONG_FILE}: {len(long)} rows ({len(groups)} groups x {len(patients)} patients)')
    print(f'  {CODEBOOK_FILE}: {len(codebook)} entries')
    print(f'  groups: {", ".join(groups)}')

    flagged = patients['data_quality_flag'].dropna()
    if len(flagged):
        print(f'\n  {len(flagged)} data-quality contradiction(s) detected:')
        for subject, flag in flagged.items():
            print(f'    {subject}: {flag}')

    if len(issues):
        print(f'\n  {len(issues)} raw-data issue(s), listed in {RAW_ISSUES_CSV.name}:')
        for status, by_status in issues.groupby('status', sort=False):
            print(f'    {status}:')
            for check, rows in by_status.groupby('check'):
                subjects = ', '.join(dict.fromkeys(rows['subject_id']))
                print(f'      {check}: {subjects}')
    if len(fixed):
        print(f'\n  {len(fixed)} issue(s) in {ISSUE_STATUS_CSV.name} no longer found (fixed in the data?):')
        for _, row in fixed.iterrows():
            print(f'    {row["subject_id"]} {row["check"]} ({row["status"]})')


if __name__ == '__main__':
    main()
