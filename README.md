# CC_Stats

Outcomes after corpus callosotomy by seizure type. Which seizure types disappear
after surgery, and does the type a patient had predict their Engel or ILAE outcome?

## Quick start

```bash
pixi install                # Python environment, with cc_stats installed editable
pixi run setup-git          # once per clone: strip notebook outputs from commits
pixi run build-analysis     # raw workbooks -> the CSVs in data/derived/v2/
pixi run run-analysis       # rebuild, then every script and notebook -> results/v2/
```

`build-analysis` needs the raw data first (see below). Then open the notebooks in
any `analysis/` folder. Every notebook reads its data through `cc_stats.paths`, so it
runs from any directory.

## Data versions

Everything built from the raw data is kept per version: derived CSVs in
`data/derived/<version>/` and results in `results/<version>/<analysis folder>/`.
One version is in use:

| version | raw data |
|---|---|
| `v2` | the October 2026 refresh in `data/raw/new_raw/` |

The Engel, ILAE and drop-seizure outcomes are from the post-op neurology note at
least 6 months after surgery. The 2024-05-29 data-pull values are kept as
`*_at_pull` columns in `cc_patients.csv`.

v1, the original workbooks, was retired on 2026-10-20. Its raw files, its results
and the code that read them are kept in a private copy of the project's earlier
history, outside this repository. When the data is refreshed again, add it as a new version beside v2 (see
"When new patients arrive"). The `CC_DATA` environment variable picks the
version, for both the Python code and the R scripts; without it, everything
uses v2. For notebooks, set it before starting Jupyter. A notebook prints the
version it used on its first line.

