"""Single source of truth for colours, typography, the Plotly template and page CSS.

The categorical, ordinal, sequential and status values come from the validated reference
palette of the data-viz method (light mode). Categorical hues are assigned in fixed slot
order and follow the entity, never its rank. Text always uses the ink tokens below, never
a series colour.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# --- Surfaces & ink (WCAG AA: INK_SECONDARY on white is 7.9:1) ---------------------------
PAGE_BG = "#f6f8fb"
SIDEBAR_BG = "#eef2f7"
SURFACE = "#ffffff"
BORDER = "#dde3ea"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e6e8ec"
AXIS = "#c3c2b7"
ACCENT = "#1c5cab"  # primary UI colour; 6.6:1 on white

# --- Categorical slots (fixed order; never cycled past 8) --------------------------------
SERIES = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#6250d6",  # 7 violet
    "#e34948",  # 8 red
]
PRIMARY = SERIES[0]
SECONDARY = SERIES[1]
DE_EMPHASIS = "#b9c3cf"

# Fixed entity -> colour assignments shared by every chart.
SEX_COLORS = {"F": SERIES[0], "M": SERIES[1]}
SEX_LABELS = {"F": "Female", "M": "Male"}
ICU_COLORS = {"ICU care": SERIES[0], "No ICU care": SERIES[1]}

# Ordinal blue ramp (starts at step 250 so the lightest step clears 2:1 on the surface).
AGE_ORDER = ["18-44", "45-64", "65-79", "80+"]
AGE_COLORS = dict(zip(AGE_ORDER, ["#86b6ef", "#5598e7", "#256abf", "#104281"], strict=True))
LOS_BAND_ORDER = ["<1 day", "1-2 days", "3-6 days", "7-13 days", "14+ days"]
ADMISSION_GROUP_ORDER = ["Emergency", "Urgent", "Elective", "Observation"]

# Sequential (one hue, light -> dark) for heatmaps.
SEQUENTIAL = [
    [0.0, "#f3f7fd"],
    [0.15, "#cde2fb"],
    [0.35, "#86b6ef"],
    [0.55, "#3987e5"],
    [0.75, "#1c5cab"],
    [1.0, "#0d366b"],
]

# Status palette - reserved for pass/flag/fail states, always paired with a text label.
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
STATUS_TEXT = {"good": "#006300", "warning": "#7a5200", "serious": "#9a3412", "critical": "#b42323"}

FONT_FAMILY = 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'
TEMPLATE_NAME = "hospital_intel"

PLOTLY_CONFIG: dict = {"displayModeBar": False, "responsive": True}


def register_plotly_template() -> None:
    """Register and activate the shared Plotly template (idempotent)."""
    axis = dict(
        showgrid=True,
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor=AXIS,
        linewidth=1,
        ticks="",
        tickfont=dict(color=INK_SECONDARY, size=12),
        title=dict(font=dict(color=INK_SECONDARY, size=12), standoff=10),
        automargin=True,
    )
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_FAMILY, color=INK, size=13),
            paper_bgcolor=SURFACE,
            plot_bgcolor=SURFACE,
            colorway=SERIES,
            title=dict(
                x=0, xanchor="left", y=0.98, yanchor="top",
                font=dict(size=15, color=INK, family=FONT_FAMILY, weight=600),
                pad=dict(l=4, t=4),
            ),
            margin=dict(l=8, r=16, t=56, b=8),
            xaxis=axis,
            yaxis=axis,
            legend=dict(
                orientation="h", x=0, xanchor="left", y=1.0, yanchor="bottom",
                font=dict(color=INK_SECONDARY, size=12), title=dict(text=""),
                bgcolor="rgba(0,0,0,0)",
            ),
            hoverlabel=dict(
                bgcolor=SURFACE, bordercolor=BORDER,
                font=dict(family=FONT_FAMILY, color=INK, size=12),
            ),
            bargap=0.42,
            bargroupgap=0.08,
            barcornerradius=4,
            separators=".,",
        )
    )
    template.data.bar = [go.Bar(marker=dict(line=dict(width=0)))]
    template.data.heatmap = [go.Heatmap(colorscale=SEQUENTIAL, xgap=2, ygap=2)]
    pio.templates[TEMPLATE_NAME] = template
    pio.templates.default = TEMPLATE_NAME


def bar_height(n_categories: int, *, per_row: int = 34, base: int = 120) -> int:
    """Height for a horizontal bar chart so bars stay thin (<= ~20px) and labels fit."""
    return max(220, base + per_row * n_categories)


PAGE_CSS = f"""
<style>
  .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1320px; }}
  h1, h2, h3 {{ letter-spacing: -0.01em; }}
  [data-testid="stSidebar"] {{ border-right: 1px solid {BORDER}; }}
  [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{
      color: {INK_SECONDARY} !important; opacity: 1 !important; }}

  .hi-header {{ margin: 0 0 1.25rem 0; }}
  .hi-eyebrow {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
                letter-spacing: 0.08em; color: {ACCENT}; margin-bottom: 0.25rem; }}
  .hi-header h1.hi-title {{ font-size: 2rem !important; font-weight: 700 !important;
      color: {INK}; margin: 0 !important; padding: 0 !important; line-height: 1.2 !important; }}
  .hi-subtitle {{ font-size: 0.98rem; color: {INK_SECONDARY}; margin-top: 0.35rem; max-width: 70ch; }}

  .hi-kpi {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px;
            padding: 16px 18px 14px 18px; height: 100%; min-height: 118px;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04); }}
  .hi-kpi-label {{ font-size: 0.8rem; font-weight: 600; color: {INK_SECONDARY}; margin-bottom: 6px; }}
  .hi-kpi-value {{ font-size: 1.9rem; font-weight: 650; color: {INK}; line-height: 1.1; }}
  .hi-kpi-unit {{ font-size: 0.95rem; font-weight: 500; color: {INK_SECONDARY}; margin-left: 2px; }}
  .hi-kpi-sub {{ font-size: 0.78rem; color: {INK_SECONDARY}; margin-top: 8px; line-height: 1.35; }}

  .hi-banner {{ display: flex; gap: 12px; align-items: flex-start; border-radius: 10px;
               padding: 14px 16px; margin: 0 0 1.25rem 0; font-size: 0.92rem; line-height: 1.45;
               border: 1px solid; }}
  .hi-banner-icon {{ font-size: 1.1rem; line-height: 1.3; }}
  .hi-banner.caveat {{ background: #fff8e6; border-color: #f2d58a; color: #3d2f00; }}
  .hi-banner.note {{ background: #eef4fc; border-color: #c4d8f3; color: #102a4c; }}
  .hi-banner b {{ font-weight: 650; }}

  .hi-pill {{ display: inline-block; font-size: 0.72rem; font-weight: 600; padding: 2px 8px;
             border-radius: 999px; border: 1px solid {BORDER}; background: {SURFACE};
             color: {INK_SECONDARY}; margin-right: 6px; }}
  .hi-status {{ display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }}
  .hi-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}

  .hi-section {{ font-size: 1.05rem; font-weight: 650; color: {INK}; margin: 1.4rem 0 0.4rem 0; }}
  .hi-field-label {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
                    letter-spacing: 0.06em; color: {INK_SECONDARY}; margin-top: 0.6rem; }}
  .hi-field-value {{ font-size: 0.93rem; color: {INK}; line-height: 1.45; }}
</style>
"""
