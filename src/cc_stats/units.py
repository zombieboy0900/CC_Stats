"""What an analysis runs on: seizure-type groups ("types") or individual ILAE
2017 seizure codes ("codes"). Every analysis script takes the unit as its one
optional argument and writes to results/<version>/<folder>/<unit>/:

    python analysis/2_disappearance/disappearance_rates.py          # types
    python analysis/2_disappearance/disappearance_rates.py codes

A unit names three lists of groups, each for the analyses that use it:

    groups        improvement, disappearance: every group (the 10 type groups;
                  the codes with at least CODE_MIN_N patients before surgery)
    pair_groups   combinations, which split patients two ways: the 5 core types;
                  the codes with at least CODE_PAIR_MIN_N patients, except the
                  focal awareness codes
    count_groups  count change: the 5 core types; the codes in `groups`, except
                  the focal awareness codes

and the before / after column of each group in cc_analysis.csv. build_analysis
writes the same definitions to cc_units.csv, so the R scripts read the lists
rather than repeat the thresholds.
"""

import sys
from dataclasses import dataclass

import pandas as pd

from cc_stats.ilae_taxonomy import types as CODE_LABELS

UNITS = ('types', 'codes')
CODE_MIN_N = 10
CODE_PAIR_MIN_N = 20
# ILAE 2017 describes a focal seizure twice: by awareness (focal motor /
# non-motor, aware / impaired awareness) and by its feature (tonic, behaviour
# arrest, to BTC, ...). Counting or pairing both would count one seizure twice
# (e.g. codes 26 and 29 correlate at 0.97), so pairs and counts leave the
# awareness codes out; each focal seizure counts once, through its feature.
FOCAL_AWARENESS_CODES = (14, 15, 25, 26)


@dataclass(frozen=True)
class Unit:
    name: str
    groups: list
    pair_groups: list
    count_groups: list
    pre_prefix: str
    post_prefix: str

    def pre(self, group):
        """The group's 1/0/NA column before surgery."""
        return f'{self.pre_prefix}{group}'

    def post(self, group):
        """The group's 1/0/NA column after surgery."""
        return f'{self.post_prefix}{group}'

    def label(self, group):
        """'atonic'; '4 generalized motor tonic' (as plots.pretty writes them)."""
        return group if self.name == 'types' else code_label(group)


def code_label(group):
    """code_04 -> '4 generalized motor tonic'."""
    code = int(group.removeprefix('code_'))
    return f'{code} {CODE_LABELS[code]}'


def code_group(code):
    """code_04: a code's group name; its columns are pre_code_04 / post_code_04."""
    return f'code_{code:02d}'


def unit(name, analysis):
    """The unit `name` ('types' or 'codes') for the analysis dataset."""
    from cc_stats.build_analysis import CORE_TYPES

    if name == 'types':
        # Every registered group, in registration order
        groups = [c.removeprefix('has_') for c in analysis.columns if c.startswith('has_')]
        return Unit('types', groups, list(CORE_TYPES), list(CORE_TYPES), 'has_', 'had_post_')
    if name == 'codes':
        n_pre = {code_group(c): int((analysis[f'pre_{code_group(c)}'] == 1).sum()) for c in CODE_LABELS}
        groups = [g for g, n in n_pre.items() if n >= CODE_MIN_N]
        feature = {code_group(c) for c in CODE_LABELS if c not in FOCAL_AWARENESS_CODES}
        pairs = [g for g, n in n_pre.items() if n >= CODE_PAIR_MIN_N and g in feature]
        return Unit('codes', groups, pairs, [g for g in groups if g in feature], 'pre_', 'post_')
    raise ValueError(f'unknown unit {name!r}: use one of {UNITS}')


def from_argv(analysis):
    """The unit named on the command line (default types)."""
    return unit(sys.argv[1] if len(sys.argv) > 1 else 'types', analysis)


def table(analysis):
    """Both units' groups, one row each, for cc_units.csv: which lists the
    group is in (1/0), its columns, label and pre-op count."""
    rows = []
    for name in UNITS:
        u = unit(name, analysis)
        for g in dict.fromkeys(u.groups + u.pair_groups + u.count_groups):
            rows.append({'unit': name, 'group': g, 'label': u.label(g),
                         'pre_column': u.pre(g), 'post_column': u.post(g),
                         'n_pre': int((analysis[u.pre(g)] == 1).sum()),
                         'main': int(g in u.groups), 'pairs': int(g in u.pair_groups),
                         'count': int(g in u.count_groups)})
    return pd.DataFrame(rows)
