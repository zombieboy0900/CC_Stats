"""Write each folder's codes notebook from its types notebook.

The types notebook is the source: a codes notebook is the same notebook with
UNIT = 'codes' in its cell tagged "unit". Markdown cells tagged "unit-notes"
(the reading of the results, which differs by unit) are kept from the codes
notebook as it is, in order; a new one starts with a placeholder.

    pixi run python analysis/unit_notebooks.py           # write
    pixi run python analysis/unit_notebooks.py --check   # fail if any is stale

Edit the types notebook, never the codes one (except its notes), and rerun.
"""

import copy
import json
import sys
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parent
# (types notebook, codes notebook), relative to analysis/
PAIRS = [
    ('1_improvement/types/Firth_results.ipynb', '1_improvement/codes/Firth_results.ipynb'),
    ('2_disappearance/types/disappearance.ipynb', '2_disappearance/codes/disappearance.ipynb'),
    ('2_disappearance/types/disappearance_and_improvement.ipynb', '2_disappearance/codes/disappearance_and_improvement.ipynb'),
    ('2_disappearance/types/count_change.ipynb', '2_disappearance/codes/count_change.ipynb'),
    ('4_combinations/types/combinations_and_outcome.ipynb', '4_combinations/codes/combinations_and_outcome.ipynb'),
    ('4_combinations/types/conditional_disappearance.ipynb', '4_combinations/codes/conditional_disappearance.ipynb'),
]
PLACEHOLDER = '## Notes for interpretation\n\n*Not written yet for codes: read the results above.*'


def tags(cell):
    return cell.get('metadata', {}).get('tags', [])


def codes_notebook(types_nb, existing):
    nb = copy.deepcopy(types_nb)
    notes = [c for c in (existing or {}).get('cells', []) if 'unit-notes' in tags(c)]
    unit_cells = [c for c in nb['cells'] if 'unit' in tags(c)]
    assert len(unit_cells) == 1, 'the types notebook needs exactly one cell tagged "unit"'
    source = ''.join(unit_cells[0]['source'])
    assert "UNIT = 'types'" in source
    unit_cells[0]['source'] = source.replace("UNIT = 'types'", "UNIT = 'codes'").splitlines(keepends=True)
    k = 0
    for i, cell in enumerate(nb['cells']):
        if 'unit-notes' in tags(cell):
            if k < len(notes):
                nb['cells'][i] = copy.deepcopy(notes[k])
            else:
                cell['source'] = PLACEHOLDER.splitlines(keepends=True)
            k += 1
    return nb


def dump(nb):
    return json.dumps(nb, indent=1, ensure_ascii=False) + '\n'


def main():
    check = '--check' in sys.argv
    stale = []
    for types_path, codes_path in PAIRS:
        types_nb = json.loads((ANALYSIS / types_path).read_text(encoding='utf-8'))
        target = ANALYSIS / codes_path
        existing = json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
        text = dump(codes_notebook(types_nb, existing))
        if existing is not None and text == dump(existing):
            continue
        if check:
            stale.append(codes_path)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8', newline='\n')
            print(f'wrote {codes_path}')
    if stale:
        sys.exit('stale, rerun analysis/unit_notebooks.py: ' + ', '.join(stale))


if __name__ == '__main__':
    main()
