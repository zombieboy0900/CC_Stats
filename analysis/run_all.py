"""Runs every analysis for one data version, writing into results/<version>/.

    pixi run run-analysis                  # v2 (the default)

Set CC_DATA to run another data version (see src/cc_stats/paths.py).

Scripts first, then every notebook. Scripts and notebooks both cover the two
outcomes, Engel and ILAE (see src/cc_stats/outcomes.py). The notebooks that
present a script's results also run it themselves; running it here as well
gives it its own log.
Notebooks are executed into copies under results/<version>/<folder>/ (and
<folder>/types/, <folder>/codes/), so the
copies in analysis/ are never touched and each version keeps its own
outputs to compare. Keeps going past a failure and reports all of them at
the end. The slide figures (presentation/) run after the folders, into
results/<version>/presentation/; presentation/'s Engel diagram doesn't depend
on the data and is not run here.
"""

import subprocess
import sys
from pathlib import Path

from cc_stats.paths import DATASET, PROJECT_ROOT, RESULTS, results_dir
from cc_stats.rscript import find_rscript

ANALYSIS = Path(__file__).resolve().parent

# (script, unit): a script with no unit runs on types (cc_stats/units.py)
PYTHON_SCRIPTS = [
    '0_cohort/code_counts.py',  # first: the code scripts below read its counts
    '4_combinations/code_correlations.py',
    '2_disappearance/disappearance_rates.py',
    ('2_disappearance/disappearance_rates.py', 'codes'),
    '2_disappearance/improvement_rates.py',
    ('2_disappearance/improvement_rates.py', 'codes'),
    '2_disappearance/count_change.py',
    ('2_disappearance/count_change.py', 'codes'),
    '3_drop_seizures/drop_seizures.py',
    '4_combinations/combinations_and_outcome.py',
    ('4_combinations/combinations_and_outcome.py', 'codes'),
    '4_combinations/conditional_disappearance.py',
    ('4_combinations/conditional_disappearance.py', 'codes'),
]
# (script, unit): a script with no unit runs on types (cc_stats/units.py)
R_SCRIPTS = [
    '0_cohort/firths_covariates.R',
    '1_improvement/firths_analysis.R',
    ('1_improvement/firths_analysis.R', 'codes'),
    '2_disappearance/count_change_firth.R',
    ('2_disappearance/count_change_firth.R', 'codes'),
]
# In story order: each folder answers the next question. A folder's own notebooks
# run first, then those in its types/ and codes/ subfolders.
NOTEBOOK_FOLDERS = [
    '0_cohort',
    '1_improvement',
    '2_disappearance',
    '3_drop_seizures',
    '4_combinations',
]
# Drawn from the folders' CSVs and saved figures, so they run last: every
# candidate slide figure, then every other figure.
FIGURE_NOTEBOOKS = ['story.ipynb', 'figure_catalogue.ipynb']
# Slide figures combining folder results; they save to results/<version>/presentation/.
PRESENTATION = ANALYSIS / 'presentation'


def run(label, command, log):
    """Run one step from the project root, saving its output to `log`."""
    done = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    log.write_text(done.stdout + done.stderr, encoding='utf-8')
    print(f'  {"ok  " if done.returncode == 0 else "FAIL"} {label}')
    return done.returncode == 0


def main():
    print(f'dataset {DATASET} -> {RESULTS}')
    logs = results_dir('logs')
    rscript = find_rscript()
    failed = []

    # (label, command)
    steps = []
    for s in PYTHON_SCRIPTS:
        script, unit = s if isinstance(s, tuple) else (s, None)
        steps.append((f'{script} {unit}' if unit else script, [sys.executable, str(ANALYSIS / script)] + ([unit] if unit else [])))
    for s in R_SCRIPTS:
        script, unit = s if isinstance(s, tuple) else (s, None)
        steps.append((f'{script} {unit}' if unit else script, [rscript, f'analysis/{script}'] + ([unit] if unit else [])))

    def execute(notebook, output_dir):
        return [sys.executable, '-m', 'jupyter', 'nbconvert', '--to', 'notebook', '--execute',
                '--ExecutePreprocessor.timeout=900', '--output-dir', str(output_dir), str(notebook)]

    for folder in NOTEBOOK_FOLDERS:
        for sub in ('', '/types', '/codes'):
            for notebook in sorted((ANALYSIS / f'{folder}{sub}').glob('*.ipynb')):
                steps.append((f'{folder}{sub}/{notebook.name}', execute(notebook, results_dir(folder + sub))))
    steps += [(f'presentation/{nb.name}', execute(nb, results_dir('presentation')))
              for nb in sorted(PRESENTATION.glob('*.ipynb'))]
    steps += [(notebook, execute(ANALYSIS / notebook, RESULTS)) for notebook in FIGURE_NOTEBOOKS]

    for label, command in steps:
        if not run(label, command, logs / (label.replace('/', '__') + '.log')):
            failed.append(label)

    if failed:
        print(f'\n{len(failed)} failed - see {logs}:')
        for label in failed:
            print(f'  {label}')
        sys.exit(1)
    print(f'\nall {len(steps)} steps ran')


if __name__ == '__main__':
    main()
