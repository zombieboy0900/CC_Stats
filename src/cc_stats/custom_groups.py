"""Single source of truth for every custom cohort group defined across the
project's notebooks. cohort.groups isn't persisted between sessions -
register_all(cohort) re-registers everything on a freshly loaded Cohort.

To add a group, write a _register_*() below and call it from register_all();
build_dataset picks it up with no other edit. cohort.ilae.list_taxonomy()
shows the label-set names at() accepts, and cohort.groups.list_groups()
shows the pre/post/stayed counts of what you registered.

Provenance: these definitions were worked out interactively in an earlier
notebook (kept with the project's private history), then factored out to
here."""


# Groups that exist only so another group can be composed from them - they
# aren't independent analysis groups and shouldn't ship in the dataset as if
# they were. Defined as a subtraction rather than an allow-list on purpose:
# register a new group below and it appears in the exported dataset with no
# further edit. Only add a name here if it's pure scaffolding.
SCAFFOLDING_GROUPS = frozenset({'Generalized BTC', 'Focal BTC'})


def analysis_groups(cohort):
    """Registered group names that ship in the analysis dataset, in
    registration order. Call after register_all()."""
    return [name for name in cohort.groups.names if name not in SCAFFOLDING_GROUPS]


def register_all(cohort):
    _register_atonic(cohort)
    _register_btc(cohort)
    _register_general(cohort)
    _register_focal(cohort)
    _register_pure_general(cohort)
    _register_pure_focal(cohort)
    _register_both_focal_general(cohort)
    _register_tonic(cohort)
    _register_myoclonic(cohort)
    _register_absence(cohort)


def _register_atonic(cohort):
    atonic = (cohort.groups.at('atonic_f') | cohort.groups.at('atonic_m_g')
              | cohort.groups.at('myoclonic_atonic_m_g'))
    cohort.groups.register_expr(
        'atonic', atonic,
        formula='atonic_f | atonic_m_g | myoclonic_atonic_m_g',
        components=['atonic_f', 'atonic_m_g', 'myoclonic_atonic_m_g'],
    )


def _register_btc(cohort):
    generalized_btc = cohort.groups.at('tonic_clonic_m_g') | cohort.groups.at('myoclonic_tonic_m_g')
    cohort.groups.register_expr(
        'Generalized BTC', generalized_btc,
        formula='general tonic clonic | general myoclonic tonic',
        components=['tonic_clonic_m_g', 'myoclonic_tonic_m_g'],
    )

    focal_btc = cohort.groups.at('to_BTC_non') | cohort.groups.at('to_BTC_motor')
    cohort.groups.register_expr(
        'Focal BTC', focal_btc,
        formula='Focal nonmotor to BTC | Focal motor to BTC',
        components=['to_BTC_non', 'to_BTC_motor'],
    )

    btc = cohort.groups.at('Generalized BTC') | cohort.groups.at('Focal BTC')
    cohort.groups.register_expr(
        'BTC', btc,
        formula='Generalized BTC | Focal BTC',
        components=['Generalized BTC', 'Focal BTC'],
    )


def _register_general(cohort):
    cohort.groups.register_expr('general', cohort.groups.at('general'), formula='general')


def _register_focal(cohort):
    cohort.groups.register_expr('focal', cohort.groups.at('focal'), formula='focal')


def _register_pure_general(cohort):
    pre = cohort.groups.subjects('general', 'pre') - cohort.groups.subjects('focal', 'pre')
    post = cohort.groups.subjects('general', 'post') - cohort.groups.subjects('focal', 'post')
    cohort.groups.register_subjects(
        'pure_general', pre, post,
        formula="subjects('general') - subjects('focal')",
        components=['general', 'focal'],
    )


def _register_pure_focal(cohort):
    cohort.groups.register_expr(
        'pure_focal', cohort.groups.at('focal') - cohort.groups.at('general'),
        formula='focal - general',
    )


def _register_both_focal_general(cohort):
    cohort.groups.register_expr(
        'both_focal_general', cohort.groups.at('focal') & cohort.groups.at('general'),
        formula='focal & general',
    )


def _register_tonic(cohort):
    # Pure tonic only - excludes tonic-clonic, which is a distinct compound
    # seizure type, not a subset of tonic (see the false-positive lesson from
    # over-broadly matching 'generalized motor tonic-clonic' as "tonic").
    cohort.groups.register_expr(
        'tonic', cohort.groups.at('tonic_m_g') | cohort.groups.at('tonic_f'),
        formula='tonic_m_g | tonic_f',
        components=['tonic_m_g', 'tonic_f'],
    )


def _register_myoclonic(cohort):
    # Pure myoclonic only - excludes the compound myoclonic-tonic-clonic and
    # myoclonic-atonic types, and excludes myoclonic absence (that's an
    # absence subtype, grouped under _register_absence instead).
    cohort.groups.register_expr(
        'myoclonic', cohort.groups.at('myoclonic_m_g') | cohort.groups.at('myclonic_f'),
        formula='myoclonic_m_g | myclonic_f',
        components=['myoclonic_m_g', 'myclonic_f'],
    )


def _register_absence(cohort):
    absence = (cohort.groups.at('typical_ab') | cohort.groups.at('atypical_ab')
               | cohort.groups.at('myoclonic_ab') | cohort.groups.at('eyelid_myoclonia'))
    cohort.groups.register_expr(
        'absence', absence,
        formula='typical_ab | atypical_ab | myoclonic_ab | eyelid_myoclonia',
        components=['typical_ab', 'atypical_ab', 'myoclonic_ab', 'eyelid_myoclonia'],
    )
