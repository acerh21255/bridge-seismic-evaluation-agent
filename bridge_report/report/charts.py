"""Engineering charts rendered with matplotlib (Agg): design spectra and ground-motion spectra comparison."""
import matplotlib

matplotlib.use('Agg')
from matplotlib import pyplot as plt  # noqa: E402

CM = 1 / 2.54
T0 = 0.1  # JTG/T 2231-01—2020 horizontal design spectrum plateau start (s)
WAVE_COLORS = ['#4F81BD', '#C0504D', '#9BBB59', '#8064A2', '#4BACC6', '#F79646', '#1F497D']
STYLE = {
    'font.family': ['Times New Roman', 'SimSun'],
    'font.size': 10.5,
    'axes.linewidth': 0.8,
    'axes.unicode_minus': False,
    'mathtext.fontset': 'stix',
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'savefig.dpi': 220,
}


def design_spectrum(t, smax, tg):
    """Horizontal design acceleration spectrum ordinate S(T) in the unit of smax."""
    if t < T0:
        return smax * (0.6 * t / T0 + 0.4)
    if t <= tg:
        return smax
    return smax * tg / t


def design_spectrum_png(spectrum, path, t_max=10.0, step=0.025):
    periods = [round(i * step, 6) for i in range(int(t_max / step) + 1)]
    values = [design_spectrum(t, spectrum['Smax'], spectrum['Tg']) for t in periods]
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(13.25 * CM, 7.3 * CM))
        ax.plot(periods, values, color='black', linewidth=1.5)
        ax.set_xlim(0, t_max)
        ax.set_ylim(0, round(spectrum['Smax'] * 1.2, 4))
        ax.set_xlabel('T (s)')
        ax.set_ylabel('S (g)')
        ax.grid(False)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
    return path


def wave_spectra_png(series, path, target=None, t_max=6.0):
    """series: [(name, periods, values)], target: (name, periods, values) drawn in red."""
    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=(16 * CM, 9 * CM))
        for n, (name, periods, values) in enumerate(series):
            if name == '平均值':
                ax.plot(periods, values, color='black', linewidth=2.6, label=name, zorder=3)
            else:
                ax.plot(periods, values, color=WAVE_COLORS[n % len(WAVE_COLORS)], linewidth=1.0, label=name)
        if target:
            ax.plot(target[1], target[2], color='#FF0000', linewidth=2.2, label=target[0], zorder=4)
        ax.set_xlim(0, t_max)
        ax.set_ylim(bottom=0)
        ax.set_xlabel('周期 (s)')
        ax.set_ylabel('$S_a$ (m/s$^2$)')
        ax.legend(loc='upper right', fontsize=9, frameon=False, ncol=1)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
    return path
