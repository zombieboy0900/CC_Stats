"""Plotting shared by more than one analysis folder.

Only charts drawn the same way in several notebooks belong here; a chart
used once stays in its notebook.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from cc_stats.paths import results_dir

# --- Labels -------------------------------------------------------------------
# Column names as they read on a slide. pretty() swaps whole words only, so it
# is safe on longer labels ("+ btc", "myoclonic, among lgs").
LABELS = {
    'btc': 'BTC', 'lgs': 'LGS', 'pure_focal': 'pure focal', 'pure_general': 'pure generalized',
    'both_focal_general': 'both focal & generalized', 'general': 'generalized',
}


def pretty(text):
    """`text` with column names (btc, lgs, pure_focal, ...) written for reading,
    and seizure codes' group names (code_04) as code and label."""
    import re
    from cc_stats.units import code_label
    text = re.sub(r'\bcode_\d\d\b', lambda m: code_label(m.group(0)), str(text))
    return re.sub(r'\b(' + '|'.join(sorted(LABELS, key=len, reverse=True)) + r')\b',
                  lambda m: LABELS[m.group(1)], text)


def pretty_all(labels):
    return [pretty(label) for label in labels]


# --- Palette -------------------------------------------------------------------
# One series on its own is teal (PAIR_A); two compared row by row are teal and
# orange (with / without a predictor, type left / stayed, Engel / ILAE,
# unadjusted / adjusted). No figure uses green / red.
INK = '#444444'
PAIR_A = '#087f8c'
PAIR_B = '#bd6c28'
# One colour per core group, for labels that say which group a seizure code
# counts towards (code counts, improvement by code, co-occurrence); NO_GROUP
# for codes in none.
GROUP_COLORS = dict(zip(['atonic', 'absence', 'btc', 'tonic', 'myoclonic'],
                        ['#3b6fb6', '#d1872c', '#5a9e4b', '#b5463a', '#7d5ba6']))
NO_GROUP = '#a8a8a8'


def stacked_bar(counts, highlight, cohort_n, ax=None, figsize=(8, 5), fontsize=None):
    """Stacked bar chart of patient counts, one bar per row of `counts`.

    Each segment is labelled with its count. Segments in the `highlight`
    column also show their share of that bar, e.g. the % of atonic patients
    who improved. Above each bar is its total and that total's share of
    `cohort_n`, the number of patients the chart is drawn from, written as
    e.g. "35% of 95" so the label says what it is a share of.

    Returns the axes, so a title or labels can be added afterwards.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    # The highlighted column teal, the rest orange
    counts = counts.rename(index=pretty)
    counts.plot(kind='bar', stacked=True, ax=ax, color=[PAIR_A if c == highlight else PAIR_B for c in counts.columns])

    totals = counts.sum(axis=1)
    ax.set_ylim(0, totals.max() + 8)
    # The height of one line of label text in patients, so a segment too short
    # for a two-line label gets its count and share on one line
    size = fontsize or plt.rcParams['font.size']
    line = size / 72 * 1.25 * (totals.max() + 8) / (ax.get_window_extent().height / ax.figure.dpi)
    for container, column_name in zip(ax.containers, counts.columns):
        labels = []
        for i, v in enumerate(container):
            count = v.get_height()
            if count == 0:
                labels.append('')
            elif column_name == highlight:
                percentage = (count / totals.iloc[i]) * 100
                sep = '\n' if count >= 2.2 * line else ' '
                labels.append(f'{int(count)}{sep}({percentage:.0f}%)')
            else:
                labels.append(str(int(count)))
        ax.bar_label(container, labels=labels, label_type='center', fontsize=fontsize, color='white')

    for i, count in enumerate(totals):
        ax.text(i, count + 1.5, f'{count}\n{count / cohort_n:.0%} of {cohort_n}', ha='center')

    ax.set_ylabel('Patients')
    ax.tick_params(axis='x', rotation=0)
    return ax


def rate_plot(labels, rate, lo, hi, ax=None, figsize=(8, 5), offset=0, color=PAIR_A, label=None,
              counts=None, header='n / total', fontsize=9.5):
    """Proportions with capped confidence intervals, one row per label, on a
    0-100% axis. `counts` = (k, n), one value per row, adds a headed column of
    k/n (%) on the right, in `color`. Call again on the same `ax` with an
    `offset` (e.g. +-0.15) and another `color`/`label` to compare two series
    row by row (paired_rate_plot does this with the counts column for both).
    Missing rates (a group with no patients) leave their row empty.

    Returns the axes, so a title or legend can be added afterwards.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    y = np.arange(len(labels)) + offset
    rate, lo, hi = (np.asarray(v, dtype=float) for v in (rate, lo, hi))
    has = ~np.isnan(rate)
    ax.errorbar(rate[has], y[has], xerr=np.clip([rate[has] - lo[has], hi[has] - rate[has]], 0, None),
                fmt='o', ms=7, color=color, elinewidth=2, capsize=4, capthick=2, label=label)
    if counts is not None:
        for yi, k, n in zip(y, *counts):
            ax.text(1.04, yi, f'{k:.0f}/{n:.0f} ({k / n:.0%})' if n else '-', transform=ax.get_yaxis_transform(),
                    va='center', ha='left', fontsize=fontsize, color=color)
        ax.text(1.04, len(labels) - 0.35, header, transform=ax.get_yaxis_transform(),
                va='center', ha='left', fontsize=fontsize, fontweight='bold', color=INK)

    ax.set_yticks(range(len(labels)), pretty_all(labels))
    ax.set_ylim(-0.6, len(labels) - 0.4)
    # A little past 100%, so a dot at 100% isn't cut in half by the edge.
    ax.set_xlim(0, 1.03)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v:.0%}'))
    ax.grid(axis='x', color='#e5e5e5')
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    return ax


