from typing import NamedTuple

import pandas as pd

from cc_stats.paths import (
    DATASET,
    EXCLUDED_SUBJECTS_CSV,
    CLASSIFICATION_WORKBOOK_V2,
    VARIABLES_WORKBOOK_V2,
)

TYPE_COLUMNS = ["GM_Type", "GN_Type", "FM_Type", "FN_Type", "U_Type"]

# A study ID, optionally followed by an annotation in the source, e.g.
# "S000 (note)". Group 1 is the ID itself.
SUBJECT_ID = r'^\s*(S\d+)\b'


def subject_ids(values):
    """The study ID at the start of each value, NaN where there isn't one.
    The v2 sheets mix subject rows with blank rows, a code legend, and IDs
    carrying an annotation; this is what tells them apart."""
    return values.astype(str).str.extract(SUBJECT_ID)[0]


def read_classifications(dataset=DATASET):
    """The raw pre- and post-op classification frames, indexed by 'Subject #',
    with the source's own column names. A future data version that is laid
    out differently gets its own branch here, returning the same shape, so
    the cleaning in load_pre_post_full never needs to know which one it has."""
    # v2 is one sheet with pre and post side by side: a banner row, then the
    # header, then subjects, blank rows and a legend of the codes.
    sheet = pd.read_excel(CLASSIFICATION_WORKBOOK_V2, sheet_name='Sz Classifications', header=1)
    ids = subject_ids(sheet['Subject #'])
    sheet = sheet[ids.notna()].assign(**{'Subject #': ids[ids.notna()]}).set_index('Subject #')
    pre = sheet[['DOS (CC)'] + [c for c in sheet.columns if c.endswith('Pre-CC')]]
    post = sheet[[c for c in sheet.columns if c.endswith('Post-CC')]]
    return pre, post


def read_variables(dataset=DATASET):
    """The raw demographics/outcome table, with the source's own column
    names and one row per subject ID."""
    variables = pd.read_excel(VARIABLES_WORKBOOK_V2, sheet_name='Data Collection Sheet')
    ids = subject_ids(variables['Subject ID'])
    return variables[ids.notna()].assign(**{'Subject ID': ids[ids.notna()]})



def load_excluded_subjects(path=EXCLUDED_SUBJECTS_CSV):
    """Subject IDs excluded for cause: their prefix columns are miscoded, so
    the label->column mapping is ambiguous. Read from data/raw/ alongside the
    data, never hardcoded. A missing file is an error, not an empty set -
    building without the exclusions would silently use miscoded rows."""
    if not path.exists():
        raise FileNotFoundError(
            f'{path} not found. It lists the subjects excluded for cause '
            '(columns subject_id, reason) and is kept with the raw data, '
            'outside the repository.')
    return set(pd.read_csv(path)['subject_id'])

RENAME_PRE = {
    "DOS (CC)": "DOS",
    "Generalized Motor Pre-CC": "Generalized_Motor",
    "Generalized Nonmotor Pre-CC": "Generalized_Nonmotor",
    "Focal Motor Pre-CC": "Focal_Motor",
    "Focal Nonmotor Pre-CC": "Focal_Nonmotor",
    "Unknown Motor Pre-CC": "Unknown_Motor",
    "Unknown Nonmotor Pre-CC": "Unknown_Nonmotor",
    "GM Type Pre-CC": "GM_Type",
    "GN Type Pre-CC": "GN_Type",
    "FM Type Pre-CC": "FM_Type",
    "FN Type Pre-CC": "FN_Type",
    "U Type Pre-CC": "U_Type",
}

RENAME_POST = {
    "DOS (CC)": "DOS",
    "Generalized Motor Post-CC": "Generalized_Motor",
    "Generalized Nonmotor Post-CC": "Generalized_Nonmotor",
    "Focal Motor Post-CC": "Focal_Motor",
    "Focal Nonmotor Post-CC": "Focal_Nonmotor",
    "Unknown Motor Post-CC": "Unknown_Motor",
    "Unknown Nonmotor Post-CC": "Unknown_Nonmotor",
    "GM Type Post-CC": "GM_Type",
    "GN Type Post-CC": "GN_Type",
    "FM Type Post-CC": "FM_Type",
    "FN Type Post-CC": "FN_Type",
    "U Type Post-CC": "U_Type",
}

# Placeholder/missing-value dummy columns that get_dummies produces from blank
# or "0" cells - not real ILAE codes, drop them once the real columns are aligned.
EMPTY_DUMMY_COLUMNS = [
    'FM_Type_0', 'GM_Type_0', 'GN_Type_0', 'FN_Type_0', 'U_Type_0',
    'FM_Type_nan', 'GM_Type_nan', 'GN_Type_nan', 'FN_Type_nan', 'U_Type_nan',
]


