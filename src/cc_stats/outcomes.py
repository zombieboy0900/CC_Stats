"""The two outcome scales, Engel and ILAE, in one place.

Every analysis that uses an outcome runs on both. Scripts loop over OUTCOMES
and write one CSV with an `outcome` column; notebooks loop over it too, and
show each table and figure for Engel then ILAE, under a heading() each. The
cut-offs themselves live in build_analysis.py, which builds the *_improved
columns.

    OUTCOMES['ilae']['improved']   -> 'ilae_improved'
"""

from cc_stats.build_analysis import ENGEL_IMPROVED_MAX, ILAE_IMPROVED_MAX

_ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV'}

OUTCOMES = {
    'engel': {
        'name': 'Engel',
        'scale': 'engel_class',          # 1-4, higher is worse
        'improved': 'engel_improved',    # 1 / 0 / NA
        'improved_max': ENGEL_IMPROVED_MAX,  # classes up to this count as improved
        'classes': {k: v for k, v in _ROMAN.items()},
        'improved_label': f'Engel I-{_ROMAN[ENGEL_IMPROVED_MAX]}',
        'not_improved_label': f'Engel {_ROMAN[ENGEL_IMPROVED_MAX + 1]}',
    },
    'ilae': {
        'name': 'ILAE',
        'scale': 'ilae',                 # 1-6, higher is worse
        'improved': 'ilae_improved',
        'improved_max': ILAE_IMPROVED_MAX,
        'classes': {k: str(k) for k in range(1, 7)},
        'improved_label': f'ILAE 1-{ILAE_IMPROVED_MAX}',
        'not_improved_label': f'ILAE {ILAE_IMPROVED_MAX + 1}-6',
    },
}


def heading(outcome):
    """In a notebook, a heading naming the outcome the output below is for."""
    from IPython.display import Markdown, display
    o = OUTCOMES[outcome]
    display(Markdown(f"#### {o['name']} (improved = {o['improved_label']}, "
                     f"not improved = {o['not_improved_label']})"))
