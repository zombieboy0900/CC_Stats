types = {
    2: 'generalized motor tonic-clonic',
    3: 'generalized motor clonic',
    4: 'generalized motor tonic',
    5: 'generalized motor myoclonic',
    6: 'generalized motor myoclonic-tonic-clonic',
    7: 'generalized motor myoclonic-atonic',
    8: 'generalized motor atonic',
    9: 'generalized motor epileptic spasms',
    10: 'generalized nonmotor (absence) typical',
    11: 'generalized nonmotor (absence) atypical',
    12: 'generalized nonmotor (absence) myoclonic',
    13: 'generalized nonmotor (absence) eyelid myoclonia',
    14: 'focal motor aware',
    15: 'focal motor impaired awareness',
    16: 'focal motor unknown awareness',
    17: 'focal motor automatisms',
    18: 'focal motor atonic',
    19: 'focal motor clonic',
    20: 'focal motor epileptic spasms',
    21: 'focal motor hyperkinetic',
    22: 'focal motor myoclonic',
    23: 'focal motor tonic',
    24: 'focal motor to BTC',
    25: 'focal nonmotor aware',
    26: 'focal nonmotor impaired awareness',
    27: 'focal nonmotor unknown awareness',
    28: 'focal nonmotor autonomic',
    29: 'focal nonmotor behavior arrest',
    30: 'focal nonmotor cognitive',
    31: 'focal nonmotor emotional',
    32: 'focal nonmotor sensory',
    33: 'focal nonmotor to BTC',
    34: 'unknown motor tonic-clonic',
    35: 'unknown motor epileptic spasms',
    36: 'unknown nonmotor behavior arrest',
    37: 'unclassified seizures',
    38: 'infantile spasms',
}

# Base template of named label-sets, grouped by the ILAE hierarchy - this
# nested structure IS the source of truth (not just documentation): every
# name below becomes both a `label_sets` entry and a module-level set you can
# import directly (`from ilae_taxonomy import atonic_f`, or `import *` for
# everything). A node is either a dict (an internal grouping, mapping child
# name -> child node) or a set of raw ILAE labels (a leaf). Combine any of
# these with |, &, - to build your own comparisons - the lowest-level
# elements to work with are the individual label strings themselves (the
# values of `types`). See describe_label_tree() / print_label_tree() in
# group_analysis.py to browse this structure.
TAXONOMY_TREE = {
    'both': {
        'focal': {
            'onset_feature': {
                'nonmotor_onset_f': {
                    'sensory': {'focal nonmotor sensory'},
                    'cognitive': {'focal nonmotor cognitive'},
                    'autonomic': {'focal nonmotor autonomic'},
                    'emotional': {'focal nonmotor emotional'},
                    'behavior_arrest': {'focal nonmotor behavior arrest'},
                    'to_BTC_non': {'focal nonmotor to BTC'},
                },
                'motor_onset_f': {
                    'tonic_f': {'focal motor tonic'},
                    'clonic_f': {'focal motor clonic'},
                    'ep_spams_f': {'focal motor epileptic spasms'},
                    'atonic_f': {'focal motor atonic'},
                    'myclonic_f': {'focal motor myoclonic'},
                    'hyperkinetic_f': {'focal motor hyperkinetic'},
                    'automatism_f': {'focal motor automatisms'},
                    'to_BTC_motor': {'focal motor to BTC'},
                },
                'f_awareness': {
                    'f_motor_a': {
                        'aware_m_f': {'focal motor aware'},
                        'impaired_awareness_m_f': {'focal motor impaired awareness'},
                        'unknown_awareness_m_f': {'focal motor unknown awareness'},
                    },
                    'f_non_a': {
                        'aware_non_f': {'focal nonmotor aware'},
                        'impaired_awareness_non_f': {'focal nonmotor impaired awareness'},
                        'unknown_awareness_non_f': {'focal nonmotor unknown awareness'},
                    },
                },
            },
            'f_to_BTC': set(),  # placeholder - unpopulated in the original taxonomy
        },
        'general': {
            'motor_onset_g': {
                'ep_spasms_m_g': {'generalized motor epileptic spasms'},
                'tonic_m_g': {'generalized motor tonic'},
                'tonic_clonic_m_g': {'generalized motor tonic-clonic'},
                'atonic_m_g': {'generalized motor atonic'},
                'clonic_m_g': {'generalized motor clonic'},
                'myoclonic_m_g': {'generalized motor myoclonic'},
                'myoclonic_tonic_m_g': {'generalized motor myoclonic-tonic-clonic'},
                'myoclonic_atonic_m_g': {'generalized motor myoclonic-atonic'},
            },
            'nonmotor_onset_g': {
                'typical_ab': {'generalized nonmotor (absence) typical'},
                'atypical_ab': {'generalized nonmotor (absence) atypical'},
                'myoclonic_ab': {'generalized nonmotor (absence) myoclonic'},
                'eyelid_myoclonia': {'generalized nonmotor (absence) eyelid myoclonia'},
            },
        },
        'unknown': {
            'motor_onset_u': {
                'tonic_clonic_m_u': {'unknown motor tonic-clonic'},
                'ep_spasms_m_u': {'unknown motor epileptic spasms'},
            },
            'nonmotor_onset_u': {
                'behavior_arrest_u': {'unknown nonmotor behavior arrest'},
            },
        },
    },
}


def _flatten_taxonomy(tree, out):
    """Populate out[name] = set-of-labels for every node (leaf and internal
    alike), returning the union of labels at this level."""
    level_union = set()
    for name, node in tree.items():
        value = _flatten_taxonomy(node, out) if isinstance(node, dict) else set(node)
        out[name] = value
        level_union |= value
    return level_union


# Every named node in TAXONOMY_TREE, flattened to name -> set-of-labels.
label_sets = {}
_flatten_taxonomy(TAXONOMY_TREE, label_sets)

# Make every node a real module-level name (so `atonic_f | atonic_m_g` works
# after `from ilae_taxonomy import *`), derived from - not duplicating - the
# tree above.
globals().update(label_sets)

__all__ = ['types', 'label_sets', 'TAXONOMY_TREE'] + list(label_sets.keys())