def _dummies_for(excel_df):
    dummies_list = []
    for col in TYPE_COLUMNS:
        clean_text = excel_df[col].astype(str)
        clean_text = clean_text.str.replace('(', ',', regex=False)
        clean_text = clean_text.str.replace(')', '', regex=False)
        clean_text = clean_text.str.replace(' ', '', regex=False)
        clean_text = clean_text.str.replace('.0', '', regex=False)

        dummies = clean_text.str.get_dummies(sep=',')
        dummies = dummies.add_prefix(f"{col}_")
        dummies_list.append(dummies)
    return pd.concat(dummies_list, axis=1)


class TypeFrames(NamedTuple):
    """Everything the classification workbook knows, missingness intact.

    pre/post carry a nullable Int64 dtype so every cell is genuinely
    three-state: 1 = recorded as having this type, 0 = recorded as *not*
    having it, <NA> = nothing recorded either way.

    pre_recorded/post_recorded flag which subjects have a filled-in row at
    each timepoint - once the dummies are built there is no other way to
    tell "recorded as absent" from "never recorded". Read them as "has
    usable recorded data": excluded subjects (see load_excluded_subjects) are
    False even though cells exist for them, because their prefix columns are
    miscoded and the resulting label->column mapping is ambiguous."""
    pre: pd.DataFrame
    post: pd.DataFrame
    pre_recorded: pd.Series
    post_recorded: pd.Series


def load_pre_post_full(dataset=DATASET):
    """Every subject the workbook mentions, values as nullable Int64 so 0
    ("recorded as absent") stays distinct from <NA> ("never recorded"), plus
    the per-timepoint recorded masks. This is what the shared analysis
    dataset is built from - see TypeFrames."""
    pre_excel, post_excel = read_classifications(dataset)
    for frame in (pre_excel, post_excel):
        if not frame.index.is_unique:
            raise ValueError(f'duplicate subject IDs: {sorted(set(frame.index[frame.index.duplicated()]))}')

    # Roster taken before the exclusion drop, so excluded subjects come back
    # as present-but-empty rows rather than silently absent ones - a reader
    # can then see they exist and see why they're blank.
    roster = pre_excel.index.union(post_excel.index)

    excluded = load_excluded_subjects()
    pre_excel = pre_excel.drop(index=excluded)
    post_excel = post_excel.drop(index=excluded)

    pre_excel = pre_excel.rename(columns=RENAME_PRE)
    post_excel = post_excel.rename(columns=RENAME_POST)

    # "Did anyone write anything here?" - must be read off the raw cells,
    # because _dummies_for's .astype(str) renders a blank as the string 'nan'
    # and from that point on it is indistinguishable from a typed value. A
    # cell holding 0 counts as recorded: in this workbook 0 is an affirmative
    # "none in this category" (some rows have 0s sitting alongside a real
    # code), not a stand-in for missing.
    pre_recorded = pre_excel[TYPE_COLUMNS].notna().any(axis=1)
    post_recorded = post_excel[TYPE_COLUMNS].notna().any(axis=1)

    pre = _dummies_for(pre_excel)
    post = _dummies_for(post_excel)

    all_columns = pre.columns.union(post.columns)
    pre_align = pre.reindex(columns=all_columns, fill_value=0)
    post_align = post.reindex(columns=all_columns, fill_value=0)

    # Placeholder/missing-value dummy columns (get_dummies' own markers for a
    # blank or zero cell) aren't real type codes - strip them. The
    # information they carried is preserved in the *_recorded masks above.
    pre_align = pre_align.drop(columns=EMPTY_DUMMY_COLUMNS, errors='ignore')
    post_align = post_align.drop(columns=EMPTY_DUMMY_COLUMNS, errors='ignore')

    # Infantile spasms (code 38) was recorded as either GM_Type_38 or
    # FM_Type_38 depending on how it was classified - merge into one column.
    # Done while both are still plain int, before any <NA> is introduced.
    pre_align['Type_38'] = pre_align['GM_Type_38'] | pre_align['FM_Type_38']
    post_align['Type_38'] = post_align['GM_Type_38'] | post_align['FM_Type_38']
    pre_align = pre_align.drop(columns=['GM_Type_38', 'FM_Type_38'])
    post_align = post_align.drop(columns=['GM_Type_38', 'FM_Type_38'])

    pre_recorded = pre_recorded.reindex(roster, fill_value=False)
    post_recorded = post_recorded.reindex(roster, fill_value=False)

    # Reindex to the full roster first (absent subjects arrive as <NA>),
    # then blank out the rows where nothing was recorded - their zeros are
    # an artifact of get_dummies, not data.
    pre_align = pre_align.astype('Int64').reindex(roster)
    post_align = post_align.astype('Int64').reindex(roster)
    pre_align.loc[~pre_recorded, :] = pd.NA
    post_align.loc[~post_recorded, :] = pd.NA

    return TypeFrames(pre_align, post_align, pre_recorded, post_recorded)


