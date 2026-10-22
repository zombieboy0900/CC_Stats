"""Every filesystem location this project knows about, in one place.

Nothing else should build a path out of a bare relative string. Those resolve
against the *current working directory*, so the same call succeeds from the
project root and fails from a subdirectory. Import from here instead and a
path means the same thing wherever it is evaluated.

PROJECT_ROOT is derived from this file's own location, so moving the checkout
never matters. If this module itself moves, that one line is the only thing to
update.

Every derived file and result is kept per version of the raw data. One
version is in use:

    v2  the October 2026 refresh in data/raw/new_raw/

v1, the original workbooks, was retired on 2026-10-20: its raw files and the
code that read them are kept in a private copy of the project's earlier
history, outside this repository. A future refresh comes in as a new version beside v2. The CC_DATA environment
variable picks one (default v2); everything below DATA_DERIVED and RESULTS
follows it. The R scripts read the same variable.
"""

import os
from pathlib import Path

# src/cc_stats/paths.py -> src/cc_stats -> src -> the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATASETS = ('v2',)
DATASET = os.environ.get('CC_DATA', 'v2')
if DATASET not in DATASETS:
    raise ValueError(f'CC_DATA={DATASET!r}; expected one of {DATASETS}')

# Inputs. Read-only: the clinical workbook and the demographics/outcome export.
DATA_RAW = PROJECT_ROOT / 'data' / 'raw'
# Subjects excluded for cause, with the reason. Kept with the raw data rather
# than in code, so no study ID appears in the repository.
EXCLUDED_SUBJECTS_CSV = DATA_RAW / 'excluded_subjects.csv'

# v2 inputs. One classification workbook with pre and post side by side, and
# the variables as a workbook rather than a csv.
DATA_RAW_V2 = DATA_RAW / 'new_raw'
CLASSIFICATION_WORKBOOK_V2 = DATA_RAW_V2 / 'CC Seizure Classifications - De-Identified 10.16.26.xlsx'
VARIABLES_WORKBOOK_V2 = DATA_RAW_V2 / 'CC Seizure Project Variables 7.21.26.xlsx'
# The data owner's verdict on each raw-data issue in the v2 workbooks
# (resolved / accepted / open), keyed by subject and check. Kept with the raw
# data so no study ID appears in the repository; read by cc_stats.validate.
ISSUE_STATUS_CSV = DATA_RAW_V2 / 'issue_status.csv'

# The shareable dataset - the contract between the Python pipeline and the R
# analysis. Written only by build_dataset.py; everything downstream reads it.
DATA_DERIVED = PROJECT_ROOT / 'data' / 'derived' / DATASET
PATIENTS_CSV = DATA_DERIVED / 'cc_patients.csv'
SEIZURE_TYPES_CSV = DATA_DERIVED / 'cc_seizure_types.csv'
CODEBOOK_CSV = DATA_DERIVED / 'cc_codebook.csv'
# Problems in the raw data for the data owner to resolve. Written by
# build_dataset.py from cc_stats.validate; nothing reads it.
RAW_ISSUES_CSV = DATA_DERIVED / 'cc_raw_issues.csv'

# The curated analysis dataset - cc_patients.csv with the project's fixed
# outcome definitions applied. Written only by build_analysis.py; every
# analysis in analysis/, Python and R, reads this.
ANALYSIS_CSV = DATA_DERIVED / 'cc_analysis.csv'
# The groups each unit (types, codes) analyses - cc_stats.units - for the R
# scripts. Written by build_analysis.py beside cc_analysis.csv.
UNITS_CSV = DATA_DERIVED / 'cc_units.csv'

# What the analyses write: results/<version>/<analysis folder>/. Kept out of
# analysis/ so one version's run never overwrites another's results.
RESULTS = PROJECT_ROOT / 'results' / DATASET


def results_dir(folder):
    """results/<version>/<folder>/, created if needed. Pass the analysis
    folder's name, e.g. results_dir('1_improvement')."""
    path = RESULTS / folder
    path.mkdir(parents=True, exist_ok=True)
    return path