def right_of(ax, inches):
    """A transform for text `inches` right of the plot's right edge, y in data."""
    from matplotlib.transforms import ScaledTranslation
    return ax.get_yaxis_transform() + ScaledTranslation(inches, 0, ax.figure.dpi_scale_trans)


def paired_rate_plot(ax, labels, top, bottom, header='Improved / total', fontsize=9.5, p=None, p_holm=None,
                     percent=True, bottom_hollow=False, ms=7, lw=2, offset=0.17):
    """Two groups' observed rates compared row by row, on a 0-100% axis:
    `top` and `bottom` are (label, improved, n, colour), with improved and n
    one value per row. Each dot has a capped Wilson 95% CI, and a headed
    column on the right gives improved/n (%) in the group's colour. `p` and
    `p_holm` (one per row) add headed "p" and "Holm p" columns after it;
    `percent=False` drops the (%) from the counts, to save width, and
    `bottom_hollow=True` draws the bottom group's dots hollow (for two groups
    in one colour). `ms`, `lw` and `offset` set the dot size, line width
    and the two groups' distance from the row (smaller for many rows). A
    group with no patients leaves its place empty."""
    from statsmodels.stats.proportion import proportion_confint

    y = np.arange(len(labels))
    texts = []
    for (label, k, n, color), dy, hollow in ((top, offset, False), (bottom, -offset, bottom_hollow)):
        k, n = np.asarray(k, dtype=float), np.asarray(n, dtype=float)
        has = n > 0
        rate = np.where(has, k / np.where(has, n, 1), np.nan)
        lo, hi = proportion_confint(k[has], n[has], alpha=0.05, method='wilson')
        ax.errorbar(rate[has], y[has] + dy, xerr=np.clip([rate[has] - lo, hi - rate[has]], 0, None),
                    fmt='o', ms=ms, color=color, elinewidth=lw, capsize=ms * 0.55, capthick=lw, label=label,
                    mfc='white' if hollow else color, mew=lw)
        texts += [(yi + dy, (f'{ki:.0f}/{ni:.0f}' + (f' ({ki / ni:.0%})' if percent else '')) if ni else '0/0', color)
                  for yi, ki, ni in zip(y, k, n)]
    # Columns are placed in inches right of the plot, so they keep their spacing
    # however wide the plot itself comes out.
    counts_x = 0.15
    for yi, text, color in texts:
        ax.text(1, yi, text, transform=right_of(ax, counts_x), va='center', ha='left', fontsize=fontsize, color=color)
    ax.text(1, len(labels) - 0.35, header, transform=right_of(ax, counts_x),
            va='center', ha='left', fontsize=fontsize, fontweight='bold', color=INK)
    # The p columns start after the counts column's widest entry
    width = max(len(header), *(len(t) for _, t, _ in texts)) * fontsize * 0.6 / 72
    p_x = counts_x + width + 0.35
    for x, name, values in ((p_x, 'p', p), (p_x + 0.65, 'Holm p', p_holm)):
        if values is None:
            continue
        ax.text(1, len(labels) - 0.35, name, transform=right_of(ax, x),
                va='center', ha='center', fontsize=fontsize, fontweight='bold', color=INK)
        for yi, v in zip(y, values):
            ax.text(1, yi, '-' if pd.isna(v) else '<0.001' if v < 0.001 else f'{v:.3f}',
                    transform=right_of(ax, x), va='center', ha='center', fontsize=fontsize, color=INK)

    ax.set_yticks(y, pretty_all(labels))
    ax.set_ylim(-0.6, len(labels) - 0.4)
    ax.set_xlim(0, 1.03)  # 0-100%, as rate_plot
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v:.0%}'))
    ax.grid(axis='x', color='#e5e5e5')
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    return ax