**The Firth models in `analysis/1_improvement/` need R ≥ 4.4 from
[CRAN](https://cran.r-project.org/)**, with `install.packages("logistf")` run in it.
`Firth_results.ipynb` finds that R by itself. Set the `RSCRIPT` environment variable
to point it at a specific one. pixi installs an R too, but it can't load `logistf`
yet (see Gotchas).

## Getting the data

**This repository contains no patient data, and no results.** The clinical workbooks
are available to study team members only. The build reads these files from
`data/raw/`:

```
data/raw/
  excluded_subjects.csv                    subjects excluded for cause (subject_id, reason)
  new_raw/
    CC Seizure Classifications - De-Identified 10.16.26.xlsx   pre- and post-op classifications
    CC Seizure Project Variables 7.21.26.xlsx                  demographics and outcomes
    issue_status.csv                       the data owner's verdict on each raw-data issue
```

The exclusion list and the issue statuses live with the data, not in the code, so no
study ID appears in this repository. The build stops with an error if the exclusion
list is missing; without the issue statuses, every issue is listed as unreviewed.

`data/raw/`, `data/derived/` and `results/` are gitignored. Notebook outputs, which display patient rows, are stripped from every
commit by `pixi run setup-git`. Run it before your first commit; it is a per-clone
setting, so a fresh clone doesn't have it.

## The data

Two layers, both in `data/derived/<version>/`, both rebuilt by `pixi run build-analysis`:

| file | what it is |
|---|---|
| `cc_patients.csv` | **The faithful record.** One row per patient, every patient. What was recorded, with no analytic decisions: missing stays missing. |
| `cc_seizure_types.csv` | One row per patient × seizure-type group, with pre / post / stayed. |
| `cc_analysis.csv` | **What every analysis reads.** `cc_patients.csv` plus the project's fixed definitions: `engel_improved` (Engel I–III), `ilae_improved` (ILAE 1–4), `n_types_5`, `drop_sz_reduction_pct` with `drop_free` (drop seizures gone at 6 months), and the per-code `pre_code_NN` / `post_code_NN` columns. |
| `cc_units.csv` | Which groups each unit (types, codes) analyses, written from `src/cc_stats/units.py` so the R scripts use the same lists (see Types and codes). |
| `cc_codebook.csv` | Every column of the files above: description, values, missingness. Generated from the data, so it cannot go stale. |
| `cc_raw_issues.csv` | Problems in the raw data for the data owner to resolve: contradictory rows, codes in the wrong column, IDs the two files disagree on. Nothing reads it; the build also prints a summary. See `src/cc_stats/validate.py`. |

**Read `cc_codebook.csv` before analysing anything.** In particular:

- **`engel_class` and `ilae` are higher = worse.** `drop_sz_reduction_pct` is
  negative = better.
- **Seizure-type columns are three-state: 1 / 0 / NA, never a silent zero.** `has_<type>`
  is pre-op, `had_post_<type>` is post-op; for single ILAE codes, `pre_code_NN` and
  `post_code_NN`. NA means not recorded, not "doesn't have it".
- **No patient is ever dropped from the files.** Each analysis filters to the columns
  it actually uses, in one visible line, and prints its n. So different analyses have
  different n, by design. A patient missing post-op seizure types still counts in a
  model that never uses them.

The improvement cutoffs live as constants at the top of
`src/cc_stats/build_analysis.py`. Change one there and rebuild; the codebook text
updates with it. `docs/engel_cutpoints.html` reviews where the callosotomy literature
draws the Engel cut, and why this project uses I–III vs IV. `cc_patients.csv` never
changes, so anyone who prefers a different definition can start from it.

## When new patients arrive

1. Add the files as a new data version (see Data versions), rather than overwriting
   the old ones, so the results can be compared. That means a new entry in
   `DATASETS` and its input paths in `src/cc_stats/paths.py`, and a branch in
   `data_loading.read_classifications` / `read_variables` if the workbooks are laid
   out differently.
2. `pixi run build-analysis`. It rebuilds both layers in order and stops with an error
   if the curated file breaks one of its rules.
3. `pixi run run-analysis` to rerun everything. No counts are hardcoded; every
   notebook computes its own n.

Notes inside notebooks that quote specific results say what date and n they were
checked at. Re-check them after a rebuild.

## Adding a seizure-type group

Write a `_register_*()` function in `src/cc_stats/custom_groups.py`, call it from
`register_all()`, and rebuild. The new `has_` / `had_post_` columns, the codebook
entries and the `cc_analysis.csv` columns all appear without any other edit. The rate
scripts in folder 2 and folder 1's models pick the group up automatically.
`cohort.ilae.list_taxonomy()` lists the names you can build from.

Combinations work the same way (for example, atonic & tonic). `4_combinations`
instead compares pairs of existing groups directly (with vs without one, among
patients with the other), so it needs no new group.

## Types and codes

Folders 1, 2 and 4 ask each question twice, on two **units** defined in
`src/cc_stats/units.py`:

- **types**: the seizure-type groups (`has_<type>`). Pairs and counts use the five
  core groups (atonic, absence, BTC, tonic, myoclonic).
- **codes**: single ILAE codes (`pre_code_NN`) with at least 10 patients before
  surgery (14 codes). Pairs use the 7 with at least 20, counts the 12 that aren't
  focal awareness codes (a focal seizure counts once, through its feature).

Every script takes the unit as an optional argument (`types` by default) and writes to
`results/<v>/<folder>/<unit>/`. Each folder has a `types/` and a `codes/` notebook
subfolder. **The codes notebooks are generated** from the types ones by
`analysis/unit_notebooks.py`: only the `UNIT` cell and the "Reading the results" notes
differ. Edit the types notebook, then run `pixi run python analysis/unit_notebooks.py`
(`--check` reports any codes notebook that is out of date). The notes of a codes
notebook are its own and are kept when it is regenerated.

## Layout

```
data/raw/              clinical workbooks + demographics export (not in the repository)
data/derived/<v>/      the CSVs above, per data version (built locally, not in the repository)
results/<v>/           everything the analyses write, per data version and unit
                       (not in the repository)
src/cc_stats/          builds the dataset; also shared plotting, statistics and units.
                       See its __init__.py for a module map.
analysis/                           one folder per question, in story order. Scripts sit
                                    at the folder root; notebooks in types/ and codes/
  0_cohort/                         who the patients are and what data they have:
                                    outcome classes; patient characteristics (sex and
                                    age); codes/: every ILAE seizure code's counts
  1_improvement/                    which pre-op features go with improvement? Firth
                                    logistic models, one predictor each (two when
                                    adjusted for LGS), with the observed counts
  2_disappearance/                  how often each seizure type disappears, with CIs
                                    (disappearance.ipynb), and does disappearance go
                                    with improvement? Improvement when each type
                                    stayed vs left (disappearance_and_improvement.ipynb);
                                    the number of types before and after, and whether
                                    losing more goes with a better outcome
                                    (count_change.ipynb)
  3_drop_seizures/                  how much drop seizures fell at 6 months, and how
                                    that relates to Engel / ILAE class, improvement and
                                    seizure type (types only)
  4_combinations/                   does having one type (or LGS) change whether
                                    another disappears, or whether patients improve?
                                    Also which types (cooccurrence.ipynb) and codes
                                    occur together
  story.ipynb                       every candidate slide figure, in story order, drawn
                                    from the folders' results (runs last)
  figure_catalogue.ipynb            every other figure the folders draw, by question,
                                    types then codes, with what each shows. Every
                                    notebook figure is also saved as a PNG in
                                    results/<v>/<folder>/<unit>/figures/
  presentation/                     notebooks that build the slide figures from the
                                    folders' results, saved to
                                    results/<v>/presentation/; and the Engel
                                    classification diagram (results/figures/, as it
                                    doesn't depend on the data)
  unit_notebooks.py                 generates the codes notebooks from the types ones
  run_all.py                        runs every script and notebook (pixi run run-analysis)
docs/                  background for analytic decisions (Engel cut-point review)
```

### Why `results/` mirrors `analysis/`

`analysis/` is the source: scripts and notebooks, committed without their outputs.
`results/<v>/` has the same folder layout and holds everything a run produces: the
CSVs, the figures, a log per step, and an **executed copy of every notebook**.
`run_all.py` never runs a notebook in place; it saves the run into the matching results
folder (`analysis/2_disappearance/types/disappearance.ipynb` ->
`results/v2/2_disappearance/types/disappearance.ipynb`).

- **Notebook outputs show patient rows**, so they can't go in git (`setup-git` strips
  them, and `results/` is gitignored). The executed copy is the only saved record of
  what a full run printed.
- **Each data version keeps its own run** (`results/v2/`, a later `v3/` beside it), so
  two versions can be compared output for output. That is how v2 was checked against v1.

So read results from `results/<v>/`. A notebook you run by hand in `analysis/` gets
outputs there too (locally only), and they can differ from the `results/` copy until the
next `pixi run run-analysis`.

## Gotchas

- **`data/raw/` is not de-identified.** The workbooks contain exact surgery dates. Never
  copy it, or anything built from it, into a tracked folder.
- **pixi's R can't load `logistf`.** On R 4.4, conda-forge's `lme4` build needs a C++
  runtime function the current runtime no longer exports. On R 4.5, Windows hits
  [conda-forge/r-base-feedstock#428](https://github.com/conda-forge/r-base-feedstock/issues/428).
  Use a CRAN R for the Firth step until that is fixed.
