"""Corpus callosotomy seizure-type analysis: the data layer, plus shared helpers.

Turns the raw classification workbooks and the demographics export into the
shareable CSVs in data/derived/. Analysis code reads those CSVs; from here it
needs only paths, plots and stats.

Layer map, roughly bottom-up:

  paths            every filesystem location, so nothing builds a relative path
  ilae_taxonomy    the ILAE code -> label vocabulary and the template hierarchy
  data_loading     workbook -> aligned pre/post frames; demographics
  cohort           Cohort, Ilae, PrePost, Groups - subject-set arithmetic over
                   those frames
  custom_groups    the project's registered seizure-type groups
  validate         checks the raw data for problems a person has to resolve
  build_dataset    writes the three shareable CSVs in data/derived/<version>/,
                   plus validate's cc_raw_issues.csv
  build_analysis   writes cc_analysis.csv, the curated dataset every analysis
                   reads: cc_patients.csv plus the fixed outcome definitions
  units            the two units the analyses run on (seizure-type groups, single
                   ILAE codes): which groups, pairs and counts each uses
  outcomes        the Engel and ILAE scales in one place
  plots            charts drawn the same way in more than one analysis folder
  stats            statistics used by more than one notebook (Hodges-Lehmann)
  rscript          finds a CRAN R that can load logistf, for the Firth models

Rebuild everything with `pixi run build-analysis` (it runs build-dataset
first).

Import the modules, not this package's namespace:

    from cc_stats.cohort import Cohort
    from cc_stats.ilae_taxonomy import types
    from cc_stats import custom_groups

Deliberately kept flat. Thirteen modules do not need subpackages.
"""