# --- Odds-ratio forest plots (folder 1's Firth models, and the story) -------



def forest(ax, d, cols, offset=0, hollow=False, color=PAIR_A, label=None, ms=8, lw=2):
    """One row per row of `d`: the estimate and CI in `cols` (estimate, lo,
    hi), in `color`. Call twice with an `offset` and another colour (e.g.
    PAIR_A / PAIR_B for Engel / ILAE) to compare two models row by row; `label`
    names the series for a legend; `ms` and `lw` set the dot size and line width."""
    y = np.arange(len(d)) + offset
    est, lo, hi = (d[c].to_numpy() for c in cols)
    colors = [color] * len(est)
    if label is not None:
        ax.plot([], [], 'o-', ms=ms, lw=lw, color=color, label=label)
    ax.hlines(y, lo, hi, colors=colors, lw=lw)
    for yi, e, c in zip(y, est, colors):
        ax.plot(e, yi, 'o', ms=ms, color=c, mfc='white' if hollow else c, mew=lw)


def setup_or_axis(ax, labels, title, ticks=(0.01, 0.1, 1, 10, 100)):
    """Log odds-ratio axis with a dashed line at 1, for a forest() plot. The
    axis is symmetric about 1 on the log scale (as far below 1 as above), set
    from the widest tick; CIs past the edge are cut off."""
    span = max(max(ticks), 1 / min(ticks)) * 1.4
    ax.set_xscale('log')
    ax.set_xlim(1 / span, span)
    ax.set_xticks(ticks, [f'{t:g}' for t in ticks])
    ax.minorticks_off()
    ax.axvline(1, color='gray', ls='--', lw=1)
    ax.set_yticks(range(len(labels)), pretty_all(labels))
    ax.set_xlabel('Odds ratio')
    ax.set_title(title, loc='left')
    ax.grid(axis='x', color='#e5e5e5')
    ax.set_axisbelow(True)
    for s in ['top', 'right']:
        ax.spines[s].set_visible(False)


# --- Conditional disappearance heatmap (folder 4, and the story) ------------

