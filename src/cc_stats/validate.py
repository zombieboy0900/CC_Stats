"""Checks on the raw data that the build itself can't act on.

Each check finds something a person has to resolve - a contradiction inside
a row, an ID the two files disagree on - and reports it rather than guessing.
Nothing here changes the data. build_dataset writes the result to
cc_raw_issues.csv next to the derived files and prints a summary, so a
refreshed pull shows which issues were fixed and which are new.

Written as rules over the source's own column names, so the same checks run
on every data version.
"""

import re

import pandas as pd

from cc_stats.data_loading import (
    load_excluded_subjects, read_classifications, read_variables, subject_ids,
)
from cc_stats.ilae_taxonomy import types
from cc_stats.paths import (
    DATASET, CLASSIFICATION_WORKBOOK_V2, ISSUE_STATUS_CSV, VARIABLES_WORKBOOK_V2,
)

# Category flag column -> the type-code column it describes, per prefix.
CATEGORY_FLAGS = {
    'GM': ['Generalized Motor'],
    'GN': ['Generalized Nonmotor'],
    'FM': ['Focal Motor'],
    'FN': ['Focal Nonmotor'],
    'U': ['Unknown Motor', 'Unknown Nonmotor'],
}

# The ILAE codes that belong under each prefix, from the legend. Infantile
# spasms (38) is recorded under GM or FM depending on how it was classified.
CATEGORY_CODES = {
    'GM': set(range(2, 10)) | {38},
    'GN': set(range(10, 14)),
    'FM': set(range(14, 25)) | {38},
    'FN': set(range(25, 34)),
    'U': set(range(34, 39)),
}

COLUMNS = ['subject_id', 'timepoint', 'check', 'detail', 'excluded']
STATUS_COLUMNS = ['subject_id', 'check', 'status', 'question', 'note']


def _is_blank_or_zero(value):
    return pd.isna(value) or str(value).strip() in ('0', '0.0')


def _codes(value):
    """(main codes, every code) in one cell. Codes in parentheses describe
    what a seizure evolves into, so they may belong to another category;
    only the main codes have to match the column."""
    if _is_blank_or_zero(value):
        return [], []
    text = str(value)
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    main = re.sub(r'\(.*?(\)|$)', '', text)
    return [int(c) for c in re.findall(r'\d+', main)], [int(c) for c in re.findall(r'\d+', text)]


def _row_issues(subject, timepoint, row):
    suffix = f' {timepoint}-CC'
    issues = []

    def add(check, detail):
        issues.append((subject, timepoint, check, detail))

    for prefix, flag_names in CATEGORY_FLAGS.items():
        code_col = f'{prefix} Type{suffix}'
        flags = {name: row[f'{name}{suffix}'] for name in flag_names}
        code = row[code_col]
        if all(pd.isna(v) for v in [*flags.values(), code]):
            continue

        for name, flag in flags.items():
            if pd.notna(flag) and str(flag).strip() not in ('0', '1', '0.0', '1.0'):
                add('bad_flag_value', f'{name}{suffix} = {flag!r}')
        flagged = any(str(f).strip() in ('1', '1.0') for f in flags.values())
        has_code = not _is_blank_or_zero(code)
        if flagged and not has_code:
            add('flag_without_code', f'{" / ".join(flag_names)} marked present, {code_col} = {code!r}')
        elif has_code and not flagged:
            add('code_without_flag', f'{code_col} = {code!r}, but {" / ".join(flag_names)} not marked present')

        text = '' if pd.isna(code) else str(code)
        if text.count('(') != text.count(')'):
            add('unbalanced_parentheses', f'{code_col} = {code!r}')
        main, every = _codes(code)
        outside = [c for c in main if c not in CATEGORY_CODES[prefix]]
        if outside:
            add('code_outside_category', f'{code_col} = {code!r}: {outside} are not {prefix} codes')
        unknown = [c for c in every if c not in types]
        if unknown:
            add('unknown_code', f'{code_col} = {code!r}: {unknown} not in the ILAE legend')
    return issues


def _annotated_ids(values, source):
    """IDs carrying extra text, e.g. 'S000 (note)'. The build keeps the
    leading ID; whether that's right is a question for the data owner."""
    ids = subject_ids(values)
    annotated = values[ids.notna() & (values.astype(str).str.strip() != ids)]
    return [(ids[i], '', 'annotated_id', f'{source} lists {values[i]!r}; built as {ids[i]}')
            for i in annotated.index]


def raw_issues(dataset=DATASET, quality_flags=None):
    """One row per issue found: subject_id, timepoint (Pre / Post / blank),
    check, detail, and whether the subject is already excluded for cause.

    quality_flags is cc_patients' data_quality_flag column (seizure types
    that contradict the outcome); its flags join the list as checks of the
    same name, so every question for the data owner is in one place."""
    pre, post = read_classifications(dataset)
    issues = []
    if quality_flags is not None:
        issues += [(subject, 'Post', flag, 'post-op seizure types contradict the 6-month outcome')
                   for subject, flag in quality_flags.dropna().items()]
    for timepoint, frame in (('Pre', pre), ('Post', post)):
        for subject, row in frame.iterrows():
            issues += _row_issues(subject, timepoint, row)

    if dataset == 'v2':
        sheet = pd.read_excel(CLASSIFICATION_WORKBOOK_V2, sheet_name='Sz Classifications', header=1)
        issues += _annotated_ids(sheet['Subject #'], 'classification workbook')
        variables = pd.read_excel(VARIABLES_WORKBOOK_V2, sheet_name='Data Collection Sheet')
        issues += _annotated_ids(variables['Subject ID'], 'variables workbook')

    classified = set(pre.index) | set(post.index)
    in_variables = set(read_variables(dataset)['Subject ID'])
    for subject in classified - in_variables:
        issues.append((subject, '', 'no_variables_row', 'has seizure types but no demographics/outcome row'))
    for subject in in_variables - classified:
        issues.append((subject, '', 'no_classification_row', 'has demographics/outcomes but no seizure-type row'))

    excluded = load_excluded_subjects()
    report = pd.DataFrame([(*i, i[0] in excluded) for i in issues], columns=COLUMNS)
    order = report['subject_id'].str[1:].astype(int)
    return report.assign(_order=order).sort_values(['check', '_order', 'timepoint']).drop(columns='_order').reset_index(drop=True)


def with_status(issues, dataset=DATASET, path=ISSUE_STATUS_CSV):
    """issues plus the data owner's verdict on each: status (resolved /
    accepted / open, or 'unreviewed' for an issue not in the status file),
    the question it was asked as, and a note. Also returns the status rows
    that no longer match any issue - on a refreshed pull, those are the
    ones the data owner has fixed. The verdicts are about the v2 workbooks;
    a future version starts with every issue unreviewed."""
    if dataset == 'v2' and path.exists():
        status = pd.read_csv(path)
    else:
        status = pd.DataFrame(columns=STATUS_COLUMNS)
    merged = issues.merge(status, on=['subject_id', 'check'], how='left')
    merged['status'] = merged['status'].fillna('unreviewed')
    key = ['subject_id', 'check']
    stale = status[~status.set_index(key).index.isin(issues.set_index(key).index)]
    return merged, stale.reset_index(drop=True)
