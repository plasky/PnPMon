import io

import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt


_BG = "#0e0e0e"
_FG = "#4f86e0"
_TEXT_COLOR = "#ececec"


def _generate_chirp(n: int = 4000) -> tuple[np.ndarray, np.ndarray]:
    t = np.linspace(-1.2, 0.15, n)
    tau = np.where(t < 0, -t, 1e-6)
    f = 30.0 * (tau / 1.2) ** (-3 / 8)
    f = np.clip(f, 0, 500)
    dt = (t[-1] - t[0]) / n
    phase = 2 * np.pi * np.cumsum(f) * dt
    amp = (tau / 1.2) ** (-1 / 4)
    amp = amp / amp.max()
    h = amp * np.sin(phase)
    decay_mask = t > 0
    h[decay_mask] *= np.exp(-t[decay_mask] / 0.04)
    return t, h


class WaveformWidget(FigureCanvasQTAgg):
    def __init__(self, parent=None) -> None:
        fig, ax = plt.subplots(figsize=(10, 1.1), facecolor=_BG)
        t, h = _generate_chirp()
        ax.plot(t, h, color=_FG, linewidth=0.9, alpha=0.95)
        ax.fill_between(t, h, alpha=0.15, color=_FG)
        ax.set_xlim(t[0], t[-1])
        ax.set_ylim(-1.15, 1.15)
        ax.set_facecolor(_BG)
        ax.set_axis_off()
        fig.text(
            0.015, 0.82, "LIGO  P&P  MONITOR",
            color=_TEXT_COLOR, fontsize=9, va="top", ha="left",
            fontfamily="monospace", alpha=0.75,
        )
        fig.text(
            0.015, 0.22, "pnp.ligo.org",
            color=_FG, fontsize=7.5, va="bottom", ha="left",
            fontfamily="monospace", alpha=0.6,
        )
        fig.tight_layout(pad=0)
        super().__init__(fig)
        self.setFixedHeight(90)
        if parent:
            self.setParent(parent)


def make_tray_icon_pixmap(size: int = 22) -> QPixmap:
    """Generate a small chirp waveform pixmap for use as the tray icon."""
    fig, ax = plt.subplots(figsize=(1, 1), facecolor="none")
    t, h = _generate_chirp(800)
    ax.plot(t, h, color=_FG, linewidth=1.5)
    ax.set_xlim(t[0], t[-1])
    ax.set_ylim(-1.3, 1.3)
    ax.set_facecolor("none")
    ax.set_axis_off()
    fig.tight_layout(pad=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=size, transparent=True, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    img = QImage.fromData(buf.read())
    return QPixmap.fromImage(img).scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
