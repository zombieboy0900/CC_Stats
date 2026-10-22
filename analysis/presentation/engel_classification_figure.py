import matplotlib.pyplot as plt

from cc_stats.paths import PROJECT_ROOT
from cc_stats.plots import PAIR_A, PAIR_B

# A diagram, not data: it doesn't depend on the data version, so it goes in
# results/figures/ rather than results/<version>/.
# Doesn't depend on the data, so it isn't kept per data version
OUT = PROJECT_ROOT / 'results' / 'figures'

LABEL = '#555555'

classes = [
    'Class I: Free of disabling seizures',
    'Class II: Rare disabling seizures ("almost seizure free")',
    'Class III: Worthwhile improvement',
    'Class IV: No worthwhile improvement',
]

plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman', 'DejaVu Serif']

fig, ax = plt.subplots(figsize=(11, 4.2))
ax.set_xlim(0, 11)
ax.set_ylim(0, 4.2)
ax.axis('off')

ax.text(7.05, 3.95, "Engel's Classification of Postoperative Outcome",
        ha='center', va='center', fontsize=17, style='italic')
ax.plot([3.9, 10.2], [3.65, 3.65], color='black', lw=1)

rows_y = [3.25, 2.65, 2.05, 1.05]
for y, text in zip(rows_y, classes):
    ax.text(4.0, y, text, ha='left', va='center', fontsize=15)

divider_y = 1.6
ax.plot([3.5, 10.4], [divider_y, divider_y], color='black', lw=2.5)
ax.plot([3.9, 10.2], [0.6, 0.6], color='black', lw=1)

ax.plot([3.6, 3.6], [divider_y + 0.05, 3.55], color=PAIR_A, lw=3, solid_capstyle='butt')
ax.plot([3.6, 3.6], [divider_y - 0.05, 0.65], color=PAIR_B, lw=3, solid_capstyle='butt')

ax.text(3.1, 2.6, 'Improved', ha='right', va='center', fontsize=20,
        fontweight='bold', color=LABEL, family='sans-serif')
ax.text(3.1, 1.05, 'Not Improved', ha='right', va='center', fontsize=20,
        fontweight='bold', color=LABEL, family='sans-serif')

OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / 'engel_classification.png', dpi=300, bbox_inches='tight', facecolor='white')
