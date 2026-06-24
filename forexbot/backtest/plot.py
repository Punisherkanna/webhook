"""Equity-curve plotting for backtest results.

Two backends:
  * ``.svg`` -> a pure-Python, zero-dependency renderer (always available).
  * ``.png`` -> matplotlib, imported lazily so it's an *optional* dependency.

:func:`save_equity_plot` dispatches on the file extension, so callers just pick a
path. The SVG path means the project can produce a chart with nothing beyond the
standard library installed.
"""
from __future__ import annotations

from typing import List, Tuple

from .engine import BacktestResult


def save_equity_plot(result: BacktestResult, path: str) -> str:
    """Render ``result``'s equity curve to ``path`` (.svg or .png)."""
    lower = path.lower()
    if lower.endswith(".png"):
        return _save_png(result, path)
    if lower.endswith(".svg"):
        return _save_svg(result, path)
    raise ValueError(f"unsupported plot format: {path} (use .svg or .png)")


# --- high-water-mark helper -------------------------------------------------
def _high_water(curve: List[float]) -> List[float]:
    peak = curve[0] if curve else 0.0
    out = []
    for v in curve:
        peak = max(peak, v)
        out.append(peak)
    return out


# --- matplotlib (PNG) -------------------------------------------------------
def _save_png(result: BacktestResult, path: str) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless: no display needed
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on host
        raise RuntimeError(
            "matplotlib is required for PNG plots (`pip install matplotlib`). "
            "Use a .svg path for the zero-dependency renderer instead."
        ) from exc

    curve = result.equity_curve
    peaks = _high_water(curve)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(curve, color="#1f77b4", linewidth=1.4, label="Equity")
    ax.plot(peaks, color="#2ca02c", linewidth=0.8, linestyle="--",
            label="High-water mark")
    ax.fill_between(range(len(curve)), curve, peaks, color="#d62728",
                    alpha=0.12, label="Drawdown")
    ax.set_title(
        f"{result.config.symbol} equity  |  "
        f"net {result.net_profit:,.0f} ({result.return_pct:+.1f}%)  |  "
        f"PF {result.profit_factor:.2f}  |  maxDD {result.max_drawdown_pct:.1f}%"
    )
    ax.set_xlabel("Bar")
    ax.set_ylabel(f"Equity ({result.config.risk.contract_size and 'acct ccy'})")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


# --- pure-Python SVG --------------------------------------------------------
def _save_svg(result: BacktestResult, path: str,
              width: int = 900, height: int = 460) -> str:
    svg = render_svg(result, width, height)
    with open(path, "w") as fh:
        fh.write(svg)
    return path


def render_svg(result: BacktestResult, width: int = 900,
               height: int = 460) -> str:
    """Build an SVG string for the equity curve. Split out for testing."""
    curve = result.equity_curve or [result.starting_equity]
    peaks = _high_water(curve)

    pad_l, pad_r, pad_t, pad_b = 70, 20, 50, 40
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    lo = min(min(curve), min(peaks))
    hi = max(max(curve), max(peaks))
    if hi == lo:  # flat curve: give it a sliver of range so it renders
        hi += 1.0
        lo -= 1.0
    n = len(curve)

    def x(i: int) -> float:
        if n <= 1:
            return pad_l
        return pad_l + (i / (n - 1)) * plot_w

    def y(v: float) -> float:
        return pad_t + (1.0 - (v - lo) / (hi - lo)) * plot_h

    equity_pts = _points([(x(i), y(v)) for i, v in enumerate(curve)])
    peak_pts = _points([(x(i), y(v)) for i, v in enumerate(peaks)])

    # Drawdown band: equity polyline forward, peak polyline back -> closed area.
    band = (
        " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(curve))
        + " "
        + " ".join(f"{x(i):.1f},{y(v):.1f}"
                   for i, v in reversed(list(enumerate(peaks))))
    )

    # Horizontal gridlines + y-axis labels at 5 levels.
    grid, labels = [], []
    for k in range(5):
        val = lo + (hi - lo) * k / 4
        gy = y(val)
        grid.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" '
            f'y2="{gy:.1f}" stroke="#e6e6e6" stroke-width="1"/>'
        )
        labels.append(
            f'<text x="{pad_l - 8}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#555">{val:,.0f}</text>'
        )

    title = (
        f"{result.config.symbol} equity — net {result.net_profit:,.0f} "
        f"({result.return_pct:+.1f}%) | PF {result.profit_factor:.2f} | "
        f"win {result.win_rate:.0f}% | maxDD {result.max_drawdown_pct:.1f}%"
    )

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" font-family="sans-serif">
  <rect width="{width}" height="{height}" fill="white"/>
  <text x="{pad_l}" y="28" font-size="15" font-weight="bold" fill="#222">{_esc(title)}</text>
  {''.join(grid)}
  <polygon points="{band}" fill="#d62728" fill-opacity="0.10"/>
  <polyline points="{peak_pts}" fill="none" stroke="#2ca02c"
            stroke-width="1" stroke-dasharray="4 3"/>
  <polyline points="{equity_pts}" fill="none" stroke="#1f77b4" stroke-width="1.6"/>
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}"
        stroke="#999" stroke-width="1"/>
  <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}"
        y2="{pad_t + plot_h}" stroke="#999" stroke-width="1"/>
  {''.join(labels)}
  <text x="{pad_l}" y="{height - 12}" font-size="11" fill="#555">bar 0</text>
  <text x="{pad_l + plot_w}" y="{height - 12}" text-anchor="end"
        font-size="11" fill="#555">bar {n - 1}</text>
</svg>
'''


def _points(coords: List[Tuple[float, float]]) -> str:
    return " ".join(f"{px:.1f},{py:.1f}" for px, py in coords)


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