RENAME_DEMOGRAPHICS = {
    "DOS (CC)": "DOS",
    "Age at CC (Years)": "Age",
    "Age at Data Pull (May 29 2024)": "Age at Data Pull:5.29.24",
    "Latest Engel at 5.29.24": "Engel:5.29.24",
    "Latest ILAE at 5.29.24": "ILAE:5.29.24",
    "Latest Drop Sz Reduction at 5.29.24": "Drop Sz Reduction:5.29.24",
}

# The outcomes at the 6-month post-op neurology note.
RENAME_DEMOGRAPHICS_V2 = {
    "Date of Post-CC Neurology Note": "Date:6mo",
    "Engel at min 6 Months Post-CC": "Engel:6mo",
    "ILAE at min 6 Months Post-CC": "ILAE:6mo",
    "Drop Sz Reduction at 6 Months Post-CC": "Drop Sz Reduction:6mo",
}

# The timepoints outcomes are recorded at, as suffixes on the renamed columns.
OUTCOME_TIMEPOINTS = ('5.29.24', '6mo')


def load_demographics(dataset=DATASET):
    """Loads and cleans the per-subject demographics/outcome table. Renames columns to shorter names (see
    RENAME_DEMOGRAPHICS), converts 'Age at Data Pull' from a ' yrs' string to
    a float, adds 'Time Since Surgery' (Age at Data Pull - Age), and maps Sex
    to 1 (Male) / 0 (Female). Outcome columns are suffixed with their
    timepoint (OUTCOME_TIMEPOINTS), plus 'Follow-up:6mo', years from surgery
    to the 6-month note.

    Doesn't drop any rows - different analyses need different columns, so
    which subjects have enough data varies by analysis. Scope your own
    `.dropna(subset=[...])` to the columns you're actually using."""
    demographics = read_variables(dataset)
    demographics = demographics.set_index('Subject ID').rename_axis('subject')
    if not demographics.index.is_unique:
        raise ValueError(f'duplicate subject IDs: {sorted(set(demographics.index[demographics.index.duplicated()]))}')

    age_at_pull = demographics['Age at Data Pull (May 29 2024)'].str.replace(' yrs', '', regex=False).astype(float)
    demographics['Age at Data Pull (May 29 2024)'] = age_at_pull
    demographics['Time Since Surgery'] = age_at_pull - demographics['Age at CC (Years)']

    demographics = demographics.rename(columns=RENAME_DEMOGRAPHICS | RENAME_DEMOGRAPHICS_V2)
    demographics['Sex'] = demographics['Sex'].map({'Male': 1, 'Female': 0})

    # Outcomes at the 5.29.24 data pull and at the 6-month post-op note.
    # Each timepoint gets the same cleaning.
    for when in [t for t in OUTCOME_TIMEPOINTS if f'Engel:{t}' in demographics.columns]:
        # "unknown" (nothing recorded) becomes NaN, same missing-data
        # convention as every other column here - for drop seizures,
        # negative values are reduction, positive an increase (worsening).
        engel = demographics[f'Engel:{when}']
        demographics[f'Engel:{when}'] = engel.mask(engel.astype(str).str.strip().str.lower() == 'unknown')
        for col in (f'ILAE:{when}', f'Drop Sz Reduction:{when}'):
            demographics[col] = pd.to_numeric(demographics[col], errors='coerce')

        # Engel's lettered sub-grades (IA, IB, IC...) aren't a strict ordering
        # within a class, so rank on the roman-numeral class only (I=1 best ..
        # IV=4 worst) - alternation order matters here (IV/III/II before I) so
        # e.g. 'IIIA' matches the 3-letter 'III' alternative, not 'I' twice.
        engel_class = demographics[f'Engel:{when}'].str.extract(r'^(IV|III|II|I)')[0]
        demographics[f'Engel Class:{when}'] = engel_class.map({'I': 1, 'II': 2, 'III': 3, 'IV': 4})

    if 'Date:6mo' in demographics.columns:
        # How long after surgery the 6-month outcome was actually assessed:
        # "at least 6 months" in the source, and in practice 3 months to years.
        days = pd.to_datetime(demographics['Date:6mo']) - pd.to_datetime(demographics['DOS'])
        demographics['Follow-up:6mo'] = days.dt.days / 365.25

    return demographics

