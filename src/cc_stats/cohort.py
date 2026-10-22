from dataclasses import dataclass
from functools import cached_property

import pandas as pd

from cc_stats.data_loading import load_pre_post_full
from cc_stats.paths import DATASET
from cc_stats.ilae_taxonomy import TAXONOMY_TREE, label_sets as _template_label_sets


def build_label_to_columns(types, align_df):
    """ILAE label -> every dummy column that holds it (e.g. 'focal motor
    tonic' -> ['FM_Type_23']).

    A list, because the same code can be recorded under more than one
    category prefix - 'generalized motor tonic' as both GM_Type_4 and
    FM_Type_4. Mapping a label to one column kept whichever came last and
    silently dropped the subjects in the other."""
    label_to_columns = {}
    for col in align_df.columns:
        num = int(col.split('_')[-1])
        label = types.get(num)
        if label is not None:
            label_to_columns.setdefault(label, []).append(col)
    return label_to_columns


def subjects_with(label_set, align_df, label_to_columns):
    """Subject IDs whose row has any label in label_set."""
    cols = [col for label in label_set for col in label_to_columns.get(label, [])]
    if not cols:
        return set()
    mask = align_df[cols].any(axis=1)
    return set(align_df.index[mask])


def print_label_tree(tree, label_sets=None):
    """Print a directory-style view of a label-set hierarchy (e.g.
    ilae_taxonomy.TAXONOMY_TREE) - internal nodes show their name and total
    size, leaves show the raw ILAE label(s) they contain. Pass `label_sets`
    (e.g. ilae_taxonomy.label_sets) to annotate internal nodes with sizes."""
    def _walk(node, prefix):
        items = list(node.items())
        for i, (name, child) in enumerate(items):
            is_last = i == len(items) - 1
            connector = '`-- ' if is_last else '|-- '
            if isinstance(child, dict):
                size = f' [{len(label_sets[name])}]' if label_sets is not None and name in label_sets else ''
                print(f'{prefix}{connector}{name}{size}')
                if child:
                    extension = '    ' if is_last else '|   '
                    _walk(child, prefix + extension)
            else:
                members = ', '.join(sorted(child)) if child else '(empty)'
                print(f'{prefix}{connector}{name}: {members}')

    _walk(tree, '')


@dataclass(frozen=True)
class Cohort:
    pre_align: pd.DataFrame
    post_align: pd.DataFrame
    label_to_columns: dict
    types: dict
    pre_recorded: pd.Series
    post_recorded: pd.Series

    @classmethod
    def load_full(cls, types, dataset=DATASET):
        """Cohort over every subject the workbook mentions, built on the
        non-lossy frames (see data_loading.load_pre_post_full).

        The group registry this feeds still answers in *sets of subject IDs*,
        which are inherently two-state - a subject is in a group or isn't,
        with no way to say "unknown". So membership here means "the recorded
        data shows this type", and callers that need three-state answers must
        mask the result with pre_recorded/post_recorded themselves. Nothing
        downstream of this cohort does that for you."""
        frames = load_pre_post_full(dataset)
        label_to_columns = build_label_to_columns(types, frames.pre)
        return cls(frames.pre, frames.post, label_to_columns, types,
                   frames.pre_recorded, frames.post_recorded)

    # cached_property writes straight into instance.__dict__, bypassing the
    # frozen dataclass's __setattr__ override, so these still work despite
    # frozen=True.
    @cached_property
    def ilae(self):
        return Ilae(self)

    @cached_property
    def groups(self):
        return Groups(self)


class Ilae:
    """Base taxonomy + label-set vocabulary, scoped to one cohort - only
    needed so list_taxonomy() can flag which labels are actually present in
    this cohort's data. label_sets is this instance's own copy of
    ilae_taxonomy's template (the built-in TAXONOMY_TREE hierarchy) - the
    fixed vocabulary that Groups.at()/subjects() resolve names against.
    Custom, user-defined groups live in Groups instead."""

    def __init__(self, cohort):
        self.cohort = cohort
        self.tree = TAXONOMY_TREE
        self._label_sets = dict(_template_label_sets)

    def label_name(self, number):
        return self.cohort.types[number]

    def label_sets(self):
        return self._label_sets

    def print_tree(self):
        print_label_tree(self.tree, self._label_sets)

    def list_taxonomy(self):
        """One row per named label set in the built-in taxonomy hierarchy,
        each with its size, member labels, and whether any member appears in
        this cohort's data - plus one row per raw ILAE label that isn't
        covered by any named set (e.g. 'unclassified seizures'), so nothing
        silently disappears."""
        number_by_label = {label: num for num, label in self.cohort.types.items()}

        def row(name, members):
            number = number_by_label.get(next(iter(members))) if len(members) == 1 else pd.NA
            return (
                name, number, len(members), ', '.join(sorted(members)),
                any(member in self.cohort.label_to_columns for member in members),
            )

        rows = [row(name, members) for name, members in sorted(self._label_sets.items())]

        covered = {next(iter(members)) for members in self._label_sets.values() if len(members) == 1}
        uncovered = sorted(label for label in number_by_label if label not in covered)
        rows += [row(label, {label}) for label in uncovered]

        return pd.DataFrame(rows, columns=['Name', 'Number', 'Size', 'Members', 'In dataset'])