def pair_heatmap(pairs, targets, conditions, ax=None, figsize=(8, 5), min_n=5, row='target', col='condition',
                 row_label='{} disappears', col_label='with {}',
                 cbar_label='Difference in disappearance (percentage points)', counts=('left_with', 'left_without')):
    """A folder 4 pairs table as a grid: one row per `row` value (`targets`),
    one column per `col` value (`conditions`), each cell the column `difference`
    (rate with minus without) in percentage points. The defaults draw
    conditional_disappearance.csv; combinations_and_outcome.csv passes its own
    columns and labels. Under each difference are the counts behind it, with
    vs without (`counts` names the numerator columns; the denominators are
    n_with / n_without). * marks uncorrected p < 0.05; pairs with fewer than
    `min_n` patients on either side are left uncoloured, with grey text."""
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    grid = lambda values: pairs.pivot(index=row, columns=col, values=values).reindex(
        index=targets, columns=conditions)
    diff, p = grid('difference'), grid('p')
    n_with, n_without = grid('n_with'), grid('n_without')
    k_with, k_without = grid(counts[0]), grid(counts[1])
    small = ((n_with < min_n) | (n_without < min_n))
    im = ax.imshow(diff.where(~small).to_numpy(dtype=float) * 100, cmap='RdBu_r', vmin=-60, vmax=60)
    for i in range(len(targets)):
        for j in range(len(conditions)):
            v = diff.iat[i, j]
            if pd.isna(v):
                continue
            points = int(round(v * 100))
            label = (f'{points:+d}' if points else '0') + ('*' if p.iat[i, j] < 0.05 else '')
            # Grey text for small pairs; white on the darkest cells
            color = '#999999' if small.iat[i, j] else 'white' if abs(points) >= 45 else 'black'
            ax.text(j, i - 0.12, label, ha='center', va='center', fontsize=10, color=color)
            ax.text(j, i + 0.22, f'{k_with.iat[i, j]:.0f}/{n_with.iat[i, j]:.0f} vs {k_without.iat[i, j]:.0f}/{n_without.iat[i, j]:.0f}',
                    ha='center', va='center', fontsize=6.5, color=color)
    ax.set_xticks(range(len(conditions)), [col_label.format(pretty(c)) for c in conditions], rotation=30, ha='right')
    ax.set_yticks(range(len(targets)), [row_label.format(pretty(t)) for t in targets])
    ax.figure.colorbar(im, ax=ax, label=cbar_label)
    return ax


# --- Saving figures ----------------------------------------------------------

def save_figure(folder, name, fig=None):
    """Save `fig` (default: the current figure) as
    results/<version>/<folder>/figures/<name>.png, at a resolution fit for a
    slide. Every notebook figure is saved this way under a stable name, so
    figure_catalogue.ipynb can show them and slides can use the files."""
    path = results_dir(folder) / 'figures'
    path.mkdir(parents=True, exist_ok=True)
    (fig or plt.gcf()).savefig(path / f'{name}.png', dpi=200, bbox_inches='tight')


# --- Slide figures --------------------------------------------------------------
# Presentation figures are drawn at the size they appear on the slide, so a 10pt
# label in the figure is 10pt on screen. Google Slides' widescreen page is
# 10 x 5.625 in; SLIDE_SIZE fills its width below a one-line slide title.
SLIDE_SIZE = (10, 4.9)
SLIDE_FONTS = {'font.size': 10.5, 'axes.titlesize': 12, 'axes.labelsize': 11, 'xtick.labelsize': 10.5,
               'ytick.labelsize': 10.5, 'legend.fontsize': 10.5, 'figure.titlesize': 13}


def slide_figure(**kwargs):
    """A new figure at SLIDE_SIZE with constrained layout, using SLIDE_FONTS.
    The fonts stay set for the rest of the notebook (presentation notebooks
    draw nothing else)."""
    plt.rcParams.update(SLIDE_FONTS)
    return plt.figure(figsize=SLIDE_SIZE, layout='constrained', **kwargs)


def save_presentation_figure(name, fig=None):
    """Save a slide figure built in analysis/presentation/ as
    results/<version>/presentation/<name>.png at exactly its figure size (no
    cropping), so every slide image has the same shape and its text keeps
    its point size when placed full width on a slide. Slide figures are drawn
    from a data version's results, so they are kept per version too."""
    path = results_dir('presentation')
    (fig or plt.gcf()).savefig(path / f'{name}.png', dpi=300)