class PrePost:
    """A (pre, post) pair of subject-ID sets that combines with |, &, - as a
    single unit - so building a subject-level group never involves naming
    'pre'/'post' yourself. Build one with Groups.at()/universe(), combine
    with set operators, then hand the result to Groups.register_expr()."""

    __slots__ = ('pre', 'post')

    def __init__(self, pre, post):
        self.pre = pre
        self.post = post

    def _combine(self, other, op):
        if not isinstance(other, PrePost):
            return NotImplemented
        return PrePost(op(self.pre, other.pre), op(self.post, other.post))

    def __or__(self, other):
        return self._combine(other, lambda a, b: a | b)

    def __and__(self, other):
        return self._combine(other, lambda a, b: a & b)

    def __sub__(self, other):
        return self._combine(other, lambda a, b: a - b)

    def __repr__(self):
        return f'PrePost(pre={len(self.pre)}, post={len(self.post)})'


class Groups:
    """Custom seizure-type groups, scoped to one cohort. custom_groups.py
    registers the project's set; list_groups() shows what's registered."""

    def __init__(self, cohort):
        self.cohort = cohort
        self._registry = {}
        self._formulas = {}
        self._components = {}

    @property
    def names(self):
        return list(self._registry.keys())

    def registry(self):
        """name -> [pre, post, stayed, lost, joined] subject-ID sets for
        every registered group."""
        return self._registry

    def formulas(self):
        return self._formulas

    def components(self):
        return self._components

    def list_groups(self):
        """One row per registered subject-level group - name, how many
        distinct subjects were ever in it, pre/post/stayed/lost/joined
        counts, its formula (or a default placeholder), and any components
        it was nested from. The subject-group counterpart of
        cohort.ilae.list_taxonomy()."""
        rows = []
        for name, (pre, post, stayed, lost, joined) in self._registry.items():
            rows.append({
                'Name': name,
                'Size': len(pre | post),
                'Pre': len(pre), 'Post': len(post), 'Stayed': len(stayed),
                'Lost': len(lost), 'Joined': len(joined),
                'Members': self._formulas.get(name, 'subject-defined group'),
                'Components': ', '.join(self._components[name]) if name in self._components else None,
            })
        columns = ['Name', 'Size', 'Pre', 'Post', 'Stayed', 'Lost', 'Joined', 'Members', 'Components']
        return pd.DataFrame(rows, columns=columns).sort_values('Name').reset_index(drop=True)

    def subjects(self, name, timepoint='pre'):
        """Subject IDs at pre- or post-surgery for the named label-set (from
        cohort.ilae.label_sets()) OR a group you already registered - not a
        group registration itself, just a lookup, so you can combine several
        of these with |/&/- yourself before calling register_subjects(). This
        is subject-membership arithmetic, not label arithmetic: e.g.
        'general' and 'focal' are disjoint as label sets (no raw label
        belongs to both), but a subject can have labels from both at once, so
        'subjects who are only general' isn't expressible as general - focal
        on the label side - it's subjects('general', t) - subjects('focal', t)
        on the subject side.

        Checking the group registry first (before falling back to
        label_sets()) is what lets at()/register_expr() compose a new group
        from groups you've already registered, not just from base taxonomy
        names - e.g. registering 'BTC' from 'Generalized BTC' | 'Focal BTC'
        after those two are themselves registered groups."""
        if name in self._registry:
            return self._registry[name][0 if timepoint == 'pre' else 1]
        align_df = self.cohort.pre_align if timepoint == 'pre' else self.cohort.post_align
        return subjects_with(self.cohort.ilae.label_sets()[name], align_df, self.cohort.label_to_columns)

    def all_subjects(self, timepoint='pre'):
        """Every subject present at pre- or post-surgery - the universe to
        subtract from for a complement, e.g.
        all_subjects('pre') - subjects('focal', 'pre')."""
        align_df = self.cohort.pre_align if timepoint == 'pre' else self.cohort.post_align
        return set(align_df.index)

    def register_subjects(self, name, pre, post, formula=None, components=None):
        """Register a custom group directly from pre/post subject-ID sets you
        built yourself (e.g. via |/&/- combinations of subjects()/
        all_subjects() calls) - stayed/lost/joined are derived from them.

        components is an optional list of other registered group names this
        one was built from, recorded for list_groups()."""
        stayed = pre & post
        lost = pre - post
        joined = post - pre
        self._registry[name] = [pre, post, stayed, lost, joined]
        if formula is not None:
            self._formulas[name] = formula
        if components is not None:
            self._components[name] = list(components)
        return self._registry[name]

    def at(self, name):
        """PrePost view of a named label-set (from cohort.ilae.label_sets())
        - both timepoints at once, so |/&/- combinations build 'pre' and
        'post' together instead of you writing each one out separately.
        Combine these, then pass the result to register_expr()."""
        return PrePost(self.subjects(name, 'pre'), self.subjects(name, 'post'))

    def universe(self):
        """PrePost view of every subject present at each timepoint - the
        complement base, e.g. cohort.groups.universe() - cohort.groups.at('focal')."""
        return PrePost(self.all_subjects('pre'), self.all_subjects('post'))

    def register_expr(self, name, dual, formula=None, components=None):
        """Register a subject-level group from a PrePost built by combining
        at()/universe() calls with |/&/- - construction never touches
        'pre'/'post' directly. stayed/lost/joined are derived the same way
        register_subjects() derives them, e.g.:

            cohort.groups.register_expr(
                'focal_only', cohort.groups.at('focal') - cohort.groups.at('general'),
                formula='focal - general',
            )
        """
        return self.register_subjects(name, dual.pre, dual.post, formula=formula, components=components)
